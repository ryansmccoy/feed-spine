# RSS Feed Subscriptions with FeedSpine

This guide covers common patterns for subscribing to and managing RSS feeds with FeedSpine, including deduplication, incremental updates, and multi-feed aggregation.

## Quick Start

```python
import asyncio
from feedspine import FeedSpine, DuckDBStorage
from feedspine.adapter import RSSFeedAdapter

async def main():
    # Use DuckDB for persistent storage
    storage = DuckDBStorage("feeds.duckdb")
    await storage.initialize()
    
    spine = FeedSpine(storage=storage)
    
    # Subscribe to an RSS feed
    feed = RSSFeedAdapter(
        name="hacker-news",
        url="https://news.ycombinator.com/rss",
    )
    spine.register_feed(feed)
    
    # Poll and get results
    result = await spine.poll("hacker-news")
    print(f"New items: {result.new_count}")
    print(f"Duplicates skipped: {result.duplicate_count}")
    
    await storage.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## How Deduplication Works

FeedSpine automatically deduplicates RSS entries using a **natural key**:

```
natural_key = (guid or link).strip().lower()
```

### First Poll

```python
# First time seeing this article
item = {"guid": "https://example.com/article/123", "title": "Hello World"}

# FeedSpine:
# 1. Computes natural_key: "https://example.com/article/123"
# 2. Checks storage: not found
# 3. Creates Record + Sighting (is_new=True)
# 4. Returns: new_count=1
```

### Subsequent Polls

```python
# Same article appears again
item = {"guid": "https://example.com/article/123", "title": "Hello World"}

# FeedSpine:
# 1. Computes natural_key: "https://example.com/article/123"
# 2. Checks storage: FOUND
# 3. Creates Sighting only (is_new=False)
# 4. Returns: duplicate_count=1
```

### Deduplication Flow Diagram

```
                     ┌─────────────────┐
                     │   RSS Entry     │
                     │ guid="abc-123"  │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │ Normalize Key   │
                     │ "abc-123".lower │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
             ┌───────│ Key Exists?     │───────┐
             │  NO   └─────────────────┘  YES  │
             ▼                                  ▼
    ┌─────────────────┐               ┌─────────────────┐
    │ Create Record   │               │ Skip Record     │
    │ Create Sighting │               │ Create Sighting │
    │ (is_new=True)   │               │ (is_new=False)  │
    └────────┬────────┘               └────────┬────────┘
             │                                  │
             └──────────────┬───────────────────┘
                            ▼
                   ┌─────────────────┐
                   │ Return Result   │
                   │ new_count=?     │
                   │ dup_count=?     │
                   └─────────────────┘
```

## Multi-Feed Aggregation

### Subscribing to Multiple Feeds

```python
import asyncio
from feedspine import FeedSpine, DuckDBStorage
from feedspine.adapter import RSSFeedAdapter

async def aggregate_tech_news():
    storage = DuckDBStorage("tech_news.duckdb")
    await storage.initialize()
    
    spine = FeedSpine(storage=storage)
    
    # Register multiple feeds
    feeds = [
        RSSFeedAdapter(name="hackernews", url="https://news.ycombinator.com/rss"),
        RSSFeedAdapter(name="lobsters", url="https://lobste.rs/rss"),
        RSSFeedAdapter(name="reddit-prog", url="https://www.reddit.com/r/programming/.rss"),
        RSSFeedAdapter(name="reddit-python", url="https://www.reddit.com/r/python/.rss"),
    ]
    
    for feed in feeds:
        spine.register_feed(feed)
    
    # Poll all feeds
    total_new = 0
    for name in spine.list_feeds():
        result = await spine.poll(name)
        print(f"{name}: {result.new_count} new, {result.duplicate_count} duplicates")
        total_new += result.new_count
    
    print(f"\nTotal new items: {total_new}")
    
    await storage.close()

if __name__ == "__main__":
    asyncio.run(aggregate_tech_news())
```

### Cross-Feed Deduplication

When the same article appears in multiple feeds (e.g., shared links), FeedSpine automatically deduplicates:

```python
# Article posted on Hacker News
# guid: "https://blog.example.com/cool-post"

# Same article posted on Reddit
# link: "https://blog.example.com/cool-post" (guid may differ!)

# If natural_key is the same → deduplicated
# Each appearance still creates a Sighting for tracking
```

## Querying Collected Data

### Get Recent Items

```python
async def get_recent_items(storage, limit=10):
    """Get the most recent items across all feeds."""
    async for record in storage.query(
        limit=limit,
        order_by="-published_at",  # Most recent first
    ):
        print(f"[{record.metadata.source}] {record.content.get('title')}")
        print(f"  URL: {record.content.get('link')}")
        print(f"  Published: {record.published_at}")
        print()
```

### Filter by Source

```python
async def get_items_from_feed(storage, source_name, limit=20):
    """Get items from a specific feed."""
    async for record in storage.query(
        filters={"metadata.source": source_name},
        limit=limit,
        order_by="-published_at",
    ):
        yield record
```

### Count by Source

```python
async def count_items_per_feed(storage):
    """Count items per feed source."""
    # With DuckDB, you can run SQL directly
    if hasattr(storage, '_conn'):
        result = storage._conn.execute("""
            SELECT 
                json_extract_string(metadata, '$.source') as source,
                COUNT(*) as count
            FROM records
            GROUP BY source
            ORDER BY count DESC
        """).fetchall()
        
        for source, count in result:
            print(f"{source}: {count} items")
