---
title: "Module Reference"
type: architecture
status: active
tags: [feed-spine, architecture, python, data-model]
created: 2026-02-22
updated: 2026-04-12
---
# FeedSpine Module Reference

> Quick reference for all packages under `src/feedspine/` — v0.3.0.

---

## Core Modules

### `core/`

Application factory and configuration.

| File | Key Exports |
|------|-------------|
| `app.py` | `FeedSpineApp`, `create_feed_spine()` |
| `config.py` | `FeedSpineSettings`, `get_settings()` |
| `exceptions.py` | `FeedSpineError`, `StorageError`, `FeedError`, `PipelineError`, `ValidationError`, `ConfigurationError`, `NotFoundError`, `DuplicateError` |
| `feed_config.py` | `FeedConfig`, `load_config()`, `create_adapters_from_config()`, `find_config_file()` |
| `resources.py` | `ResourcePool`, `RateLimiter`, `Semaphore` |
| `storage_config.py` | `StorageConfig` |

### `ops/`

Pure business logic — transport-agnostic. All functions accept `OperationContext` and return `OperationResult[T]`.

| File | Key Functions |
|------|---------------|
| `__init__.py` | `OperationContext`, `OperationResult[T]` dataclasses |
| `query.py` | `execute_search()`, `fetch_records()`, `fetch_record_history()`, `fetch_sightings()` |
| `feed.py` | `fetch_timeline()`, `fetch_sources()`, `record_to_timeline_item()` |
| `enrich.py` | `submit_enrichment_batch()`, `get_batch_status()` |
| `schedules.py` | `list_schedules()`, `create_schedule()`, `get_schedule()`, `update_schedule()`, `delete_schedule()`, `list_due_schedules()` |
| `runs.py` | `query_feed_runs()` |
| `export.py` | `export_to_json()`, `export_to_jsonl()`, `export_to_csv()`, `export_to_parquet()` |
| `stats.py` | `fetch_storage_summary()`, `fetch_layer_distribution()`, `fetch_feed_runs()`, `fetch_collection_stats()`, `check_storage_health()` |
| `health.py` | `fetch_all_feed_health()`, `fetch_feed_health()`, `fetch_feed_run_history()`, `fetch_health_alerts()` |
| `collection.py` | `submit_collection()` |
| `capture.py` | `ingest_single()`, `ingest_batch()`, `build_ingest_payload()`, `check_capture_health()` |
| `feed_formats.py` | `generate_rss_feed()`, `generate_atom_feed()` |

### `pipeline/`

Record processing with automatic deduplication and update detection.

| File | Key Exports |
|------|-------------|
| `context.py` | `PipelineContext` (dependency container for storage, run_log, services) |
| `stages.py` | `process_candidate()` — deduplication logic (CREATED, DUPLICATE, UPDATED) |
| `runner.py` | `run_feed()` — orchestrates feed processing, emits run events |
| `core.py` | `Pipeline` — facade class wrapping context + stages + runner |
| `dedup.py` | `DedupMatch`, `DedupIndex`, `DedupStats` |
| `action.py` | `ProcessAction` enum |
| `result.py` | `ProcessResult` dataclass |
| `stats.py` | `PipelineStats` metrics |

### `services/`

High-level service layer for orchestrating collection workflows.

| File | Key Exports |
|------|-------------|
| `collection.py` | `FeedCollectionService` — orchestrates collection runs, returns `CollectionOutcome` |
| `publishing.py` | `CollectionEventPublisher` — emits events to event bus |
| `recording.py` | `CollectionOutcomeRecorder` — persists run results |

### `workflows/`

Runtime orchestration for feed collection.

| File | Key Exports |
|------|-------------|
| `collect.py` | `FeedCollectionRuntime` — coordinates adapters, pipeline, and services |

---

## Storage Modules

### `storage/`

Database access with repository pattern and dialect abstraction.

**Repository core:**

