# FeedSpine: Media & News Aggregation Use Case

## Real-Time News Intelligence Platform

**Industry:** Media & Publishing / News Aggregation  
**Use Case:** Multi-Source News Feed Collection with Deduplication  
**Companies:** Reuters, Bloomberg, Google News, Apple News, Flipboard

---

## The Problem

News platforms must aggregate content from thousands of sources—RSS feeds, APIs, wire services—while ensuring:
- No duplicate stories shown to users
- Real-time content freshness
- Attribution tracking to original sources  
- Search across millions of articles
- Scalable collection infrastructure

**Current Pain Points:**
- Same story from AP appears in 50+ outlets = 50 duplicates
- Different headlines, same content (hard to dedupe)
- RSS parsing inconsistencies across sources
- No unified sighting history for copyright compliance
- Scaling collection infrastructure is expensive

---

## FeedSpine Solution

```python
"""
Media & News Example: Real-Time News Aggregator
Collect from multiple news sources with smart deduplication.
"""

import asyncio
import hashlib
from datetime import UTC, datetime
from feedspine import (
    FeedSpine,
    RSSFeedAdapter,
    JSONFeedAdapter,
    DuckDBStorage,
    MemorySearch,
    ConsoleNotifier,
)
from feedspine.enricher.metadata import MetadataEnricher


# Diverse news sources
NEWS_FEEDS = {
    # Major Wire Services
    "reuters-world": {
        "type": "rss",
        "url": "https://www.reutersagency.com/feed/?taxonomy=best-regions&post_type=best",
    },
    "ap-news": {
        "type": "rss",
        "url": "https://feeds.apnews.com/rss/topnews",
    },
    
    # Tech News
    "hackernews": {
        "type": "json",
        "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "items_path": None,  # Array at root
    },
    "techcrunch": {
        "type": "rss",
        "url": "https://techcrunch.com/feed/",
    },
    
    # Business
    "wsj-markets": {
        "type": "rss",
        "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    },
    
    # General
    "bbc-world": {
        "type": "rss",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
    },
    "nyt-homepage": {
        "type": "rss",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    },
}


class ContentHashEnricher(MetadataEnricher):
    """Enricher that adds content fingerprint for cross-source deduplication."""
    
    def __init__(self):
        super().__init__(fields={}, name="ContentHashEnricher")
    
    async def enrich(self, record):
        """Generate content hash from normalized text."""
        # Extract key content fields
        title = record.content.get("title", "").lower().strip()
        body = record.content.get("summary", "").lower().strip()
        
        # Remove common variations
        normalized = f"{title}|{body}"
        normalized = normalized.replace('"', '').replace("'", "")
        
        # Generate fingerprint
        content_hash = hashlib.md5(normalized.encode()).hexdigest()[:16]
        record.metadata.extra["content_hash"] = content_hash
        
        return await super().enrich(record)


async def main():
    # DuckDB for analytics, MemorySearch for full-text search
    storage = DuckDBStorage("news_aggregator.duckdb")
    search = MemorySearch()
    
    async with FeedSpine(
        storage=storage,
        search=search,
    ) as spine:
        
        # Register all news feeds
        for feed_name, config in NEWS_FEEDS.items():
            if config["type"] == "rss":
                adapter = RSSFeedAdapter(
                    url=config["url"],
                    name=feed_name,
                    source_type="news-rss",
                    requests_per_second=2.0,
                )
            else:
                adapter = JSONFeedAdapter(
                    url=config["url"],
                    name=feed_name,
                    source_type="news-api",
                    items_path=config.get("items_path"),
                )
            
            spine.register_feed(adapter)
        
        # Collect from all sources
        result = await spine.collect()
        
        print(f"📰 News Collection Summary:")
        print(f"   Sources:     {len(spine.list_feeds())}")
        print(f"   Articles:    {result.total_processed}")
        print(f"   Unique:      {result.total_new}")
        print(f"   Duplicates:  {result.total_duplicates}")
        print(f"   Dedup Rate:  {result.total_duplicates / max(1, result.total_processed):.1%}")
        
        # Per-source breakdown
        print(f"\n📊 By Source:")
        for feed_name, stats in result.feed_stats.items():
            print(f"   {feed_name}: {stats.new} new / {stats.duplicates} dupe")
        
        # Full-text search
        results = await search.search("artificial intelligence", limit=10)
        print(f"\n🔍 Search 'artificial intelligence': {results.total} results")
        for hit in results.results:
            print(f"   - {hit.record_id}: {hit.score:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Why FeedSpine Excels Here

### 1. **Cross-Source Deduplication**
The same AP story syndicated to 50 outlets? FeedSpine tracks sightings across all sources but stores only once.

```python
# Story natural key: "ap-story-2024-01-15-markets-rally"
# Seen on: reuters, yahoo, msn, google-news, fox-business...
# Stored: 1 time
# Sightings recorded: 50+

