# FeedSpine Architecture Analysis

## Overview

FeedSpine is a **storage-agnostic feed capture framework** built around a Medallion Architecture (Bronze → Silver → Gold layers). It provides a complete pipeline for fetching, deduplicating, storing, and querying data from various feed sources.

---

## How Deduplication Works

### The Natural Key Concept

The `natural_key` is the **primary deduplication identifier**. Every record has one, and it uniquely identifies an item within a feed source.

**Examples of natural keys:**
- SEC filing: `"sec:10-k:0001234567-24-000001"` (accession number)
- RSS item: `"rss:article:https://example.com/post/123"` (GUID or link)
- MIC code: `"xnys"` (the MIC itself)
- SEC ticker: `"0000320193:aapl"` (CIK:ticker combination)

### Normalization

FeedSpine normalizes all natural keys to ensure consistent deduplication:

```python
# In RecordCandidate (models/record.py)
@field_validator("natural_key")
def normalize_natural_key(cls, v: str) -> str:
    """Normalize natural key for consistent deduplication."""
    return v.strip().lower()  # Whitespace stripped + lowercased
```

This means `"AAPL"`, `" aapl "`, and `"aapl"` all become the same key: `"aapl"`.

### The Deduplication Flow

```
┌─────────────────┐
│  Feed Source    │  (RSS, API, File, etc.)
└────────┬────────┘
         │ FeedAdapter.fetch()
         ▼
┌─────────────────┐
│ RecordCandidate │  natural_key = "0000320193:aapl"
│                 │  content = {...}
│                 │  metadata = {...}
└────────┬────────┘
         │ Pipeline.process()
         ▼
┌─────────────────────────────────────────────────────────┐
│              DEDUPLICATION CHECK                        │
│                                                         │
│   exists = await storage.get_by_natural_key("...")     │
│                                                         │
│   if exists:                                            │
│       → Record sighting (is_new=False)                 │
│       → Skip storing (return None)                      │
│   else:                                                 │
│       → Create Record with UUID                         │
│       → Store in Bronze layer                           │
│       → Record first sighting (is_new=True)            │
└─────────────────────────────────────────────────────────┘
```

### Storage Index for O(1) Dedup

In **MemoryStorage**:
```python
self._key_index: dict[str, str] = {}  # natural_key -> record_id
```

In **DuckDBStorage**:
```sql
CREATE UNIQUE INDEX idx_records_natural_key ON records(natural_key);
```

---

## Querying Deduplicated Data

### 1. By Natural Key (Primary Lookup)

```python
record = await storage.get_by_natural_key("sec:10-k:0001234567-24-000001")
```

### 2. By Layer (Data Quality Filter)

```python
# Get only validated Gold-layer records
async for record in storage.query(layer=Layer.GOLD):
    print(record.content)
```

### 3. Fluent Query Builder

```python
from feedspine import Query, Layer

query = (Query()
    .layer(Layer.SILVER)
    .where("form_type", "10-K")
    .published_after(datetime(2024, 1, 1))
    .order_by("published_at", descending=True)
    .limit(50))

results = await storage.query(**query.to_dict())
```

### 4. Full-Text Search

```python
from feedspine import MemorySearch, SearchType

search = MemorySearch(storage)
response = await search.search(
    "quarterly earnings", 
    search_type=SearchType.FULLTEXT
)
```

### 5. Sighting History (Audit Trail)

```python
# See all times this item was observed
sightings = await storage.get_sightings("sec:10-k:0001234567-24-000001")
for s in sightings:
    print(f"Seen at {s.captured_at}, is_new={s.is_new}")
```

---

## Module Reference

### Core Modules (`src/feedspine/`)

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| `models/` | Data models | `Record`, `RecordCandidate`, `Sighting`, `Layer` |
| `storage/` | Persistence backends | `MemoryStorage`, `DuckDBStorage` |
| `core/` | Orchestration | `FeedSpine`, `Checkpoint`, `RateLimiter` |
| `pipeline.py` | Processing logic | `Pipeline`, `PipelineStats` |
| `protocols/` | Interface contracts | `StorageBackend`, `FeedAdapter`, `SearchBackend` |

