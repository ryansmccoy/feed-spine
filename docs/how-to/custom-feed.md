# Implement a Custom Feed Adapter

This guide shows you how to create a custom feed adapter for any data source.

## When You Need a Custom Adapter

Use a custom adapter when:

- Your data source isn't RSS, JSON Feed, or Atom
- You need custom authentication
- You want custom parsing logic
- Your source is an API, database, or file system

## The FeedAdapter Protocol

All feed adapters implement this protocol:

```python
from typing import Protocol, AsyncIterator
from feedspine.models import FeedRecord

class FeedAdapter(Protocol):
    """Protocol that all feed adapters must implement."""
    
    @property
    def name(self) -> str:
        """Unique identifier for this feed."""
        ...
    
    async def fetch(self) -> AsyncIterator[FeedRecord]:
        """Fetch and yield records from the feed."""
        ...
```

## Example: JSON API Adapter

Let's build an adapter for a JSON API (like a REST endpoint):

```python
import asyncio
from datetime import datetime, UTC
from typing import AsyncIterator
import httpx

from feedspine.models import FeedRecord
from feedspine.models.base import Layer


class JSONAPIAdapter:
    """Adapter for JSON REST APIs."""
    
    def __init__(
        self,
        name: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        items_key: str = "items",
        id_field: str = "id",
    ):
        self._name = name
        self.url = url
        self.headers = headers or {}
        self.items_key = items_key  # Key containing items list
        self.id_field = id_field    # Field to use as natural key
    
    @property
    def name(self) -> str:
        return self._name
    
    async def fetch(self) -> AsyncIterator[FeedRecord]:
        """Fetch data from JSON API and yield records."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.url,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        
        # Get items from response
        items = data.get(self.items_key, data)
        if not isinstance(items, list):
            items = [items]
        
        for item in items:
            # Create natural key from ID field
            natural_key = f"{self.name}:{item.get(self.id_field, '')}"
            
            # Parse published time if available
            published_at = None
            for time_field in ["published_at", "created_at", "date", "timestamp"]:
                if time_field in item:
                    try:
                        published_at = datetime.fromisoformat(
                            item[time_field].replace("Z", "+00:00")
                        )
                        break
                    except (ValueError, TypeError):
                        pass
            
            yield FeedRecord(
                feed_name=self.name,
                natural_key=natural_key,
                layer=Layer.BRONZE,
                captured_at=datetime.now(UTC),
                published_at=published_at,
                content=item,
                metadata={
                    "source_url": self.url,
                    "adapter": "JSONAPIAdapter",
                },
            )
```

### Using the Adapter

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage

async def main():
    storage = MemoryStorage()
    
    # Create custom adapter for GitHub API
    github_adapter = JSONAPIAdapter(
        name="github-events",
        url="https://api.github.com/repos/python/cpython/events",
        headers={"Accept": "application/vnd.github.v3+json"},
        items_key=None,  # Response is a list directly
        id_field="id",
    )
    
    async with FeedSpine(storage=storage) as spine:
        spine.register_feed(github_adapter)
        result = await spine.collect()
        print(f"Collected {result.total_new} events")

asyncio.run(main())
```

## Example: File System Adapter

Monitor a directory for new files:

```python
import asyncio
from datetime import datetime, UTC
from pathlib import Path
from typing import AsyncIterator
import hashlib

from feedspine.models import FeedRecord
from feedspine.models.base import Layer


class DirectoryAdapter:
    """Adapter that monitors a directory for files."""
    
    def __init__(
        self,
        name: str,
        directory: str | Path,
        *,
        pattern: str = "*",
        recursive: bool = False,
    ):
        self._name = name
        self.directory = Path(directory)
        self.pattern = pattern
        self.recursive = recursive
    
    @property
    def name(self) -> str:
        return self._name
    
    async def fetch(self) -> AsyncIterator[FeedRecord]:
        """Yield records for files in directory."""
        glob_method = self.directory.rglob if self.recursive else self.directory.glob
        
        for path in glob_method(self.pattern):
            if not path.is_file():
                continue
            
            # Create natural key from file path and modification time
            stat = path.stat()
            content_hash = hashlib.md5(path.read_bytes()).hexdigest()
            natural_key = f"{self.name}:{path.name}:{content_hash}"
            
            yield FeedRecord(
                feed_name=self.name,
                natural_key=natural_key,
                layer=Layer.BRONZE,
                captured_at=datetime.now(UTC),
                published_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                content={
                    "filename": path.name,
                    "path": str(path.absolute()),
                    "size": stat.st_size,
                    "content_hash": content_hash,
                },
                metadata={
                    "adapter": "DirectoryAdapter",
                    "directory": str(self.directory),
                },
            )
