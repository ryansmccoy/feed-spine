---
title: "FeedSpine README"
type: readme
status: active
tags: [feed-spine, pipeline, data-model, deduplication, medallion]
created: 2025-01-15
updated: 2026-04-12
---

<div align="center">

# feedspine

**Storage-agnostic feed capture with automatic deduplication, sighting history, and medallion architecture.**

[![Version](https://img.shields.io/badge/version-0.3.0-blue?style=flat-square)]()
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)]()
[![Tests](https://img.shields.io/badge/tests-1217%20passing-brightgreen?style=flat-square)]()
[![Ruff](https://img.shields.io/badge/linting-ruff-261230?style=flat-square)]()

[Quick Start](#quick-start) · [Architecture](#architecture) · [Adapters](#built-in-feed-adapters) · [Storage](#storage-backends) · [API](#rest-api--cli--mcp) · [Examples](#examples)

</div>

---

## What Is FeedSpine?

FeedSpine was built to solve a real problem: [py-sec-edgar](https://github.com/ryansmccoy/py-sec-edgar) needs to collect SEC filings from **four different feeds** — a real-time RSS feed, daily index files, monthly XBRL archives, and quarterly bulk indexes — each with a completely different format, but all representing the same filings identified by accession number.

Rather than writing bespoke dedup logic for each feed, FeedSpine provides a **unified collection framework** where every adapter yields `RecordCandidate` objects with a `natural_key`. The pipeline handles dedup, versioning, and sighting history automatically — regardless of whether the data came from RSS, a JSON API, a CSV file, or a custom SEC parser.

```python
# py-sec-edgar registers 4 different SEC feed formats into one FeedSpine app
# Each feed has a different format, but all deduplicate on accession number
app.register_feed(SecRssFeedAdapter(form_types=["10-K", "10-Q"]))       # Real-time Atom/RSS
app.register_feed(SecDailyIndexAdapter(start_date=date(2024, 1, 1)))    # Pipe-delimited index
app.register_feed(SecMonthlyXBRLAdapter(months_back=3))                 # XML/XBRL archive
app.register_feed(SecQuarterlyIndexAdapter(year=2024, quarter=1))       # Bulk CSV index

# Collect from all feeds — duplicates across feeds are detected automatically
for feed in app.feeds:
    outcome = await app.collection_service.run_collection(feed)
    # Same filing from RSS + daily index + monthly XBRL = 1 record, 3 sightings
```

Every record is identified by a normalized natural key and a SHA-256 content hash. Collect the same feed a thousand times — each item is stored exactly once, with a full sighting history of when and where it was seen.

### When to use it

| Use case | FeedSpine? |
|----------|:----------:|
| Collect from multiple feeds with different formats into one unified store | ✅ |
| Automatic cross-feed deduplication via natural keys | ✅ |
| Promote records through quality layers (Bronze → Silver → Gold) | ✅ |
| Track sighting history — "when did each source last see this item?" | ✅ |
| Swap storage (Memory ↔ SQLite ↔ DuckDB ↔ Postgres) without code changes | ✅ |
| Enrich records with entity resolution, metadata, or custom logic | ✅ |
| Full web scraping or browser automation | ❌ |

---

## Quick Start

### Install

```bash
uv add feedspine                      # Core
uv add "feedspine[duckdb]"            # + DuckDB analytical storage
uv add "feedspine[api]"               # + FastAPI REST server
uv add "feedspine[elasticsearch]"     # + Elasticsearch search
uv add "feedspine[entity]"            # + Entity resolution
uv add "feedspine[all]"               # Everything
```

### Collect and deduplicate in 10 lines

```python
import asyncio
from feedspine import create_feed_spine, MemoryStorage, RSSFeedAdapter

async def main():
    storage = MemoryStorage()
    app = create_feed_spine(storage)
    app.register_feed(RSSFeedAdapter(name="news", url="https://news.ycombinator.com/rss"))

    # First run — all items are new
    outcome = await app.collection_service.run_collection("news")
    print(f"New: {outcome.stats.new}, Duplicates: {outcome.stats.duplicates}")

    # Second run — duplicates detected automatically
    outcome = await app.collection_service.run_collection("news")
    print(f"New: {outcome.stats.new}, Duplicates: {outcome.stats.duplicates}")

asyncio.run(main())
```

### Or from the CLI

```bash
uv run feedspine collect run --feed news
uv run feedspine feeds list-types        # Show available adapters
uv run feedspine health summary          # Feed health (RAG status)
```

---

## Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │              PRESENTATION LAYER              │
                    │  CLI (Typer) · REST API (FastAPI) · MCP      │
                    │  Thin wrappers — delegate to Ops layer       │
                    └──────────────────┬───────────────────────────┘
                                       │
                    ┌──────────────────▼───────────────────────────┐
                    │                OPS LAYER                     │
                    │  OperationContext → OperationResult[T]       │
                    │  query · feed · enrich · schedules · runs    │
                    │  Pure business logic — no transport imports  │
                    └──────────────────┬───────────────────────────┘
                                       │
                    ┌──────────────────▼───────────────────────────┐
                    │             PIPELINE LAYER                   │
                    │  RecordCandidate → dedup → Record + Sighting │
                    │  stages · runner · stats · dedup             │
                    └──────────────────┬───────────────────────────┘
                                       │
┌───────────┐       ┌──────────────────▼───────────────────────────┐
│  Sources   │──────▶│            STORAGE LAYER                    │
│ RSS · JSON │       │  Protocols: StorageBackend, SearchBackend   │
│ CSV · File │       │  Repository pattern + dialect abstraction   │
│ SEC EDGAR  │       ├─────────┬──────────┬──────────┬─────────────┤
│ Polygon.io │       │ Memory  │  SQLite  │  DuckDB  │  PostgreSQL │
└───────────┘       └─────────┴──────────┴──────────┴─────────────┘
```

### Core data flow

1. **FeedAdapter** fetches raw data from a source and yields `RecordCandidate` objects
2. **Pipeline** deduplicates each candidate (natural key + content hash), creating or updating a `Record`
3. **Sighting** is logged for every observation — full audit trail of when and where each item was seen
4. **Enricher** can promote records through medallion layers and add metadata
5. **StorageBackend** persists everything — swap backends without changing pipeline code

### Key primitives

| Primitive | Purpose |
|-----------|---------|
| `RecordCandidate` | Raw input from an adapter. Content hash computed automatically (SHA-256). |
| `Record` | Stored item with `natural_key`, `content_hash`, `layer`, version tracking, timestamps. |
| `Sighting` | Observation audit trail — every time a record is seen, from any source. |
| `Layer` | Quality tier: `BRONZE` (raw) → `SILVER` (validated) → `GOLD` (enriched). |
| `Pipeline` | Core processing engine: candidate → dedup → record + sighting. |
| `FeedSpineApp` | Application object created by `create_feed_spine()` — holds storage, services, feeds. |
| `CollectionOutcome` | Result of a collection run with stats (processed, new, duplicates, errors). |
| `OperationContext` | Context for ops-layer functions: storage, search, request_id, caller, dry_run. |
| `OperationResult[T]` | Typed success/failure envelope returned by all ops functions. |

---

## Built-in Feed Adapters

| Adapter | Source | Natural Key |
|---------|--------|-------------|
| `RSSFeedAdapter` | RSS 2.0 and Atom feeds | Entry GUID or link |
| `JSONFeedAdapter` | JSON API endpoints with dot-notation path mapping | Configurable field |
| `CSVFeedAdapter` | Local or HTTP CSV/TSV with composite key support | Configurable column(s) |
| `FileFeedAdapter` | File-based feeds with content hash change detection | File path |
| `SECEdgarFilingAdapter` | SEC EDGAR filing submissions API | Accession number |
| `PolygonEarningsAdapter` | Polygon.io earnings calendar | Ticker + fiscal period |

All adapters implement the `FeedAdapter` protocol — a `@runtime_checkable` interface with `fetch()`, `initialize()`, and `close()` methods. Write your own adapter in ~30 lines.

---

## Storage Backends

| Backend | Best For | Install |
|---------|----------|---------|
| `MemoryStorage` | Testing, development, prototyping | Included |
| `SQLiteStorage` | Single-user, local dev, small-to-medium datasets | `feedspine[sqlalchemy]` |
| `DuckDBStorage` | Analytical queries, time-series, Parquet export | `feedspine[duckdb]` |
| `PostgresStorage` | Multi-user production, large datasets, concurrent access | `feedspine[postgres]` |

All backends implement the `StorageBackend` protocol — CRUD, batch operations, natural-key lookup for dedup, sighting tracking, and query with filtering/pagination.

```python
# Swap storage in one line — pipeline code stays the same
from feedspine.storage.backends.duckdb import DuckDBStorage

storage = DuckDBStorage("feeds.duckdb")
app = create_feed_spine(storage)
```

---

## Enrichment

Enrichers transform records and promote them through medallion layers:

| Enricher | Purpose | Install |
|----------|---------|---------|
| `PassthroughEnricher` | Layer promotion without data changes | Included |
| `MetadataEnricher` | Add custom fields to record metadata | Included |
| `EntityEnricher` | Entity resolution (CIK/ticker/name lookup) | `feedspine[entity]` |

Enrichment is orchestrated through `FeedEnrichmentWorker` with batch support.

---

## Protocols

FeedSpine defines `@runtime_checkable` protocols for every extension point:

| Protocol | Module | Purpose |
|----------|--------|---------|
| `StorageBackend` | `protocols.storage` | Record persistence (CRUD, query, batch, sightings) |
| `RecordStore` | `protocols.storage` | Record-specific storage operations |
| `SightingStore` | `protocols.storage` | Sighting tracking and queries |
| `StorageLifecycle` | `protocols.storage` | `initialize()` + `close()` lifecycle |
| `FeedAdapter` | `protocols.feed` | Feed source (fetch, initialize, close) |
| `Enricher` | `protocols.enricher` | Single-record enrichment |
| `BatchEnricher` | `protocols.enricher` | Batch enrichment |
| `SearchBackend` | `protocols.search` | Full-text search (index, search, delete) |
| `RunLogStore` | `protocols.run_log` | Pipeline run event logging |
| `FetchContextStore` | `protocols.fetch_context` | HTTP ETag/Last-Modified conditional fetching state |
| `BlobStorage` | `protocols.blob` | Binary file storage |
| `Cache` | `protocols.cache` | Async get/set/delete with TTL |
| `ProgressReporter` | `protocols.progress` | Operation monitoring with ETA |
| `MessageQueue` | `protocols.queue` | Pub/sub messaging |
| `CollectionStrategy` | `protocols.strategy` | Multi-source optimization |

Implement any protocol to extend FeedSpine — no subclassing, no registration boilerplate.

---

## REST API / CLI / MCP

FeedSpine ships with three transport layers. All delegate to the same `ops/` business logic.

### FastAPI REST API

```bash
uv run feedspine api serve --port 11300
# → OpenAPI docs at http://localhost:11300/docs
```

15 route modules: records, feeds, sightings, search, enrichment, health, metrics, stats, timeline, export, schedules, syndication (RSS/OPML), observations, runs, storage, and collection.

### Typer CLI

```bash
uv run feedspine collect run --feed sec-filings     # Collect from a feed
uv run feedspine feeds list-types                   # List available adapters
uv run feedspine feeds list                         # List configured feeds
uv run feedspine health summary                     # Feed health (RAG: Red/Amber/Green)
uv run feedspine stats summary                      # Record counts, layer distribution
uv run feedspine query records --limit 10           # Query stored records
uv run feedspine export json output.json            # Export to JSON/CSV/Parquet
uv run feedspine info                               # System info
```

### MCP Server (Model Context Protocol)

13 tools for LLM integration — feed collection, enrichment, timeline queries, search, health, and storage stats:

```bash
uv run feedspine-mcp                                # Start MCP server (stdio)
```

---

## Search

| Backend | Features | Install |
|---------|----------|---------|
| `MemorySearch` | Keyword search (linear scan, dev/testing) | Included |
| `ElasticsearchSearch` | Distributed full-text, relevance scoring, highlighting, aggregations | `feedspine[elasticsearch]` |

Both implement the `SearchBackend` protocol with `index()`, `search()`, `delete()`, `exists()`, and `initialize()`.

---

## Examples

25 runnable examples across 7 categories:

| Category | Examples | Highlights |
|----------|:--------:|------------|
| Getting Started | 2 | Quickstart, multi-feed collection |
| Storage | 2 | DuckDB persistence, data types |
| Domain Feeds | 1 | SEC EDGAR filing monitor |
| Operations | 11 | Tracking, enrichment, scheduling, health, stats, export |
| Earnings | 7 | Calendar API, CLI, REST, WebSocket, full workflow |
| API | 3 | Unified timeline, RSS/Atom syndication, export formats |
| CLI | 1 | CLI command examples |

```bash
uv run python examples/01_getting_started/01_quickstart.py
uv run python examples/run_all.py                          # Run all 25
```

---

## Development

```bash
uv sync --dev                # Install all dependencies
uv run pytest                # 1217 tests
uv run ruff check .          # Lint
uv run ruff format .         # Format
uv run mypy src              # Type check
uv run mkdocs serve          # Local docs site
```

### Project stats

| Metric | Value |
|--------|-------|
| Source files | ~190 |
| Test files | ~96 |
| Source LOC | ~35,000 |
| Tests | 1,217 passed, 23 skipped |

---

## Stability

| Aspect | Status |
|--------|--------|
| **Version** | 0.3.0 |
| **Python** | ≥ 3.12 |
| **API stability** | v0.x — API may change between minor versions |
| **License** | MIT |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
