#!/usr/bin/env python3
"""
Feed Discovery & Dynamic Registration
=======================================

This example demonstrates FeedSpine's **feed discovery and registration**
system — how to dynamically find, register, and manage feeds.

What You'll Learn:
    1. Listing available feed adapter types
    2. Registering feeds programmatically
    3. Dynamic feed discovery from configuration
    4. Managing multiple feeds (list, inspect, remove)

Key Concepts:
    - FeedAdapter: Protocol for data source adapters
    - Feed Registry: Internal registry mapping names → adapters
    - create_feed_spine: Factory that wires everything together
    - feeds.yaml: Configuration-driven feed registration

Usage:
    python examples/13_configuration/01_feed_discovery.py

Expected Output:
    Shows how to discover, register, list, and manage feeds.
"""

import asyncio
import warnings
from datetime import UTC, datetime

from feedspine import MemoryStorage, RSSFeedAdapter, create_feed_spine
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate

warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")


# ============================================================================
# Custom adapters for demonstration
# ============================================================================
class MockAPIAdapter:
    """Simulates a REST API feed."""

    def __init__(self, name: str, items: list[dict] | None = None) -> None:
        self._name = name
        self._items = items or []

    @property
    def name(self) -> str:
        return self._name

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def fetch(self):
        for item in self._items:
            yield RecordCandidate(
                natural_key=item.get("id", item.get("title", "")),
                published_at=datetime.now(UTC),
                content=item,
                metadata=Metadata(source=self._name),
            )


async def main() -> None:
    storage = MemoryStorage()
    app = create_feed_spine(storage)

    # =========================================================================
    # STEP 1: Register Feeds
    # =========================================================================
    print("=" * 60)
    print("STEP 1: Register Multiple Feeds")
    print("=" * 60)

    feeds_config = [
        RSSFeedAdapter(
            name="sec-press-releases",
            url="https://www.sec.gov/news/pressreleases.rss",
        ),
        MockAPIAdapter(
            name="earnings-api",
            items=[
                {"id": "AAPL-2024-Q2", "ticker": "AAPL", "eps": 1.52},
                {"id": "MSFT-2024-Q2", "ticker": "MSFT", "eps": 2.95},
            ],
        ),
        MockAPIAdapter(
            name="market-data-api",
            items=[
                {"id": "SPY-2024-06-15", "symbol": "SPY", "close": 543.21},
            ],
        ),
    ]

    for feed in feeds_config:
        app.register_feed(feed)
        print(f"  ✓ Registered: {feed.name}")

    # =========================================================================
    # STEP 2: List Registered Feeds
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 2: List Registered Feeds")
    print("=" * 60)

    registered = app.feeds
    print(f"\n  Total registered: {len(registered)} feeds\n")
    for name, adapter in registered.items():
        adapter_type = type(adapter).__name__
        print(f"  • {name:25s} ({adapter_type})")

    # =========================================================================
    # STEP 3: Collect from Specific Feeds
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 3: Selective Collection")
    print("=" * 60)

    # Collect only from non-RSS feeds (fast, no network needed)
    for feed_name in ["earnings-api", "market-data-api"]:
        outcome = await app.collection_service.run_collection(feed_name)
        print(f"\n  {feed_name}:")
        print(f"    Processed: {outcome.stats.processed}")
        print(f"    New:       {outcome.stats.new}")

    # =========================================================================
    # STEP 4: Query Records Across All Feeds
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 4: Cross-Feed Query")
    print("=" * 60)

    total = await storage.count()
    print(f"\n  Total records across all feeds: {total}")

    # =========================================================================
    # Configuration-Driven Registration (feeds.yaml pattern)
    # =========================================================================
    print("\n" + "=" * 60)
    print("CONFIGURATION-DRIVEN REGISTRATION")
    print("=" * 60)
    print("""
For production use, define feeds in a YAML config file:

  # feeds.yaml
  feeds:
    - name: sec-press-releases
      adapter_type: rss
      url: https://www.sec.gov/news/pressreleases.rss
      enabled: true
      schedule: "*/15 * * * *"   # Every 15 minutes

    - name: custom-api
      adapter_type: json
      url: https://api.example.com/data
      enabled: true
      config:
        api_key: ${API_KEY}      # Environment variable
        max_pages: 10

Load and register from config:

  from feedspine.core.feed_config import load_config, create_adapters_from_config

  config = load_config("feeds.yaml")
  adapters = create_adapters_from_config(config)
  for adapter in adapters:
      app.register_feed(adapter)
    """)


if __name__ == "__main__":
    asyncio.run(main())
