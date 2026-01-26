# Your First Feed

In this tutorial, you'll build a complete RSS feed collector that:

- Fetches articles from Hacker News
- Deduplicates based on URL
- Stores records with metadata
- Promotes validated records to Silver layer

By the end, you'll understand FeedSpine's core concepts and be ready to build your own feed adapters.

## Prerequisites

- Python 3.11+
- FeedSpine installed (`pip install feedspine`)
- Basic Python async knowledge

## Step 1: Create the Project

```bash
mkdir my-feed-collector
cd my-feed-collector
pip install feedspine
```

Create a file called `collector.py`:

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter

async def main():
    # We'll build this step by step
    pass

if __name__ == "__main__":
    asyncio.run(main())
```

## Step 2: Set Up Storage

FeedSpine needs a storage backend to persist records. Let's start with in-memory storage for simplicity:

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage

async def main():
    # Create storage backend
    storage = MemoryStorage()
    
    # Create FeedSpine with async context manager
    async with FeedSpine(storage=storage) as spine:
        print("FeedSpine initialized!")
        print(f"Registered feeds: {spine.list_feeds()}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
python collector.py
# Output:
# FeedSpine initialized!
# Registered feeds: []
```

## Step 3: Register a Feed

Now let's add the Hacker News RSS feed:

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter

async def main():
    storage = MemoryStorage()
    
    async with FeedSpine(storage=storage) as spine:
        # Create and register an RSS feed adapter
        hn_feed = RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        )
        spine.register_feed(hn_feed)
        
        print(f"Registered feeds: {spine.list_feeds()}")

if __name__ == "__main__":
    asyncio.run(main())
```

Output:

```
Registered feeds: ['hacker-news']
```

## Step 4: Collect Records

Now let's actually fetch and store records:

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter

async def main():
    storage = MemoryStorage()
    
    async with FeedSpine(storage=storage) as spine:
        hn_feed = RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        )
        spine.register_feed(hn_feed)
        
        # Collect from all registered feeds
        result = await spine.collect()
        
        print(f"Processed: {result.total_processed}")
        print(f"New: {result.total_new}")
        print(f"Duplicates: {result.total_duplicates}")

if __name__ == "__main__":
    asyncio.run(main())
```

Output (numbers will vary):

```
Processed: 30
New: 30
Duplicates: 0
```

## Step 5: Understand Deduplication

Run the collector again. Notice something?

```bash
python collector.py
# Output:
# Processed: 30
# New: 0
# Duplicates: 30
```

All 30 items are now duplicates! FeedSpine automatically tracks what it has seen using **natural keys**. For RSS feeds, the natural key is the item's URL or GUID.

## Step 6: Query Stored Records

Let's see what we collected:

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter
from feedspine.models.base import Layer

async def main():
    storage = MemoryStorage()
    
    async with FeedSpine(storage=storage) as spine:
        hn_feed = RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        )
        spine.register_feed(hn_feed)
        
        # Collect
        await spine.collect()
        
        # Query records
        print("\n📰 Latest Hacker News stories:\n")
        count = 0
        async for record in spine.query(layer=Layer.BRONZE, limit=5):
            print(f"• {record.content.get('title', 'No title')}")
            print(f"  URL: {record.content.get('url', 'N/A')}")
            print(f"  Captured: {record.captured_at}")
            print()
            count += 1
        
        print(f"Total records in storage: {await storage.count()}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Step 7: Promote to Silver Layer

The **medallion architecture** lets you track data quality. Bronze is raw data. Let's promote validated records to Silver:

```python
import asyncio
from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter
from feedspine.models.base import Layer

async def main():
    storage = MemoryStorage()
    
    async with FeedSpine(storage=storage) as spine:
        hn_feed = RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        )
        spine.register_feed(hn_feed)
        
        await spine.collect()
        
        # Promote records with titles to Silver
        promoted = 0
        async for record in spine.query(layer=Layer.BRONZE):
            if record.content.get('title'):
                # Promote with validation enrichment
                silver = record.promote(
                    Layer.SILVER,
                    enrichments={
                        "validated": True,
                        "has_title": True,
                        "title_length": len(record.content.get('title', '')),
                    }
                )
                await storage.store(silver)
                promoted += 1
        
        print(f"Promoted {promoted} records to Silver")
        
        # Count by layer
        bronze_count = await storage.count(layer=Layer.BRONZE)
        silver_count = await storage.count(layer=Layer.SILVER)
        print(f"Bronze: {bronze_count}, Silver: {silver_count}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Step 8: Use Persistent Storage

For production, you'll want persistent storage. Let's use DuckDB:

```bash
pip install feedspine[duckdb]
```

```python
import asyncio
from feedspine import FeedSpine, DuckDBStorage, RSSFeedAdapter

async def main():
    # Data persists in feeds.db
    storage = DuckDBStorage("feeds.db")
    
    async with FeedSpine(storage=storage) as spine:
        hn_feed = RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        )
        spine.register_feed(hn_feed)
        
        result = await spine.collect()
        
        print(f"New: {result.total_new}")
        print(f"Duplicates: {result.total_duplicates}")
        print(f"Total in database: {await storage.count()}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it multiple times - records persist and duplicates are detected across runs!

## Complete Example

Here's the full collector with all features:

```python
"""Complete RSS feed collector example."""

import asyncio
from datetime import datetime, UTC

from feedspine import FeedSpine, DuckDBStorage, RSSFeedAdapter
from feedspine.models.base import Layer


async def main():
    # Persistent storage
    storage = DuckDBStorage("hacker_news.db")
    
    async with FeedSpine(storage=storage) as spine:
        # Register feed
        spine.register_feed(RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        ))
        
        # Collect
        print(f"🔄 Collecting at {datetime.now(UTC).isoformat()}")
        result = await spine.collect()
        
        print(f"   Processed: {result.total_processed}")
        print(f"   New: {result.total_new}")
        print(f"   Duplicates: {result.total_duplicates}")
        
        # Show new items
        if result.total_new > 0:
            print(f"\n📰 New stories:")
            async for record in spine.query(layer=Layer.BRONZE, limit=5):
                title = record.content.get('title', 'No title')
                print(f"   • {title[:60]}...")
        
        # Stats
        total = await storage.count()
        print(f"\n📊 Total records: {total}")


if __name__ == "__main__":
    asyncio.run(main())
```

## What's Next?

You've learned the basics of FeedSpine:

- ✅ Setting up storage and FeedSpine
- ✅ Registering feed adapters
- ✅ Collecting and deduplicating records
- ✅ Querying stored records
- ✅ Promoting records through layers
- ✅ Using persistent storage

**Next steps:**

- [Implement a Custom Feed](../how-to/custom-feed.md) - Build your own adapter
- [Custom Storage Backend](../how-to/custom-storage.md) - Use your own database
- [Architecture Concepts](../concepts/architecture.md) - Understand the design

## Troubleshooting

### "No module named 'feedspine'"

Make sure you installed FeedSpine:

```bash
pip install feedspine
```

### "DuckDBStorage not found"

Install the DuckDB extra:

```bash
pip install feedspine[duckdb]
```

### Feed returns 0 items

Check:
1. The URL is correct and accessible
2. Your network allows outbound HTTP requests
3. The feed actually has items (some feeds are empty)

### All items are duplicates

This is expected on subsequent runs! FeedSpine tracks what it has seen. New items will only appear when the feed publishes them.
