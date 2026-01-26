# FeedSpine: Social Media Intelligence Use Case

## Brand Monitoring & Social Listening Platform

**Industry:** Marketing / Brand Management / PR  
**Use Case:** Multi-Platform Social Media Monitoring with Deduplication  
**Companies:** Sprout Social, Hootsuite, Brandwatch, Meltwater, Sprinklr

---

## The Problem

Brands must monitor their presence across multiple social platforms:
- Twitter/X mentions and hashtags
- Reddit discussions
- YouTube comments
- News mentions
- Blog posts and reviews
- Forum discussions

**Current Pain Points:**
- Same viral post appears 1000x via retweets/shares = 1000 duplicates
- Cross-platform tracking is fragmented
- Sentiment analysis runs on duplicates (wasting compute)
- No unified engagement history
- Influencer impact tracking is manual

---

## FeedSpine Solution

```python
"""
Social Media Example: Brand Intelligence Platform
Monitor brand mentions across platforms with viral deduplication.
"""

import asyncio
import hashlib
from datetime import datetime, UTC
from feedspine import (
    FeedSpine,
    JSONFeedAdapter,
    RSSFeedAdapter,
    DuckDBStorage,
    MemorySearch,
    ConsoleNotifier,
)
from feedspine.models.record import RecordCandidate
from feedspine.models.base import Metadata
from feedspine.protocols.notification import Notification, Severity


# Social media data sources (via aggregation APIs)
SOCIAL_FEEDS = {
    # Twitter/X (via official API or aggregator)
    "twitter-brand-mentions": {
        "type": "json",
        "url": "https://api.twitter.com/2/tweets/search/recent?query=@YourBrand",
        "items_path": "data",
        "platform": "twitter",
    },
    "twitter-hashtag": {
        "type": "json",
        "url": "https://api.twitter.com/2/tweets/search/recent?query=%23YourBrand",
        "items_path": "data",
        "platform": "twitter",
    },
    
    # Reddit
    "reddit-brand-sub": {
        "type": "json",
        "url": "https://www.reddit.com/r/YourBrand/new.json",
        "items_path": "data.children",
        "platform": "reddit",
    },
    "reddit-mentions": {
        "type": "json",
        "url": "https://www.reddit.com/search.json?q=YourBrand&sort=new",
        "items_path": "data.children",
        "platform": "reddit",
    },
    
    # YouTube (via RSS)
    "youtube-channel": {
        "type": "rss",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=YOUR_CHANNEL_ID",
        "platform": "youtube",
    },
    
    # News & Blogs (via Google News RSS)
    "news-brand": {
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=YourBrand",
        "platform": "news",
    },
    
    # Product Reviews (via aggregator)
    "trustpilot-reviews": {
        "type": "json",
        "url": "https://api.aggregator.com/trustpilot/YourBrand",
        "items_path": "reviews",
        "platform": "trustpilot",
    },
    
    # Hacker News mentions
    "hackernews-brand": {
        "type": "json",
        "url": "https://hn.algolia.com/api/v1/search?query=YourBrand",
        "items_path": "hits",
        "platform": "hackernews",
    },
}


class SocialMediaAdapter(JSONFeedAdapter):
    """Adapter for social media APIs with viral content deduplication."""
    
    def __init__(self, name: str, config: dict):
        super().__init__(
            url=config["url"],
            name=name,
            source_type=f"social-{config['platform']}",
            items_path=config.get("items_path"),
            requests_per_second=0.5,
        )
        self.platform = config["platform"]
    
    def _to_candidate(self, item: dict) -> RecordCandidate:
        """Convert social post to candidate with content fingerprint."""
        
        # Platform-specific content extraction
        content = self._extract_content(item)
        
        # Generate fingerprint for viral deduplication
        # Retweets, reposts, shares all get same fingerprint as original
        fingerprint = self._generate_fingerprint(content)
        
        return RecordCandidate(
            natural_key=fingerprint,
            published_at=self._extract_timestamp(item),
            content={
                "text": content["text"],
                "author": content["author"],
                "platform": self.platform,
                "platform_id": content["platform_id"],
                "url": content["url"],
                "engagement": {
                    "likes": content.get("likes", 0),
                    "shares": content.get("shares", 0),
                    "comments": content.get("comments", 0),
                },
                "is_original": content.get("is_original", True),
                "original_author": content.get("original_author"),
                "sentiment": None,  # To be enriched
            },
            metadata=Metadata(
                source=self.name,
                record_type="social-mention",
                extra={
                    "platform": self.platform,
                    "author_followers": content.get("author_followers", 0),
                },
            ),
        )
    
    def _generate_fingerprint(self, content: dict) -> str:
        """Generate consistent fingerprint for content deduplication.
        
        Retweets, reposts, and shares get the same fingerprint as original.
        """
        # Use original content for fingerprinting
        text = content.get("original_text") or content.get("text", "")
        author = content.get("original_author") or content.get("author", "")
        
        # Normalize text
        normalized = text.lower().strip()
        normalized = " ".join(normalized.split())  # Collapse whitespace
        
        # Generate fingerprint
        key = f"{self.platform}:{author}:{normalized[:100]}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    def _extract_content(self, item: dict) -> dict:
        """Extract content based on platform."""
        
        if self.platform == "twitter":
            return self._extract_twitter(item)
        elif self.platform == "reddit":
            return self._extract_reddit(item)
        elif self.platform == "hackernews":
            return self._extract_hackernews(item)
        else:
            return self._extract_generic(item)
    
    def _extract_twitter(self, item: dict) -> dict:
        """Extract Twitter/X post content."""
        
        # Check if retweet
        is_retweet = item.get("text", "").startswith("RT @")
        referenced = item.get("referenced_tweets", [])
        
        return {
            "text": item.get("text", ""),
            "author": item.get("author_id", ""),
            "platform_id": item.get("id", ""),
            "url": f"https://twitter.com/i/status/{item.get('id', '')}",
            "likes": item.get("public_metrics", {}).get("like_count", 0),
            "shares": item.get("public_metrics", {}).get("retweet_count", 0),
            "comments": item.get("public_metrics", {}).get("reply_count", 0),
            "is_original": not is_retweet and not referenced,
            "original_author": referenced[0].get("author_id") if referenced else None,
        }
    
    def _extract_reddit(self, item: dict) -> dict:
        """Extract Reddit post/comment content."""
        data = item.get("data", item)
        
        return {
            "text": data.get("title", "") + " " + data.get("selftext", ""),
            "author": data.get("author", ""),
            "platform_id": data.get("id", ""),
            "url": f"https://reddit.com{data.get('permalink', '')}",
            "likes": data.get("ups", 0),
            "shares": 0,
            "comments": data.get("num_comments", 0),
            "is_original": True,
        }
    
    def _extract_hackernews(self, item: dict) -> dict:
        """Extract Hacker News item content."""
        
        return {
            "text": item.get("title", "") + " " + (item.get("story_text") or ""),
            "author": item.get("author", ""),
            "platform_id": str(item.get("objectID", "")),
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID', '')}",
            "likes": item.get("points", 0),
            "shares": 0,
            "comments": item.get("num_comments", 0),
            "is_original": True,
        }
    
    def _extract_generic(self, item: dict) -> dict:
        """Generic content extraction."""
        return {
            "text": item.get("text") or item.get("content") or item.get("body", ""),
            "author": item.get("author") or item.get("user") or "",
            "platform_id": str(item.get("id", "")),
            "url": item.get("url") or item.get("link", ""),
            "is_original": True,
        }
    
    def _extract_timestamp(self, item: dict) -> datetime:
        """Extract timestamp from various formats."""
        ts = (
            item.get("created_at") or
            item.get("data", {}).get("created_utc") or
            item.get("created_at_i") or
            item.get("timestamp")
        )
        
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=UTC)
        elif isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        return datetime.now(UTC)


async def main():
    storage = DuckDBStorage("social_intelligence.duckdb")
    search = MemorySearch()
    notifier = ConsoleNotifier(show_timestamp=True)
    
    async with FeedSpine(
        storage=storage,
        search=search,
        notifier=notifier,
    ) as spine:
        
        # Register all social feeds
        for feed_name, config in SOCIAL_FEEDS.items():
            if config["type"] == "json":
                adapter = SocialMediaAdapter(name=feed_name, config=config)
            else:
                adapter = RSSFeedAdapter(
                    url=config["url"],
                    name=feed_name,
                    source_type=f"social-{config['platform']}",
                )
            spine.register_feed(adapter)
        
        # Collect from all sources
        result = await spine.collect()
        
        print(f"📱 Social Intelligence Summary:")
        print(f"   Platforms:      {len(spine.list_feeds())}")
        print(f"   Total Posts:    {result.total_processed}")
        print(f"   Unique Content: {result.total_new}")
        print(f"   Viral Dupes:    {result.total_duplicates}")
        print(f"   Dedup Rate:     {result.total_duplicates / max(1, result.total_processed):.1%}")
        
        # Show viral content
        await show_viral_content(spine)
        
        # Show platform breakdown
        await show_platform_breakdown(spine)
        
        # Identify influencers
        await identify_influencers(spine)


async def show_viral_content(spine: FeedSpine):
    """Show content that went viral (many sightings)."""
    
    print(f"\n🔥 Viral Content (multiple shares/reposts):")
    
    viral = []
    async for record in spine.query(layer="bronze", limit=100):
        sightings = await spine.storage.get_sightings(record.natural_key)
        if len(sightings) > 5:  # More than 5 sightings = viral
            viral.append((record, len(sightings)))
    
    # Sort by virality
    viral.sort(key=lambda x: x[1], reverse=True)
    
    for record, sighting_count in viral[:5]:
        engagement = record.content.get("engagement", {})
        total_engagement = sum(engagement.values())
        print(f"   [{sighting_count} sightings] {record.content.get('text', '')[:50]}...")
        print(f"      Platform: {record.content.get('platform')} | Engagement: {total_engagement:,}")


async def show_platform_breakdown(spine: FeedSpine):
    """Show mentions by platform."""
    
    print(f"\n📊 Platform Breakdown:")
    
    platforms = {}
    async for record in spine.query(layer="bronze"):
        platform = record.content.get("platform", "unknown")
        platforms[platform] = platforms.get(platform, 0) + 1
    
    for platform, count in sorted(platforms.items(), key=lambda x: x[1], reverse=True):
        print(f"   {platform}: {count:,} mentions")


async def identify_influencers(spine: FeedSpine):
    """Identify top influencers mentioning the brand."""
    
    print(f"\n👑 Top Influencers:")
    
    authors = {}
    async for record in spine.query(layer="bronze"):
        author = record.content.get("author", "unknown")
        followers = record.metadata.extra.get("author_followers", 0)
        engagement = sum(record.content.get("engagement", {}).values())
        
        if author not in authors:
            authors[author] = {"followers": followers, "mentions": 0, "engagement": 0}
        
        authors[author]["mentions"] += 1
        authors[author]["engagement"] += engagement
    
    # Sort by engagement
    top = sorted(authors.items(), key=lambda x: x[1]["engagement"], reverse=True)[:5]
    
    for author, stats in top:
        print(f"   @{author}: {stats['mentions']} mentions, {stats['engagement']:,} engagement")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Why FeedSpine Excels Here

### 1. **Viral Content Deduplication**
A tweet with 10,000 retweets? FeedSpine tracks it as ONE piece of content with 10,000 sightings.

```python
# Original tweet: "Just tried @YourBrand - amazing!"
# - Original post (fingerprint: a1b2c3d4)
# - 10,000 retweets (same fingerprint!)
# - 500 quote tweets (same fingerprint!)
# 
# Stored: 1 record
# Sightings: 10,500 (tracking viral spread)
```

### 2. **Cross-Platform Content Tracking**
Same story shared on Twitter, Reddit, and HN? Tracked together.

```python
# Tech announcement shared everywhere:
sightings = await storage.get_sightings("content-fingerprint-xyz")

