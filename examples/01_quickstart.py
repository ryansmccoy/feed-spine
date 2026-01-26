#!/usr/bin/env python3
"""
FeedSpine Quickstart Example

Shows the basic flow: register feeds, collect, deduplicate.

Usage:
    python examples/01_quickstart.py
"""

import asyncio
from datetime import UTC, datetime

from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter


async def main() -> None:
    """Basic feed collection with automatic deduplication."""
    
    # Create in-memory storage (use DuckDBStorage for persistence)
    storage = MemoryStorage()
    
    async with FeedSpine(storage=storage) as spine:
        # Register a feed
        spine.register_feed(RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        ))
        
        # First collection
        print("First collection...")
        result = await spine.collect()
        
        print(f"✓ Processed: {result.total_processed}")
        print(f"✓ New: {result.total_new}")
        print(f"✓ Duplicates: {result.total_duplicates}")
        
        # Second collection - should see duplicates
        print("\nSecond collection (same data)...")
        result = await spine.collect()
        
        print(f"✓ Processed: {result.total_processed}")
        print(f"✓ New: {result.total_new}")
        print(f"✓ Duplicates: {result.total_duplicates} (deduped!)")


if __name__ == "__main__":
    asyncio.run(main())