### Feed Adapters (`adapter/`)

| File | Purpose |
|------|---------|
| `base.py` | `BaseFeedAdapter` with rate limiting |
| `rss.py` | RSS/Atom feed parser |
| `json.py` | JSON feed adapter |
| `file.py` | File-based adapter |

### Optional Backends

| Module | Dependency | Purpose |
|--------|------------|---------|
| `storage/duckdb.py` | `pip install feedspine[duckdb]` | OLAP analytics with SQL |
| `search/elasticsearch.py` | `pip install feedspine[elasticsearch]` | Scalable search |
| `api/fastapi.py` | `pip install feedspine[api]` | REST API endpoints |

### Support Modules

| Module | Purpose |
|--------|---------|
| `cache/` | Key-value caching with TTL |
| `enricher/` | Data enhancement (layer promotion) |
| `queue/` | Pub/sub messaging |
| `scheduler/` | Task scheduling |
| `http/` | HTTP client with rate limiting |
| `metrics/` | Performance metrics collection |
| `notifier/` | Event notifications |
| `reporter/` | Progress reporting (Rich, Simple) |
| `blob/` | Binary object storage |
| `composition/` | Fluent configuration builders |
| `executor/` | Execution backends |
| `utils/` | Retry logic, helpers |

---

## Folder-by-Folder Analysis

### `src/feedspine/models/` - Core Data Models

```
models/
├── __init__.py
├── base.py       # Layer enum (BRONZE/SILVER/GOLD), Metadata, FeedSpineModel
├── record.py     # RecordCandidate (pre-dedup), Record (stored)
├── sighting.py   # Tracks each observation of a natural_key
├── query.py      # Fluent query builder
├── content.py    # Typed content schemas
├── converter.py  # Record type converters
└── task.py       # Task/TaskResult for async jobs
```

**Status: ✅ Active, Well-Organized**

### `src/feedspine/storage/` - Storage Backends

```
storage/
├── __init__.py
├── memory.py     # In-memory dict-based storage
└── duckdb.py     # DuckDB OLAP backend (optional)
```

**Status: ✅ Active, No Duplicates**

### `src/feedspine/core/` - Orchestration

```
core/
├── __init__.py
├── feedspine.py  # Main FeedSpine orchestrator
├── checkpoint.py # Resume support for collections
├── config.py     # Configuration management
└── resources.py  # RateLimiter, Semaphore, ResourcePool
```

**Status: ✅ Active, Essential**

### `src/feedspine/protocols/` - Interface Contracts

```
protocols/
├── __init__.py
├── storage.py    # StorageBackend protocol
├── feed.py       # FeedAdapter protocol
├── search.py     # SearchBackend protocol
├── cache.py      # CacheBackend protocol
├── enricher.py   # Enricher protocol
├── notifier.py   # Notifier protocol
└── progress.py   # ProgressReporter protocol
```

**Status: ✅ Active, Clean Separation of Concerns**

### `src/feedspine/adapter/` - Feed Adapters

```
adapter/
├── __init__.py
├── base.py       # BaseFeedAdapter with rate limiting
├── rss.py        # RSS/Atom feed parser
├── json.py       # JSON feed adapter
└── file.py       # File-based adapter
```

**Status: ✅ Active, No Dead Code**

### `src/feedspine/search/` - Search Backends

```
search/
├── __init__.py
├── memory.py         # Linear scan search (dev/testing)
└── elasticsearch.py  # Elasticsearch backend (optional)
```

**Status: ✅ Active**

### `src/feedspine/cache/` - Caching

```
cache/
├── __init__.py
└── memory.py     # In-memory cache with TTL
```

**Status: ✅ Active, Simple**

### `src/feedspine/enricher/` - Data Enhancement

```
enricher/
├── __init__.py
├── metadata.py       # Add metadata fields
├── passthrough.py    # No-op enricher
└── entity_enricher.py # Entity linking (EntitySpine integration)
```

**Status: ✅ Active, EntitySpine Integration Point**

### `src/feedspine/queue/` - Message Queue

```
queue/
├── __init__.py
└── memory.py     # In-memory pub/sub
```

