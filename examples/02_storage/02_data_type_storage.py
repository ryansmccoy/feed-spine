#!/usr/bin/env python
"""
FeedSpine Data Type Aware Storage
=================================

This example demonstrates FeedSpine's **intelligent storage optimization**
based on the type of data being stored. Different data types have different
access patterns, and FeedSpine automatically configures storage accordingly.

What You'll Learn:
    1. How FeedSpine detects data types from content
    2. How storage is optimized per data type (indexing, partitioning, etc.)
    3. How to get scaling recommendations for your data volume

Why Data Type Matters:
    Not all feed data is the same. Consider these different patterns:

    - **Observations** (earnings, metrics): Query by entity + period, need versioning
    - **Events** (earnings calls, dividends): Query by date range, need scheduling
    - **Entities** (companies, people): Query by identifier, need deduplication
    - **Documents** (filings, reports): Query by ID, need full-text search
    - **Prices** (quotes, trades): Query by symbol + time, need high throughput

    Each type benefits from different:
    - Indexing strategies (B-tree vs BRIN vs GIN)
    - Partitioning schemes (by date, by entity, none)
    - Batch sizes (100 for docs, 100K for prices)
    - Versioning (observations need it, prices don't)

FeedSpine's Data Types:
    ┌──────────────┬─────────────────────┬────────────────────────────────┐
    │ Data Type    │ Primary Index       │ Optimized For                  │
    ├──────────────┼─────────────────────┼────────────────────────────────┤
    │ OBSERVATIONS │ entity+metric+period│ Financial metrics, time series │
    │ EVENTS       │ entity+type+date    │ Calendars, schedules           │
    │ ENTITIES     │ entity_id           │ Master data, deduplication     │
    │ DOCUMENTS    │ document_id         │ Filings, reports, full-text    │
    │ PRICES       │ symbol+timestamp    │ High-frequency time series     │
    │ GENERIC      │ natural_key         │ Default, when type unknown     │
    └──────────────┴─────────────────────┴────────────────────────────────┘

Features Demonstrated:
    - Data type detection from record content
    - Per-type storage configuration
    - Scaling recommendations (SQLite → PostgreSQL)
    - Observation-specific supersession tracking

Usage:
    python examples/02_storage/02_data_type_storage.py
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from feedspine.storage import (
    DataType,
    create_storage,
    get_config,
    get_storage_recommendations,
)


async def main() -> None:
    """Demonstrate data type aware storage optimization.

    This function shows how FeedSpine optimizes storage based on data type:
    1. Display configuration for each data type
    2. Show scaling recommendations for different data volumes
    3. Create storage and store sample records
    4. Demonstrate automatic data type detection

    Returns:
        None. Prints storage configurations and recommendations.
    """
    print("=" * 60)
    print("FEEDSPINE DATA TYPE STORAGE OPTIMIZATION")
    print("=" * 60)
    print("""