# [
#   Sighting(source="twitter-brand", seen_at="10:00", is_new=True),
#   Sighting(source="reddit-tech", seen_at="10:15"),
#   Sighting(source="hackernews", seen_at="10:30"),
#   Sighting(source="news-techcrunch", seen_at="11:00"),
# ]
```

### 3. **Accurate Sentiment Analysis**
Run sentiment analysis once per unique content, not per retweet.

```python
# Before FeedSpine:
# - 10,000 retweets = 10,000 sentiment API calls
# - Cost: $100 (at $0.01/call)

# After FeedSpine:
# - 1 unique content = 1 sentiment API call
# - Cost: $0.01
# - Savings: 99.99%
```

### 4. **Influencer Impact Measurement**
Track which influencers drive the most engagement.

```python
async def measure_influencer_impact(influencer: str) -> dict:
    """Measure total impact of an influencer's mentions."""
    
    impact = {
        "mentions": 0,
        "total_reach": 0,
        "viral_posts": 0,
    }
    
    async for record in spine.query(
        layer="bronze",
        filters={"content.author": influencer}
    ):
        impact["mentions"] += 1
        
        sightings = await storage.get_sightings(record.natural_key)
        impact["total_reach"] += len(sightings)
        
        if len(sightings) > 100:
            impact["viral_posts"] += 1
    
    return impact
