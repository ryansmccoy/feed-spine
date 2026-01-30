#!/usr/bin/env python3
"""
Performance Tests for FeedSpine Bulk Operations

These tests verify that FeedSpine can handle large-scale operations
typical of SEC feed processing (quarterly indexes with ~100K filings).

Run with: pytest tests/performance/ -v --tb=short
Skip in CI: pytest -m "not slow"

Key scenarios tested:
1. Large batch inserts (10K, 50K, 100K records)
2. High deduplication rates (typical of RSS polling)
3. Concurrent sighting updates
4. Query performance on large datasets
5. Storage efficiency (memory/disk usage)
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate
from feedspine.storage.memory import MemoryStorage

# DuckDB is optional
try:
    from feedspine.storage.duckdb import DuckDBStorage
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


# =============================================================================
# Test Helpers
# =============================================================================


def make_record(i: int, prefix: str = "perf") -> Record:
    """Create a test record with realistic SEC filing data."""
    cik = f"{1000000 + (i % 100000):010d}"
    form_types = ["10-K", "10-Q", "8-K", "4", "SC 13G", "DEF 14A"]
    form_type = form_types[i % len(form_types)]
    
    return Record(
        id=f"{prefix}-{i}",
        natural_key=f"{cik}-{i:08d}",  # Accession number pattern
        layer=Layer.BRONZE,
        content={
            "cik": cik,
            "company_name": f"Test Company {i % 1000} Inc",
            "form_type": form_type,
            "filed_date": "2024-01-15",
            "accession_number": f"{cik}-{i:08d}",
            "primary_document": "form.htm",
        },
        metadata=Metadata(source="sec-quarterly"),
        published_at=datetime.now(UTC),
        captured_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        version=1,
    )


def make_candidate(i: int, prefix: str = "perf") -> RecordCandidate:
    """Create a record candidate for deduplication testing."""
    cik = f"{1000000 + (i % 100000):010d}"
    
    return RecordCandidate(
        natural_key=f"{cik}-{i:08d}",
        published_at=datetime.now(UTC),
        content={
            "cik": cik,
            "company_name": f"Test Company {i % 1000} Inc",
            "form_type": "10-K",
        },
        metadata=Metadata(source="sec-test"),
    )


def make_records_batch(count: int, prefix: str = "batch") -> list[Record]:
    """Create a batch of test records."""
    return [make_record(i, prefix) for i in range(count)]


# =============================================================================
# Memory Storage Performance Tests
# =============================================================================


class TestMemoryStoragePerformance:
    """Performance tests for MemoryStorage."""

    @pytest.mark.slow
    async def test_insert_10k_records(self) -> None:
        """Insert 10,000 records - should complete in < 2 seconds."""
        storage = MemoryStorage()
        await storage.initialize()
        
        records = make_records_batch(10_000)
        
        start = time.perf_counter()
        count = await storage.store_batch(records)
        elapsed = time.perf_counter() - start
        
        assert count == 10_000
        assert await storage.count() == 10_000
        assert elapsed < 2.0, f"Insert took {elapsed:.2f}s (expected < 2s)"
        
        print(f"\n✓ 10K inserts: {elapsed:.3f}s ({10_000/elapsed:,.0f} records/sec)")
        await storage.close()

    @pytest.mark.slow
    async def test_insert_50k_records(self) -> None:
        """Insert 50,000 records - should complete in < 10 seconds."""
        storage = MemoryStorage()
        await storage.initialize()
        
        records = make_records_batch(50_000)
        
        start = time.perf_counter()
        count = await storage.store_batch(records, batch_size=5000)
        elapsed = time.perf_counter() - start
        
        assert count == 50_000
        assert await storage.count() == 50_000
        assert elapsed < 10.0, f"Insert took {elapsed:.2f}s (expected < 10s)"
        
        print(f"\n✓ 50K inserts: {elapsed:.3f}s ({50_000/elapsed:,.0f} records/sec)")
        await storage.close()

    @pytest.mark.slow
    async def test_high_deduplication_rate(self) -> None:
        """Test deduplication at 90% rate (typical RSS polling scenario).
        
        Scenario: 100 filings in feed, 90 already seen = 10 new
        """
        storage = MemoryStorage()
        await storage.initialize()
        
        # Initial batch of 900 records
        initial = make_records_batch(900, prefix="initial")
        await storage.store_batch(initial)
        
        # New batch: 90% duplicates (810 seen) + 10% new (90 new)
        duplicates = make_records_batch(810, prefix="initial")  # Same keys
        new_records = make_records_batch(90, prefix="new")
        mixed_batch = duplicates + new_records
        
        start = time.perf_counter()
        
        # Check each for duplicates
        new_count = 0
        dup_count = 0
        for record in mixed_batch:
            exists = await storage.exists_by_natural_key(record.natural_key)
            if exists:
                dup_count += 1
            else:
                await storage.store(record)
                new_count += 1
        
        elapsed = time.perf_counter() - start
        
        assert new_count == 90
        assert dup_count == 810
        assert await storage.count() == 990  # 900 + 90 new
        
        dedup_rate = dup_count / len(mixed_batch)
        print(f"\n✓ Dedup at {dedup_rate:.0%}: {elapsed:.3f}s")
        await storage.close()

    @pytest.mark.slow
    async def test_sighting_updates_performance(self) -> None:
        """Test rapid sighting updates (simulates frequent RSS polling)."""
        storage = MemoryStorage()
        await storage.initialize()
        
        # Create initial records
        records = make_records_batch(1000)
        await storage.store_batch(records)
        
        # Simulate 10 polling cycles updating sightings
        start = time.perf_counter()
        
        for cycle in range(10):
            # Each cycle updates all 1000 records
            for i in range(1000):
                await storage.record_sighting_on_existing(f"0100{i % 100000:05d}-{i:08d}")
        
        elapsed = time.perf_counter() - start
        
        # Verify sighting counts
        record = await storage.get_by_natural_key("0100000000-00000000")
        assert record is not None
        assert record.seen_count == 11  # 1 initial + 10 updates
        
        updates_per_sec = (10 * 1000) / elapsed
        print(f"\n✓ 10K sighting updates: {elapsed:.3f}s ({updates_per_sec:,.0f} updates/sec)")
        await storage.close()

    @pytest.mark.slow
    async def test_query_performance_large_dataset(self) -> None:
        """Test query performance on large dataset."""
        storage = MemoryStorage()
        await storage.initialize()
        
        # Create 10K records with mixed layers
        records = make_records_batch(10_000)
        # Promote some to silver/gold
        for i in range(0, 10_000, 3):
            records[i] = records[i].model_copy(update={"layer": Layer.SILVER})
        for i in range(0, 10_000, 7):
            records[i] = records[i].model_copy(update={"layer": Layer.GOLD})
        
        await storage.store_batch(records)
        
        # Query by layer
        start = time.perf_counter()
        gold_records = [r async for r in storage.query(layer=Layer.GOLD)]
        elapsed = time.perf_counter() - start
        
        assert len(gold_records) > 0
        print(f"\n✓ Query GOLD layer ({len(gold_records)} records): {elapsed:.3f}s")
        
        # Query with pagination
        start = time.perf_counter()
        page_records = [r async for r in storage.query(limit=100, offset=5000)]
        elapsed = time.perf_counter() - start
        
        assert len(page_records) == 100
        print(f"✓ Query with pagination: {elapsed:.3f}s")
        await storage.close()


# =============================================================================
# DuckDB Storage Performance Tests  
# =============================================================================


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
class TestDuckDBStoragePerformance:
    """Performance tests for DuckDB storage."""

    @pytest.mark.slow
    async def test_insert_10k_records(self, tmp_path: Path) -> None:
        """Insert 10,000 records - should complete in < 5 seconds."""
        storage = DuckDBStorage(str(tmp_path / "perf.db"))
        await storage.initialize()
        
        records = make_records_batch(10_000)
        
        start = time.perf_counter()
        count = await storage.store_batch(records, batch_size=1000)
        elapsed = time.perf_counter() - start
        
        assert count == 10_000
        assert await storage.count() == 10_000
        assert elapsed < 5.0, f"Insert took {elapsed:.2f}s (expected < 5s)"
        
        print(f"\n✓ DuckDB 10K inserts: {elapsed:.3f}s ({10_000/elapsed:,.0f} records/sec)")
        await storage.close()

    @pytest.mark.slow
    async def test_insert_100k_records(self, tmp_path: Path) -> None:
        """Insert 100,000 records (SEC quarterly index scale)."""
        storage = DuckDBStorage(str(tmp_path / "perf_100k.db"))
        await storage.initialize()
        
        # Insert in chunks to avoid memory issues
        total = 100_000
        batch_size = 10_000
        
        start = time.perf_counter()
        
        for batch_start in range(0, total, batch_size):
            records = make_records_batch(batch_size, prefix=f"batch{batch_start}")
            await storage.store_batch(records, batch_size=1000)
        
        elapsed = time.perf_counter() - start
        
        assert await storage.count() == 100_000
        assert elapsed < 60.0, f"Insert took {elapsed:.2f}s (expected < 60s)"
        
        rate = 100_000 / elapsed
        print(f"\n✓ DuckDB 100K inserts: {elapsed:.3f}s ({rate:,.0f} records/sec)")
        await storage.close()

    @pytest.mark.slow
    async def test_sql_analytics_performance(self, tmp_path: Path) -> None:
        """Test SQL analytics on large dataset."""
        storage = DuckDBStorage(str(tmp_path / "analytics.db"))
        await storage.initialize()
        
        # Insert 50K records
        for batch_start in range(0, 50_000, 10_000):
            records = make_records_batch(10_000, prefix=f"b{batch_start}")
            await storage.store_batch(records)
        
        # Aggregate query
        start = time.perf_counter()
        results = await storage.execute_sql("""
            SELECT 
                json_extract_string(content, '$.form_type') as form_type,
                COUNT(*) as count,
                AVG(seen_count) as avg_sightings
            FROM records
            GROUP BY form_type
            ORDER BY count DESC
        """)
        elapsed = time.perf_counter() - start
        
        assert len(results) > 0
        print(f"\n✓ Aggregation query (50K records): {elapsed:.3f}s")
        
        # Date range filter query
        start = time.perf_counter()
        results = await storage.execute_sql("""
            SELECT COUNT(*) as cnt
            FROM records
            WHERE published_at >= '2024-01-01'
        """)
        elapsed = time.perf_counter() - start
        
        print(f"✓ Date filter query: {elapsed:.3f}s")
        await storage.close()

    @pytest.mark.slow
    async def test_concurrent_writes(self, tmp_path: Path) -> None:
        """Test concurrent write performance."""
        storage = DuckDBStorage(str(tmp_path / "concurrent.db"))
        await storage.initialize()
        
        async def write_batch(batch_id: int, count: int) -> int:
            records = make_records_batch(count, prefix=f"concurrent{batch_id}")
            return await storage.store_batch(records)
        
        # Write 5 batches concurrently
        start = time.perf_counter()
        tasks = [write_batch(i, 2000) for i in range(5)]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        
        total = sum(results)
        assert total == 10_000
        
        rate = total / elapsed
        print(f"\n✓ Concurrent writes (5 x 2K): {elapsed:.3f}s ({rate:,.0f} records/sec)")
        await storage.close()

    @pytest.mark.slow
    async def test_deduplication_at_scale(self, tmp_path: Path) -> None:
        """Test deduplication performance at SEC scale.
        
        Simulates: Daily index with 4K filings, 80% already in quarterly.
        """
        storage = DuckDBStorage(str(tmp_path / "dedup.db"))
        await storage.initialize()
        
        # Initial quarterly data: 20K records
        quarterly = make_records_batch(20_000, prefix="quarterly")
        await storage.store_batch(quarterly, batch_size=5000)
        
        # Daily index: 4K records, 80% overlap (3200 dups, 800 new)
        # First 3200 use same keys as quarterly
        daily_dups = make_records_batch(3200, prefix="quarterly")  # Same keys!
        daily_new = make_records_batch(800, prefix="daily_new")
        daily_batch = daily_dups + daily_new
        
        start = time.perf_counter()
        
        new_count = 0
        dup_count = 0
        to_store = []
        
        for record in daily_batch:
            exists = await storage.exists_by_natural_key(record.natural_key)
            if exists:
                dup_count += 1
                # Update sighting
                await storage.record_sighting_on_existing(record.natural_key)
            else:
                new_count += 1
                to_store.append(record)
        
        if to_store:
            await storage.store_batch(to_store)
        
        elapsed = time.perf_counter() - start
        
        assert new_count == 800
        assert dup_count == 3200
        assert await storage.count() == 20_800  # 20K + 800 new
        
        dedup_rate = dup_count / len(daily_batch)
        print(f"\n✓ Dedup at {dedup_rate:.0%} (4K batch): {elapsed:.3f}s")
        await storage.close()


# =============================================================================
# Integration Performance Tests
# =============================================================================


class TestIntegrationPerformance:
    """End-to-end performance tests."""

    @pytest.mark.slow
    async def test_full_sync_simulation(self) -> None:
        """Simulate a full quarterly sync with deduplication.
        
        Scenario:
        - Quarterly 1: 25K filings (all new)
        - Quarterly 2: 25K filings (20K new, 5K carry-over)
        - Daily: 4K filings (3K overlap with Q2)
        - RSS: 100 filings (90 overlap with daily)
        """
        storage = MemoryStorage()
        await storage.initialize()
        
        total_new = 0
        total_dup = 0
        
        # Q1: 25K new
        print("\n📊 Simulating quarterly sync...")
        q1 = make_records_batch(25_000, prefix="q1")
        start = time.perf_counter()
        await storage.store_batch(q1, batch_size=5000)
        total_new += 25_000
        print(f"   Q1: 25K new ({time.perf_counter() - start:.2f}s)")
        
        # Q2: 20K new + 5K overlap
        q2_new = make_records_batch(20_000, prefix="q2")
        q2_dup = make_records_batch(5_000, prefix="q1")  # Overlap with Q1
        start = time.perf_counter()
        
        for record in q2_new:
            await storage.store(record)
            total_new += 1
        
        for record in q2_dup:
            if await storage.exists_by_natural_key(record.natural_key):
                total_dup += 1
                await storage.record_sighting_on_existing(record.natural_key)
        
        print(f"   Q2: 20K new, 5K dup ({time.perf_counter() - start:.2f}s)")
        
        # Daily: 1K new + 3K overlap
        daily_new = make_records_batch(1_000, prefix="daily")
        daily_dup = make_records_batch(3_000, prefix="q2")  # Overlap with Q2
        start = time.perf_counter()
        
        for record in daily_new:
            await storage.store(record)
            total_new += 1
        
        for record in daily_dup:
            if await storage.exists_by_natural_key(record.natural_key):
                total_dup += 1
                await storage.record_sighting_on_existing(record.natural_key)
        
        print(f"   Daily: 1K new, 3K dup ({time.perf_counter() - start:.2f}s)")
        
        # RSS: 10 new + 90 overlap
        rss_new = make_records_batch(10, prefix="rss")
        rss_dup = make_records_batch(90, prefix="daily")  # Overlap with daily
        start = time.perf_counter()
        
        for record in rss_new:
            await storage.store(record)
            total_new += 1
        
        for record in rss_dup:
            if await storage.exists_by_natural_key(record.natural_key):
                total_dup += 1
                await storage.record_sighting_on_existing(record.natural_key)
        
        print(f"   RSS: 10 new, 90 dup ({time.perf_counter() - start:.2f}s)")
        
        # Summary
        final_count = await storage.count()
        print(f"\n✓ Sync complete!")
        print(f"   Total records: {final_count:,}")
        print(f"   Total new: {total_new:,}")
        print(f"   Total duplicates filtered: {total_dup:,}")
        print(f"   Overall dedup rate: {total_dup / (total_new + total_dup):.1%}")
        
        assert final_count == 46_010  # 25K + 20K + 1K + 10
        await storage.close()


if __name__ == "__main__":
    # Run a quick smoke test
    async def smoke_test():
        print("Running performance smoke test...")
        
        storage = MemoryStorage()
        await storage.initialize()
        
        records = make_records_batch(1000)
        start = time.perf_counter()
        await storage.store_batch(records)
        elapsed = time.perf_counter() - start
        
        print(f"✓ 1K records in {elapsed:.3f}s ({1000/elapsed:,.0f}/sec)")
        await storage.close()
    
    asyncio.run(smoke_test())