FeedSpine automatically optimizes storage based on what kind of
data you're storing. This example shows the different configurations
and how to leverage them for your use case.
    """)

    # =========================================================================
    # 1. Show configurations for each data type
    # =========================================================================
    # Each data type has a pre-configured storage strategy optimized for
    # its typical access patterns. These configs are battle-tested defaults.
    print("\n📊 DATA TYPE CONFIGURATIONS")
    print("-" * 60)

    for dt in DataType:
        if dt in (DataType.AUTO_DETECT, DataType.GENERIC):
            continue

        config = get_config(dt)
        print(f"\n  {dt.value.upper()}:")
        partition_desc = f"{config.partition_by} ({config.partition_interval})" if config.partition_by else "None"
        print(f"    Partition by:   {partition_desc}")
        print(f"    Primary index:  {config.primary_index}")
        print(f"    Batch size:     {config.batch_size:,} records")
        print(f"    BRIN index:     {'✅' if config.use_brin else '❌'} (range queries)")
        print(f"    GIN index:      {'✅' if config.use_gin else '❌'} (JSON/text search)")
        print(f"    Versioning:     {'✅' if config.enable_versioning else '❌'} (track history)")
        print(f"    Supersession:   {'✅' if config.enable_supersession else '❌'} (replace old values)")

    # =========================================================================
    # 2. Show scaling recommendations
    # =========================================================================
    # As your data grows, you need different storage backends.
    # FeedSpine recommends the right backend for your scale.
    print("\n\n📈 SCALING RECOMMENDATIONS")
    print("-" * 60)
    print("""
  As your data volume grows, FeedSpine recommends different backends:
  - Small (<1M):   SQLite - simple, embedded, no server
  - Medium (1-50M): PostgreSQL - reliable, scalable, SQL
  - Large (50M+):   PostgreSQL + Partitioning - handle billions of rows
    """)

    scales = [
        ("Small", 100_000),
        ("Medium", 10_000_000),
        ("Large", 100_000_000),
        ("Massive", 1_000_000_000),
    ]

    print(f"  {'Scale':<10} {'Rows':<15} {'Backend':<12} {'Partition':<10} {'Compression'}")
    print("  " + "-" * 65)

    for name, rows in scales:
        rec = get_storage_recommendations(DataType.OBSERVATIONS, rows)
        print(
            f"  {name:<10} {rows:>14,} {rec['backend']:<12} "
            f"{'Yes' if rec['partitioning']['enabled'] else 'No':<10} "
            f"{'Yes' if rec['compression']['enabled'] else 'No'}"
        )

    # =========================================================================
    # 3. Create storage and store sample data
    # =========================================================================
    # Let's create an in-memory SQLite storage and store some sample records.
    print("\n\n🔧 CREATING STORAGE WITH AUTO-CONFIG")
    print("-" * 60)

    # create_storage() is a factory function that creates the right storage
    # backend based on the connection string. It applies type-specific configs.
    storage = create_storage("sqlite:///:memory:")
    await storage.initialize()

    print("  ✓ Storage initialized (SQLite in-memory)")

    # Store some sample observation records
    import uuid

    from feedspine.models.base import Metadata
    from feedspine.models.record import Record, RecordCandidate

    records = []
    for i in range(10):
        # Create sample observation data (earnings-like)
        candidate = RecordCandidate(
            natural_key=f"obs:AAPL:eps_diluted:2024:Q{(i % 4) + 1}:{i}",
            published_at=datetime.now(UTC),
            content={
                "entity_id": "AAPL",
                "metric": "eps_diluted",
                "period": f"2024:Q{(i % 4) + 1}",
                "value": float(Decimal("1.50") + Decimal(str(i)) / 100),
                "observation_type": "actual",
            },
            metadata=Metadata(source="test"),
        )
        record = Record.from_candidate(candidate, str(uuid.uuid4()))
        records.append(record)

    for rec in records:
        await storage.store(rec)

    print(f"  ✓ Stored {len(records)} observation records")

    # Query back to verify
    count = 0
    async for _rec in storage.query():
        count += 1

    print(f"  ✓ Retrieved {count} records")

    # =========================================================================
    # 4. Demonstrate data type detection
    # =========================================================================
    # FeedSpine can automatically detect the data type from record content.
    # This is useful when you're ingesting data from unknown sources.
    print("\n\n🔍 AUTOMATIC DATA TYPE DETECTION")
    print("-" * 60)
    print("""
  FeedSpine analyzes your data and detects the type automatically.
  This determines which storage optimizations to apply.
    """)

    from feedspine.storage.data_types import detect_data_type

    # Sample records for each type
    test_cases = [
        (
            "Observation-like",
            [
                {"entity_id": "AAPL", "metric": "eps", "period": "2024:Q1", "value": 1.50, "as_of": "2024-01-15"},
                {
                    "entity_id": "GOOGL",
                    "metric": "revenue",
                    "period": "2024:Q1",
                    "value": 80000000000,
                    "as_of": "2024-01-20",
                },
            ],
        ),
        (
            "Event-like",
            [
                {
                    "entity_id": "AAPL",
                    "event_type": "earnings_call",
                    "scheduled_at": "2024-01-25",
                    "status": "confirmed",
                },
                {"entity_id": "GOOGL", "event_type": "dividend", "scheduled_at": "2024-02-15", "status": "announced"},
            ],
        ),
        (
            "Entity-like",
            [
                {"entity_type": "company", "name": "Apple Inc", "identifiers": {"cik": "0000320193", "ticker": "AAPL"}},
                {
                    "entity_type": "company",
                    "name": "Alphabet Inc",
                    "identifiers": {"cik": "0001652044", "ticker": "GOOGL"},
                },
            ],
        ),
        (
            "Price-like",
            [
                {"symbol": "AAPL", "price": 185.50, "volume": 50000000, "timestamp": "2024-01-15T16:00:00Z"},
                {"symbol": "GOOGL", "price": 140.25, "bid": 140.20, "ask": 140.30, "volume": 20000000},
            ],
        ),
    ]

    for name, samples in test_cases:
        detected = detect_data_type([{"content": s} for s in samples])
        print(f"  {name:20} → Detected as: {detected.value.upper()}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n\n" + "=" * 60)
    print("WHAT FEEDSPINE DID FOR YOU")
    print("=" * 60)
    print("""
✓ Automatically detected data types from content
✓ Applied type-specific storage optimizations
✓ Recommended appropriate backends for your scale
✓ Configured indexes, partitioning, and batch sizes

Without FeedSpine, you'd need to:
- Research optimal index strategies for each data type
- Implement partitioning schemes manually
- Tune batch sizes for different workloads
- Handle version tracking and supersession logic

FeedSpine handles all of this automatically based on your data! 🚀
    """)


if __name__ == "__main__":
    asyncio.run(main())
