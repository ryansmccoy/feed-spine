# Migration Guides

## Overview

This document provides step-by-step guides for migrating to FeedSpine from various existing solutions. Each guide includes code comparisons, data migration strategies, and common pitfalls.

---

## Migration 1: From Custom Python Scripts

### Typical Custom Script Pattern

Many teams start with ad-hoc scripts like this:

```python
# OLD: custom_feed_collector.py
import feedparser
import sqlite3
import hashlib
from datetime import datetime

def collect_feeds():
    conn = sqlite3.connect("feeds.db")
    
    feeds = [
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom",
        "https://news.ycombinator.com/rss",
    ]
    
    for feed_url in feeds:
        parsed = feedparser.parse(feed_url)
        
        for entry in parsed.entries:
            # Manual deduplication
            entry_hash = hashlib.md5(entry.link.encode()).hexdigest()
            
            cursor = conn.execute(
                "SELECT 1 FROM entries WHERE hash = ?", (entry_hash,)
            )
            if cursor.fetchone():
                continue  # Skip duplicate
            
            # Manual storage
            conn.execute("""
                INSERT INTO entries (hash, title, link, published, raw_data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                entry_hash,
                entry.get("title", ""),
                entry.link,
                entry.get("published", ""),
                str(entry)
            ))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    collect_feeds()
```

### Problems with Custom Scripts

| Problem | Impact |
|---------|--------|
| No separation of concerns | Hard to test, modify |
| Hardcoded storage | Can't switch databases |
| No data quality layers | Everything is "raw" |
| No sighting tracking | Don't know when first seen |
| Manual deduplication | Prone to bugs |
| No async | Slow for many feeds |
| No error handling | Silent failures |

### Migration to FeedSpine

#### Step 1: Create Feed Adapter

```python
# NEW: adapters/sec_feed.py
from feedspine.adapter.rss import RSSAdapter

sec_adapter = RSSAdapter(
    name="sec-edgar",
    url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom",
    # Optional: customize natural key generation
    natural_key_fn=lambda entry: f"sec-{entry.link.split('/')[-1]}"
)

hn_adapter = RSSAdapter(
    name="hacker-news",
    url="https://news.ycombinator.com/rss",
)
```

#### Step 2: Set Up FeedSpine

```python
# NEW: collector.py
import asyncio
from feedspine import FeedSpine
from feedspine.storage.sqlite import SQLiteStorage
from adapters.sec_feed import sec_adapter, hn_adapter

async def main():
    async with FeedSpine(
        storage=SQLiteStorage("feedspine.db")
    ) as fs:
        # Register feeds
        fs.register_feed(sec_adapter)
        fs.register_feed(hn_adapter)
        
        # Collect with automatic deduplication
        result = await fs.collect()
        
        print(f"New records: {result.new_count}")
        print(f"Duplicates skipped: {result.duplicate_count}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Step 3: Migrate Existing Data

```python
# migrate_data.py
import sqlite3
import asyncio
from feedspine import FeedSpine
from feedspine.storage.sqlite import SQLiteStorage
from feedspine.models import Record, Layer, Metadata
from datetime import datetime, UTC

async def migrate():
    # Connect to old database
    old_conn = sqlite3.connect("feeds.db")
    old_conn.row_factory = sqlite3.Row
    
    # Connect to new FeedSpine storage
    async with FeedSpine(storage=SQLiteStorage("feedspine.db")) as fs:
        await fs.storage.initialize()
        
        # Read old entries
        cursor = old_conn.execute("SELECT * FROM entries")
        
        for row in cursor:
            # Create FeedSpine record
            record = Record(
                record_id=f"migrated-{row['hash']}",
                natural_key=row['hash'],
                layer=Layer.BRONZE,  # Start in Bronze
                content={
                    "title": row['title'],
                    "link": row['link'],
                    "published": row['published'],
                    "raw": row['raw_data'],
                },
                metadata=Metadata(
                    source="migration",
                    collected_at=datetime.now(UTC),
                ),
                published_at=parse_date(row['published']),
            )
            
            await fs.storage.store(record)
        
        print(f"Migrated {cursor.rowcount} records")

asyncio.run(migrate())
```

### Feature Mapping

| Custom Script | FeedSpine Equivalent |
|---------------|---------------------|
| `feedparser.parse()` | `RSSAdapter` (built-in) |
| `sqlite3.connect()` | `SQLiteStorage` |
| Manual hash dedup | Automatic natural key dedup |
| `INSERT INTO entries` | `storage.store(record)` |
| No quality layers | `Layer.BRONZE/SILVER/GOLD` |
| Cron job | `Prefect` executor or cron |

---

## Migration 2: From feedparser + Storage

### Typical feedparser Pattern

```python
# OLD: rss_monitor.py
import feedparser
import json
from pathlib import Path
from datetime import datetime