**Status: ✅ Active**

### `src/feedspine/scheduler/` - Task Scheduling

```
scheduler/
├── __init__.py
└── memory.py     # In-memory scheduler
```

**Status: ✅ Active, Minimal**

### `src/feedspine/http/` - HTTP Utilities

```
http/
├── __init__.py
├── client.py         # HTTP client with retries
└── rate_limiter.py   # Request rate limiting
```

**Status: ✅ Active**

### `src/feedspine/metrics/` - Metrics

```
metrics/
├── __init__.py
└── collector.py  # Performance metrics collection
```

**Status: ✅ Active**

### `src/feedspine/notifier/` - Notifications

```
notifier/
├── __init__.py
└── console.py    # Console output notifier
```

**Status: ✅ Active, Minimal**

### `src/feedspine/reporter/` - Progress Reporting

```
reporter/
├── __init__.py
├── rich.py       # Rich terminal progress bars
└── simple.py     # Simple text progress
```

**Status: ✅ Active**

### `src/feedspine/api/` - REST API

```
api/
├── __init__.py
└── fastapi.py    # FastAPI endpoints (optional)
```

**Status: ✅ Active, Optional**

### `src/feedspine/blob/` - Binary Storage

```
blob/
├── __init__.py
└── filesystem.py # Filesystem blob storage
```

**Status: ✅ Active**

### `src/feedspine/composition/` - Fluent Configuration

```
composition/
├── __init__.py
├── config.py     # Configuration builder
├── feed.py       # Feed composition
├── ops.py        # Operations
├── preset.py     # Preset configurations
└── testing.py    # Test utilities
```

**Status: ✅ Active, Helper Utilities**

### `src/feedspine/executor/` - Execution

```
executor/
├── __init__.py
└── sync.py       # Synchronous executor
```

**Status: ✅ Active, Minimal**

### `src/feedspine/utils/` - Utilities

```
utils/
├── __init__.py
└── retry.py      # Retry logic with backoff
```

**Status: ✅ Active**

---

## Archive Folder Analysis

### `archive/` - Archived Content

```
archive/
├── site/                              # Old MkDocs build output
│   └── (HTML, CSS, JS files)
├── TRUSTFALL_COMPARISON.md            # Research notes
├── TRUSTFALL_FEATURES_TO_ADOPT.md     # Research notes
└── TRUSTFALL_INTEGRATION_ANALYSIS.md  # Research notes
```

**Status: ⚠️ Can Be Cleaned**
- `site/` is build output, shouldn't be in git
- TRUSTFALL docs are research notes, could move to `docs/design/`

### `native/` - Rust Extensions (Placeholder)

```
native/
└── sec_parser_rs/
    ├── Cargo.toml   # Minimal stub
    └── README.md
```

**Status: ⚠️ Placeholder**
- Contains only config, no actual Rust code yet
- Future extension point for performance-critical parsing

---

## Summary: No Duplicate Code Found

| Area | Status |
|------|--------|
| Core modules | ✅ Clean, no duplication |
| Storage backends | ✅ Clean (Memory, DuckDB) |
| Adapters | ✅ Clean (RSS, JSON, File) |
| Protocols | ✅ Clean interface contracts |
| Tests | ✅ Mirror src structure |
| Archive | ⚠️ `site/` should be gitignored |
| Native | ⚠️ Placeholder, no code |

### Recommendations

1. **Add to `.gitignore`:**
   ```
   archive/site/
   ```

2. **Move research docs:**
   ```bash
   mv archive/TRUSTFALL_*.md docs/design/
   ```

3. **Consider removing empty native scaffold** unless Rust development is planned

---

## Integration with EntitySpine

The EntitySpine `feeds/` module provides adapters that wrap EntitySpine sources as FeedSpine feeds:

```
entityspine/src/entityspine/feeds/
├── __init__.py      # Module exports
├── adapters.py      # Feed adapters (SEC, MIC, LEI, etc.)
└── sync.py          # FeedSpine → EntitySpine sync utilities
```

### Flow: EntitySpine → FeedSpine → EntitySpine