| File | Key Exports |
|------|-------------|
| `repository.py` | `BaseRepository`, `Connection` protocol, `SAConnectionBridge` |
| `feed_queries.py` | `FeedQueryMixin` — all read operations |
| `feed_mutations.py` | `FeedMutationMixin` — all write operations |
| `feed_repository.py` | `FeedRepository` — facade composing Query + Mutation + Base |
| `dialect.py` | `SQLiteDialect`, `PostgreSQLDialect`, `get_dialect()` |
| `schemas.py` | DDL definitions for all tables |
| `repository_backend.py` | `RepositoryStorageBackend` — storage protocol adapter for FeedRepository |

**Domain mixins:**

| File | Key Exports |
|------|-------------|
| `feed_mixins.py` | `SightingOperationsMixin`, `FeedRunOperationsMixin`, `FeedConfigOperationsMixin`, `ObservationOperationsMixin`, `StatsOperationsMixin` |
| `record_mixins.py` | `RecordOperationsMixin`, `BatchOperationsMixin`, `VersionControlMixin` |

**Data handling:**

| File | Key Exports |
|------|-------------|
| `memory.py` | `MemoryStorage` — dict-based in-memory storage for testing |
| `factory.py` | `create_storage()`, `storage_from_env()`, `register_storage_backend()`, `detect_storage_type()` |
| `models.py` | SQLAlchemy models: `RecordModel`, `SightingModel`, `FeedRunModel`, `RecordVersionModel`, `MetadataModel` |
| `data_types.py` | `DataType`, `detect_data_type()`, `get_storage_recommendations()` |
| `optimization.py` | `Cursor`, `Page[T]`, `paginate_with_cursor()`, `BatchConfig`, `batch_iterator()` |
| `analysis.py` | `QueryPlan`, `analyze_query_plan()`, `IndexRecommendation` |
| `scaling.py` | `TimePartition`, `generate_monthly_partitions()`, `get_scaling_recommendations()` |

### `storage/backends/`

Pluggable database backends (all implement `StorageBackend` protocol):

| File | Backend |
|------|---------|
| `sqlite.py` | `SQLiteStorage` — development and testing |
| `postgres.py` | `PostgresStorage` — production |
| `duckdb.py` | `DuckDBStorage` — analytics |

### `storage/observations/`

Observation tracking (version history across record updates):

| File | Key Exports |
|------|-------------|
| `storage.py` | `ObservationStorage` — main facade |
| `converter.py` | `ObservationConverterMixin` |
| `core_operations.py` | `CoreOperationsMixin` |
| `query_operations.py` | `QueryOperationsMixin` |

### `storage/shared/`

Shared database utilities:

| File | Key Exports |
|------|-------------|
| `converters.py` | `row_to_record()`, `record_to_row()`, `row_to_sighting()`, `sighting_to_row()` |
| `query_builders.py` | `QueryBuilder`, `SQLiteQueryBuilder`, `PostgresQueryBuilder`, `DuckDBQueryBuilder` |
| `validators.py` | `validate_record()`, `validate_sighting()`, `validate_layer()`, `sanitize_order_by()` |

### `storage/shared/mixins/`

Reusable storage mixins for cross-cutting concerns:

| File | Key Exports |
|------|-------------|
| `fetch_context.py` | `FetchContextMixin` — HTTP conditional fetch state (ETag, Last-Modified) |
| `records.py` | `RecordStorageMixin` |
| `run_log.py` | `RunLogMixin` — pipeline event logging |

---

## Protocol Definitions

### `protocols/`

Runtime-checkable protocols (`@runtime_checkable`) for dependency injection. The `protocols/__init__.py` re-exports 8 primary interfaces.

