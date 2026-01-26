#!/usr/bin/env python3
"""
FeedSpine Multi-Feed Collection Example

Demonstrates collecting from multiple feeds with natural key deduplication.
Same content appearing in multiple feeds is stored only once.

Usage:
    python examples/02_multi_feed.py
"""

import asyncio

from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter


async def main() -> None:
    """Collect from multiple feeds with deduplication."""
    
    storage = MemoryStorage()
    
    # Define multiple feeds
    feeds = [
        RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        ),
        RSSFeedAdapter(
            name="lobsters",
            url="https://lobste.rs/rss",
        ),
        # Add more feeds as needed
    ]
    
    async with FeedSpine(storage=storage) as spine:
        # Register all feeds
        for feed in feeds:
            spine.register_feed(feed)
            print(f"Registered: {feed.name}")
        
        # Collect from all feeds
        print("\nCollecting from all feeds...")
        result = await spine.collect()
        
        print(f"\n{'='*50}")
        print(f"Total processed: {result.total_processed}")
        print(f"New records: {result.total_new}")
        print(f"Duplicates: {result.total_duplicates}")
        
        # If same article appears on multiple feeds, it's stored once
        # but all sightings are tracked
        if result.total_duplicates > 0:
            rate = result.total_duplicates / result.total_processed
            print(f"\nDeduplication rate: {rate:.1%}")
            print("(Same content from multiple sources stored only once)")


if __name__ == "__main__":
    asyncio.run(main())
