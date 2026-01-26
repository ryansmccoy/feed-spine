# Protocol Design

FeedSpine uses Python's **Protocol** (structural subtyping) rather than abstract base classes. This enables flexibility without inheritance hierarchies.

## Why Protocols?

### Structural Typing

With protocols, you don't inherit from a base class. You just implement the required methods:

```python
# No inheritance needed!
class MyStorage:
    async def store(self, record: FeedRecord) -> None:
        # Your implementation
        pass
    
    async def exists(self, natural_key: str) -> bool:
        # Your implementation
        pass
```

If your class has the right methods with the right signatures, it "implements" the protocol automatically.

### Benefits

1. **No coupling** - Your code doesn't depend on FeedSpine's base classes
2. **Easy testing** - Create simple mocks without complex inheritance
3. **Existing code** - Adapt existing classes without modification
4. **Multiple protocols** - A class can satisfy multiple protocols naturally

### Comparison with ABC

```python
# Abstract Base Class approach (NOT used by FeedSpine)
from abc import ABC, abstractmethod

class StorageBackendABC(ABC):
    @abstractmethod
    async def store(self, record): pass

# You MUST inherit
class MyStorage(StorageBackendABC):  # Required inheritance
    async def store(self, record):
        ...

# Protocol approach (used by FeedSpine)
from typing import Protocol

class StorageBackend(Protocol):
    async def store(self, record: FeedRecord) -> None: ...

# Just implement the methods - no inheritance
class MyStorage:  # No inheritance!
    async def store(self, record: FeedRecord) -> None:
        ...
```

## FeedSpine's 8 Protocols

FeedSpine defines 8 extension points through protocols:

### 1. StorageBackend

The core protocol for persisting records:

```python
class StorageBackend(Protocol):
    """Store and retrieve feed records."""
    
    async def store(self, record: FeedRecord) -> None:
        """Store a record."""
        ...
    
    async def exists(self, natural_key: str) -> bool:
        """Check if a natural key exists (for deduplication)."""
        ...
    
    async def get(self, natural_key: str) -> FeedRecord | None:
        """Retrieve a record by natural key."""
        ...
    
    async def query(
        self,
        *,
        feed_name: str | None = None,
        layer: Layer | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[FeedRecord]:
        """Query records with optional filters."""
        ...
    
    async def count(
        self,
        *,
        feed_name: str | None = None,
        layer: Layer | None = None,
    ) -> int:
        """Count records matching filters."""
        ...
```

**Built-in implementations:**

- `MemoryStorage` - In-memory, good for testing
- `DuckDBStorage` - Persistent, good for production

### 2. FeedAdapter

Defines how to fetch data from a source:

```python
class FeedAdapter(Protocol):
    """Fetch records from a data source."""
    
    @property
    def name(self) -> str:
        """Unique identifier for this feed."""
        ...
    
    async def fetch(self) -> AsyncIterator[FeedRecord]:
        """Fetch and yield records."""
        ...
```

**Built-in implementations:**

- `RSSFeedAdapter` - RSS/Atom feeds
- `JSONFeedAdapter` - JSON Feed format

### 3. SearchBackend

Full-text and semantic search:

```python
class SearchBackend(Protocol):
    """Search across stored records."""
    
    async def index(self, record: FeedRecord) -> None:
        """Index a record for search."""
        ...
    
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search indexed records."""
        ...
```

### 4. CacheBackend

Caching for expensive operations:

```python
class CacheBackend(Protocol):
    """Cache results for performance."""
    
    async def get(self, key: str) -> Any | None:
        """Get cached value."""
        ...
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set cached value with optional TTL."""
        ...
    
    async def delete(self, key: str) -> None:
        """Delete cached value."""
        ...
```

### 5. BlobStorage

Store large binary objects (files, images):

```python
class BlobStorage(Protocol):
    """Store binary large objects."""
    
    async def put(self, key: str, data: bytes) -> str:
        """Store blob, return storage URL."""
        ...
    
    async def get(self, key: str) -> bytes | None:
        """Retrieve blob by key."""
        ...
    
    async def delete(self, key: str) -> None:
        """Delete blob."""
        ...
```

### 6. MessageQueue

Async message passing:

```python
class MessageQueue(Protocol):
    """Publish and subscribe to messages."""
    
    async def publish(self, topic: str, message: Any) -> None:
        """Publish message to topic."""
        ...
    
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Any], Awaitable[None]],
    ) -> None:
        """Subscribe to topic with handler."""
        ...
```

### 7. Notifier

Send notifications:

```python
class Notifier(Protocol):
    """Send notifications."""
    
    async def notify(
        self,
        message: str,
        *,
        title: str | None = None,
        level: str = "info",
    ) -> None:
        """Send a notification."""
        ...
```

### 8. Executor

Control execution model:

```python
class Executor(Protocol):
    """Execute async tasks."""
    
    async def submit(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Submit and await a task."""
        ...
    
    async def map(
        self,
        func: Callable[[T], Awaitable[R]],
        items: Iterable[T],
    ) -> list[R]:
        """Map function over items concurrently."""
        ...
```

## Implementing a Protocol

### Step 1: Check the Protocol

Read the protocol definition to understand required methods:

