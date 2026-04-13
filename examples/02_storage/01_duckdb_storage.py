#!/usr/bin/env python3
"""
FeedSpine with DuckDB Persistent Storage
========================================

This example demonstrates how to use **DuckDB** as a persistent storage backend
for FeedSpine. Unlike MemoryStorage (which loses data when the program exits),
DuckDB persists records to disk and supports powerful SQL analytics.

What You'll Learn:
    1. How to configure DuckDB as your storage backend
    2. How persistence works across program restarts
    3. Why DuckDB is ideal for feed data analytics

Why DuckDB for Feed Data?
    DuckDB is an embedded analytical database (like SQLite, but columnar).
    It's perfect for feed data because:

    - **Persistent**: Data survives program restarts
    - **Columnar**: Fast aggregations (count by source, date ranges, etc.)
    - **SQL-native**: Query your feeds with standard SQL
    - **Zero config**: No server to install or manage
    - **Portable**: Single .db file you can share or backup
    - **Analytics-ready**: Built-in support for Parquet, JSON, CSV export

Storage Comparison:
    +-------------------+--------------+-------------+---------------+
    | Feature           | MemoryStorage| DuckDBStorage| PostgreSQL   |
    +-------------------+--------------+-------------+---------------+
    | Persistence       | None         | File        | Server       |
    | Setup             | Zero         | Zero        | Complex      |
    | SQL Queries       | No           | Yes         | Yes          |
    | Analytics         | Limited      | Excellent   | Good         |
    | Scalability       | RAM only     | ~100GB      | Unlimited    |
    | Use Case          | Testing      | Local/Dev   | Production   |
    +-------------------+--------------+-------------+---------------+

Installation:
    pip install feedspine[duckdb]
    # or: uv add feedspine[duckdb]

Usage:
    python examples/02_storage/01_duckdb_storage.py
    # Run again to see deduplication across restarts!

Expected Output:
    First run:  N new records stored, 0 duplicates
    Second run: 0 new records, N duplicates (data persisted!)
"""

import asyncio
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")

from feedspine import RSSFeedAdapter, create_feed_spine  # noqa: E402

# ============================================================================
# DuckDB is an OPTIONAL dependency - gracefully handle if not installed
# ============================================================================
try:
    from feedspine import DuckDBStorage

    # DuckDBStorage might be None if duckdb isn't installed
    HAS_DUCKDB = DuckDBStorage is not None
except ImportError:
    DuckDBStorage = None
    HAS_DUCKDB = False


async def main() -> None:
    """Demonstrate persistent feed storage with DuckDB.

    This function shows the DuckDB workflow:
    1. Create a DuckDBStorage pointing to a file path
    2. Use ``create_feed_spine()`` exactly like with MemoryStorage
    3. Data persists to disk automatically
    4. Re-running the script shows deduplication working across restarts

    The key insight: Your storage choice is a one-line change.
    Everything else in FeedSpine works identically.
    """
    # =========================================================================
    # STEP 0: Check DuckDB Availability
    # =========================================================================
    if not HAS_DUCKDB:
        print("=" * 60)
        print("DUCKDB NOT INSTALLED")
        print("=" * 60)
        print("""
DuckDB is an optional dependency for FeedSpine.

To install:
    pip install feedspine[duckdb]
    # or
    uv add feedspine[duckdb]

Why DuckDB?
    - Persistent storage (data survives restarts)
    - SQL queries on your feed data
    - Analytics-friendly columnar format
    - Zero configuration (just a file path)
        """)
        return

    # =========================================================================
    # STEP 1: Create DuckDB Storage
    # =========================================================================
    # Just provide a file path - DuckDB handles everything else.
    # The file is created automatically if it doesn't exist.
    db_path = Path("feeds.db")
    storage = DuckDBStorage(str(db_path))

    # Initialize the storage (opens the database connection and creates tables).
    # This is required for all storage backends except MemoryStorage.
    await storage.initialize()

    print("=" * 60)
    print("DUCKDB PERSISTENT STORAGE")
    print("=" * 60)
    print(f"  Database file: {db_path.absolute()}")
    print(f"  File exists:   {db_path.exists()}")

    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        print(f"  Current size:  {size_kb:.1f} KB")
        print("\n  -> Database already exists! Watch for deduplication...")
    else:
        print("\n  -> New database will be created...")

    # =========================================================================
    # STEP 2: Use create_feed_spine() (Identical to MemoryStorage!)
    # =========================================================================
    # Notice: The code below is EXACTLY the same as the quickstart example.
    # Only the storage backend changed. This is FeedSpine's pluggable design.
    app = create_feed_spine(storage)

    # Register feed
    app.register_feed(
        RSSFeedAdapter(
            name="hacker-news",
            url="https://news.ycombinator.com/rss",
        )
    )

    # Collect
    print("\n" + "=" * 60)
    print("COLLECTING FEED DATA")
    print("=" * 60)
    print("Fetching from Hacker News RSS...")

    outcome = await app.collection_service.run_collection("hacker-news")

    print(f"\n  ✓ Processed:  {outcome.stats.processed}")
    print(f"  ✓ New:        {outcome.stats.new}")
    print(f"  ✓ Duplicates: {outcome.stats.duplicates}")

    # =========================================================================
    # STEP 3: Show Persistence Benefits
    # =========================================================================
    print("\n" + "=" * 60)
    print("PERSISTENCE IN ACTION")
    print("=" * 60)

    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        print(f"  Database saved: {db_path.absolute()}")
        print(f"  File size:      {size_kb:.1f} KB")

    print("""
What Just Happened:
    1. FeedSpine collected records from the RSS feed
    2. DuckDB stored them in a persistent file (feeds.db)
    3. The file remains after the program exits

Run This Script Again:
    - You'll see DUPLICATES detected (not NEW records)
    - This proves data persisted across program restarts
    - Without persistence, every run would store duplicates

Query Your Data with SQL:
    # Connect to the database
    import duckdb
    conn = duckdb.connect('feeds.db')

    # Count records by source
    conn.execute("SELECT source, COUNT(*) FROM records GROUP BY source").fetchall()

    # Find recent records
    conn.execute("SELECT * FROM records ORDER BY published_at DESC LIMIT 10").fetchall()

    # Export to Parquet for analytics
    conn.execute("COPY records TO 'feeds.parquet' (FORMAT PARQUET)")
    """)


if __name__ == "__main__":
    asyncio.run(main())
