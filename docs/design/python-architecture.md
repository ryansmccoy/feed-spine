# Python Architecture

**FeedSpine + py-sec-edgar Package Split**

*Storage-agnostic, executor-agnostic core with domain-specific implementations*

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Storage Agnostic** | Protocol-based backends (DuckDB, Postgres, Redis, etc.) |
| **Executor Agnostic** | Protocol-based executors (sync, async, Celery, Airflow, Prefect) |
| **Search Agnostic** | Protocol-based search (SQLite FTS, Postgres, Elasticsearch, vector DBs) |
| **Cache Agnostic** | Protocol-based caching (memory, Redis, Memcached) |
| **Blob Agnostic** | Protocol-based blob storage (filesystem, S3, GCS, Azure) |
| **Queue Agnostic** | Protocol-based messaging (memory, Redis, RabbitMQ, Kafka) |
| **Notification Agnostic** | Protocol-based alerts (webhook, Slack, email) |
| **Zero Lock-in** | Swap any component without code changes |

---

## Protocol Overview

FeedSpine uses Python's `Protocol` pattern for maximum flexibility:

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ StorageBackend   │  │  SearchBackend   │  │  CacheBackend    │  │   BlobStorage    │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ • Memory         │  │ • Memory         │  │ • Memory (LRU)   │  │ • Filesystem     │
│ • Filesystem     │  │ • Filesystem     │  │ • Disk (SQLite)  │  │ • S3 / MinIO     │
│ • SQLite         │  │ • SQLite FTS5    │  │ • Redis          │  │ • GCS            │
│ • PostgreSQL     │  │ • PostgreSQL FTS │  │ • Memcached      │  │ • Azure Blob     │
│ • DuckDB         │  │ • Elasticsearch  │  │                  │  │                  │
│ • Redis          │  │ • Chroma (vec)   │  │                  │  │                  │
│ • MongoDB        │  │ • Qdrant (vec)   │  │                  │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  MessageQueue    │  │    Notifier      │  │    Executor      │  │   FeedAdapter    │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ • Memory         │  │ • Console        │  │ • Sync           │  │ • RSS/Atom       │
│ • Filesystem     │  │ • Webhook        │  │ • AsyncIO        │  │ • REST API       │
│ • Redis Streams  │  │ • Email (SMTP)   │  │ • Threaded       │  │ • WebSocket      │
│ • RabbitMQ       │  │ • Slack          │  │ • Celery         │  │ • Scraper        │
│ • Kafka          │  │ • Discord        │  │ • Prefect        │  │ • File           │
│ • AWS SQS        │  │ • Telegram       │  │ • Dagster        │  │ • Custom         │
└──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

**Usage**: Mix and match any combination:

```python
feedspine.configure(
    storage=PostgresBackend(),      # Any StorageBackend
    search=ElasticsearchSearch(),   # Any SearchBackend
    cache=RedisCache(),             # Any CacheBackend
    blob=S3Blob(),                  # Any BlobStorage
    queue=KafkaQueue(),             # Any MessageQueue
    notify=SlackNotifier(),         # Any Notifier
    executor=PrefectExecutor(),     # Any Executor
)
```

---

## Package Structure

```
feedspine/
├── pyproject.toml
├── README.md
├── src/
│   └── feedspine/
│       ├── __init__.py
│       │
│       ├── core/
│       │   ├── config.py           # BaseSettings, environment config
│       │   └── exceptions.py       # FeedSpineError hierarchy
│       │
│       ├── models/                 # Pydantic models
│       │   ├── base.py             # Layer enum, FeedSpineModel
│       │   ├── record.py           # RecordCandidate, Record
│       │   ├── sighting.py         # Sighting model
│       │   └── task.py             # Task, TaskResult
│       │
│       ├── protocols/              # Extension point interfaces
│       │   ├── storage.py          # StorageBackend
│       │   ├── search.py           # SearchBackend
│       │   ├── cache.py            # CacheBackend
│       │   ├── blob.py             # BlobStorage
│       │   ├── queue.py            # MessageQueue
│       │   ├── notification.py     # Notifier
│       │   ├── feed.py             # FeedAdapter
│       │   └── executor.py         # Executor
│       │
│       ├── storage/                # Storage implementations
│       │   ├── memory.py           # In-memory (testing)
│       │   ├── sqlite.py           # SQLite
│       │   ├── duckdb.py           # DuckDB
│       │   ├── postgres.py         # PostgreSQL
│       │   └── ...
│       │
│       ├── search/                 # Search implementations
│       ├── cache/                  # Cache implementations
│       ├── blob/                   # Blob storage implementations
│       ├── queue/                  # Message queue implementations
│       ├── notification/           # Notification implementations
│       ├── executors/              # Executor implementations
│       │
│       ├── pipeline/               # Streaming pipeline pattern
│       │   ├── stage.py            # Stage protocol
│       │   └── stages/             # Built-in stages
│       │       ├── collect.py
│       │       ├── deduplicate.py
│       │       └── enrich.py
│       │
│       └── reader/
│           ├── service.py          # Query interface
│           ├── api.py              # FastAPI (optional)
│           └── cli.py              # Typer CLI
```

---

## Package Separation

FeedSpine is a **generic framework**. Domain-specific packages extend it:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              feedspine (PyPI)                                │
│                     Generic Feed Capture Framework                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Protocol-based backends (storage, search, cache, etc.)                   │
│  • Pydantic models                                                          │
│  • Medallion architecture (Bronze → Silver → Gold)                          │
│  • Deduplication by natural key                                             │
│  • Two-timestamp model (published_at / captured_at)                         │
│  • FeedAdapter protocol                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ pip install feedspine
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           py-sec-edgar (PyPI)                                │
│                     SEC EDGAR Domain Implementation                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  • SEC feed adapters (RSS, daily-index, full-index, XBRL)                   │
│  • Accession number as natural key                                           │
│  • Filing models (10-K, 8-K, etc.)                                          │
│  • SEC-specific enrichers                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline vs Workflow

FeedSpine supports **both** patterns:

### Pipeline (Streaming)

For continuous data ingestion:

```python
pipeline = (
    Pipeline("sec-ingest")
    .add(CollectStage(feed=sec_rss_feed))
    .add(DeduplicateStage())
    .add(StoreStage(storage=storage))
    .add(EnrichStage(enrichers=[...]))
)

await pipeline.run()
```

### Workflow (DAG)

For batch/scheduled jobs:

```python
wf = Workflow("daily_job")

@wf.task()
def collect(): ...

@wf.task(upstream=["collect"])
def enrich(): ...

@wf.task(upstream=["enrich"])
def report(): ...

# Execute locally or export
await wf.run()            # Local execution
wf.to_airflow()           # Export to Airflow DAG
wf.to_prefect()           # Export to Prefect Flow
```

---

## Configuration

Environment-based configuration with sensible defaults:

```toml
# feedspine.toml
[storage]
backend = "duckdb"
path = "./data/feedspine.duckdb"

[cache]
backend = "memory"

[search]
backend = "sqlite_fts"

[rate_limits]
default = 10.0
"sec.*" = 8.0
```

Environment overrides:
```bash
FEEDSPINE_STORAGE__BACKEND=postgres
FEEDSPINE_STORAGE__URL=postgresql://user:pass@localhost/feedspine
```

---

## Installation Options

```bash
# Core only (memory storage, sync executor)
pip install feedspine

# With DuckDB (recommended for analytics)
pip install feedspine[duckdb]

# With PostgreSQL (production)
pip install feedspine[postgres]

# With search
pip install feedspine[elasticsearch]

# With everything
pip install feedspine[all]
```
