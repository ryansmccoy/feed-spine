# FeedSpine

**The backbone for your feed collection pipelines.**

[![PyPI version](https://img.shields.io/pypi/v/feedspine.svg)](https://pypi.org/project/feedspine/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/ryansmccoy/feed-spine/actions/workflows/ci.yml/badge.svg)](https://github.com/ryansmccoy/feed-spine/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ryansmccoy/feed-spine/branch/main/graph/badge.svg)](https://codecov.io/gh/ryansmccoy/feed-spine)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://ryansmccoy.github.io/feed-spine/)

---

**FeedSpine** is a storage-agnostic, executor-agnostic feed capture framework for Python. It handles the hard parts of data collection—**deduplication**, **sighting history**, and **data quality tiers**—so you can focus on your domain logic.

## Why FeedSpine?

When collecting data from multiple feeds, you face these challenges:

| Challenge | Traditional Approach | FeedSpine Approach |
|-----------|---------------------|-------------------|
| **Same record in multiple feeds** | Manual dedup, wasted storage | Automatic natural key deduplication |
| **"When did we first see this?"** | Not tracked, lost context | Complete sighting history |
| **Switching databases** | Rewrite everything | Swap backends with zero code changes |
| **Raw vs. clean vs. enriched data** | Ad-hoc, unclear boundaries | Medallion architecture (Bronze → Silver → Gold) |

**Real-world example:** An SEC filing appears in the RSS feed (5 min), daily index (next day), AND quarterly index (quarterly). FeedSpine stores it once, tracks all sightings.

## Quick Start

### Installation

```bash
pip install feedspine
```

### 30-Second Example

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter

async def main():
    # Create storage and spine
    storage = MemoryStorage()
    
    async with FeedSpine(storage=storage) as spine:
        # Register a feed
        spine.register_feed(RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        ))
        
        # Collect with automatic deduplication
        result = await spine.collect()
        
        print(f"✓ Processed: {result.total_processed}")
        print(f"✓ New: {result.total_new}")
        print(f"✓ Duplicates: {result.total_duplicates}")

asyncio.run(main())
```

### With Persistent Storage

```bash
pip install feedspine[duckdb]
```

```python
from feedspine import FeedSpine, DuckDBStorage

storage = DuckDBStorage("feeds.db")

async with FeedSpine(storage=storage) as spine:
    # Your records persist across runs
    # Duplicates are automatically detected
    ...
```

## Features

### 🔌 Protocol-Based Design

Swap any component without code changes:

```python
# Development
spine = FeedSpine(storage=MemoryStorage())

# Production - just change the backend
spine = FeedSpine(storage=DuckDBStorage("prod.db"))
# Or: PostgresStorage, RedisStorage, etc.
```

### 🥉🥈🥇 Medallion Architecture

Data flows through quality tiers:

```python
from feedspine.models import Layer

# Raw data (as received)
record = Record.from_candidate(candidate)  # Bronze

# Cleaned data (validated, normalized)
silver = record.promote(Layer.SILVER, enrichments={"validated": True})

# Enriched data (ML predictions, aggregations)
gold = silver.promote(Layer.GOLD, enrichments={"sentiment": 0.85})
```

### 🔍 Natural Key Deduplication

Each record has a unique business identifier:

```python
candidate = RecordCandidate(
    natural_key="sec-edgar:0001234567-24-000001",  # Your domain's ID
    published_at=datetime.now(UTC),
    content={"form_type": "10-K", "company": "Apple Inc."},
)

# FeedSpine tracks when you first saw it and from which feed
```

### ⏱️ Two Timestamps

Know both publication time AND capture time:

```python
record.published_at  # When the source published it
record.captured_at   # When you first captured it

# "Show me filings published today" vs. "Show me what's new since my last check"
```

### 📡 Built-in Feed Adapters

```python
from feedspine import RSSFeedAdapter, JSONFeedAdapter

# RSS/Atom feeds
rss = RSSFeedAdapter(name="news", url="https://example.com/feed.xml")

# JSON APIs
json_feed = JSONFeedAdapter(
    name="api",
    url="https://api.example.com/items",
    items_path="$.data.items",  # JSONPath to items
)

# Or build your own by implementing FeedAdapter protocol
```

## Installation Options

```bash
# Core only (in-memory storage)
pip install feedspine

# With DuckDB (embedded analytics)
pip install feedspine[duckdb]

# With PostgreSQL
pip install feedspine[postgres]

# With Elasticsearch search
pip install feedspine[elasticsearch]

# With FastAPI for REST endpoints
pip install feedspine[api]

# Everything
pip install feedspine[all]
```

## When to Use FeedSpine

### ✅ FeedSpine is great for:

- **RSS/Atom feed aggregation** with deduplication
- **API polling** with change tracking
- **Multi-source data collection** (same data from different feeds)
- **Regulatory monitoring** (SEC EDGAR, UK Companies House)
- **Alert aggregation** from multiple monitoring tools
- **Research data collection** with audit trails

### ❌ Consider alternatives for:

- **350+ pre-built connectors needed** → [Airbyte](https://airbyte.com/)
- **Complex DAG orchestration** → [Dagster](https://dagster.io/) / [Prefect](https://prefect.io/)
- **Real-time streaming at scale** → [Kafka](https://kafka.apache.org/)
- **Web scraping** → [Scrapy](https://scrapy.org/)

## Documentation

📚 **[Full Documentation](https://ryansmccoy.github.io/feed-spine/)**

- [Getting Started](https://ryansmccoy.github.io/feed-spine/getting-started/quickstart/)
- [Concepts](https://ryansmccoy.github.io/feed-spine/concepts/architecture/)
- [Tutorials](https://ryansmccoy.github.io/feed-spine/tutorials/)
- [How-To Guides](https://ryansmccoy.github.io/feed-spine/how-to/)
- [API Reference](https://ryansmccoy.github.io/feed-spine/reference/)

## Examples

### SEC EDGAR Filing Monitor

```python
from feedspine import FeedSpine, DuckDBStorage, RSSFeedAdapter

class SECFilingFeed(RSSFeedAdapter):
    def __init__(self, form_type: str):
        super().__init__(
            name=f"sec-{form_type.lower()}",
            url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={form_type}&output=atom",
        )
    
    def _create_natural_key(self, entry: dict) -> str:
        return f"sec:{entry['edgar_accessionnumber']}"

async with FeedSpine(storage=DuckDBStorage("sec.db")) as spine:
    spine.register_feed(SECFilingFeed("10-K"))
    spine.register_feed(SECFilingFeed("8-K"))
    spine.register_feed(SECFilingFeed("4"))  # Insider trades
    
    result = await spine.collect()
```

### Multi-Source News Aggregator

```python
feeds = [
    RSSFeedAdapter(name="hn", url="https://news.ycombinator.com/rss"),
    RSSFeedAdapter(name="lobsters", url="https://lobste.rs/rss"),
    RSSFeedAdapter(name="reddit-python", url="https://reddit.com/r/python/.rss"),
]

async with FeedSpine(storage=storage) as spine:
    for feed in feeds:
        spine.register_feed(feed)
    
    # Same article posted to multiple sources = stored once
    result = await spine.collect()
    print(f"Dedup rate: {result.total_duplicates / result.total_processed:.1%}")
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FeedSpine                            │
├─────────────────────────────────────────────────────────────┤
│  Protocols (interfaces)                                     │
│  ├── StorageBackend    ├── SearchBackend                   │
│  ├── CacheBackend      ├── BlobStorage                     │
│  ├── MessageQueue      ├── Notifier                        │
│  ├── Executor          └── FeedAdapter                     │
├─────────────────────────────────────────────────────────────┤
│  Implementations                                            │
│  ├── storage/   (memory, duckdb, postgres, redis)          │
│  ├── search/    (memory, elasticsearch, chroma)            │
│  ├── adapter/   (rss, json, custom)                        │
│  └── ...                                                    │
├─────────────────────────────────────────────────────────────┤
│  Data Flow: Feed → Bronze → Silver → Gold                   │
└─────────────────────────────────────────────────────────────┘
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Clone and setup
git clone https://github.com/ryansmccoy/feed-spine.git
cd feed-spine

# Install with uv (recommended)
uv sync --dev

# Run tests
uv run pytest

# Run lints
uv run ruff check src tests
uv run mypy src
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

FeedSpine was born from building [py-sec-edgar](https://github.com/ryansmccoy/py-sec-edgar), where the challenge of collecting SEC filings from multiple feeds (RSS, daily index, quarterly index) while avoiding duplicates led to this generic framework.

---

<p align="center">
  <strong>FeedSpine: The backbone for your feed collection pipelines.</strong>
</p>
