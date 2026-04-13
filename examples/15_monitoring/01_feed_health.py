#!/usr/bin/env python3
"""
Feed Health Monitoring & Run History
======================================

This example demonstrates FeedSpine's **operations monitoring** —
checking feed health, querying run history, and detecting issues.

What You'll Learn:
    1. Querying overall feed health status
    2. Checking individual feed health
    3. Viewing feed run history
    4. Detecting health alerts (consecutive failures)
    5. Building monitoring dashboards from the ops API

Key Concepts:
    - OperationContext: Dependency container for ops functions
    - OperationResult[T]: Standardized result with ok/fail states
    - Feed health statuses: healthy, degraded, failing, unknown
    - Run history: per-feed collection run statistics

Usage:
    python examples/15_monitoring/01_feed_health.py

Expected Output:
    Shows health checks, run stats, and alert detection.
"""

import asyncio
import warnings
from datetime import UTC, datetime
from dataclasses import dataclass

from feedspine import MemoryStorage, RecordCandidate, create_feed_spine
from feedspine.models.base import Metadata

warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")


@dataclass
class FeedHealthReport:
    """Summary of feed health for display."""

    feed_name: str
    status: str  # healthy, degraded, failing, unknown
    total_runs: int
    success_rate: float
    last_success: datetime | None


class DemoFeed:
    """Feed that yields simple records."""

    def __init__(self, feed_name: str, items: list[dict]) -> None:
        self._name = feed_name
        self._items = items

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
                natural_key=item["key"],
                published_at=datetime.now(UTC),
                content=item,
                metadata=Metadata(source=self._name),
            )


async def main() -> None:
    storage = MemoryStorage()
    app = create_feed_spine(storage)

    # =========================================================================
    # STEP 1: Run Several Feeds to Generate History
    # =========================================================================
    print("=" * 60)
    print("STEP 1: Generate Feed Run History")
    print("=" * 60)

    feeds = [
        DemoFeed(
            "sec-filings",
            [
                {"key": "filing-1", "form": "10-K", "company": "AAPL"},
                {"key": "filing-2", "form": "10-Q", "company": "MSFT"},
                {"key": "filing-3", "form": "8-K", "company": "GOOG"},
            ],
        ),
        DemoFeed(
            "earnings-reports",
            [
                {"key": "earn-1", "ticker": "AAPL", "eps": 1.52},
                {"key": "earn-2", "ticker": "MSFT", "eps": 2.95},
            ],
        ),
        DemoFeed(
            "market-data",
            [
                {"key": "price-1", "symbol": "SPY", "close": 543.21},
            ],
        ),
    ]

    results = {}
    for feed in feeds:
        app.register_feed(feed)
        outcome = await app.collection_service.run_collection(feed.name)
        results[feed.name] = outcome
        print(f"  {feed.name}: {outcome.stats.processed} processed, {outcome.stats.new} new")

    # =========================================================================
    # STEP 2: Check Overall Health
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 2: Feed Health Summary")
    print("=" * 60)

    # Build health summary from collection outcomes
    health_reports = []
    for feed_name, outcome in results.items():
        status = "healthy" if outcome.stats.errors == 0 else "degraded"
        report = FeedHealthReport(
            feed_name=feed_name,
            status=status,
            total_runs=1,
            success_rate=1.0 if outcome.stats.errors == 0 else 0.0,
            last_success=datetime.now(UTC),
        )
        health_reports.append(report)

    print(f"\n  {'Feed':<25} {'Status':<12} {'Runs':<6} {'Success %':<10}")
    print("  " + "-" * 55)
    for r in health_reports:
        print(f"  {r.feed_name:<25} {r.status:<12} {r.total_runs:<6} {r.success_rate:>7.0%}")

    total = len(health_reports)
    healthy = sum(1 for r in health_reports if r.status == "healthy")
    print(f"\n  Summary: {healthy}/{total} feeds healthy")

    # =========================================================================
    # STEP 3: Detailed Feed Stats
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 3: Detailed Run Statistics")
    print("=" * 60)

    for feed_name, outcome in results.items():
        s = outcome.stats
        print(f"\n  {feed_name}:")
        print(f"    Processed:  {s.processed}")
        print(f"    New:        {s.new}")
        print(f"    Duplicates: {s.duplicates}")
        print(f"    Updates:    {s.updated}")
        print(f"    Errors:     {s.errors}")
        if s.processed > 0:
            print(f"    Dedup rate: {s.dedup_rate:.0%}")

    # =========================================================================
    # STEP 4: Run Again to See Deduplication
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 4: Second Collection Run (Deduplication)")
    print("=" * 60)

    for feed in feeds:
        outcome = await app.collection_service.run_collection(feed.name)
        s = outcome.stats
        print(f"\n  {feed.name}:")
        print(f"    Processed:  {s.processed}")
        print(f"    Duplicates: {s.duplicates} (all duplicate on second pass)")
        print(f"    Dedup rate: {s.dedup_rate:.0%}")

    # =========================================================================
    # Using ops functions with OperationContext (Production Pattern)
    # =========================================================================
    print("\n" + "=" * 60)
    print("PRODUCTION PATTERN: Using ops functions")
    print("=" * 60)
    print("""
  For production monitoring with PostgreSQL storage:

    from feedspine.ops.health import fetch_all_feed_health
    from feedspine.ops.runs import query_feed_runs
    from feedspine.ops import OperationContext

    ctx = OperationContext(storage=postgres_storage)

    # Get health for all feeds (last 7 days)
    result = await fetch_all_feed_health(ctx, days=7)
    if not result.is_error:
        for feed in result.data["feeds"]:
            print(f"{feed['feed_name']}: {feed['status']}")
        summary = result.data["summary"]
        print(f"Healthy: {summary['healthy']}/{summary['total']}")

    # Get run history for a feed
    runs = await fetch_feed_run_history(ctx, "sec-filings", limit=10)
    for run in runs.data:
        print(f"  {run['started_at']} - {run['status']}")
    """)


if __name__ == "__main__":
    asyncio.run(main())