| File | Protocols |
|------|-----------|
| `storage.py` | `StorageLifecycle`, `RecordStore`, `SightingStore`, `StorageBackend` |
| `search.py` | `SearchBackend`, `SearchType` enum, `SearchResult`, `SearchResponse` |
| `feed.py` | `FeedAdapter` |
| `enricher.py` | `Enricher`, `BatchEnricher`, `EnrichmentResult`, `EnrichmentStatus`, `EnricherConfig` |
| `run_log.py` | `RunLogStore` |
| `fetch_context.py` | `FetchContextStore` |
| `blob.py` | `BlobInfo`, `BlobStorage` |
| `cache.py` | `CacheBackend` |
| `queue.py` | `MessageQueue` |
| `progress.py` | `ProgressStage`, `ProgressEvent`, `ProgressReporter`, `NullProgressReporter`, `CallbackProgressReporter` |
| `strategy.py` | `CollectionStrategy`, `IncrementalStrategy`, `BaseCollectionStrategy`, `SourcePriority`, `CollectionPlan` |

---

## Presentation Layer

### `api/`

FastAPI HTTP application.

| File | Purpose |
|------|---------|
| `fastapi.py` | App factory, lifespan hooks |
| `route_registry.py` | `include_all_routers()` centralized registration |
| `middleware.py` | Request correlation, error handling |
| `settings.py` | Pydantic settings model |
| `models.py` | API request/response models |

### `api/routes/`

Domain routers (16 files):

| Router | Endpoints |
|--------|-----------|
| `collect.py` | `/collect` — trigger collection |
| `enrich.py` | `/enrich` — enrichment pipelines |
| `export.py` | `/export` — JSON/CSV/Parquet |
| `feeds.py` | `/feeds` — feed configuration CRUD |
| `health.py` | `/health` — feed health monitoring |
| `metrics.py` | `/metrics` — Prometheus-compatible |
| `observations.py` | `/observations` — version tracking |
| `records.py` | `/records` — record CRUD + query |
| `runs.py` | `/runs` — feed run history |
| `schedules.py` | `/schedules` — schedule management |
| `search.py` | `/search` — full-text search |
| `sightings.py` | `/sightings` — sighting history |
| `stats.py` | `/stats` — statistics |
| `storage.py` | `/storage` — storage backend status |
| `syndication.py` | `/syndication` — RSS/Atom/OPML output |
| `timeline.py` | `/timeline` — merged event timeline |

### `cli.py` + `cli_modules/`

Typer CLI entry point with command groups:

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
| `formatters.py` | Output formatting (tables, JSON) |

### `transports/mcp/`

Model Context Protocol server for LLM integration:

| File | Key Exports |
|------|-------------|
| `server.py` | MCP server exposing 13 tools (feed_collect, search_records, export_data, etc.) |

---

## Feed Adapters

### `adapter/`

Feed source implementations (all extend `BaseFeedAdapter`):

| File | Key Exports |
|------|-------------|
| `base.py` | `BaseFeedAdapter`, `FeedError` |
| `rss.py` | `RSSFeedAdapter` — RSS/Atom feed parsing |
| `json.py` | `JSONFeedAdapter` — JSON API consumption |
| `csv_adapter.py` | CSV file/URL adapter |
| `file.py` | Local file adapter |
| `sec_edgar.py` | SEC EDGAR RSS feed adapter |
| `polygon_earnings.py` | Polygon.io earnings adapter |
| `rate_limiter.py` | Adapter-level rate limiting |

---

## Enrichment

### `enricher/`

Record enrichment implementations:

| File | Key Exports |
|------|-------------|
| `metadata.py` | `MetadataEnricher` — adds computed metadata fields |
| `passthrough.py` | `PassthroughEnricher` — no-op enricher |
| `entity_enricher.py` | `EntityEnricher` — entity resolution via entity-spine |
| `batch.py` | Batch enrichment coordinator |
| `worker.py` | Enrichment worker (async processing) |
| `job_store.py` | Enrichment job persistence |

---

## Supporting Modules

### `models/`

Domain models and data classes:

| File | Key Exports |
|------|-------------|
| `base.py` | `Layer` enum (BRONZE, SILVER, GOLD) |
| `record.py` | `Record`, `RecordCandidate` |
| `sighting.py` | `Sighting` |
| `content.py` | Content models |
| `feed_run.py` | `FeedRun` |
| `run_event.py` | `RunEvent` |
| `observation.py` | `Observation` |
| `fetch_context.py` | `FetchContext` |
| `enrichment_batch.py` | `EnrichmentBatch` |
| `query.py` | Query parameter models |
| `converter.py` | Model conversion utilities |

