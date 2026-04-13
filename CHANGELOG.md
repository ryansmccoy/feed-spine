---
title: "Changelog"
type: changelog
status: active
tags: [feedspine]
created: 2026-01-01
updated: 2026-06-15
---
# Changelog

## [0.3.0] — 2026-04-12

### Added

- `ops/schedules.py` — CRUD operations wrapping spine-core `ScheduleStore` (list, create, get, update, delete, list-due)
- Schedule API routes now backed by persistent spine-core `ScheduleStore` (survives restarts)
- `RunLogStore` wired through factory → `FeedCollectionService` → `Pipeline`
- `entityspine` declared as optional dependency (`pip install feedspine[entity]`)
- 80 new tests: `RunLogMixin` (22), `FetchContextMixin` (18), `ops/schedules` (13), schedule API routes (15), plus 12 more
- Test count: 1217 passed, 23 skipped

### Changed

- **BREAKING**: `protocols/__init__.py` narrowed from 57 → 8 exports (import from submodules directly)
- **BREAKING**: `feedspine/__init__.py` narrowed from ~60 → 20 focused imports
- Observation storage restructured: `storage/observation_storage.py` + `storage/mixins/` → `storage/observations/` (4 modules)
- `RunLogMixin` methods renamed to match `RunLogStore` protocol: `log_event`→`log`, `log_events_batch`→`log_batch`, `get_events_by_run`→`get_by_run`, `get_events_by_feed`→`get_by_feed`, `get_error_events`→`get_errors`
- `FetchContextMixin` methods renamed to match `FetchContextStore` protocol: `get_fetch_context`→`get`, `save_fetch_context`→`save`, `delete_fetch_context`→`delete`, `list_fetch_contexts`→`list_all`, `get_stale_fetch_contexts`→`get_stale`, `get_unhealthy_fetch_contexts`→`get_unhealthy`
- Schedule API routes rewritten: in-memory dict → `ops/schedules.py` → spine-core `ScheduleStore`
- `ops/feed.py` consolidated (removed duplicated timeline/stats logic)
- API routes thinned to delegate through ops layer; MCP bypasses removed
- Backward-compatibility re-exports removed from transport layers

### Removed

- `storage/shared/connection_managers.py` — dead code (~230 lines), zero consumers
- `protocols/queue.py` — replaced with spine-core `EventBus` re-exports
- 8 dead files from Phase 1 cleanup (unused storage backends, search stubs)
- `SEMANTIC`/`HYBRID` variants from `SearchType` enum
- Stale `__all__` entries in `cli_modules/util_cmds.py` (`api_app`, `migrate_app`, `stats_app`)

### Fixed

- `Layer` import missing at module level in `api/routes/metrics.py` (F821)
- Unused `uuid4` import in `ops/schedules.py` (F401)
- Import sorting in `feedspine/__init__.py` (I001)

## [0.2.0] — 2026-03-30

### Added

- CRUD API endpoints: POST/PATCH/DELETE for records, sightings, observations
- Cross-feed deduplication via `DedupIndex` — opt-in content-hash based dedup
- API versioning: all routes under `/api/v1/` prefix
- MCP tools: `timeline_query`, `storage_stats`, `feed_health`, `fetch_records_tool`, `record_history`, `export_data` (13 total, up from 7)
- MCP DB path configurable via `FEEDSPINE_MCP_DB` environment variable
- 19 new MCP tool tests covering ops-layer backing functions
- 14 new deduplication tests

### Changed

- MCP server shares single `OperationContext` via lifespan (no more per-tool storage creation)
- Reduced C901 complexity in 7 functions via extract-method refactoring
- Entity enricher cleaned up: single `__all__` with conditional append
- Fixed `OperationResult` attribute access: `.success`/`.data` (not `.ok`/`.value`)
- Fixed `OperationContext` import paths (`feedspine.ops` not `feedspine.ops.query`)

### Removed

- Disconnected `composition/` module (9 source files + 4 test files, zero consumers)

### Fixed

- ~120 test failures from stale imports and mock setups
- Ruff lint errors (F401, F841, I001, UP017, W293, F811, B017)

### Notes

- Test count: 1047 passed, 25 skipped, 1 xfailed
- Silent `except: pass` audit: all 8 instances are legitimate (ImportError for optional deps, ValueError/TypeError for parsing fallbacks)

## [0.1.0] — 2026-02-06

### Added

- `FeedAdapter` base class with pluggable adapter discovery via entry points
- Pipeline stages: Collector, Parser, Enricher, Store
- `TypedRecord`, `ContentSchema`, `Layer` content models
- `StorageBackend` protocol with implementations (SQLite, PostgreSQL, DuckDB, Redis, S3)
- `CopilotChatAdapter` for VS Code chat ingestion
- `CaptureSpineClient` HTTP integration (optional, try/except guarded)
- HTTP `RateLimiter` for polite crawling
- `RetryConfig` + `with_retry` decorator for resilient operations
- Progress reporters (Rich terminal, Simple text)
- Scheduler framework (memory, cron-based)
- Enricher framework (entity enricher, LLM enricher)
- Batch executor with configurable concurrency
- Content deduplication via hashing
- Queue abstraction (memory, Redis, RabbitMQ, Kafka)
- Notification framework (Slack, email, webhook)
- REST API service (optional `[api]` extra)
- CLI entry point `feedspine` (Typer-based)
- Full type annotations (`py.typed` marker)
- 760+ unit tests

### Notes

- First public release
- All cross-spine imports are optional and try/except guarded
- Requires Python 3.12+
- Hard dependencies: pydantic, structlog, beautifulsoup4, lxml, html2text, aiofiles, cachetools