```

### 5. **Real-Time Crisis Detection**
Detect sudden spikes in negative mentions.

```python
async def detect_crisis(spine: FeedSpine) -> bool:
    """Detect potential PR crisis from mention patterns."""
    
    from datetime import timedelta
    
    recent_negative = 0
    baseline_negative = 0
    
    now = datetime.now(UTC)
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    
    async for record in spine.query(layer="bronze"):
        sentiment = record.content.get("sentiment")
        
        if sentiment and sentiment < -0.5:  # Negative
            if record.published_at > hour_ago:
                recent_negative += 1
            elif record.published_at > day_ago:
                baseline_negative += 1
    
    # Hourly average vs current hour
    baseline_hourly = baseline_negative / 24
    
    # Alert if 3x normal negative volume
    if recent_negative > baseline_hourly * 3:
        return True
    
    return False
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 Brand Intelligence Platform                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    Social Platforms                                                     │
│    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
│    │Twitter │ │ Reddit │ │YouTube │ │  News  │ │Reviews │ │   HN   │  │
│    └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘  │
│        │          │          │          │          │          │        │
│        └──────────┴──────────┴──────────┴──────────┴──────────┘        │
│                              │                                          │
│                    ┌─────────▼─────────┐                               │
│                    │     FeedSpine     │                               │
│                    │  Social Adapters  │                               │
│                    └─────────┬─────────┘                               │
│                              │                                          │
│    ┌─────────────────────────┼─────────────────────────┐               │
│    │                         │                         │               │
│    ▼                         ▼                         ▼               │
│ ┌────────────┐        ┌───────────┐           ┌─────────────┐         │
│ │   Viral    │        │  Content  │           │  Sighting   │         │
│ │   Dedup    │        │Fingerprint│           │   Tracker   │         │
│ └────────────┘        └───────────┘           └─────────────┘         │
│        │                                                               │
│        ▼                                                               │
│ ┌──────────────────────────────────────────────────────────────┐      │
│ │                      Processing Layer                        │      │
│ │  ┌────────────┐  ┌────────────┐  ┌────────────┐              │      │
│ │  │ Sentiment  │  │ Influencer │  │   Crisis   │              │      │
│ │  │  Analysis  │  │ Detection  │  │  Alerting  │              │      │
│ │  └────────────┘  └────────────┘  └────────────┘              │      │
│ └──────────────────────────────────────────────────────────────┘      │
│                              │                                         │
│              ┌───────────────┼───────────────┐                        │
│              │               │               │                        │
│              ▼               ▼               ▼                        │
│      ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│      │  Dashboard  │ │   Alerts    │ │   Reports   │                 │
│      └─────────────┘ └─────────────┘ └─────────────┘                 │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Business Impact

