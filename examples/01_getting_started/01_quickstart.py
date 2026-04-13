#!/usr/bin/env python3
"""
FeedSpine Quickstart Example
============================

This example demonstrates FeedSpine's core value proposition:
**automatic deduplication** of feed data across multiple collections.

What You'll Learn:
    1. How to create a FeedSpineApp with ``create_feed_spine()``
    2. How to register RSS feeds for collection
    3. How deduplication works automatically (same item = stored once)

The Problem FeedSpine Solves:
    When monitoring feeds (RSS, APIs, etc.), the same content appears repeatedly.
    Without deduplication, you'd store duplicates, waste storage, and complicate
    downstream processing. FeedSpine uses "natural keys" (unique identifiers
    derived from the content) to ensure each item is stored exactly once.

Key Concepts:
    - create_feed_spine: Factory that wires storage, services, and runtime
    - FeedSpineApp: The application object holding all components
    - MemoryStorage: In-memory storage (for testing; use DuckDB for persistence)
    - RSSFeedAdapter: Adapter that fetches and parses RSS/Atom feeds
    - Natural Key: A unique identifier for each record (e.g., article URL)
    - Deduplication: Same natural_key = same record = stored only once

Usage:
    python examples/01_getting_started/01_quickstart.py

Expected Output:
    First collection:  N new records (fresh data from feed)
    Second collection: 0 new records, N duplicates (same data, already stored)
"""

import asyncio
import warnings

from feedspine import MemoryStorage, RSSFeedAdapter, create_feed_spine

# Suppress internal WatermarkStore warning when using MemoryStorage
warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")


async def main() -> None:
    """Demonstrate basic feed collection with automatic deduplication.

    This function shows the fundamental FeedSpine workflow:
    1. Create storage backend (where records are persisted)
    2. Create a FeedSpineApp via ``create_feed_spine()``
    3. Register one or more feeds to collect from
    4. Call ``collection_service.run_collection()`` to fetch and deduplicate
    5. Observe that repeated collections don't create duplicates
    """
    # =========================================================================
    # STEP 1: Create Storage Backend
    # =========================================================================
    # MemoryStorage keeps everything in RAM - great for testing and examples.
    # For production, use DuckDBStorage (persistent, analytics-friendly):
    #   from feedspine import DuckDBStorage
    #   storage = DuckDBStorage("feeds.db")
    storage = MemoryStorage()

    # =========================================================================
    # STEP 2: Create FeedSpineApp
    # =========================================================================
    # create_feed_spine() wires storage, services, recorder, publisher,
    # and the spine-core runtime together in one call.
    app = create_feed_spine(storage)

    # =========================================================================
    # STEP 3: Register Feeds
    # =========================================================================
    # RSSFeedAdapter handles RSS 2.0 and Atom feeds automatically.
    # The adapter:
    #   - Fetches the XML from the URL
    #   - Parses entries into RecordCandidate objects
    #   - Generates natural_key from entry ID or link (for deduplication)
    app.register_feed(
        RSSFeedAdapter(
            name="hacker-news",  # Human-readable name for logging/tracking
            url="https://news.ycombinator.com/rss",  # Feed URL
        )
    )

    # =========================================================================
    # STEP 4: First Collection
    # =========================================================================
    # run_collection() fetches from a registered feed and stores new records.
    # The outcome object tells you what happened via its stats:
    #   - stats.processed: How many items were fetched from the feed
    #   - stats.new: How many were NEW (not seen before)
    #   - stats.duplicates: How many were already in storage
    print("=" * 60)
    print("FIRST COLLECTION")
    print("=" * 60)
    print("Fetching from Hacker News RSS feed...")

    outcome = await app.collection_service.run_collection("hacker-news")

    print(f"\n✓ Processed: {outcome.stats.processed} items from feed")
    print(f"✓ New:        {outcome.stats.new} records stored")
    print(f"✓ Duplicates: {outcome.stats.duplicates} (none yet - first run!)")

    # =========================================================================
    # STEP 5: Second Collection (Demonstrates Deduplication)
    # =========================================================================
    # Running run_collection() again fetches the same feed. But since the
    # items have the same natural_key, FeedSpine recognizes them as duplicates
    # and does NOT store them again. This is the core value!
    print("\n" + "=" * 60)
    print("SECOND COLLECTION (same feed, moments later)")
    print("=" * 60)
    print("Fetching again - watch the deduplication in action...")

    outcome = await app.collection_service.run_collection("hacker-news")

    print(f"\n✓ Processed: {outcome.stats.processed} items from feed")
    print(f"✓ New:        {outcome.stats.new} (should be 0 or very few)")
    print(f"✓ Duplicates: {outcome.stats.duplicates} ← DEDUPED!")

    # =========================================================================
    # What Just Happened?
    # =========================================================================
    print("\n" + "=" * 60)
    print("WHAT FEEDSPINE DID FOR YOU")
    print("=" * 60)
    print("""
1. Fetched RSS feed and parsed all entries
2. Generated a unique 'natural_key' for each entry (from GUID/link)
3. Checked storage: "Have I seen this natural_key before?"
4. Stored only NEW records, skipped duplicates
5. Tracked metadata: first_seen_at, last_seen_at, seen_count

Without FeedSpine, you'd need to:
- Write XML parsing code
- Design a deduplication strategy
- Handle storage yourself
- Track when items were first/last seen

FeedSpine does all of this automatically!
    """)


if __name__ == "__main__":
    asyncio.run(main())