```
┌─────────────────────────────────────────────────────────────────┐
│                     REFERENCE DATA SOURCES                      │
│  SEC API │ ISO 10383 │ GLEIF │ ISO 3166 │ ISO 4217             │
└────────┬────────────────────────────────────────────────────────┘
         │
         │ EntitySpine Sources
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ENTITYSPINE FEED ADAPTERS                     │
│  SECTickerFeedAdapter │ MICFeedAdapter │ LEIFeedAdapter │ ...  │
│                                                                 │
│  Produces RecordCandidate with natural_key for dedup           │
└────────┬────────────────────────────────────────────────────────┘
         │
         │ FeedSpine Pipeline (dedup via natural_key)
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FEEDSPINE STORAGE                          │
│                                                                 │
│  MemoryStorage or DuckDBStorage                                 │
│  - Deduplicated records (Bronze layer)                          │
│  - Sighting history (change tracking)                           │
└────────┬────────────────────────────────────────────────────────┘
         │
         │ FeedSpineEntitySpineSync
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ENTITYSPINE REGISTRIES                       │
│                                                                 │
│  MICRegistry │ LEIRegistry │ SqliteStore (Entities)            │
│  (Gold layer - validated, queryable)                           │
└─────────────────────────────────────────────────────────────────┘
```

This integration enables:
- **Incremental updates**: Only new/changed data is processed
- **Deduplication**: Same entity won't be stored twice
- **Change tracking**: Sightings record when data was last seen
- **Resume support**: Long-running downloads can be checkpointed

---

## Quick Start Examples

### Basic Feed Collection with Deduplication

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter

async def main():
    # Create storage (dedup index lives here)
    storage = MemoryStorage()
    
    # Create orchestrator
    spine = FeedSpine(storage=storage)
    
    # Register a feed
    class HackerNewsAdapter(RSSFeedAdapter):
        def __init__(self):
            super().__init__(
                name="hackernews",
                url="https://hnrss.org/frontpage",
            )
    
    spine.register_feed(HackerNewsAdapter())
    
    # First collection - all new
    async with spine:
        result = await spine.collect()
        print(f"First run: {result.total_new} new, {result.total_duplicates} duplicates")
    
    # Second collection - duplicates detected
    async with spine:
        result = await spine.collect()
        print(f"Second run: {result.total_new} new, {result.total_duplicates} duplicates")
    
    # Query the data
    async for record in storage.query(limit=5):
        print(f"- {record.natural_key}: {record.content.get('title', 'N/A')}")

asyncio.run(main())
```

### Using EntitySpine Feeds

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage
from entityspine.feeds import MICFeedAdapter, CountryFeedAdapter

async def main():
    storage = MemoryStorage()
    spine = FeedSpine(storage=storage)
    
    # Register EntitySpine reference data feeds
    spine.register_feed(MICFeedAdapter())      # ISO 10383 exchanges
    spine.register_feed(CountryFeedAdapter())  # ISO 3166 countries
    
    async with spine:
        result = await spine.collect()
        print(f"Collected {result.total_new} reference data records")
    
    # Query by natural key
    nyse = await storage.get_by_natural_key("xnys")  # Normalized to lowercase
    if nyse:
        print(f"NYSE MIC: {nyse.content}")

asyncio.run(main())
```

### Checking Sighting History

```python
# See when an item was last observed
sightings = await storage.get_sightings("xnys")
for s in sightings:
    print(f"Seen: {s.captured_at}, First time: {s.is_new}")
```

---

## Test Coverage

FeedSpine has comprehensive test coverage:

```
tests/unit/
├── adapter/     # FeedAdapter tests
├── api/         # FastAPI endpoint tests
├── blob/        # Blob storage tests
├── cache/       # Cache backend tests
├── composition/ # Config builder tests
├── core/        # FeedSpine orchestrator tests
├── enricher/    # Enricher tests
├── executor/    # Executor tests
├── models/      # Data model tests
├── notifier/    # Notifier tests
├── queue/       # Queue tests
├── scheduler/   # Scheduler tests
├── search/      # Search backend tests
├── storage/     # Storage backend tests
└── test_pipeline.py  # Pipeline tests
```

**Total: 655 tests** covering all modules.
