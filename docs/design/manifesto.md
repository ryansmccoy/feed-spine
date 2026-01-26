# FeedSpine Manifesto

**A Generic Feed/Content Capture Framework**

*Version: 0.1 Draft*
*Date: January 2026*

---

## The Problem

You want to:
1. Ingest feeds from **multiple sources** (SEC, press releases, news APIs, regulatory filings)
2. **Deduplicate** across sources (same filing appears in RSS AND full-index)
3. **Capture content** (download and store full documents)
4. **Query** by time, entity, type with both "newest published" and "newest captured" views
5. **Enrich** with NLP/LLM analysis (entities, tags, summaries)
6. Track **complete lineage** from discovery through enrichment

Existing solutions are either:
- Too heavy (PostgreSQL server, Docker, complex setup)
- Too simple (no deduplication, no lineage, no multi-source)
- Domain-locked (SEC only, no generic feed support)

---

## The Solution: FeedSpine

A **bare-bones, scalable** Python package that:

```bash
pip install feedspine
feedspine init
feedspine collect --feed sec_rss
feedspine list --limit 10
```

Or scale up with workers:
```bash
feedspine worker --stage fetch --workers 4
feedspine worker --stage parse --workers 2
```

Or go distributed:
```bash
docker-compose up  # Redis queue + multiple workers
```

---

## Core Principles

### 1. Medallion Architecture (Bronze → Silver → Gold)

```
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│      BRONZE         │   │       SILVER        │   │        GOLD         │
│   (Raw/Untouched)   │──▶│   (Normalized)      │──▶│    (Enriched)       │
├─────────────────────┤   ├─────────────────────┤   ├─────────────────────┤
│ Exactly as received │   │ Common schema       │   │ NLP/LLM analysis    │
│ No transformations  │   │ Deduplicated        │   │ Entities extracted  │
│ Full provenance     │   │ Cross-source joins  │   │ Tags applied        │
│ Never modified      │   │ Business keys set   │   │ Summaries generated │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
```

**Bronze**: Raw feed items, never modified. Complete audit trail.
**Silver**: Normalized records with common schema. Deduplicated by natural key.
**Gold**: Enriched with analysis. Entities, tags, summaries.

### 2. Multi-Feed Deduplication

The same SEC filing appears in **4 different feeds**:
- `sec.rss` (real-time, ~5 min)
- `sec.daily_index` (daily crawler.idx)
- `sec.full_index` (quarterly master.idx)
- `sec.monthly_xbrl` (monthly archives)

**Solution**: Normalizer-defined `dedup_key` - each domain knows its natural key

```python
class Normalizer(Protocol):
    """Transform bronze items to silver records."""
    
    @property
    def domain(self) -> str:
        """Domain prefix (e.g., 'sec', 'press', 'news')."""
        ...
    
    def compute_dedup_key(self, item: BronzeItem) -> str:
        """Primary deduplication key. Unique within domain."""
        ...
    
    def compute_content_hash(self, item: BronzeItem) -> str | None:
        """Optional fingerprint for cross-source dedup."""
        return None
```

| Domain | Natural Key | Example | Globally Unique? |
|--------|-------------|---------|------------------|
| SEC EDGAR | Accession number | `0000320193-24-000081` | ✅ Yes |
| UK Companies House | Filing ref | `MzM1OTI5MzM1OWFkaXF6` | ✅ Yes |
| Press Release | Source + ID | `globenewswire:9876543` | ✅ Per-source |
| News Article | URL hash | `a1b2c3d4e5f6` | ✅ Yes |
| Patent | Patent number | `US-11234567-B2` | ✅ Yes |

### 3. Two Timestamps (Published vs Captured)

Every record has:
- `published_at`: When the **source** published it (filing date)
- `captured_at`: When **we** first saw it

This enables:
- "Show me the newest filings by filing date" → `ORDER BY published_at DESC`
- "Show me what was just captured" → `ORDER BY captured_at DESC`

### 4. Unified API + CLI

Same operations, same service layer, different interfaces:

```python
# CLI
feedspine list --limit 10 --type sec.10_k --entity 0000320193

# API
GET /api/v1/records?limit=10&type=sec.10_k&entity=0000320193

# Python SDK
spine.records.list(limit=10, record_type="sec.10_k", entity_id="0000320193")
```

All three use the same service layer under the hood.

### 5. Pluggable Everything

```python
# Configure any combination of backends
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

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FEEDSPINE                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│  INTERFACE      │  CLI (Typer)  │  API (FastAPI)  │  Python SDK               │
├─────────────────────────────────────────────────────────────────────────────────┤
│  SERVICES       │  ReaderService  │  CollectorService  │  EnrichmentService   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PIPELINE       │  Queue (Memory/Redis)  │  Workers (Fetch/Parse/Store/etc.)  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  MEDALLION      │  Bronze (raw)  │  Silver (normalized)  │  Gold (enriched)   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  PROTOCOLS      │  StorageBackend  │  SearchBackend  │  Executor  │  ...      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  STORAGE        │  DuckDB  │  PostgreSQL  │  Redis  │  Filesystem  │  S3      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Modes

### 1. Single Process (Development / Personal Use)

```bash
pip install feedspine
feedspine init
feedspine worker --all  # All stages in one process
```

- DuckDB file database
- All workers in single process
- Good for: personal use, development, <10k records/day

### 2. Multi-Process (Medium Scale)

```bash
# Terminal 1: Fetch workers
feedspine worker --stage fetch --workers 4

# Terminal 2: Parse + Store
feedspine worker --stage parse --workers 2
feedspine worker --stage store --workers 1
```

- DuckDB with WAL mode (concurrent access)
- Multiple worker processes
- Good for: small team, <100k records/day

### 3. Distributed (Large Scale)

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    
  api:
    image: feedspine:latest
    command: feedspine api run
    
  fetch-worker:
    image: feedspine:latest
    command: feedspine worker --stage fetch
    deploy:
      replicas: 4
```

- Redis queue for distribution
- PostgreSQL or cloud storage
- Good for: production, >100k records/day

---

## What We're NOT Building

- **Multi-tenant**: Single user/organization focus
- **Real-time streaming**: Poll-based, not websocket
- **Complex UI**: CLI + API, no web dashboard (yet)
- **ML training**: Capture and enrich, not train models
- **Data warehouse**: DuckDB for OLAP queries, not big data

---

## TL;DR

FeedSpine is a **generic feed capture framework** that:

- Ingests **any feed** (RSS, API, index files)
- Uses **medallion architecture** (Bronze → Silver → Gold)
- **Deduplicates** across multiple sources
- Tracks **published_at** (source time) AND **captured_at** (capture time)
- Stores in **DuckDB** (embedded, portable) or **PostgreSQL** (production)
- Scales from **single process** to **distributed workers**
- Has **unified API + CLI** (same service layer)
- Is **extensible** via protocol-based backends

Domain packages (py-sec-edgar, py-press-releases) add domain-specific feed adapters and parsers.
