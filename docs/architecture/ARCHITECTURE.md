---
title: "Architecture"
type: architecture
status: active
tags: [feed-spine, pipeline, data-model, architecture]
created: 2026-02-22
updated: 2026-04-12
---
# FeedSpine Architecture

> Storage-agnostic feed capture framework with automatic deduplication, sighting history, and medallion architecture.

---

## Overview

FeedSpine is a protocol-based framework for building data collection pipelines. It solves the "noisy feed" problem: SEC RSS feeds, company filings APIs, and market data feeds contain massive amounts of duplicate data. Processing the same filing 100 times wastes compute and storage.

**Core capabilities:**

- **Protocol-based design** — Swap backends (storage, search, cache) without code changes
- **Medallion architecture** — Bronze → Silver → Gold layered data refinement
- **Natural key deduplication** — Same key = same record
- **Content hash update detection** — Same key + different hash = content update
- **Sighting history** — Track when/where each record was observed
- **Ops layer pattern** — All business logic is transport-agnostic, returning typed `OperationResult[T]`

---

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                          │
│                                                                     │
│   CLI (Typer)           API (FastAPI)           MCP Server         │
│   cli.py +              api/fastapi.py +        transports/mcp/    │
│   cli_modules/*         api/routes/*            server.py          │
│                                                                     │
│   Thin wrappers that delegate to Ops layer                         │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          OPS LAYER                                  │
│                                                                     │
│   ops/__init__.py   — OperationContext, OperationResult[T]         │
│   ops/query.py      — fetch_records, execute_search, export_*      │
│   ops/feed.py       — feed stats, timeline queries                 │
│   ops/enrich.py     — enrichment operations                        │
│   ops/schedules.py  — schedule CRUD                                │
│   ops/runs.py       — collection run queries                       │
│                                                                     │
│   Pure business logic — no CLI/API/Rich imports                    │
│   All functions: (ctx: OperationContext) -> OperationResult[T]     │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       PIPELINE LAYER                                │
│                                                                     │
│   pipeline/context.py   — PipelineContext (storage, run_log, etc.) │
│   pipeline/stages.py    — process_candidate() deduplication logic  │
│   pipeline/runner.py    — run_feed() orchestration + event logging │
│   pipeline/core.py      — Pipeline facade class                    │
│   pipeline/dedup.py     — compute_natural_key, check_update        │
│                                                                     │
│   RecordCandidate → CREATED | DUPLICATE | UPDATED → Record         │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                                 │
│                                                                     │
│   Protocols (protocols/storage.py):                                │
│     StorageLifecycle, RecordStore, SightingStore, StorageBackend   │
│                                                                     │
│   Repository Pattern (storage/):                                    │
│     repository.py        — BaseRepository + Connection protocol    │
│     feed_queries.py      — FeedQueryMixin (all reads)              │
│     feed_mutations.py    — FeedMutationMixin (all writes)          │
│     feed_repository.py   — FeedRepository facade                   │
│     dialect.py           — SQLiteDialect, PostgreSQLDialect        │
│                                                                     │
│   In-Memory Backend:                                                │
│     memory.py           — MemoryStorage (dict-based)               │
│                                                                     │
│   Database Backends (storage/backends/):                            │
│     sqlite.py           — SQLite (dev/test)                        │
│     postgres.py         — PostgreSQL (production)                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Modules

### `ops/` — Operation Layer

Pure business logic following the spine-core ops pattern. All functions accept `OperationContext` and return `OperationResult[T]`.

| File | Purpose |
|------|---------|
| `__init__.py` | `OperationContext`, `OperationResult[T]` dataclasses |
| `query.py` | `fetch_records()`, `execute_search()`, `export_to_json/csv/parquet()`, `fetch_timeline()` |
| `feed.py` | Feed statistics, timeline, feed-specific operations |
| `enrich.py` | Enrichment orchestration |
| `schedules.py` | Schedule CRUD (list, create, get, update, delete, list_due) |
| `runs.py` | Collection run history queries |

**Key abstractions:**

```python
@dataclass
class OperationContext:
    storage: Any           # StorageBackend
    search: Any | None     # SearchBackend
    request_id: str        # Auto-generated UUID
    caller: str            # "api" | "cli" | "sdk" | "scheduler"
    dry_run: bool          # Preview mode
    metadata: dict         # Tracing data

@dataclass
class OperationResult(Generic[T]):
    success: bool
    data: T | None
    error: str | None
    warnings: list[str]
    metadata: dict
```

All op functions are async, transport-agnostic, and return `OperationResult[T]` (never raise for expected errors).

---

### `storage/` — Mixin-Based Repository

Database access follows the repository pattern with mixin composition:

| File | Purpose |
|------|---------|
| `repository.py` | `BaseRepository` with `query()`, `execute()`, `insert()`, dialect-aware SQL |
| `feed_queries.py` | `FeedQueryMixin` — all read operations (record/sighting/feed_run queries) |
| `feed_mutations.py` | `FeedMutationMixin` — all write operations (upserts, schema init) |
| `feed_repository.py` | `FeedRepository` — facade composing Query + Mutation + Base |
| `dialect.py` | `SQLiteDialect`, `PostgreSQLDialect` — portable SQL generation |
| `schemas.py` | DDL definitions for records, sightings, observations, feed_runs, fetch_contexts |
| `factory.py` | `StorageFactory` — creates backends by type string |
| `memory.py` | `MemoryStorage` — in-memory dict-based storage for testing |
| `observations/` | Observation storage (version tracking across record updates) |
| `shared/converters.py` | `row_to_record()`, `record_to_row()`, `row_to_sighting()` |

**Composition pattern:**

```python
class FeedRepository(FeedQueryMixin, FeedMutationMixin, BaseRepository):
    """Domain repository blending queries + mutations."""
    pass
```

**Dialect abstraction:**

```python
repo = FeedRepository(conn, SQLiteDialect())  # → ?
repo = FeedRepository(conn, PostgreSQLDialect())  # → $1
```

Same code runs on SQLite or PostgreSQL — dialect handles placeholders, timestamps, and upsert syntax.

---

### `pipeline/` — Processing Pipeline

Decomposed into focused modules:

| File | Purpose |
|------|---------|
| `context.py` | `PipelineContext` — dependency container for storage, run_log, services |
| `stages.py` | `process_candidate()` — deduplication logic (CREATED, DUPLICATE, UPDATED) |
| `runner.py` | `run_feed()` — orchestrates feed processing, emits run events |
| `core.py` | `Pipeline` — facade class wrapping context + stages + runner |
| `dedup.py` | `compute_natural_key()`, `check_update()` |
| `action.py` | `ProcessAction` enum |
| `result.py` | `ProcessResult` dataclass |
| `stats.py` | `PipelineStats` metrics |

**Processing flow:**

```
RecordCandidate
      │
      ▼
storage.get_by_natural_key(key)
      │
      ├── Not found ──────► CREATED (new record + first sighting)
      │
      ├── Found, same hash ► DUPLICATE (record sighting only)
      │
      └── Found, diff hash ► UPDATED (update record + sighting)
```

---

### `services/` — High-Level Services

| File | Purpose |
|------|---------|
| `collection.py` | `FeedCollectionService` — orchestrates collection runs, returns `CollectionOutcome` |
| `publishing.py` | `CollectionEventPublisher` — emits events to event bus |
| `recording.py` | `CollectionOutcomeRecorder` — persists run results |

---

### `core/` — Application Factory

| File | Purpose |
|------|---------|
| `app.py` | `FeedSpineApp` + `create_feed_spine()` factory |
| `config.py` | Core configuration |
| `exceptions.py` | FeedSpine-specific exception types |
| `feed_config.py` | Feed configuration models |
| `resources.py` | `RateLimiter`, `ResourcePool`, `Semaphore` |
| `storage_config.py` | Storage backend configuration |

---

### `api/` — FastAPI Application

| File | Purpose |
|------|---------|
| `fastapi.py` | App factory, lifespan hooks |
| `route_registry.py` | Centralized router registration |
| `middleware.py` | Request correlation, error handling |
| `settings.py` | Pydantic settings model |
| `models.py` | API request/response models |

**Route modules (15 in `api/routes/`):**

| Router | Endpoints |
|--------|-----------|
| `collect.py` | Trigger collection |
| `enrich.py` | Enrichment pipelines |
| `export.py` | JSON/CSV/Parquet exports |
| `feeds.py` | Feed configuration CRUD |
| `health.py` | Feed health monitoring |
| `metrics.py` | Prometheus-compatible metrics |
| `observations.py` | Observation version tracking |
| `records.py` | Record CRUD + query |
| `runs.py` | Feed run history |
| `schedules.py` | Schedule management |
| `search.py` | Full-text search |
| `sightings.py` | Sighting history |
| `stats.py` | Statistics and aggregation |
| `storage.py` | Storage backend status |
| `syndication.py` | RSS/Atom/OPML syndication output |
| `timeline.py` | Unified timeline across feeds |

---

### `cli_modules/` — Typer CLI

Thin wrappers that delegate to `ops/` functions:

| Module | Commands |
|--------|----------|
| `collect_cmds.py` | `collect run`, `collect init`, `collect check-config` |
| `feeds_cmds.py` | `feeds list`, `feeds list-types`, `feeds validate` |
| `feed_cmds.py` | `feed init`, `feed show` |
| `query_cmds.py` | `query records`, `query search`, `query sightings`, `query by-natural-key` |
| `export_cmds.py` | `export json`, `export csv`, `export parquet` |
| `enrich_cmds.py` | `enrich run` |
| `health_cmds.py` | `health list`, `health show`, `health failing` |
| `stats_cmds.py` | `stats summary`, `stats feeds`, `stats collection` |
| `capture_cmds.py` | Capture feeds and records |
| `migrate_cmds.py` | `migrate upgrade`, `migrate downgrade`, `migrate current` |
| `api_cmds.py` | `api serve --port <port>` |
| `util_cmds.py` | `config show`, `config validate` |
| `shared.py` | Common CLI utilities |
| `formatters.py` | Output formatting (tables, JSON, etc.) |

---

### `protocols/` — Interface Definitions

Runtime-checkable protocols for dependency injection. The `protocols/__init__.py` re-exports 8 primary interfaces:

| Protocol | Module | Purpose |
|----------|--------|---------|
| `StorageBackend` | `protocols/storage.py` | Full storage interface (lifecycle + records + sightings) |
| `RecordStore` | `protocols/storage.py` | Record-specific CRUD + query |
| `SightingStore` | `protocols/storage.py` | Sighting tracking |
| `StorageLifecycle` | `protocols/storage.py` | `initialize()` + `close()` |
| `SearchBackend` | `protocols/search.py` | Full-text search (KEYWORD type) |
| `FeedAdapter` | `protocols/feed.py` | Feed source contract |
| `Enricher` | `protocols/enricher.py` | Single-record enrichment |
| `ProgressReporter` | `protocols/progress.py` | Operation monitoring |

Additional protocols (import from submodules):

| Protocol | Module | Purpose |
|----------|--------|---------|
| `BatchEnricher` | `protocols/enricher.py` | Batch enrichment |
| `RunLogStore` | `protocols/run_log.py` | Pipeline event logging |
| `FetchContextStore` | `protocols/fetch_context.py` | HTTP conditional fetch state |
| `BlobStorage` | `protocols/blob.py` | Binary file storage |
| `Cache` | `protocols/cache.py` | Async key-value cache |
| `MessageQueue` | `protocols/queue.py` | Pub/sub messaging |
| `CollectionStrategy` | `protocols/strategy.py` | Multi-source optimization |

---

### `transports/mcp/` — MCP Server

Model Context Protocol server exposing 13 tools for LLM integration:

| Tool | Purpose |
|------|---------|
| `feed_collect` | Trigger collection for a feed |
| `feed_enrich` | Trigger enrichment |
| `feed_enrich_status` | Check enrichment status |
| `feed_health` | Feed health (RAG status) |
| `feed_runs` | Collection run history |
| `fetch_records` | Query stored records |
| `list_feeds` | List configured feeds |
| `search_records` | Full-text search |
| `timeline_query` | Unified timeline |
| `storage_stats` | Storage backend statistics |
| `export_data` | Export to JSON/CSV/Parquet |
| `record_history` | Record version history |
| `health_check` | System health |

---

## Design Patterns

### 1. Facade Pattern

Core modules expose a single facade that composes submodules:

```
pipeline/core.py  → context.py, stages.py, runner.py
storage/feed_repository.py  → feed_queries.py, feed_mutations.py, repository.py
core/app.py → storage, services, pipeline
```

### 2. Mixin Composition

Separates read/write concerns in the storage layer:

```python
class FeedRepository(FeedQueryMixin, FeedMutationMixin, BaseRepository):
    pass
```

### 3. Protocol-Based Backends

All backends implement protocols — swap implementations without changing consumers:

```python
storage: StorageBackend = MemoryStorage()       # For testing
storage: StorageBackend = SQLiteStorage(path)   # For dev
storage: StorageBackend = PostgresStorage(url)  # For prod
```

### 4. Generic Result Types

`OperationResult[T]` enforces typed success/failure envelopes:

```python
result = await fetch_records(ctx, layer="bronze")
if result.success:
    records = result.data  # type: list[dict]
else:
    error_msg = result.error
```

### 5. Dialect Abstraction

Single codebase, multiple databases:

```python
sql = dialect.upsert("records", columns, ["natural_key"])
# SQLite: INSERT OR REPLACE ...
# PostgreSQL: INSERT ... ON CONFLICT ...
```

---

## Data Flow

### Record Capture Flow

```
[Feed Source]  →  [FeedAdapter.fetch()]  →  [RecordCandidate]
                         │
                         ▼
[Pipeline.process_candidate()]
    │
    ├─► Lookup by natural_key
    │
    ├─► If not found:
    │       Create Record (id, natural_key, content_hash, layer="bronze")
    │       Store Sighting (first seen, source)
    │       → ProcessAction.CREATED
    │
    ├─► If found + same hash:
    │       Store Sighting (seen again, source)
    │       → ProcessAction.DUPLICATE
    │
    └─► If found + different hash:
        Update Record (new content_hash, version++, seen_count++)
        Store Sighting (updated, source)
        → ProcessAction.UPDATED

[FeedRepository]  →  [Database]
```

### Query Flow

```
[CLI / API / MCP Request]
      │
      ▼
[OperationContext(storage, search)]
      │
      ▼
[ops/ functions]
    │
    ├─► fetch_records(ctx, layer, limit, offset)
    │       → storage.query() → OperationResult[list[dict]]
    │
    ├─► execute_search(ctx, query, type)
    │       → search.search() → OperationResult[dict]
    │
    └─► export_to_json/csv/parquet(ctx, path)
        → storage.query() → write file → OperationResult[dict]
```

---

## Extension Points

1. **New storage backend** — Implement `StorageBackend` protocol
2. **New feed adapter** — Extend `BaseFeedAdapter` or implement `FeedAdapter` protocol
3. **New enricher** — Implement `Enricher` or `BatchEnricher` protocol
4. **New search backend** — Implement `SearchBackend` protocol
5. **New ops operations** — Add functions to `ops/` (new module or extend existing)
6. **New CLI commands** — Add to `cli_modules/`, delegate to `ops/`
7. **New API routes** — Add to `api/routes/`, register in `route_registry.py`
8. **New MCP tools** — Add to `transports/mcp/server.py`
