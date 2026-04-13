#!/usr/bin/env python3
"""
Sighting History & Cross-Feed Analysis
=======================================

This example demonstrates FeedSpine's **sighting system** — the audit trail
that tracks every time a record is observed across feeds.

What You'll Learn:
    1. What sightings are and why they matter
    2. How to inspect sightings after collection
    3. Cross-feed deduplication: same content from different sources
    4. Using sightings for feed health analysis

Key Concepts:
    - Sighting: A record of "I saw this natural_key at this source at this time"
    - is_new: True on first observation, False for subsequent sightings
    - Cross-feed dedup: Same article from 2 feeds → 1 record, 2 sightings
    - Feed staleness: No new sightings = feed may be broken

Usage:
    python examples/10_sightings/01_sighting_history.py

Expected Output:
    Shows sightings created during collection, cross-feed deduplication,
    and how to analyze feed activity from sighting data.
"""

import asyncio
import warnings
from datetime import UTC, datetime

from feedspine import MemoryStorage, create_feed_spine
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate
from feedspine.protocols.feed import FeedAdapter

warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")


# ============================================================================
# Custom Adapter: Simulates a news feed with known articles
# ============================================================================
class MockNewsFeed:
    """Simulates a news feed returning known articles."""

    def __init__(self, name: str, articles: list[dict]) -> None:
        self._name = name
        self._articles = articles

    @property
    def name(self) -> str:
        return self._name

    async def fetch(self):
        """Yield each article as a RecordCandidate."""
        for article in self._articles:
            yield RecordCandidate(
                natural_key=article["url"],  # URL is the natural key
                published_at=article.get("published_at", datetime.now(UTC)),
                content={"title": article["title"], "url": article["url"]},
                metadata=Metadata(source=self._name),
            )

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass


async def main() -> None:
    storage = MemoryStorage()
    app = create_feed_spine(storage)

    # Same articles appear in multiple feeds (common in news aggregation)
    shared_articles = [
        {
            "url": "https://example.com/fed-rate-decision-2024",
            "title": "Fed Holds Rates Steady",
            "published_at": datetime(2024, 6, 15, tzinfo=UTC),
        },
        {
            "url": "https://example.com/q2-earnings-preview",
            "title": "Q2 Earnings Season Preview",
            "published_at": datetime(2024, 6, 14, tzinfo=UTC),
        },
    ]

    # Feed A has the shared articles plus one exclusive
    feed_a_articles = shared_articles + [
        {
            "url": "https://example.com/exclusive-feed-a",
            "title": "Feed A Exclusive: Market Analysis",
            "published_at": datetime(2024, 6, 15, tzinfo=UTC),
        },
    ]

    # Feed B has the shared articles plus a different exclusive
    feed_b_articles = shared_articles + [
        {
            "url": "https://example.com/exclusive-feed-b",
            "title": "Feed B Exclusive: Tech Sector Report",
            "published_at": datetime(2024, 6, 15, tzinfo=UTC),
        },
    ]

    # Register both feeds
    app.register_feed(MockNewsFeed("reuters-rss", feed_a_articles))
    app.register_feed(MockNewsFeed("bloomberg-rss", feed_b_articles))

    # =========================================================================
    # STEP 1: Collect from Feed A
    # =========================================================================
    print("=" * 60)
    print("COLLECT FROM FEED A (reuters-rss)")
    print("=" * 60)

    outcome_a = await app.collection_service.run_collection("reuters-rss")
    print(f"  Processed: {outcome_a.stats.processed}")
    print(f"  New:       {outcome_a.stats.new}")
    print(f"  Dupes:     {outcome_a.stats.duplicates}")

    # =========================================================================
    # STEP 2: Collect from Feed B (cross-feed deduplication)
    # =========================================================================
    print("\n" + "=" * 60)
    print("COLLECT FROM FEED B (bloomberg-rss)")
    print("=" * 60)
    print("Watch: shared articles already exist → sighted, not duplicated\n")

    outcome_b = await app.collection_service.run_collection("bloomberg-rss")
    print(f"  Processed: {outcome_b.stats.processed}")
    print(f"  New:       {outcome_b.stats.new} (only the exclusive article)")
    print(f"  Dupes:     {outcome_b.stats.duplicates} (shared articles seen before)")

    # =========================================================================
    # STEP 3: Query sightings
    # =========================================================================
    print("\n" + "=" * 60)
    print("SIGHTING HISTORY")
    print("=" * 60)

    # Get all sightings from storage
    all_sightings = await storage.get_sightings()
    print(f"\nTotal sightings: {len(all_sightings)}")
    print("\nDetails:")
    for s in all_sightings:
        status = "NEW" if s.is_new else "SEEN BEFORE"
        print(f"  [{status:11s}] {s.source:15s} → {s.natural_key[:50]}")

    # =========================================================================
    # WHAT SIGHTINGS TELL YOU
    # =========================================================================
    print("\n" + "=" * 60)
    print("WHAT SIGHTINGS TELL YOU")
    print("=" * 60)
    print("""
1. DEDUPLICATION PROOF: Same article from 2 feeds → stored once,
   sighted twice. The record exists once; sightings track provenance.

2. FEED HEALTH: A feed with zero new sightings over time may be
   broken (not updating) or redundant (fully overlaps another feed).

3. AUDIT TRAIL: For compliance, sightings prove when and where
   you first captured a piece of data — crucial for financial data.

4. COVERAGE ANALYSIS: Compare sighting overlap between feeds to
   identify which feeds provide unique content vs. redundant data.
    """)


if __name__ == "__main__":
    asyncio.run(main())
