# Implementation Roadmap

**Systematic approach to building a production-ready framework**

---

## Implementation Philosophy

### Why Order Matters

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DEPENDENCY HIERARCHY                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LAYER 1: Foundation (No dependencies)                                     │
│   ══════════════════════════════════════                                    │
│   • Pydantic Models (data contracts)                                        │
│   • Enums, Exceptions, Config                                               │
│   • Protocol Definitions (interfaces)                                       │
│                                                                              │
│   LAYER 2: In-Memory Implementations (depends on Layer 1)                   │
│   ═══════════════════════════════════════════════════════                   │
│   • MemoryStorage, MemoryCache, MemoryQueue                                 │
│   • SyncExecutor, MemorySearch                                              │
│   • ConsoleNotifier, FilesystemBlob                                         │
│                                                                              │
│   LAYER 3: Core Logic (depends on Layers 1-2)                               │
│   ════════════════════════════════════════════                              │
│   • Pipeline stages                                                         │
│   • Workflow engine                                                         │
│   • FeedSpine orchestrator                                                  │
│                                                                              │
│   LAYER 4: Production Backends (depends on Layers 1-3)                      │
│   ════════════════════════════════════════════════════                      │
│   • PostgresStorage, DuckDBStorage, RedisStorage                            │
│   • ElasticsearchSearch, ChromaSearch                                       │
│   • CeleryExecutor, PrefectExecutor                                         │
│   • S3Blob, SlackNotifier, KafkaQueue                                       │
│                                                                              │
│   LAYER 5: Domain Implementations (depends on all above)                    │
│   ══════════════════════════════════════════════════════                    │
│   • py-sec-edgar feeds, enrichers, models                                   │
│   • CLI, API, Reader service                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core Models & Protocols ✅

**Goal**: Define all data contracts and interfaces before any implementation.

### Models

| Model | Purpose | Status |
|-------|---------|--------|
| `Layer` | Medallion tier enum | ✅ Done |
| `Metadata` | Common metadata fields | ✅ Done |
| `RecordCandidate` | Pre-dedup incoming record | ✅ Done |
| `Record` | Stored record with full metadata | ✅ Done |
| `Sighting` | Tracks when records are seen | ✅ Done |
| `Task`, `TaskResult` | Executor communication | ✅ Done |

### Protocols

| Protocol | Purpose | Status |
|----------|---------|--------|
| `StorageBackend` | Record storage | ✅ Done |
| `CacheBackend` | Key-value caching | ✅ Done |
| `SearchBackend` | Full-text/semantic search | ✅ Done |
| `BlobStorage` | Binary file storage | ✅ Done |
| `MessageQueue` | Pub/sub messaging | ✅ Done |
| `Notifier` | Alert notifications | ✅ Done |
| `Executor` | Task execution | ✅ Done |
| `FeedAdapter` | Feed parsing | ✅ Done |

---

## Phase 2: In-Memory Implementations ✅

**Goal**: Working implementations for testing, no external dependencies.

| Component | Purpose | Status |
|-----------|---------|--------|
| `MemoryStorage` | In-memory record storage | ✅ Done |
| `MemoryCache` | In-memory cache with TTL | ✅ Done |
| `MemoryQueue` | In-memory message queue | ✅ Done |
| `MemorySearch` | Linear search through records | ✅ Done |
| `SyncExecutor` | Simple sync/async executor | ✅ Done |
| `FilesystemBlob` | Local file blob storage | ✅ Done |
| `ConsoleNotifier` | Print notifications | ✅ Done |

---

## Phase 3: Core Logic ✅

**Goal**: Pipeline stages and the FeedSpine orchestrator.

### Pipeline Architecture

```
FeedAdapter ──▶ CollectStage ──▶ DedupeStage ──▶ StoreStage
                     │               │               │
                     ▼               ▼               ▼
               RecordCandidate    Record         Record
                                (BRONZE)       (stored)

Optional stages:
──────────────
EnrichStage: BRONZE → SILVER → GOLD
FilterStage: Drop records matching criteria
NotifyStage: Send alerts for certain records
```

### FeedSpine Orchestrator

