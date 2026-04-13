#!/usr/bin/env python3
"""
FeedSpine Multi-Feed Collection Example
=======================================

This example demonstrates FeedSpine's ability to collect from **multiple feeds**
while maintaining **cross-feed deduplication**.

What You'll Learn:
    1. How to register multiple feeds with ``create_feed_spine()``
    2. How cross-feed deduplication works (same story on HN + Lobsters = 1 record)
    3. How to interpret collection results across multiple sources

The Problem This Solves:
    Tech news often appears on multiple aggregators simultaneously.
    A popular article might be on Hacker News, Lobsters, Reddit, and more.
    Without cross-feed deduplication, you'd store the same content N times.

    FeedSpine uses the article's URL as a natural key, so the same article
    appearing on 5 different feeds is stored exactly once. This:
    - Saves storage space
    - Simplifies downstream processing
    - Tracks all sources where content appeared (sightings)

Key Concepts:
    - Multiple Feeds: Register any number of feeds via the feeds dict
    - Cross-Feed Dedup: Same natural_key from different feeds = one record
    - Sightings: FeedSpine tracks WHERE and WHEN each record was seen
    - Per-Feed Collection: Collect from each feed individually

Usage:
    python examples/01_getting_started/02_multi_feed.py

Expected Output:
    - Total items fetched across all feeds
    - New unique records stored
    - Duplicates detected (cross-feed overlap)
"""

import asyncio
import warnings

from feedspine import MemoryStorage, RSSFeedAdapter, create_feed_spine

# Suppress internal WatermarkStore warning when using MemoryStorage
warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")


async def main() -> None:
    """Collect from multiple RSS feeds with cross-feed deduplication.

    This function demonstrates the multi-feed workflow:
    1. Create feed adapters for different sources
    2. Pass them to ``create_feed_spine()``
    3. Collect from each feed — FeedSpine deduplicates across all
    4. Observe cross-feed deduplication in action
    """
    # =========================================================================
    # STEP 1: Create Storage
    # =========================================================================
    storage = MemoryStorage()

    # =========================================================================
    # STEP 2: Define Multiple Feeds
    # =========================================================================
    # Each RSSFeedAdapter represents one feed source.
    feeds = [
        RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        ),
        RSSFeedAdapter(
            name="lobsters",
            url="https://lobste.rs/rss",
        ),
        # Easy to add more feeds:
        # RSSFeedAdapter(name="reddit-programming", url="https://www.reddit.com/r/programming/.rss"),
        # RSSFeedAdapter(name="dev-to", url="https://dev.to/feed"),
    ]

    # =========================================================================
    # STEP 3: Create FeedSpineApp with All Feeds
    # =========================================================================
    # Pass feeds as a dict to create_feed_spine() for one-step registration.
    app = create_feed_spine(
        storage,
        feeds={f.name: f for f in feeds},
    )

    print("=" * 60)
    print("REGISTERING FEEDS")
    print("=" * 60)
    for feed in feeds:
        print(f"  ✓ Registered: {feed.name} ({feed.url})")
    print(f"\nTotal feeds registered: {len(feeds)}")

    # =========================================================================
    # STEP 4: Collect From All Feeds
    # =========================================================================
    # Collect from each feed individually. FeedSpine deduplicates
    # across ALL feeds — same natural_key = stored once.
    print("\n" + "=" * 60)
    print("COLLECTING FROM ALL FEEDS")
    print("=" * 60)
    print("Fetching feeds...")

    total_processed = 0
    total_new = 0
    total_duplicates = 0

    for feed in feeds:
        outcome = await app.collection_service.run_collection(feed.name)
        total_processed += outcome.stats.processed
        total_new += outcome.stats.new
        total_duplicates += outcome.stats.duplicates
        print(
            f"  {feed.name}: {outcome.stats.processed} processed, "
            f"{outcome.stats.new} new, {outcome.stats.duplicates} duplicates"
        )

    # =========================================================================
    # STEP 5: Analyze Results
    # =========================================================================
    print("\n" + "=" * 60)
    print("COLLECTION RESULTS")
    print("=" * 60)
    print(f"  Total items processed: {total_processed}")
    print(f"  New unique records:    {total_new}")
    print(f"  Duplicates detected:   {total_duplicates}")

    # Calculate and display deduplication rate
    if total_processed > 0:
        dedup_rate = total_duplicates / total_processed * 100
        unique_rate = total_new / total_processed * 100

        print(f"\n  Deduplication rate: {dedup_rate:.1f}%")
        print(f"  Unique content rate: {unique_rate:.1f}%")

    # =========================================================================
    # What Cross-Feed Deduplication Means
    # =========================================================================
    print("\n" + "=" * 60)
    print("HOW CROSS-FEED DEDUPLICATION WORKS")
    print("=" * 60)
    print("""
Scenario: A popular blog post appears on both Hacker News and Lobsters.

Without FeedSpine:
  - HN fetch: Store article (record #1)
  - Lobsters fetch: Store same article again (record #2) <- DUPLICATE!
  - Result: Same content stored twice

With FeedSpine:
  - HN fetch: Store article (record #1, natural_key = article URL)
  - Lobsters fetch: Same natural_key -> UPDATE sighting, DON'T duplicate
  - Result: One record, multiple sightings tracked

The 'sightings' feature tells you:
  - first_seen_at: When FeedSpine first saw this content
  - last_seen_at: Most recent appearance
  - seen_count: How many times it appeared across all feeds
  - sources: Which feeds contained this content

This is invaluable for:
  - Popularity analysis (viral content appears on many feeds)
  - Source attribution (where did this originate?)
  - Trend detection (content spreading across platforms)
    """)


if __name__ == "__main__":
    asyncio.run(main())