sightings = await storage.get_sightings("ap-story-2024-01-15-markets-rally")
# Returns all 50 sources with timestamps
```

### 2. **Multi-Protocol Adapters**
RSS, Atom, JSON APIs, REST endpoints—all with the same interface.

```python
# RSS Feed
rss = RSSFeedAdapter(url="https://feed.example.com/rss")

# JSON API
json_api = JSONFeedAdapter(
    url="https://api.example.com/articles",
    items_path="data.articles",  # Navigate nested JSON
    field_mapping={"id": "article_id", "title": "headline"},
)

# Same Pipeline interface for both
await pipeline.run(rss)
await pipeline.run(json_api)
```

### 3. **Content-Based Deduplication**
Beyond URL matching—detect duplicate content even with different headlines.

```python
# Same story, different headlines:
# - "Markets Rally on Fed News" (Reuters)
# - "Stocks Surge After Federal Reserve Announcement" (CNBC)
# 
# Content hash matches → tracked as single story with multiple sightings
```

### 4. **Full-Text Search Integration**
Pluggable search backends for instant article discovery.

```python
# Development: In-memory search
search = MemorySearch()

# Production: Elasticsearch
search = ElasticsearchSearch(
    hosts=["https://es-cluster:9200"],
    index_prefix="news"
)

# Or: Vector search for semantic similarity
search = ChromaSearch(collection="news_embeddings")
```

### 5. **Real-Time Statistics**
Monitor collection health per-source.

```python
result = await spine.collect()

# Per-feed metrics
for feed_name, stats in result.feed_stats.items():
    if stats.errors > 0:
        alert(f"Feed {feed_name} had {stats.errors} errors")
    if stats.dedup_rate > 0.5:
        log(f"Feed {feed_name} has 50%+ duplicates")