class FeedMonitor:
    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.seen_file = self.storage_dir / "seen.json"
        self.seen = self._load_seen()
    
    def _load_seen(self) -> set:
        if self.seen_file.exists():
            return set(json.loads(self.seen_file.read_text()))
        return set()
    
    def _save_seen(self):
        self.seen_file.write_text(json.dumps(list(self.seen)))
    
    def collect(self, feed_url: str) -> list[dict]:
        new_entries = []
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries:
            entry_id = entry.get("id") or entry.link
            
            if entry_id in self.seen:
                continue
            
            self.seen.add(entry_id)
            
            # Store entry
            entry_file = self.storage_dir / f"{hash(entry_id)}.json"
            entry_file.write_text(json.dumps({
                "id": entry_id,
                "title": entry.get("title"),
                "link": entry.link,
                "summary": entry.get("summary"),
                "published": entry.get("published"),
                "collected_at": datetime.now().isoformat(),
            }))
            
            new_entries.append(entry)
        
        self._save_seen()
        return new_entries
```

### Migration to FeedSpine

```python
# NEW: Using FeedSpine with similar simplicity but more features

from feedspine import FeedSpine
from feedspine.storage.memory import MemoryStorage  # Or SQLite, DuckDB, etc.
from feedspine.adapter.rss import RSSAdapter

async def main():
    async with FeedSpine(storage=MemoryStorage()) as fs:
        # Same simplicity, more power
        fs.register_feed(RSSAdapter(
            name="my-feed",
            url="https://example.com/feed.xml"
        ))
        
        result = await fs.collect()
        
        # Get new entries (like before)
        new_entries = [r async for r in fs.storage.query(
            layer=Layer.BRONZE,
            filters={"metadata.source": "my-feed"},
            order_by="-collected_at",
            limit=result.new_count
        )]
```

### Data Migration Script

```python
# migrate_from_feedparser.py
import json
from pathlib import Path
from feedspine import FeedSpine
from feedspine.storage.sqlite import SQLiteStorage
from feedspine.models import Record, Layer, Metadata, Sighting
from datetime import datetime, UTC

async def migrate_feedparser_storage(old_dir: str, new_db: str):
    old_path = Path(old_dir)
    
    async with FeedSpine(storage=SQLiteStorage(new_db)) as fs:
        # Migrate seen entries (sightings)
        seen_file = old_path / "seen.json"
        if seen_file.exists():
            seen_ids = json.loads(seen_file.read_text())
            
            for entry_id in seen_ids:
                # Record as sighting
                sighting = Sighting(
                    natural_key=entry_id,
                    seen_at=datetime.now(UTC),  # Original time unknown
                    source="migration"
                )
                await fs.storage.record_sighting(sighting)
        
        # Migrate stored entries
        for entry_file in old_path.glob("*.json"):
            if entry_file.name == "seen.json":
                continue
            
            data = json.loads(entry_file.read_text())
            
            record = Record(
                record_id=f"migrated-{entry_file.stem}",
                natural_key=data["id"],
                layer=Layer.BRONZE,
                content={
                    "title": data.get("title"),
                    "link": data.get("link"),
                    "summary": data.get("summary"),
                },
                metadata=Metadata(
                    source="migration",
                    collected_at=datetime.fromisoformat(data["collected_at"]),
                ),
                published_at=parse_date(data.get("published")),
            )
            
            await fs.storage.store(record)
        
        print(f"Migration complete!")
```

---

## Migration 3: From Airbyte (Custom Connector)

### When to Migrate from Airbyte

Consider migrating if:
- Your custom Airbyte connector is for feeds/APIs
- You don't need Airbyte's other connectors
- Infrastructure overhead is too high
- You want Python-native development

### Airbyte Source Pattern

```python
# OLD: Airbyte custom source (source_sec_edgar/source.py)
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream

class SECEdgarStream(HttpStream):
    url_base = "https://www.sec.gov/"
    primary_key = "accession_number"
    
    def path(self, **kwargs) -> str:
        return "cgi-bin/browse-edgar"
    
    def request_params(self, **kwargs) -> dict:
        return {
            "action": "getcurrent",
            "output": "atom",
        }
    
    def parse_response(self, response, **kwargs):
        # Parse XML/Atom response
        for entry in parse_atom(response.text):
            yield {
                "accession_number": extract_accession(entry),
                "form_type": entry.get("form_type"),
                "company": entry.get("company"),
                # ...
            }

class SourceSECEdgar(AbstractSource):
    def check_connection(self, logger, config):
        return True, None
    
    def streams(self, config):
        return [SECEdgarStream()]
```

### FeedSpine Equivalent

```python
# NEW: FeedSpine adapter (much simpler)
from feedspine.adapter.base import BaseFeedAdapter
from feedspine.models import RecordCandidate, Metadata
import httpx
from datetime import datetime, UTC

