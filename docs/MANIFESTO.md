---
title: "Manifesto"
type: specification
status: active
tags: [feed-spine, pipeline, architecture]
created: 2026-02-22
updated: 2026-04-12
---
# FeedSpine Manifesto

**Storage-Agnostic Feed Capture Framework**

*Version: 0.3*  
*Updated: April 2026*

---

## The Problem

Data collection pipelines are deceptively complex:

```python
# Seems simple...
response = requests.get(feed_url)
records = parse(response)
db.insert(records)

# But then you need:
# - Deduplication (same record from multiple feeds)
# - Sighting history (when did we first see this?)
# - Error handling (retry logic, rate limiting)
# - Storage flexibility (swap databases without rewriting)
# - Quality tiers (raw vs. cleaned vs. enriched)
```

Traditional solutions:
- **ETL frameworks** - Too heavy, vendor lock-in
- **Task queues** - Just execution, not the data model
- **Custom pipelines** - Reinventing wheels, tech debt

---

## The Solution: FeedSpine

FeedSpine provides the **data backbone** for feed collection:

```
Feed → Adapter → Record → Storage
         ↓
    Deduplication
    Sighting History
    Quality Tiers
```

### Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FEEDSPINE PIPELINE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │   Feed   │───→│ Adapter  │───→│  Record  │              │
│   │  Source  │    │ (parse)  │    │  Model   │              │
│   └──────────┘    └──────────┘    └────┬─────┘              │
│                                        │                     │
│                                        ▼                     │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    DEDUPLICATION                     │   │
│   │   natural_key = hash(source, type, content_id)      │   │
│   │   if exists: add_sighting() else: insert()          │   │
│   └─────────────────────────────────────────────────────┘   │
│                                        │                     │
│                                        ▼                     │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                  QUALITY TIERS                       │   │
│   │   Bronze (raw) → Silver (cleaned) → Gold (enriched) │   │
│   └─────────────────────────────────────────────────────┘   │
│                                        │                     │
│                                        ▼                     │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │  Memory  │    │  SQLite  │    │  DuckDB  │              │
│   │  Store   │    │  Store   │    │  Store   │              │
│   └──────────┘    └──────────┘    └──────────┘              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Principles

### 1. Storage Agnostic

Same code, different backends:

```python
# Development
spine = create_feed_spine(MemoryStorage())

# Local persistence
spine = create_feed_spine(SQLiteStorage("feeds.db"))

# Analytics at scale
spine = create_feed_spine(DuckDBStorage("feeds.duckdb"))

# Production
spine = create_feed_spine(PostgresStorage(connection_string))
```

**Why?** Start simple, scale when needed. No code rewrites.

### 2. Natural Key Deduplication

Records are identified by their **natural key**, not database IDs:

```python
# This record appears in 3 feeds:
# - SEC RSS (5-minute delay)
# - SEC Daily Index (next day)
# - SEC Quarterly Index (quarterly)

natural_key = hash(
    source="sec_edgar",
    record_type="filing",
    content_id="0000320193-24-000081"  # Accession number
)

# FeedSpine stores it ONCE, tracks ALL sightings
```

### 3. Sighting History

Every record knows its history:

```python
record = storage.get(natural_key)

record.first_sighted_at  # 2024-01-15 14:32:00
record.last_sighted_at   # 2024-01-16 08:00:00
record.sighting_count    # 3
record.sighting_sources  # ["sec_rss", "sec_daily", "sec_full"]
```

**Why?** "When did we first see this?" is a common question.

### 4. Quality Tiers (Medallion Architecture)

Data moves through quality levels:

```
BRONZE → SILVER → GOLD
(raw)    (clean)   (enriched)

┌─────────────────────────────────────────────────────┐
│ BRONZE (Raw)                                        │
│ - Original data as received                         │
│ - No transformations                                │
│ - Full provenance                                   │
└───────────────────────────┬─────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────┐
│ SILVER (Cleaned)                                    │
│ - Standardized schemas                              │
│ - Validated data types                              │
│ - Deduplication applied                             │
└───────────────────────────┬─────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────┐
│ GOLD (Enriched)                                     │
│ - Business logic applied                            │
│ - Aggregations computed                             │
│ - Ready for analysis                                │
└─────────────────────────────────────────────────────┘
```

### 5. Protocol-Based Design

All components are defined by protocols (interfaces):

```python
from typing import Protocol

class StorageProtocol(Protocol):
    """Any storage backend must implement this."""
    
    async def save(self, record: Record) -> None: ...
    async def get(self, key: str) -> Record | None: ...
    async def exists(self, key: str) -> bool: ...
    async def add_sighting(self, key: str, source: str) -> None: ...

# Implement your own backend:
class MyCustomStorage(StorageProtocol):
    ...
```

---

## What We're NOT Building

1. **A general ETL framework** - We do one thing: feed capture
2. **A task scheduler** - Use Celery, Airflow, or cron
3. **A data warehouse** - We capture; you analyze elsewhere
4. **A web scraper** - We consume structured feeds, not HTML

---

## Use Cases

### SEC EDGAR Data Collection
```python
spine.register_feed(SECRSSAdapter())      # 5-min filings
spine.register_feed(SECDailyAdapter())    # Daily index
spine.register_feed(SECFullAdapter())     # Full quarterly
```

### News Aggregation
```python
spine.register_feed(RSSFeedAdapter(url="https://news.ycombinator.com/rss"))
spine.register_feed(RSSFeedAdapter(url="https://feeds.arstechnica.com/arstechnica/technology"))
```

### Market Data Capture
```python
spine.register_feed(PolygonAdapter(api_key=KEY))
spine.register_feed(AlphaVantageAdapter(api_key=KEY))
```

---

## Success Metrics

1. **Zero data loss** - Every record captured
2. **Zero duplicates** - Natural key deduplication works
3. **Full provenance** - Know when and where every record came from
4. **< 100ms latency** - Fast pipeline execution
5. **Swap backends in < 5 minutes** - True storage agnosticism

---

## Getting Started

```python
import asyncio
from feedspine import create_feed_spine, MemoryStorage, RSSFeedAdapter

async def main():
    storage = MemoryStorage()
    app = create_feed_spine(storage)

    app.register_feed(RSSFeedAdapter(
        name="hn",
        url="https://news.ycombinator.com/rss"
    ))

    result = await app.collect()
    print(f"Captured {result.total_new} new records")

asyncio.run(main())
```

---

*FeedSpine: The backbone for your feed collection pipelines.*