```python
class FeedSpine:
    """Main orchestrator for feed capture."""
    
    def __init__(
        self,
        storage: StorageBackend,
        *,
        search: SearchBackend | None = None,
        cache: CacheBackend | None = None,
        executor: Executor | None = None,
    ) -> None: ...
    
    # Registration
    def register_feed(self, feed: FeedAdapter) -> None: ...
    def register_enricher(self, enricher: Enricher) -> None: ...
    
    # Collection
    async def collect(self, feeds: list[str] | None = None) -> CollectionResult: ...
    
    # Query
    async def query(self, **filters) -> AsyncIterator[Record]: ...
    async def search(self, query: str) -> SearchResponse: ...
    
    # Lifecycle
    async def __aenter__(self) -> FeedSpine: ...
    async def __aexit__(self, *args) -> None: ...
```

---

## Phase 4: Production Backends

**Goal**: Real-world storage, search, and execution backends.

### Priority Order

| Priority | Backend | Use Case | Status |
|----------|---------|----------|--------|
| 🔴 High | SQLite Storage | Portable, single-file | ⏳ |
| 🔴 High | DuckDB Storage | Analytics, Parquet | ✅ Done |
| 🔴 High | SQLite FTS | Simple full-text search | ⏳ |
| 🟡 Medium | PostgreSQL Storage | Production databases | ⏳ |
| 🟡 Medium | Redis Cache | Distributed caching | ⏳ |
| 🟡 Medium | Elasticsearch | Production search | ✅ Done |
| 🟢 Low | S3/GCS Blob | Cloud blob storage | ⏳ |
| 🟢 Low | Celery/Prefect | Distributed execution | ⏳ |

### Completed Backends

#### DuckDB Storage (`feedspine.storage.duckdb`)
- **38 tests** covering full StorageBackend protocol
- SQL analytics via `execute_sql()` method
- Parquet export via `export_to_parquet()`
- Install: `pip install feedspine[duckdb]`

#### Elasticsearch Search (`feedspine.search.elasticsearch`)
- **18 tests** covering full SearchBackend protocol
- Full-text, keyword, and filter search
- Highlights and relevance scoring
- Install: `pip install feedspine[elasticsearch]`

#### FastAPI Integration (`feedspine.api.fastapi`)
- **17 tests** covering REST API
- App factory pattern with `create_app()`
- Endpoints: records CRUD, search, stats, collection
- Install: `pip install feedspine[api]`

---

## Phase 5: Domain Implementations

**Goal**: Real-world feed adapters and domain-specific logic.

### SEC EDGAR (Reference Implementation)

| Component | Purpose |
|-----------|---------|
| `SECRSSFeed` | Real-time RSS feed adapter |
| `SECDailyIndexFeed` | Daily crawler.idx parser |
| `SECFullIndexFeed` | Quarterly master.idx parser |
| `SECFilingEnricher` | Extract form type, CIK, etc. |

### Future Domains

| Domain | Natural Key |
|--------|-------------|
| Press Releases | `source:release_id` |
| News Articles | URL hash |
| UK Companies House | Filing reference |
| Patents | Patent number |

---

## Development Principles

| Principle | Why It Works |
|-----------|--------------|
| **Protocol-first** | Define contracts → Implement consistently |
| **Test-driven** | Write tests first → Clear acceptance criteria |
| **Small batches** | One protocol + implementation at a time → Higher quality |
| **Type annotations** | Full typing → Catch errors early |
| **Docstrings with examples** | Detailed docs → Runnable documentation |

---

## Current Status

- ✅ **Phase 1**: Complete (models, protocols, exceptions)
- ✅ **Phase 2**: Complete (all 7 in-memory backends with full test coverage)
- ✅ **Phase 3**: Complete (Pipeline, FeedSpine, Adapters, Scheduler, Enricher)
- 🔄 **Phase 4**: In Progress (DuckDB ✅, Elasticsearch ✅, FastAPI ✅)
- ⏳ **Phase 5**: Future (domain implementations)

### Test Coverage (448 tests)

| Component | Tests |
|-----------|-------|
| Models | 40+ |
| Storage (Memory) | 30 |
| Storage (DuckDB) | 38 |
| Cache (Memory) | 25 |
| Queue (Memory) | 17 |
| Search (Memory) | 29 |
| Search (Elasticsearch) | 18 |
| Executor (Sync) | 19 |
| Blob (Filesystem) | 26 |
| Notifier (Console) | 23 |
| Pipeline | 18 |
| FeedAdapter (RSS/JSON) | 53 |
| FeedSpine | 21 |
| Scheduler | 38 |
| Enricher | 23 |
| API (FastAPI) | 17 |
