# Feed Composition Pattern

> A modern, Pythonic alternative to the Builder pattern for FeedSpine pipelines.

**Status**: Proposal  
**Author**: FeedSpine Team  
**Date**: January 2026

---

## Problems with Builder Pattern

```python
# Traditional Builder - What we want to avoid
pipeline = (
    PipelineBuilder()
    .with_adapter(MyAdapter())
    .with_storage(MyStorage())
    .with_enricher(MyEnricher())
    .with_cache(MyCache())
    .with_notifier(MyNotifier())
    .build()
)
```

**Issues**:
1. **Verbose** - Every component needs `.with_*()` 
2. **Runtime errors** - Missing required component? Discover at `.build()` time
3. **Poor IDE support** - Autocomplete shows all 20 `.with_*` methods, can't tell what's missing
4. **Not composable** - Can't easily reuse partial configurations
5. **Order-dependent** - Some builders care about method call order
6. **Feels like Java** - Not idiomatic Python

---

## Design Principles

1. **Explicit is better than implicit** - No hidden state or magic
2. **Flat is better than nested** - No deep method chains
3. **Simple things should be simple** - One-liner for common cases
4. **Complex things should be possible** - Full customization available
5. **Type-safe** - IDE autocomplete and mypy work perfectly
6. **Errors at definition time** - Not runtime

---

## The Feed Composition Pattern

### Core Idea: Dataclass Configuration + Function Composition

Instead of a builder, we use:
1. **Dataclass for configuration** - Type-safe, IDE-friendly, immutable
2. **Functions for transformation** - Composable, testable, reusable
3. **Context manager for lifecycle** - Pythonic resource management

### Basic Usage

```python
from feedspine import Feed, collect

# Simplest case - just adapter and storage
async with Feed(adapter=MyAdapter(), storage=MyStorage()) as feed:
    result = await feed.collect()

# Or even simpler with the function interface
result = await collect(MyAdapter(), MyStorage())
```

### With Configuration

```python
from feedspine import Feed, FeedConfig

# Explicit configuration - IDE shows all options
config = FeedConfig(
    adapter=SECFilingsAdapter(cik="0000320193"),
    storage=DuckDBStorage("filings.db"),
    enrichers=[CompanyEnricher(), FinancialEnricher()],
    cache=RedisCache(),
    rate_limit=10,  # requests per second
    checkpoint_interval=100,  # save every 100 records
)

async with Feed(config) as feed:
    result = await feed.collect()
```

### Composition via Operators

```python
from feedspine import Feed, ops

# Functional composition for transformations
feed = Feed(
    adapter=RSSAdapter("https://example.com/feed"),
    storage=storage,
    pipeline=[
        ops.filter(lambda r: r.content.get("category") == "tech"),
        ops.enrich(SentimentEnricher()),
        ops.enrich(CategoryEnricher()),
        ops.dedupe(key="url"),
        ops.notify(SlackNotifier(), on="new"),
    ]
)
```

### Reusable Presets

```python
from feedspine import Feed, Preset

# Define reusable configurations
class SECPreset(Preset):
    """Standard SEC filing collection preset."""
    
    storage = DuckDBStorage
    enrichers = [SECSubmissionEnricher, SECFinancialEnricher]
    rate_limit = 10
    checkpoint = True

# Use the preset
async with Feed.from_preset(SECPreset, adapter=MyAdapter()) as feed:
    result = await feed.collect()

# Or customize it
async with Feed.from_preset(
    SECPreset, 
    adapter=MyAdapter(),
    storage_path="custom.db",
    rate_limit=5,  # Override
) as feed:
    result = await feed.collect()
```

---

## API Design

### FeedConfig Dataclass

```python
@dataclass(frozen=True)
class FeedConfig:
    """Immutable feed configuration.
    
    All parameters are explicit and type-safe.
    IDE autocomplete shows exactly what's available.
    """
    
    # Required
    adapter: FeedAdapter
    storage: StorageBackend
    
    # Optional components
    enrichers: Sequence[Enricher] = ()
    cache: CacheBackend | None = None
    search: SearchBackend | None = None
    notifier: Notifier | None = None
    
    # Behavior configuration
    rate_limit: float | None = None  # requests/second
    concurrency: int = 1
    checkpoint_interval: int | None = None
    batch_size: int = 100
    
    # Pipeline operations
    pipeline: Sequence[PipelineOp] = ()
    
    def with_enricher(self, enricher: Enricher) -> FeedConfig:
        """Return new config with additional enricher."""
        return dataclasses.replace(
            self, 
            enrichers=(*self.enrichers, enricher)
        )
    
    def with_rate_limit(self, rps: float) -> FeedConfig:
        """Return new config with rate limit."""
        return dataclasses.replace(self, rate_limit=rps)
```

### Feed Class