```

### Using the File Adapter

```python
async def main():
    storage = MemoryStorage()
    
    file_adapter = DirectoryAdapter(
        name="downloads",
        directory="/home/user/Downloads",
        pattern="*.pdf",
        recursive=True,
    )
    
    async with FeedSpine(storage=storage) as spine:
        spine.register_feed(file_adapter)
        result = await spine.collect()
        print(f"Found {result.total_new} new PDF files")
```

## Example: Database Adapter

Monitor a database table for changes:

```python
import asyncio
from datetime import datetime, UTC
from typing import AsyncIterator

from feedspine.models import FeedRecord
from feedspine.models.base import Layer


class PostgresTableAdapter:
    """Adapter that monitors a PostgreSQL table."""
    
    def __init__(
        self,
        name: str,
        connection_string: str,
        table: str,
        *,
        id_column: str = "id",
        timestamp_column: str = "updated_at",
    ):
        self._name = name
        self.connection_string = connection_string
        self.table = table
        self.id_column = id_column
        self.timestamp_column = timestamp_column
    
    @property
    def name(self) -> str:
        return self._name
    
    async def fetch(self) -> AsyncIterator[FeedRecord]:
        """Fetch rows and yield as records."""
        import asyncpg
        
        conn = await asyncpg.connect(self.connection_string)
        try:
            query = f"SELECT * FROM {self.table} ORDER BY {self.timestamp_column} DESC LIMIT 1000"
            rows = await conn.fetch(query)
            
            for row in rows:
                row_dict = dict(row)
                natural_key = f"{self.name}:{row_dict[self.id_column]}"
                
                published_at = row_dict.get(self.timestamp_column)
                if published_at and not isinstance(published_at, datetime):
                    published_at = None
                
                yield FeedRecord(
                    feed_name=self.name,
                    natural_key=natural_key,
                    layer=Layer.BRONZE,
                    captured_at=datetime.now(UTC),
                    published_at=published_at,
                    content=row_dict,
                    metadata={
                        "adapter": "PostgresTableAdapter",
                        "table": self.table,
                    },
                )
        finally:
            await conn.close()
```

## Best Practices

### 1. Natural Keys Must Be Unique

The natural key determines deduplication. Make it unique:

```python
# Good: includes feed name and unique identifier
natural_key = f"{self.name}:{item['id']}"

# Better: includes version/hash for change detection
natural_key = f"{self.name}:{item['id']}:{item['version']}"

# Bad: might collide with other feeds
natural_key = item['id']
```

### 2. Handle Errors Gracefully

```python
async def fetch(self) -> AsyncIterator[FeedRecord]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.url, timeout=30.0)
            response.raise_for_status()
    except httpx.HTTPError as e:
        # Log and return empty - don't crash the collector
        logger.error(f"Failed to fetch {self.name}: {e}")
        return
    
    # Process response...
```

### 3. Use Async Properly

```python
# Good: truly async I/O
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# Bad: blocking I/O in async context
import requests
response = requests.get(url)  # Blocks the event loop!
```

### 4. Include Metadata

```python
yield FeedRecord(
    # ...
    metadata={
        "adapter": self.__class__.__name__,
        "source_url": self.url,
        "fetch_time_ms": fetch_duration_ms,
        "api_version": "v2",
    },
)
```

### 5. Respect Rate Limits

```python
class RateLimitedAdapter:
    def __init__(self, name: str, url: str, requests_per_second: float = 1.0):
        self._name = name
        self.url = url
        self.delay = 1.0 / requests_per_second
        self._last_request = 0.0
    
    async def _rate_limit(self):
        import time
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            await asyncio.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()
    
    async def fetch(self) -> AsyncIterator[FeedRecord]:
        await self._rate_limit()
        # ... fetch logic
```

## Testing Your Adapter

```python
import pytest
from your_adapter import JSONAPIAdapter

@pytest.mark.asyncio
async def test_adapter_fetches_records():
    adapter = JSONAPIAdapter(
        name="test",
        url="https://httpbin.org/json",
        items_key="slideshow.slides",
        id_field="title",
    )
    
    records = [r async for r in adapter.fetch()]
    
    assert len(records) > 0
    assert all(r.feed_name == "test" for r in records)
    assert all(r.natural_key.startswith("test:") for r in records)

@pytest.mark.asyncio
async def test_adapter_handles_errors():
    adapter = JSONAPIAdapter(
        name="test",
        url="https://httpbin.org/status/500",
    )
    
    # Should not raise, just return empty
    records = [r async for r in adapter.fetch()]
    assert records == []
```

## Next Steps

- [Custom Storage Backend](custom-storage.md) - Store records your way
- [Architecture Concepts](../concepts/architecture.md) - Understand the design
- [Protocol Reference](../reference/protocols.md) - All extension points
