---
title: "Quickstart"
type: guide
status: active
tags: [feed-spine, pipeline, python]
created: 2026-02-22
updated: 2026-04-12
---
# Quick Start

This guide gets you up and running with FeedSpine in 5 minutes.

## Two Paths: CLI or Python SDK

FeedSpine works both as a **CLI tool** (config-driven, no code needed) and as a **Python SDK** (full programmatic control).

### Path A: CLI Quick Start (2 minutes)

```bash
# Install
uv add feedspine

# Generate a starter config file
feedspine collect init

# Edit feeds.yaml — uncomment/add your feed sources, then:
feedspine collect run --config feeds.yaml

# See what was collected
feedspine query records --limit 10

# Search across records
feedspine query search "your search term"

# Export results
feedspine export json output.json
```

Example `feeds.yaml`:

```yaml
storage:
  type: sqlite
  connection: feeds.db

feeds:
  - name: hacker-news
    type: rss
    url: https://news.ycombinator.com/rss

  - name: lobsters
    type: rss
    url: https://lobste.rs/rss
```

Useful management commands:

```bash
# List available adapter types (rss, json, file, csv, sec_edgar, etc.)
feedspine feeds list-types

# Validate your config before running
feedspine feeds validate --config feeds.yaml

# List feeds defined in config
feedspine feeds list --config feeds.yaml

# Start the REST API
feedspine api serve --port 8000
```

**That's it!** For full programmatic control, continue with the Python SDK below.

---

### Path B: Python SDK Quick Start (5 minutes)

## Core Concepts

Before we start, understand these key concepts:

| Concept | Description |
|---------|-------------|
| **Record** | A piece of captured data with metadata |
| **Natural Key** | Unique business identifier (e.g., `SEC-AAPL-10K-2024`) |
| **Layer** | Data quality tier: Bronze → Silver → Gold |
| **Sighting** | A record of when we "saw" a natural key |

## Step 1: Create a Storage Backend

FeedSpine is storage-agnostic. Start with the in-memory backend for testing:

```python
from feedspine import MemoryStorage

storage = MemoryStorage()
```

## Step 2: Create a Record Candidate

When you capture data from a feed, create a `RecordCandidate`:

```python
from feedspine.models.record import RecordCandidate
from feedspine.models.base import Metadata
from datetime import datetime, timezone

candidate = RecordCandidate(
    natural_key="my-unique-key-123",      # Business identifier
    published_at=datetime.now(timezone.utc),  # When the data was published
    content={                              # The actual data
        "title": "Example Record",
        "value": 42,
    },
    metadata=Metadata(source="my-feed"),   # Where it came from
)
```

## Step 3: Promote to a Record

A `RecordCandidate` becomes a `Record` when you assign it an ID:

```python
from feedspine.models.record import Record

record = Record.from_candidate(candidate, record_id="rec-001")
print(record.layer)  # Layer.BRONZE - starts at Bronze
```

## Step 4: Store and Retrieve

```python
# Store the record
await storage.store(record)

# Check if it exists
exists = await storage.exists("rec-001")
print(exists)  # True

# Retrieve by ID
retrieved = await storage.get("rec-001")
print(retrieved.content["title"])  # "Example Record"

# Retrieve by natural key
by_key = await storage.get_by_natural_key("my-unique-key-123")
print(by_key.id)  # "rec-001"
```

## Step 5: Promote Through Layers

As you enrich and validate data, promote it through layers:

```python
from feedspine.models.base import Layer

# Bronze → Silver (clean, validated data)
silver = record.promote(
    target_layer=Layer.SILVER,
    enrichments={"validated": True, "score": 0.95},
)
await storage.store(silver)

# Silver → Gold (fully enriched, ready for consumption)
gold = silver.promote(
    target_layer=Layer.GOLD,
    enrichments={"ml_prediction": "positive"},
)
await storage.store(gold)
```

## Step 6: Query Records

```python
# Count by layer
bronze_count = await storage.count(layer=Layer.BRONZE)
silver_count = await storage.count(layer=Layer.SILVER)

# Query records
async for record in storage.query(layer=Layer.GOLD, limit=10):
    print(f"{record.id}: {record.content}")
```

## Step 7: Track Sightings

Sightings help with deduplication - know if you've seen a key before:

```python
from feedspine.models.sighting import Sighting

sighting = Sighting(
    id="sight-001",
    natural_key="my-unique-key-123",
    source="my-feed",
)

# Returns True if first time, False if seen before
is_new = await storage.record_sighting(sighting)
print(is_new)  # True (first time)

# Try again
another = Sighting(id="sight-002", natural_key="my-unique-key-123", source="my-feed")
is_new = await storage.record_sighting(another)
print(is_new)  # False (already seen)
```

## Complete Example

```python
import asyncio
from datetime import datetime, timezone

from feedspine.storage.memory import MemoryStorage
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.base import Layer, Metadata
from feedspine.models.sighting import Sighting


async def main():
    # Initialize
    storage = MemoryStorage()
    await storage.initialize()
    
    # Simulate feed capture
    feed_items = [
        {"key": "item-1", "title": "First Item", "value": 100},
        {"key": "item-2", "title": "Second Item", "value": 200},
        {"key": "item-1", "title": "First Item (duplicate)", "value": 100},
    ]
    
    for item in feed_items:
        # Check if we've seen this before
        sighting = Sighting(
            id=f"sight-{item['key']}-{datetime.now().timestamp()}",
            natural_key=item["key"],
            source="demo-feed",
        )
        is_new = await storage.record_sighting(sighting)
        
        if not is_new:
            print(f"Skipping duplicate: {item['key']}")
            continue
        
        # Create and store new record
        candidate = RecordCandidate(
            natural_key=item["key"],
            published_at=datetime.now(timezone.utc),
            content=item,
            metadata=Metadata(source="demo-feed"),
        )
        record = Record.from_candidate(candidate, record_id=f"rec-{item['key']}")
        await storage.store(record)
        print(f"Stored: {item['key']}")
    
    # Show results
    count = await storage.count()
    print(f"\nTotal records: {count}")
    
    await storage.close()


asyncio.run(main())
```

Output:
```
Stored: item-1
Stored: item-2
Skipping duplicate: item-1

Total records: 2
```

## Next Steps

- 📚 [Tutorials](../tutorials/first-feed.md) - Build a real feed collector
- 🔧 [How-To Guides](../how-to/custom-storage.md) - Implement custom backends
- 📖 [Concepts](../concepts/feeds-and-sources.md) - Understand the architecture
- [Architecture](../architecture/ARCHITECTURE.md) - System design and data flow