```python
class Feed:
    """Main entry point for feed collection.
    
    Example:
        >>> async with Feed(adapter=MyAdapter(), storage=MyStorage()) as feed:
        ...     result = await feed.collect()
    """
    
    def __init__(
        self,
        config: FeedConfig | None = None,
        *,
        # Allow direct kwargs for simple cases
        adapter: FeedAdapter | None = None,
        storage: StorageBackend | None = None,
        **kwargs: Any,
    ) -> None:
        if config is not None:
            self._config = config
        else:
            # Build config from kwargs
            if adapter is None or storage is None:
                raise TypeError("adapter and storage are required")
            self._config = FeedConfig(adapter=adapter, storage=storage, **kwargs)
    
    @classmethod
    def from_preset(
        cls,
        preset: type[Preset],
        *,
        adapter: FeedAdapter,
        **overrides: Any,
    ) -> Feed:
        """Create feed from a preset configuration."""
        config = preset.build(adapter=adapter, **overrides)
        return cls(config)
    
    async def __aenter__(self) -> Feed:
        """Initialize all components."""
        await self._config.storage.initialize()
        await self._config.adapter.initialize()
        for enricher in self._config.enrichers:
            await enricher.initialize()
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        """Clean up all components."""
        for enricher in reversed(self._config.enrichers):
            await enricher.close()
        await self._config.adapter.close()
        await self._config.storage.close()
    
    async def collect(self, **options: Any) -> CollectionResult:
        """Run feed collection."""
        ...
    
    async def query(self, query: Query) -> AsyncIterator[Record]:
        """Query collected records."""
        ...
```

### Pipeline Operations

```python
# feedspine/ops.py - Functional pipeline operators

def filter(predicate: Callable[[Record], bool]) -> FilterOp:
    """Filter records by predicate."""
    return FilterOp(predicate)

def enrich(enricher: Enricher) -> EnrichOp:
    """Enrich records with the given enricher."""
    return EnrichOp(enricher)

def dedupe(*, key: str | Callable[[Record], str]) -> DedupeOp:
    """Deduplicate records by key."""
    return DedupeOp(key)

def transform(func: Callable[[Record], Record]) -> TransformOp:
    """Transform records with a function."""
    return TransformOp(func)

def notify(notifier: Notifier, *, on: Literal["new", "error", "all"] = "new") -> NotifyOp:
    """Send notifications."""
    return NotifyOp(notifier, on)

def rate_limit(rps: float) -> RateLimitOp:
    """Limit request rate."""
    return RateLimitOp(rps)

def checkpoint(*, interval: int = 100, store: CheckpointStore | None = None) -> CheckpointOp:
    """Enable checkpointing."""
    return CheckpointOp(interval, store)

def batch(size: int) -> BatchOp:
    """Process records in batches."""
    return BatchOp(size)
```

---

## Comparison

### Before (Builder Pattern)

```python
pipeline = (
    PipelineBuilder()
    .with_adapter(SECFilingsAdapter(cik="0000320193"))
    .with_storage(DuckDBStorage("filings.db"))
    .with_enricher(CompanyEnricher())
    .with_enricher(FinancialEnricher())
    .with_cache(RedisCache())
    .with_rate_limit(10)
    .with_checkpoint(interval=100)
    .with_notifier(SlackNotifier())
    .build()
)

# Initialize manually
await pipeline.initialize()
try:
    result = await pipeline.collect()
finally:
    await pipeline.close()
```

### After (Feed Composition)

```python
async with Feed(
    adapter=SECFilingsAdapter(cik="0000320193"),
    storage=DuckDBStorage("filings.db"),
    enrichers=[CompanyEnricher(), FinancialEnricher()],
    cache=RedisCache(),
    pipeline=[
        ops.rate_limit(10),
        ops.checkpoint(interval=100),
        ops.notify(SlackNotifier()),
    ],
) as feed:
    result = await feed.collect()
```

### Simplest Case

```python
# Builder
result = await PipelineBuilder().with_adapter(a).with_storage(s).build().run()

# Feed Composition
result = await collect(adapter, storage)
```

---

## Advanced: Domain-Specific Feeds

For specific domains (like SEC filings), we can create typed feeds:

```python
from feedspine.domains.sec import SECFeed, SECFilingContent

# Domain-specific feed with typed content
async with SECFeed(
    cik="0000320193",
    forms=["10-K", "10-Q"],
    storage_path="apple_filings.db",
) as feed:
    # Typed query results
    async for filing in feed.filings(form_type="10-K"):
        # IDE knows filing.content is SECFilingContent
        print(filing.content.company_name)  # Autocomplete works!
        print(filing.content.filed_date)    # Type-safe
```

---

## Implementation Phases

### Phase 1: Core Feed Class
- `FeedConfig` dataclass
- `Feed` context manager
- Basic `collect()` and `query()`

### Phase 2: Pipeline Operations
- `ops` module with functional operators
- `FilterOp`, `EnrichOp`, `TransformOp`, etc.

### Phase 3: Presets
- `Preset` base class
- Standard presets for common use cases

### Phase 4: Domain Feeds
- `SECFeed`, `RSSFeed`, etc.
- Typed content schemas

---

## Migration Path

The new pattern is **additive** - existing code continues to work:

```python
# Old way still works
spine = FeedSpine(storage=storage)
spine.register_feed(adapter)
result = await spine.collect()

# New way available alongside
async with Feed(adapter=adapter, storage=storage) as feed:
    result = await feed.collect()
```

We can deprecate the old API gradually.
