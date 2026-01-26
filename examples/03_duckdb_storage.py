#!/usr/bin/env python3
"""
FeedSpine with DuckDB Persistent Storage

Shows how to use DuckDB for analytics-friendly persistent storage.

Usage:
    pip install feedspine[duckdb]
    python examples/03_duckdb_storage.py
"""

import asyncio
from pathlib import Path

from feedspine import FeedSpine, RSSFeedAdapter

# DuckDB is optional - check if available
try:
    from feedspine import DuckDBStorage
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    print("Install DuckDB support: pip install feedspine[duckdb]")


async def main() -> None:
    """Persistent collection with DuckDB storage."""
    
    if not HAS_DUCKDB:
        print("DuckDB not available. Install with: pip install feedspine[duckdb]")
        return
    
    # Create persistent storage
    db_path = Path("feeds.db")
    storage = DuckDBStorage(str(db_path))
    
    print(f"Using DuckDB storage: {db_path}")
    
    async with FeedSpine(storage=storage) as spine:
        # Register feed
        spine.register_feed(RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        ))
        
        # Collect
        print("\nCollecting...")
        result = await spine.collect()
        
        print(f"✓ Processed: {result.total_processed}")
        print(f"✓ New: {result.total_new}")
        print(f"✓ Duplicates: {result.total_duplicates}")
    
    print(f"\nData persisted to: {db_path.absolute()}")
    print("Run again to see deduplication in action!")


if __name__ == "__main__":
    asyncio.run(main())