```

### Time-Based Queries

```python
from datetime import datetime, timedelta, UTC

async def get_items_last_24h(storage):
    """Get items from the last 24 hours."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    
    async for record in storage.query(
        filters={"published_at__gte": cutoff.isoformat()},
        order_by="-published_at",
    ):
        yield record
```

## Scheduled Polling

### Simple Periodic Polling

```python
import asyncio
from feedspine import FeedSpine, DuckDBStorage
from feedspine.adapter import RSSFeedAdapter

async def poll_forever(spine, interval_minutes=15):
    """Poll all feeds on a schedule."""
    while True:
        for name in spine.list_feeds():
            try:
                result = await spine.poll(name)
                print(f"[{datetime.now()}] {name}: {result.new_count} new items")
            except Exception as e:
                print(f"[{datetime.now()}] {name} failed: {e}")
        
        await asyncio.sleep(interval_minutes * 60)

async def main():
    storage = DuckDBStorage("feeds.duckdb")
    await storage.initialize()
    
    spine = FeedSpine(storage=storage)
    
    # Register feeds
    spine.register_feed(RSSFeedAdapter(
        name="hn", 
        url="https://news.ycombinator.com/rss"
    ))
    
    # Run forever
    try:
        await poll_forever(spine, interval_minutes=15)
    finally:
        await storage.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Using the Scheduler Module

```python
from feedspine.scheduler import Scheduler

async def main():
    storage = DuckDBStorage("feeds.duckdb")
    await storage.initialize()
    
    spine = FeedSpine(storage=storage)
    scheduler = Scheduler(spine)
    
    # Register feeds with custom intervals
    spine.register_feed(RSSFeedAdapter(
        name="hn",
        url="https://news.ycombinator.com/rss",
    ))
    
    scheduler.schedule("hn", interval_minutes=15)
    
    # Start scheduler
    await scheduler.run()
```

## Error Handling

### Handling Feed Failures

```python
async def safe_poll(spine, feed_name):
    """Poll a feed with error handling."""
    try:
        result = await spine.poll(feed_name)
        return {
            "status": "success",
            "new_count": result.new_count,
            "duplicate_count": result.duplicate_count,
        }
    except ConnectionError:
        return {"status": "error", "error": "Network unreachable"}
    except TimeoutError:
        return {"status": "error", "error": "Request timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### Retry Logic

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
)
async def poll_with_retry(spine, feed_name):
    """Poll with automatic retries."""
    return await spine.poll(feed_name)
```

## Best Practices

### 1. Use Persistent Storage

```python
# ❌ Don't use MemoryStorage for production
storage = MemoryStorage()  # Data lost on restart!

# ✅ Use DuckDB or another persistent backend
storage = DuckDBStorage("feeds.duckdb")
```

### 2. Set Reasonable Intervals

```python
# ❌ Too aggressive (may get rate limited)
scheduler.schedule("hn", interval_minutes=1)

# ✅ Reasonable intervals
scheduler.schedule("hn", interval_minutes=15)       # News feeds
scheduler.schedule("blog", interval_minutes=60)     # Blogs
scheduler.schedule("daily-digest", interval_hours=24)  # Digests
```

### 3. Add User-Agent Headers

```python
# Some feeds require a User-Agent header
feed = RSSFeedAdapter(
    name="hn",
    url="https://news.ycombinator.com/rss",
    headers={
        "User-Agent": "MyFeedReader/1.0 (contact@example.com)"
    }
)
```

### 4. Handle Feed-Specific Quirks

```python
class CustomRSSAdapter(RSSFeedAdapter):
    """Handle feed-specific parsing quirks."""
    
    def extract_natural_key(self, entry: dict) -> str:
        # Some feeds use non-standard GUIDs
        return entry.get("id") or entry.get("guid") or entry["link"]
    
    def normalize_date(self, date_str: str) -> datetime:
        # Handle various date formats
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unknown date format: {date_str}")
```

## Monitoring & Debugging

### Check Feed Health

```python
async def check_feed_health(storage, feed_name, hours=24):
    """Check if a feed is updating."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    
    count = await storage.count(
        filters={
            "metadata.source": feed_name,
            "captured_at__gte": cutoff.isoformat(),
        }
    )
    
    if count == 0:
        print(f"⚠️ {feed_name}: No items in last {hours} hours!")
    else:
        print(f"✅ {feed_name}: {count} items in last {hours} hours")
```

### View Sighting History

```python
async def view_sighting_history(storage, natural_key):
    """See all times we've seen this item."""
    sightings = await storage.get_sightings(natural_key)
    
    print(f"Sighting history for: {natural_key}")
    for s in sightings:
        status = "🆕 NEW" if s.is_new else "📝 Seen"
        print(f"  {s.seen_at}: {status} from {s.source}")
```

## Next Steps

- [DuckDB Storage Guide](../how-to/duckdb-storage.md) - Advanced storage features
- [Custom Adapters](../how-to/custom-adapters.md) - Build adapters for any feed type
- [SEC EDGAR Feeds](../domains/sec-edgar.md) - Financial data integration