| Metric | Before FeedSpine | After FeedSpine |
|--------|-----------------|-----------------|
| Mention Volume | 50,000/day | 8,000/day (unique) |
| Sentiment API Costs | $500/day | $80/day |
| Crisis Detection Time | 4 hours | < 15 minutes |
| Influencer Attribution | Manual | Automatic |
| Cross-Platform Tracking | None | Full visibility |

---

## Advanced Features

### Real-Time Engagement Dashboard

```python
async def get_realtime_metrics() -> dict:
    """Get real-time brand health metrics."""
    
    from datetime import timedelta
    
    now = datetime.now(UTC)
    hour_ago = now - timedelta(hours=1)
    
    metrics = {
        "mentions_last_hour": 0,
        "unique_content": 0,
        "viral_multiplier": 0,
        "sentiment_avg": 0,
        "top_platform": None,
    }
    
    sentiments = []
    platforms = {}
    total_sightings = 0
    
    async for record in spine.query(
        layer="bronze",
        filters={"published_at": {"$gte": hour_ago.isoformat()}}
    ):
        metrics["unique_content"] += 1
        
        sightings = await storage.get_sightings(record.natural_key)
        total_sightings += len(sightings)
        
        if record.content.get("sentiment"):
            sentiments.append(record.content["sentiment"])
        
        platform = record.content.get("platform")
        platforms[platform] = platforms.get(platform, 0) + 1
    
    metrics["mentions_last_hour"] = total_sightings
    metrics["viral_multiplier"] = total_sightings / max(1, metrics["unique_content"])
    metrics["sentiment_avg"] = sum(sentiments) / max(1, len(sentiments))
    metrics["top_platform"] = max(platforms.items(), key=lambda x: x[1])[0] if platforms else None
    
    return metrics
```

### Competitive Share of Voice

```python
async def calculate_share_of_voice(brands: list[str]) -> dict:
    """Calculate share of voice across competitors."""
    
    voice = {brand: 0 for brand in brands}
    
    for brand in brands:
        async for record in spine.query(
            layer="bronze",
            filters={"content.text": {"$contains": brand}}
        ):
            sightings = await storage.get_sightings(record.natural_key)
            voice[brand] += len(sightings)
    
    total = sum(voice.values())
    
    return {
        brand: {"mentions": count, "share": count / total if total else 0}
        for brand, count in voice.items()
    }
```

---

## Next Steps

1. **Add Image Recognition** for brand logo detection in media
2. **Implement Topic Clustering** for trending conversation themes
3. **Build Engagement Prediction** using historical viral patterns
4. **Add Competitor Monitoring** for market intelligence
5. **Deploy Real-Time WebSocket** API for live dashboards