```

---

## Architecture for Scale

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      News Aggregation Platform                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       Feed Sources                              │   │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐      │   │
│  │  │ AP  │ │Reuters│ │ BBC │ │ NYT │ │ WSJ │ │ HN  │ │ TC  │ ...  │   │
│  │  └──┬──┘ └──┬───┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘      │   │
│  └─────┼───────┼────────┼───────┼───────┼───────┼───────┼──────────┘   │
│        │       │        │       │       │       │       │              │
│        └───────┴────────┴───────┴───────┴───────┴───────┘              │
│                                │                                        │
│                    ┌───────────▼───────────┐                           │
│                    │      FeedSpine        │                           │
│                    │   (Celery Workers)    │                           │
│                    └───────────┬───────────┘                           │
│                                │                                        │
│        ┌───────────┬───────────┼───────────┬───────────┐               │
│        │           │           │           │           │               │
│        ▼           ▼           ▼           ▼           ▼               │
│   ┌────────┐  ┌─────────┐  ┌────────┐  ┌────────┐  ┌────────┐         │
│   │ Dedup  │  │Sighting │  │Content │  │Pipeline│  │Scheduler│        │
│   │ Engine │  │ Tracker │  │ Hash   │  │ Stats  │  │(5 min)  │        │
│   └────────┘  └─────────┘  └────────┘  └────────┘  └────────┘         │
│        │                                                               │
│        ▼                                                               │
│   ┌──────────────────────────────────────────────────────────────┐    │
│   │                         Storage Layer                        │    │
│   │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │    │
│   │  │  PostgreSQL   │  │ Elasticsearch │  │     Redis     │    │    │
│   │  │  (Records)    │  │   (Search)    │  │   (Cache)     │    │    │
│   │  └───────────────┘  └───────────────┘  └───────────────┘    │    │
│   └──────────────────────────────────────────────────────────────┘    │
│                                │                                       │
│                                ▼                                       │
│   ┌──────────────────────────────────────────────────────────────┐    │
│   │                      Consumer APIs                           │    │
│   │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐             │    │
│   │  │REST API│  │GraphQL │  │WebSocket│ │  RSS   │             │    │
│   │  └────────┘  └────────┘  └────────┘  └────────┘             │    │
│   └──────────────────────────────────────────────────────────────┘    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Key Metrics

| Metric | Capability |
|--------|------------|
| Sources Supported | 10,000+ feeds |
| Articles/Day | 1M+ |
| Deduplication Rate | 60-80% |
| Search Latency | < 50ms |
| Collection Freshness | < 5 minutes |

---

## Production Configuration

```python
# production_config.py
from feedspine import FeedSpine
from feedspine.storage.postgres import PostgresStorage
from feedspine.search.elasticsearch import ElasticsearchSearch
from feedspine.cache.redis import RedisCache
from feedspine.executor.celery import CeleryExecutor
from feedspine.notifier.slack import SlackNotifier

async def create_production_spine():
    """Production-grade news aggregation pipeline."""
    
    return FeedSpine(
        # PostgreSQL for durable storage
        storage=PostgresStorage(
            dsn="postgresql://user:pass@db-cluster/news",
            pool_size=20,
        ),
        
        # Elasticsearch for full-text search
        search=ElasticsearchSearch(
            hosts=["https://es-node1:9200", "https://es-node2:9200"],
            index="news-articles",
            replicas=2,
        ),
        
        # Redis for caching & rate limiting
        cache=RedisCache(
            url="redis://redis-cluster:6379/0",
            ttl=3600,
        ),
        
        # Celery for distributed workers
        executor=CeleryExecutor(
            broker="redis://redis-cluster:6379/1",
            backend="redis://redis-cluster:6379/2",
        ),
        
        # Slack alerts for collection issues
        notifier=SlackNotifier(
            webhook_url=os.environ["SLACK_WEBHOOK"],
            channel="#news-ops",
        ),
    )
```

---

## Attribution & Compliance

FeedSpine's sighting history enables proper attribution and copyright compliance:

```python
# Get full provenance for any article
async def get_article_provenance(natural_key: str) -> dict:
    """Return complete attribution data for an article."""
    
    record = await storage.get_by_natural_key(natural_key)
    sightings = await storage.get_sightings(natural_key)
    
    return {
        "original_source": sightings[0].source if sightings else None,
        "first_seen": sightings[0].seen_at if sightings else None,
        "syndication_count": len(sightings),
        "syndicated_to": [s.source for s in sightings],
        "content": record.content if record else None,
    }

# Usage
provenance = await get_article_provenance("ap-2024-markets-rally")
# {
#     "original_source": "ap-news",
#     "first_seen": "2024-01-15T09:30:00Z",
#     "syndication_count": 47,
#     "syndicated_to": ["reuters", "yahoo", "msn", ...],
# }
```

---

## Next Steps

1. **Add NLP Enrichers** for topic classification, sentiment analysis
2. **Implement Trending Detection** using sighting velocity  
3. **Build Personalization** layer for user-specific feeds
4. **Add Image/Video Blob Storage** for media attachments
5. **Deploy Real-Time WebSocket** API for live updates
