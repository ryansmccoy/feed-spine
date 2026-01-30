#!/usr/bin/env python
"""
Example: Data Type Aware Storage

Demonstrates how FeedSpine automatically optimizes storage based on data type.

Features demonstrated:
- Data type detection from records
- Automatic storage recommendations
- Observation-specific storage with supersession tracking
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from feedspine.storage import (
    DataType,
    get_config_for_type,
    get_storage_recommendations,
    create_storage,
)


async def main():
    print("=" * 60)
    print("FeedSpine Data Type Storage Optimization")
    print("=" * 60)
    
    # =========================================================================
    # 1. Show configurations for each data type
    # =========================================================================
    print("\n📊 DATA TYPE CONFIGURATIONS\n")
    
    for dt in DataType:
        if dt in (DataType.AUTO_DETECT, DataType.GENERIC):
            continue
            
        config = get_config_for_type(dt)
        print(f"  {dt.value.upper()}:")
        print(f"    Partition by: {config.partition_by or 'None'} ({config.partition_interval})")
        print(f"    Primary index: {config.primary_index}")
        print(f"    Batch size: {config.batch_size:,}")
        print(f"    BRIN index: {config.use_brin}, GIN index: {config.use_gin}")
        print(f"    Versioning: {config.enable_versioning}, Supersession: {config.enable_supersession}")
        print()
    
    # =========================================================================
    # 2. Show scaling recommendations
    # =========================================================================
    print("\n📈 SCALING RECOMMENDATIONS\n")
    
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
        print(f"  {name:<10} {rows:>14,} {rec['backend']:<12} "
              f"{'Yes' if rec['partitioning']['enabled'] else 'No':<10} "
              f"{'Yes' if rec['compression']['enabled'] else 'No'}")
    
    # =========================================================================
    # 3. Create storage with recommendations
    # =========================================================================
    print("\n🔧 CREATING STORAGE WITH AUTO-CONFIG\n")
    
    # For demonstration, use SQLite
    storage = create_storage("sqlite:///:memory:")
    await storage.initialize()
    
    print("  ✓ Storage initialized")
    
    # Store some sample data
    import uuid
    from feedspine.models.record import Record, RecordCandidate
    from feedspine.models.base import Metadata
    
    records = []
    for i in range(10):
        candidate = RecordCandidate(
            natural_key=f"obs:{i}",
            published_at=datetime.now(timezone.utc),
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
    
    print(f"  ✓ Stored {len(records)} records")
    
    # Query back
    count = 0
    async for rec in storage.query():
        count += 1
    
    print(f"  ✓ Retrieved {count} records")
    
    # =========================================================================
    # 4. Demonstrate data type detection
    # =========================================================================
    print("\n🔍 DATA TYPE DETECTION\n")
    
    from feedspine.storage.data_types import detect_data_type
    
    # Sample records for each type
    test_cases = [
        (
            "Observation-like",
            [
                {"entity_id": "AAPL", "metric": "eps", "period": "2024:Q1", "value": 1.50, "as_of": "2024-01-15"},
                {"entity_id": "GOOGL", "metric": "revenue", "period": "2024:Q1", "value": 80000000000, "as_of": "2024-01-20"},
            ],
        ),
        (
            "Event-like",
            [
                {"entity_id": "AAPL", "event_type": "earnings_call", "scheduled_at": "2024-01-25", "status": "confirmed"},
                {"entity_id": "GOOGL", "event_type": "dividend", "scheduled_at": "2024-02-15", "status": "announced"},
            ],
        ),
        (
            "Entity-like",
            [
                {"entity_type": "company", "name": "Apple Inc", "identifiers": {"cik": "0000320193", "ticker": "AAPL"}},
                {"entity_type": "company", "name": "Alphabet Inc", "identifiers": {"cik": "0001652044", "ticker": "GOOGL"}},
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
        print(f"  {name:20} → Detected as: {detected.value}")
    
    print("\n" + "=" * 60)
    print("✓ Data type storage demonstration complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