```python
from feedspine.protocols import StorageBackend
import inspect

# See the protocol's methods
for name, method in inspect.getmembers(StorageBackend):
    if not name.startswith('_'):
        print(f"{name}: {inspect.signature(method)}")
```

### Step 2: Implement Required Methods

```python
class RedisStorage:
    """Redis-backed storage implementation."""
    
    def __init__(self, url: str = "redis://localhost"):
        self.url = url
        self._client = None
    
    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as redis
            self._client = await redis.from_url(self.url)
        return self._client
    
    async def store(self, record: FeedRecord) -> None:
        client = await self._get_client()
        await client.set(
            f"record:{record.natural_key}",
            record.model_dump_json(),
        )
    
    async def exists(self, natural_key: str) -> bool:
        client = await self._get_client()
        return await client.exists(f"record:{natural_key}")
    
    # ... implement other methods
```

### Step 3: Type Check (Optional)

Use `typing.runtime_checkable` to verify:

```python
from typing import runtime_checkable

# FeedSpine protocols are already runtime_checkable
from feedspine.protocols import StorageBackend

storage = RedisStorage()
assert isinstance(storage, StorageBackend)  # Works!
```

### Step 4: Use It

```python
from feedspine import FeedSpine

storage = RedisStorage("redis://localhost:6379")
async with FeedSpine(storage=storage) as spine:
    # Works with any StorageBackend implementation
    ...
```

## Protocol Composition

A class can implement multiple protocols:

```python
class AllInOneBackend:
    """Implements multiple protocols."""
    
    # StorageBackend methods
    async def store(self, record: FeedRecord) -> None: ...
    async def exists(self, natural_key: str) -> bool: ...
    async def get(self, natural_key: str) -> FeedRecord | None: ...
    async def query(self, **kwargs) -> AsyncIterator[FeedRecord]: ...
    async def count(self, **kwargs) -> int: ...
    
    # SearchBackend methods  
    async def index(self, record: FeedRecord) -> None: ...
    async def search(self, query: str, **kwargs) -> list[SearchResult]: ...
    
    # CacheBackend methods
    async def get_cache(self, key: str) -> Any | None: ...
    async def set_cache(self, key: str, value: Any, ttl: int = None) -> None: ...
    async def delete_cache(self, key: str) -> None: ...


# Use as both storage and search
backend = AllInOneBackend()
spine = FeedSpine(storage=backend, search=backend)
```

## Testing with Protocols

Protocols make testing easy:

```python
class MockStorage:
    """Simple mock for testing."""
    
    def __init__(self):
        self.records: dict[str, FeedRecord] = {}
    
    async def store(self, record: FeedRecord) -> None:
        self.records[record.natural_key] = record
    
    async def exists(self, natural_key: str) -> bool:
        return natural_key in self.records
    
    async def get(self, natural_key: str) -> FeedRecord | None:
        return self.records.get(natural_key)
    
    async def query(self, **kwargs) -> AsyncIterator[FeedRecord]:
        for record in self.records.values():
            yield record
    
    async def count(self, **kwargs) -> int:
        return len(self.records)


@pytest.mark.asyncio
async def test_collector():
    storage = MockStorage()  # No complex setup needed
    
    async with FeedSpine(storage=storage) as spine:
        spine.register_feed(SomeFeed())
        await spine.collect()
    
    assert len(storage.records) > 0
```

## Best Practices

### 1. Match Signatures Exactly

```python
# Protocol defines:
async def store(self, record: FeedRecord) -> None: ...

# Good: matches exactly
async def store(self, record: FeedRecord) -> None:
    ...

# Bad: different parameter name
async def store(self, data: FeedRecord) -> None:
    ...

# Bad: missing return type hint
async def store(self, record: FeedRecord):
    ...
```

### 2. Handle Optional Parameters

```python
# Protocol defines:
async def query(
    self,
    *,
    feed_name: str | None = None,
    layer: Layer | None = None,
    limit: int | None = None,
) -> AsyncIterator[FeedRecord]: ...

# Your implementation should handle all optional parameters
async def query(
    self,
    *,
    feed_name: str | None = None,
    layer: Layer | None = None,
    limit: int | None = None,
) -> AsyncIterator[FeedRecord]:
    query = self._build_query()
    
    if feed_name:
        query = query.where(feed_name=feed_name)
    if layer:
        query = query.where(layer=layer)
    if limit:
        query = query.limit(limit)
    
    async for row in query:
        yield self._row_to_record(row)
```

### 3. Document Your Implementation

```python
class PostgresStorage:
    """PostgreSQL storage backend.
    
    Implements:
        - StorageBackend: Core record storage
        - SearchBackend: Full-text search via pg_trgm
    
    Requirements:
        - asyncpg package
        - PostgreSQL 12+
        - pg_trgm extension for search
    
    Example:
        storage = PostgresStorage("postgresql://localhost/feeds")
        async with FeedSpine(storage=storage) as spine:
            ...
    """
```

## Further Reading

- [Architecture Overview](architecture.md) - How protocols fit together
- [Custom Storage How-To](../how-to/custom-storage.md) - Build a storage backend
- [Custom Feed How-To](../how-to/custom-feed.md) - Build a feed adapter
- [Protocol Reference](../reference/protocols.md) - Complete API documentation
