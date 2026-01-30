#!/usr/bin/env python3
"""
FeedSpine Operational Tracking Example

Demonstrates the complete operational tracking capabilities:
- FeedRun tracking for collection visibility
- Sighting retention (first_seen_at, last_seen_at, seen_count)
- Checkpointing for resumable collections
- Rate limiting for API compliance
- Deduplication with analytics

This is a real-world example showing production-ready feed monitoring.

Usage:
    pip install feedspine[duckdb]
    python examples/06_operational_tracking.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from feedspine import (
    FeedRun,
    FeedRunStatus,
    Layer,
    Record,
    RecordCandidate,
)
from feedspine.models.base import Metadata
from feedspine.core.checkpoint import (
    Checkpoint,
    CheckpointManager,
    FileCheckpointStore,
)
from feedspine.http import RateLimiter

# DuckDB is optional - check if available
try:
    from feedspine import DuckDBStorage

    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    print("Note: Install DuckDB for persistence: pip install feedspine[duckdb]")
    from feedspine import MemoryStorage


# =============================================================================
# Simulated Feed Adapter
# =============================================================================


class SimulatedSECFeed:
    """Simulated SEC filing feed for demonstration.

    Generates realistic-looking filing records to demonstrate
    the operational tracking features without requiring network.
    """

    def __init__(self, name: str = "sec-filings"):
        self.name = name
        self._filings = self._generate_filings()

    def _generate_filings(self) -> list[dict]:
        """Generate simulated SEC filings."""
        companies = [
            ("0001018724", "AMAZON COM INC", "AMZN"),
            ("0001652044", "ALPHABET INC", "GOOGL"),
            ("0000320193", "APPLE INC", "AAPL"),
            ("0000789019", "MICROSOFT CORP", "MSFT"),
            ("0001326801", "META PLATFORMS INC", "META"),
        ]

        form_types = ["10-K", "10-Q", "8-K", "4", "SC 13G"]

        filings = []
        for i, (cik, name, ticker) in enumerate(companies):
            for j, form_type in enumerate(form_types[:3]):  # 3 filings per company
                filings.append(
                    {
                        "accession_number": f"{cik}-24-{i * 3 + j:06d}",
                        "cik": cik,
                        "company_name": name,
                        "ticker": ticker,
                        "form_type": form_type,
                        "filed_date": "2024-01-15",
                        "document_url": f"https://www.sec.gov/Archives/edgar/data/{cik}/filing.htm",
                    }
                )
        return filings

    async def fetch(self) -> list[RecordCandidate]:
        """Fetch simulated filings as RecordCandidates."""
        candidates = []
        for filing in self._filings:
            candidate = RecordCandidate(
                natural_key=filing["accession_number"],
                published_at=datetime.now(UTC),
                content=filing,
                metadata=Metadata(source=self.name),
            )
            candidates.append(candidate)
        return candidates


# =============================================================================
# Operational Tracking Functions
# =============================================================================


def create_feed_run(feed_name: str) -> FeedRun:
    """Create a new FeedRun for tracking this collection."""
    return FeedRun(
        id=str(uuid4()),
        feed_name=feed_name,
        started_at=datetime.now(UTC),
        checkpoint_position={"page": 0},
    )


async def demonstrate_feed_run() -> None:
    """Show FeedRun tracking capabilities."""
    print("\n" + "=" * 60)
    print("1. FeedRun Tracking")
    print("=" * 60)

    # Create and start a run
    run = create_feed_run("sec-daily")
    run = run.start()

    print(f"Run ID: {run.id}")
    print(f"Status: {run.status.value} ({run.status.name})")
    print(f"Started: {run.started_at}")

    # Simulate progress updates
    for i in range(5):
        await asyncio.sleep(0.1)  # Simulate work
        run = run.update_progress(
            items_processed=(i + 1) * 3,
            items_new=(i + 1) * 2,
            items_duplicate=i + 1,
        )

    # Complete the run
    run = run.complete()

    print(f"\nFinal Status: {run.status.value}")
    print(f"Items Processed: {run.items_processed}")
    print(f"Items New: {run.items_new}")
    print(f"Items Duplicate: {run.items_duplicate}")
    print(f"Duration: {run.duration_seconds:.2f}s")
    print(f"Success Rate: {run.success_rate:.1%}")
    print(f"Dedup Rate: {run.dedup_rate:.1%}")

    # Demonstrate serialization
    run_dict = run.to_dict()
    restored_run = FeedRun.from_dict(run_dict)
    print(f"\n✓ Serialization roundtrip successful: {restored_run.id == run.id}")


async def demonstrate_sighting_tracking(storage) -> None:
    """Show record-level sighting tracking."""
    print("\n" + "=" * 60)
    print("2. Sighting Tracking (first/last seen, count)")
    print("=" * 60)

    # Create and store initial records
    feed = SimulatedSECFeed()
    candidates = await feed.fetch()

    print(f"Storing {len(candidates)} initial records...")
    for candidate in candidates[:5]:  # Just first 5 for demo
        record = Record.from_candidate(candidate, record_id=str(uuid4()))
        await storage.store(record)

    # Retrieve and show initial state
    record = await storage.get_by_natural_key(candidates[0].natural_key)
    if record:
        print(f"\nInitial state for {record.natural_key}:")
        print(f"  First seen: {record.first_seen_at}")
        print(f"  Last seen: {record.last_seen_at}")
        print(f"  Seen count: {record.seen_count}")

    # Simulate seeing the same record multiple times
    print("\nSimulating 3 additional sightings...")
    for _ in range(3):
        await asyncio.sleep(0.1)  # Small delay to show timestamp changes
        await storage.record_sighting_on_existing(candidates[0].natural_key)

    # Show updated state
    record = await storage.get_by_natural_key(candidates[0].natural_key)
    if record:
        print(f"\nAfter sightings for {record.natural_key}:")
        print(f"  First seen: {record.first_seen_at} (unchanged)")
        print(f"  Last seen: {record.last_seen_at} (updated)")
        print(f"  Seen count: {record.seen_count}")

        # Demonstrate the optimization
        print("\n✓ This replaces storing every sighting in a separate table!")
        print("  - Space efficient: O(1) per record instead of O(n) per sighting")
        print("  - Query efficient: Directly on record, no joins needed")


async def demonstrate_checkpointing() -> None:
    """Show checkpoint/resume capabilities."""
    print("\n" + "=" * 60)
    print("3. Checkpointing (Resumable Collections)")
    print("=" * 60)

    # Use file-based checkpointing
    checkpoint_dir = Path("./checkpoints")
    checkpoint_dir.mkdir(exist_ok=True)
    store = FileCheckpointStore(checkpoint_dir)

    # Create checkpoint manager
    manager = CheckpointManager(store)

    # Start a collection
    collection_id = "sec-daily-2024-01-15"
    feed_name = "sec-filings"

    checkpoint = manager.start(collection_id, feed_name)
    print(f"Started collection: {collection_id}")
    print(f"Initial position: {checkpoint.position}")

    # Simulate processing with checkpoints
    for page in range(1, 4):
        # Process page...
        await asyncio.sleep(0.1)

        checkpoint = manager.update(
            position={"page": page, "cursor": f"cursor-{page}"},
            records_processed=page * 100,
            records_new=page * 80,
            records_duplicate=page * 20,
        )
        await manager.save()  # Persist checkpoint
        print(f"Checkpoint at page {page}: {checkpoint.records_processed} records")

    # Complete the collection
    checkpoint = await manager.complete()
    print(f"\n✓ Collection completed: {checkpoint.is_complete}")
    print(f"  Total processed: {checkpoint.records_processed}")
    print(f"  New records: {checkpoint.records_new}")
    print(f"  Duplicates: {checkpoint.records_duplicate}")

    # Demonstrate loading checkpoint (for resume)
    loaded = await store.load(collection_id)
    if loaded:
        print(f"\n✓ Checkpoint persisted and loadable")
        print(f"  Can resume from position: {loaded.position}")


async def demonstrate_rate_limiting() -> None:
    """Show rate limiting capabilities."""
    print("\n" + "=" * 60)
    print("4. Rate Limiting")
    print("=" * 60)

    # Create rate limiter (5 requests per second)
    limiter = RateLimiter(rate=5.0)

    print("Making 10 requests with 5 req/s limit...")
    start = datetime.now(UTC)

    for i in range(10):
        wait_time = await limiter.acquire()
        print(f"  Request {i + 1}: waited {wait_time:.3f}s")

    elapsed = (datetime.now(UTC) - start).total_seconds()
    print(f"\nTotal time: {elapsed:.2f}s (expected ~2s for 10 requests at 5/s)")
    print("✓ Rate limiting working correctly")


async def demonstrate_analytics(storage) -> None:
    """Show analytics capabilities with sighting data."""
    print("\n" + "=" * 60)
    print("5. Analytics with Sighting Data")
    print("=" * 60)

    # Only available with DuckDB
    if not hasattr(storage, "execute_sql"):
        print("Analytics queries require DuckDB storage")
        return

    # Query records by sighting count
    results = await storage.execute_sql(
        """
        SELECT 
            natural_key,
            seen_count,
            first_seen_at,
            last_seen_at,
            json_extract_string(content, '$.company_name') as company
        FROM records
        WHERE seen_count > 1
        ORDER BY seen_count DESC
        LIMIT 5
        """
    )

    if results:
        print("\nMost frequently seen records:")
        for r in results:
            print(f"  {r['natural_key']}: {r['seen_count']} times ({r['company']})")

    # Count records by layer
    layer_stats = await storage.execute_sql(
        """
        SELECT 
            layer,
            COUNT(*) as count,
            AVG(seen_count) as avg_sightings
        FROM records
        GROUP BY layer
        """
    )

    if layer_stats:
        print("\nRecords by layer:")
        for stat in layer_stats:
            print(f"  {stat['layer']}: {stat['count']} records, avg {stat['avg_sightings']:.1f} sightings")


async def demonstrate_full_workflow() -> None:
    """Run complete operational tracking workflow."""
    print("\n" + "=" * 60)
    print("6. Complete Workflow Integration")
    print("=" * 60)

    # Create storage and FeedRun
    if HAS_DUCKDB:
        db_path = Path("./operational_demo.db")
        storage = DuckDBStorage(str(db_path))
        print(f"Using DuckDB: {db_path}")
    else:
        storage = MemoryStorage()
        print("Using in-memory storage")

    await storage.initialize()

    try:
        # Create feed run for tracking
        run = create_feed_run("sec-filings")
        run = run.start()
        print(f"\nStarted run: {run.id}")

        # Simulate feed registration and collection
        feed = SimulatedSECFeed()
        candidates = await feed.fetch()

        # Store records with deduplication
        new_count = 0
        dup_count = 0

        for candidate in candidates:
            exists = await storage.exists_by_natural_key(candidate.natural_key)
            if exists:
                # Record sighting on existing
                await storage.record_sighting_on_existing(candidate.natural_key)
                dup_count += 1
            else:
                # Store new record
                record = Record.from_candidate(candidate, record_id=str(uuid4()))
                await storage.store(record)
                new_count += 1

        # Update run with results
        run = run.update_progress(
            items_processed=len(candidates),
            items_new=new_count,
            items_duplicate=dup_count,
        )
        run = run.complete()

        # Print run summary
        print(f"\nRun completed in {run.duration_seconds:.2f}s")
        print(f"  Processed: {run.items_processed}")
        print(f"  New: {run.items_new}")
        print(f"  Duplicates: {run.items_duplicate}")
        print(f"  Dedup rate: {run.dedup_rate:.1%}")

        # Show record stats
        total = await storage.count()
        print(f"\nStorage: {total} total records")

        # Run analytics if available
        await demonstrate_analytics(storage)

    finally:
        await storage.close()


# =============================================================================
# Main Entry Point
# =============================================================================


async def main() -> None:
    """Run all operational tracking demonstrations."""
    print("=" * 60)
    print("FeedSpine Operational Tracking Demo")
    print("=" * 60)

    # Create storage once for shared demos
    if HAS_DUCKDB:
        db_path = Path("./demo.db")
        storage = DuckDBStorage(str(db_path))
    else:
        storage = MemoryStorage()

    await storage.initialize()

    try:
        # Run individual demonstrations
        await demonstrate_feed_run()
        await demonstrate_sighting_tracking(storage)
        await demonstrate_checkpointing()
        await demonstrate_rate_limiting()
        await demonstrate_analytics(storage)
        await demonstrate_full_workflow()

        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)
        print("\nKey takeaways:")
        print("1. FeedRun provides full visibility into collection runs")
        print("2. Sighting tracking prevents table bloat (O(1) vs O(n))")
        print("3. Checkpoints enable resumable long-running collections")
        print("4. Rate limiting ensures API compliance")
        print("5. DuckDB enables rich SQL analytics on sighting data")

    finally:
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