class SECEdgarAdapter(BaseFeedAdapter):
    """SEC EDGAR feed adapter."""
    
    def __init__(self):
        super().__init__(
            name="sec-edgar",
            rate_limit=1.0,  # 1 request per second
        )
        self.url = "https://www.sec.gov/cgi-bin/browse-edgar"
    
    async def _fetch_items(self):
        """Fetch items from SEC EDGAR."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.url,
                params={"action": "getcurrent", "output": "atom"}
            )
            response.raise_for_status()
            
            for entry in parse_atom(response.text):
                yield entry
    
    async def _to_candidate(self, item: dict) -> RecordCandidate:
        """Convert to RecordCandidate."""
        accession = extract_accession(item)
        
        return RecordCandidate(
            natural_key=f"sec-{accession}",
            content={
                "accession_number": accession,
                "form_type": item.get("form_type"),
                "company": item.get("company"),
                # ... same fields as Airbyte
            },
            metadata=Metadata(source=self.name),
            published_at=parse_date(item.get("published")),
        )

# Usage - no Docker, no Airbyte infrastructure
async with FeedSpine() as fs:
    fs.register_feed(SECEdgarAdapter())
    await fs.collect()
```

### Migration Checklist

- [ ] Identify Airbyte connector logic
- [ ] Create FeedSpine adapter with same parsing
- [ ] Map Airbyte schema to FeedSpine Record
- [ ] Export existing Airbyte data (if needed)
- [ ] Import into FeedSpine storage
- [ ] Update orchestration (Airbyte → Prefect/cron)
- [ ] Decommission Airbyte infrastructure

---

## Migration 4: From Scrapy

### When to Migrate from Scrapy

Migrate if:
- You're scraping structured feeds (not HTML)
- Scrapy's complexity is overkill
- You need data quality layers
- You want simpler storage abstraction

Keep Scrapy if:
- Complex web crawling requirements
- JavaScript rendering needed
- Heavy anti-bot handling

### Scrapy Spider Pattern

```python
# OLD: Scrapy spider (spiders/sec_spider.py)
import scrapy

class SECSpider(scrapy.Spider):
    name = "sec_edgar"
    start_urls = ["https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"]
    
    def parse(self, response):
        for entry in response.xpath("//entry"):
            yield {
                "title": entry.xpath("title/text()").get(),
                "link": entry.xpath("link/@href").get(),
                "published": entry.xpath("published/text()").get(),
            }
```

```python
# OLD: Scrapy pipeline (pipelines.py)
import sqlite3

class SQLitePipeline:
    def open_spider(self, spider):
        self.conn = sqlite3.connect("scrapy.db")
    
    def process_item(self, item, spider):
        self.conn.execute(
            "INSERT OR IGNORE INTO items (title, link, published) VALUES (?, ?, ?)",
            (item["title"], item["link"], item["published"])
        )
        self.conn.commit()
        return item
```

### FeedSpine Equivalent

```python
# NEW: FeedSpine adapter
from feedspine.adapter.rss import RSSAdapter
from feedspine import FeedSpine
from feedspine.storage.sqlite import SQLiteStorage

# Much simpler for RSS/Atom feeds
adapter = RSSAdapter(
    name="sec-edgar",
    url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"
)

async def main():
    async with FeedSpine(storage=SQLiteStorage("feedspine.db")) as fs:
        fs.register_feed(adapter)
        await fs.collect()
```

### Hybrid: Use Scrapy WITH FeedSpine

For complex scraping, use Scrapy for crawling and FeedSpine for storage:

```python
# scrapy_to_feedspine.py
import scrapy
from feedspine import FeedSpine
from feedspine.models import RecordCandidate
import asyncio

class FeedSpinePipeline:
    """Scrapy pipeline that stores to FeedSpine."""
    
    def open_spider(self, spider):
        self.candidates = []
    
    def process_item(self, item, spider):
        candidate = RecordCandidate(
            natural_key=item["link"],
            content=dict(item),
            metadata={"source": spider.name}
        )
        self.candidates.append(candidate)
        return item
    
    def close_spider(self, spider):
        asyncio.run(self._store_all())
    
    async def _store_all(self):
        async with FeedSpine() as fs:
            for candidate in self.candidates:
                # FeedSpine handles dedup, quality layers
                await fs.ingest(candidate)
```

---

## Migration 5: From dlt

### When to Migrate from dlt

Migrate if:
- You need medallion architecture
- Sighting tracking is important
- You prefer protocol-based design
- RSS/feed sources are primary

Keep dlt if:
- Schema inference is valuable
- Normalizing nested data automatically
- dlt's ecosystem fits better

### dlt Pattern

```python
# OLD: dlt source
import dlt

@dlt.source
def sec_edgar():
    return dlt.resource(
        fetch_sec_filings(),
        name="filings",
        primary_key="accession_number"
    )

def fetch_sec_filings():
    # Fetch and yield items
    for filing in get_filings():
        yield filing

# Run pipeline
pipeline = dlt.pipeline(
    pipeline_name="sec_edgar",
    destination="duckdb",
    dataset_name="sec"
)
pipeline.run(sec_edgar())
```

### FeedSpine Equivalent

```python
# NEW: FeedSpine approach
from feedspine import FeedSpine
from feedspine.storage.duckdb import DuckDBStorage

async def main():
    async with FeedSpine(storage=DuckDBStorage("sec.duckdb")) as fs:
        fs.register_feed(SECEdgarAdapter())
        
        # Collect to Bronze
        result = await fs.collect()
        
        # Promote to Silver after validation
        async for record in fs.storage.query(layer=Layer.BRONZE):
            if validate(record):
                silver = record.promote(Layer.SILVER)
                await fs.storage.store(silver)
```

### Key Differences

| Aspect | dlt | FeedSpine |
|--------|-----|-----------|
| Schema | Inferred automatically | Explicit Pydantic |
| Quality layers | None | Bronze/Silver/Gold |
| Deduplication | Primary key merge | Natural key + sightings |
| Storage | Destinations | Protocol-based backends |
| API style | Decorators | Classes/protocols |

---

## Common Migration Pitfalls

### Pitfall 1: Forgetting to Migrate History

**Problem:** Only migrating current data, losing historical sightings.

**Solution:**
```python
# Migrate sighting history too
for old_record in old_data:
    # Create sighting for when we first saw it
    sighting = Sighting(
        natural_key=old_record["id"],
        seen_at=old_record["first_seen"],  # Preserve original timestamp
        source="migration"
    )
    await fs.storage.record_sighting(sighting)
```

### Pitfall 2: Natural Key Mismatch

**Problem:** Old system used different IDs than FeedSpine natural keys.

**Solution:**
```python
# Create mapping during migration
key_mapping = {}

for old_record in old_data:
    old_id = old_record["id"]
    new_natural_key = generate_natural_key(old_record)  # FeedSpine style
    
    key_mapping[old_id] = new_natural_key
    
    # Store with new key
    record = Record(natural_key=new_natural_key, ...)
    await fs.storage.store(record)

# Save mapping for reference
json.dump(key_mapping, open("key_mapping.json", "w"))
```

### Pitfall 3: Losing Metadata

**Problem:** Old system had metadata that doesn't map cleanly.

**Solution:**
```python
# Preserve all metadata in content or custom fields
record = Record(
    content={
        **old_record["data"],
        "_migration": {
            "old_id": old_record["id"],
            "old_created": old_record["created_at"],
            "migrated_at": datetime.now(UTC).isoformat(),
        }
    }
)
```

### Pitfall 4: Running Both Systems

**Problem:** Duplicate collection during migration.

**Solution:**
```python
# Phase 1: Run both, FeedSpine dedupes
# Phase 2: Stop old system
# Phase 3: Verify FeedSpine catches everything
# Phase 4: Decommission old system

# During overlap, FeedSpine's natural key dedup handles duplicates
```

---

## Migration Checklist Template

```markdown
## Migration Checklist: [Source System] → FeedSpine

### Pre-Migration
- [ ] Document current data sources
- [ ] Map current schema to FeedSpine models
- [ ] Identify natural keys
- [ ] Plan storage backend (SQLite, PostgreSQL, DuckDB)
- [ ] Estimate data volume

### Migration
- [ ] Create FeedSpine adapters for each source
- [ ] Write migration script for historical data
- [ ] Test migration on sample data
- [ ] Run full migration
- [ ] Verify record counts match

### Post-Migration
- [ ] Run both systems in parallel (1 week)
- [ ] Compare outputs daily
- [ ] Switch orchestration to FeedSpine
- [ ] Decommission old system
- [ ] Update documentation

### Rollback Plan
- [ ] Keep old system data for 30 days
- [ ] Document rollback procedure
- [ ] Test rollback process
```

---

## Summary

| From | To | Difficulty | Time Estimate |
|------|-----|------------|---------------|
| Custom scripts | FeedSpine | Easy | 1-2 days |
| feedparser + files | FeedSpine | Easy | 1 day |
| Airbyte (custom) | FeedSpine | Medium | 1 week |
| Scrapy | FeedSpine | Medium | 3-5 days |
| dlt | FeedSpine | Medium | 3-5 days |
| Meltano | FeedSpine | Hard | 1-2 weeks |

FeedSpine migrations are generally straightforward because of its protocol-based design—you're essentially replacing components rather than rewriting everything.