### `blob/`

Binary content storage:

| File | Key Exports |
|------|-------------|
| `filesystem.py` | `FilesystemBlob` — local disk storage |

### `cache/`

Caching backends:

| File | Key Exports |
|------|-------------|
| `memory.py` | `MemoryCache` — in-memory LRU cache |
| `redis.py` | Redis-backed cache |

### `search/`

Search backends:

| File | Key Exports |
|------|-------------|
| `memory.py` | `MemorySearch` — in-memory search for testing |
| `elasticsearch.py` | `ElasticsearchSearch` — full-text search via Elasticsearch |

### `http/`

HTTP client with rate limiting:

| File | Key Exports |
|------|-------------|
| `client.py` | Async HTTP client (httpx-based) |
| `rate_limiter.py` | Request-level rate limiting |
| `host_rate_limiter.py` | Per-host rate limiting |

### `metrics/`

Metrics collection:

| File | Key Exports |
|------|-------------|
| `collector.py` | Metrics collector for pipeline operations |

### `reporter/`

Progress reporting implementations:

| File | Key Exports |
|------|-------------|
| `rich.py` | Rich console reporter (terminal UI) |
| `simple.py` | Simple text reporter |

### `integration/`

External service integrations:

| File | Key Exports |
|------|-------------|
| `capture_spine.py` | Integration with capture-spine for cross-system ingestion |

### `utils/`

Shared utilities:

| File | Key Exports |
|------|-------------|
| `keys.py` | `generate_content_key()`, `CompositeKeyBuilder`, `URLKeyExtractor`, `AutoKeyGenerator`, `auto_key()` |
| `retry.py` | `RetryConfig`, `RetryResult`, `with_retry()`, `retry()` |
| `transforms.py` | `KeyTransform`, `JsonPath`, `Split`, `RegexExtract`, `DatePart`, `Concat`, `Lower`, `Strip`, `Chain` |
| `versioning.py` | `VersionedRecord`, `VersionStore`, `MemoryVersionStore`, `diff_versions()` |
| `versioning_pipeline.py` | `PipelineVersion`, `VersionedPipeline` |
| `constraints.py` | `UniqueConstraint` |

### `migrations/`

Alembic database migration scripts:

| File | Purpose |
|------|---------|
| `env.py` | Alembic environment configuration |
| `versions/` | Migration version files |

---

## Directory Tree

```
src/feedspine/
├── __init__.py              # 20 public exports
├── py.typed                 # PEP 561 marker
├── cli.py                   # Typer CLI entry point
│
├── core/                    # App factory + config
├── ops/                     # Business logic (12 modules)
├── pipeline/                # Dedup/processing (8 modules)
├── services/                # Collection orchestration
├── workflows/               # Runtime coordination
│
├── storage/                 # Repository pattern
│   ├── backends/            # sqlite, postgres, duckdb
│   ├── observations/        # Version tracking
│   └── shared/              # Converters, query builders, validators
│       └── mixins/          # fetch_context, records, run_log
│
├── protocols/               # 11 protocol modules
├── models/                  # 11 domain model modules
│
├── api/                     # FastAPI application
│   └── routes/              # 16 route modules
│
├── cli_modules/             # 14 CLI command modules
│
├── transports/              # Transport layer
│   └── mcp/                 # MCP server (13 tools)
│
├── adapter/                 # 7 feed adapters
├── enricher/                # 6 enrichment modules
├── blob/                    # Filesystem blob storage
├── cache/                   # Memory + Redis cache
├── search/                  # Memory + Elasticsearch search
├── http/                    # HTTP client + rate limiting
├── metrics/                 # Metrics collection
├── reporter/                # Rich + simple reporters
├── integration/             # capture-spine integration
├── utils/                   # Keys, retry, transforms, versioning
└── migrations/              # Alembic migrations
```
