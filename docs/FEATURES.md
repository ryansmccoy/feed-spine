---
title: "Features"
type: feature
status: active
tags: [feedspine]
created: 2026-01-01
updated: 2026-06-15
---
# Feature History — FeedSpine

> Track new features as they're added. Newest first.

---

## v0.3.0 — 2026-04-12

### Persistent Schedule Store
- `ops/schedules.py` — CRUD operations wrapping spine-core `ScheduleStore`
- Schedule API routes backed by persistent store (survives restarts)
- Operations: list, create, get, update, delete, list-due

### RunLog & FetchContext Wiring
- `RunLogStore` wired through factory → `FeedCollectionService` → `Pipeline`
- `FetchContextStore` wired through factory for per-feed fetch state tracking

### Storage Restructuring
- Observation storage consolidated: `storage/observations/` (4 modules)
- `RunLogMixin` / `FetchContextMixin` methods renamed to match protocol names

### API Thinning
- `protocols/__init__.py` narrowed from 57 → 8 exports
- `feedspine/__init__.py` narrowed from ~60 → 20 focused imports
- API routes thinned to delegate through ops layer
- Backward-compatibility re-exports removed

### Cleanup
- Removed dead code: `ConnectionPoolManager`, `protocols/queue.py`, 8 unused files
- Removed `SEMANTIC`/`HYBRID` from `SearchType` enum
- 80 new tests (total: 1217 passed, 23 skipped)

---

## v0.2.0 — 2026-03-30

### CRUD API Endpoints
- POST/PATCH/DELETE for records, sightings, observations
- All routes under `/api/v1/` prefix

### Cross-Feed Deduplication
- `DedupIndex` — opt-in content-hash based dedup across feeds

### MCP Tooling Expansion
- 13 MCP tools (up from 7): `timeline_query`, `storage_stats`, `feed_health`, `fetch_records_tool`, `record_history`, `export_data`, and more
- MCP DB path configurable via `FEEDSPINE_MCP_DB` env var
- MCP server shares single `OperationContext` via lifespan

### Quality
- Reduced C901 complexity in 7 functions via extract-method refactoring
- Removed disconnected `composition/` module (9 source files, zero consumers)
- Fixed ~120 test failures from stale imports
- Test count: 1047 passed, 25 skipped

---

## v0.1.0 — 2026-02-06

### Core Pipeline
- `Pipeline` and `PipelineStats` for orchestration
- Medallion architecture (Bronze → Silver → Gold layers)
- `FeedAdapter` base class with pluggable adapter discovery

### Storage Backends
- `StorageBackend` protocol with implementations (SQLite, PostgreSQL, DuckDB, Redis, S3)
- `MemoryStorage` for development and testing
- Protocol-based design for swappable backends

### Feed Health & Scheduling
- Health monitoring with RAG (Red/Amber/Green) status
- `MemoryScheduler` with CLI + API wiring
- Feed health dashboard: `get_feed_health()`, `get_all_feed_health()`

### Enrichment & Search
- Entity enricher framework (optional `entityspine` integration)
- Content deduplication via hashing
- HTTP `RateLimiter` for polite crawling

### Metrics & Stats
- `get_collection_stats()`, `get_storage_summary()`
- CLI: `feedspine stats summary|feeds|collection`
- API: `GET /api/v1/stats/summary`

### API & CLI
- REST API service (optional `[api]` extra)
- CLI entry point `feedspine` (Typer-based)
- API key authentication middleware

### Infrastructure
- Progress reporters (Rich terminal, Simple text)
- `RetryConfig` + `with_retry` decorator
- Full type annotations (`py.typed` marker)
- 760+ unit tests

---

*For detailed changes, see [CHANGELOG.md](CHANGELOG.md).*
