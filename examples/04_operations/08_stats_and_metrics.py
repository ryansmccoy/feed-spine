#!/usr/bin/env python3
"""
FeedSpine Stats and Metrics Example

Demonstrates the enhanced statistics and metrics capabilities:
- Storage summary (records, sightings by layer)
- Collection run aggregations
- Per-feed collection statistics
- Record distribution visualizations
- Time-series collection trends

Uses FeedRepository for complete stats including feed_runs.

These stats are available via:
- CLI: `feedspine stats`
- API: `GET /api/v1/stats/`
- Python: `repo.get_stats()`

Usage:
    python examples/04_operations/08_stats_and_metrics.py
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from feedspine import Layer
from feedspine.storage.dialect import SQLiteDialect
from feedspine.storage.feed_repository import FeedRepository


def create_demo_records(repo: FeedRepository, now: datetime) -> None:
    """Create demo records across layers."""
    layers = [
        (Layer.BRONZE, 50, "Raw ingested data"),
        (Layer.SILVER, 30, "Cleaned/validated data"),
        (Layer.GOLD, 10, "Curated/enriched data"),
    ]

    for layer, count, desc in layers:
        print(f"   Creating {count} {layer.value} records ({desc})...")
        for i in range(count):
            record_id = str(uuid4())
            row = {
                "id": record_id,
                "natural_key": f"{layer.value}:record:{i:04d}",
                "layer": layer.value,
                "content": f'{{"index": {i}, "layer": "{layer.value}", "data": "Sample"}}',
                "metadata": '{"source": "demo"}',
                "published_at": (now - timedelta(days=i % 30)).isoformat(),
                "captured_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "version": 1,
                "first_seen_at": now.isoformat(),
                "last_seen_at": now.isoformat(),
                "seen_count": 1 + (i % 5),  # Vary seen count
            }
            repo.insert("records", row)

    repo.commit()


def create_demo_runs(repo: FeedRepository, now: datetime) -> None:
    """Create demo feed runs with varying success patterns."""
    feeds = [
        ("sec-filings", 85, 15, 150),  # 85% success, avg 150 records
        ("sec-press-releases", 95, 5, 25),  # 95% success, avg 25 records
        ("sec-speeches", 70, 10, 12),  # 70% success, avg 12 records
        ("sec-exhibits", 60, 8, 45),  # 60% success, avg 45 records
    ]

    for feed_name, success_pct, run_count, avg_records in feeds:
        print(f"   Creating {run_count} runs for '{feed_name}'...")
        for i in range(run_count):
            run_id = str(uuid4())
            run_time = now - timedelta(hours=i * 6)  # Every 6 hours

            # Simulate success/failure based on percentage
            import random

            random.seed(i + hash(feed_name))
            is_success = random.randint(1, 100) <= success_pct

            variance = random.randint(-avg_records // 3, avg_records // 3)
            records = max(0, avg_records + variance) if is_success else 0

            repo.start_feed_run(
                run_id=run_id,
                feed_name=feed_name,
                started_at=run_time,
            )

            if is_success:
                repo.complete_feed_run(
                    run_id=run_id,
                    status="completed",
                    records_fetched=records,
                    records_new=records // 2,
                    records_updated=records // 4,
                    records_unchanged=records // 4,
                )
            else:
                repo.complete_feed_run(
                    run_id=run_id,
                    status="failed",
                    error_message="Simulated failure for demo",
                )

    repo.commit()


def get_layer_stats(repo: FeedRepository) -> dict[str, int]:
    """Get record counts by layer."""
    result = repo.query("SELECT layer, COUNT(*) as count FROM records GROUP BY layer")
    return {r["layer"]: r["count"] for r in result}


def get_feed_run_stats(repo: FeedRepository) -> list[dict[str, Any]]:
    """Get aggregated stats per feed."""
    result = repo.query("""
        SELECT
            feed_name,
            COUNT(*) as total_runs,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(records_new) as total_new_records,
            AVG(CASE WHEN status = 'completed' THEN records_new ELSE NULL END) as avg_records
        FROM feed_runs
        GROUP BY feed_name
        ORDER BY total_runs DESC
    """)
    return list(result)


def get_collection_trend(repo: FeedRepository, days: int = 7) -> list[dict[str, Any]]:
    """Get daily collection trends."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    result = repo.query(
        """
        SELECT
            DATE(started_at) as date,
            COUNT(*) as runs,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
            SUM(records_new) as new_records
        FROM feed_runs
        WHERE started_at >= ?
        GROUP BY DATE(started_at)
        ORDER BY date DESC
    """,
        (cutoff,),
    )
    return list(result)


def main() -> None:
    """Demonstrate stats and metrics capabilities."""
    print("=" * 70)
    print("  FeedSpine Stats and Metrics Example")
    print("=" * 70)
    print()

    db_path = Path("stats_demo.db")

    # Clean up any existing demo database
    if db_path.exists():
        db_path.unlink()

    # Create SQLite connection with FeedRepository
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    repo = FeedRepository(conn, SQLiteDialect())
    repo.ensure_schema()

    now = datetime.now(UTC)

    # =========================================================================
    # 1. Populate Demo Data
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  1. POPULATING DEMO DATA" + " " * 43 + "|")
    print("+" + "-" * 68 + "+")
    print()

    create_demo_records(repo, now)
    create_demo_runs(repo, now)
    print()

    # =========================================================================
    # 2. Basic Storage Stats
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  2. STORAGE OVERVIEW" + " " * 47 + "|")
    print("+" + "-" * 68 + "+")
    print()

    total_records = repo.count_records()
    total_sightings = repo.count_sightings()

    print(f"   Total records:   {total_records:>6}")
    print(f"   Total sightings: {total_sightings:>6}")
    print()

    # =========================================================================
    # 3. Record Distribution by Layer
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  3. RECORD DISTRIBUTION BY LAYER" + " " * 34 + "|")
    print("+" + "-" * 68 + "+")
    print()

    layer_stats = get_layer_stats(repo)
    total = sum(layer_stats.values())

    for layer in ["bronze", "silver", "gold"]:
        count = layer_stats.get(layer, 0)
        pct = count / total if total > 0 else 0
        bar_len = int(pct * 40)
        bar = "#" * bar_len + "." * (40 - bar_len)
        print(f"   {layer.title():<8} [{bar}] {count:>4} ({pct:>5.1%})")

    print()

    # =========================================================================
    # 4. Collection Run Stats by Feed
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  4. COLLECTION STATISTICS BY FEED" + " " * 33 + "|")
    print("+" + "-" * 68 + "+")
    print()

    feed_stats = get_feed_run_stats(repo)

    print(f"   {'Feed':<22} {'Runs':>6} {'OK':>6} {'Fail':>6} {'Success':>8} {'Records':>8}")
    print("   " + "-" * 64)

    for stat in feed_stats:
        success_rate = stat["successful"] / stat["total_runs"] * 100 if stat["total_runs"] > 0 else 0
        avg_records = stat["avg_records"] or 0
        print(
            f"   {stat['feed_name']:<22} "
            f"{stat['total_runs']:>6} "
            f"{stat['successful']:>6} "
            f"{stat['failed']:>6} "
            f"{success_rate:>7.0f}% "
            f"{avg_records:>8.1f}"
        )

    # Totals
    total_runs = sum(s["total_runs"] for s in feed_stats)
    total_success = sum(s["successful"] for s in feed_stats)
    total_failed = sum(s["failed"] for s in feed_stats)
    overall_rate = total_success / total_runs * 100 if total_runs > 0 else 0
    total_records_new = sum(s["total_new_records"] or 0 for s in feed_stats)

    print("   " + "-" * 64)
    print(
        f"   {'TOTAL':<22} "
        f"{total_runs:>6} "
        f"{total_success:>6} "
        f"{total_failed:>6} "
        f"{overall_rate:>7.0f}% "
        f"{total_records_new:>8}"
    )
    print()

    # =========================================================================
    # 5. Collection Trend (Last 7 Days)
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  5. COLLECTION TREND (Last 7 Days)" + " " * 32 + "|")
    print("+" + "-" * 68 + "+")
    print()

    trends = get_collection_trend(repo, days=7)

    if trends:
        max_runs = max((t["runs"] for t in trends), default=1)

        print(f"   {'Date':<12} {'Runs':>6} {'OK':>6} {'Records':>8}  Chart")
        print("   " + "-" * 58)

        for t in trends[:7]:
            bar_len = int((t["runs"] / max_runs) * 25) if max_runs > 0 else 0
            bar = "|" * bar_len
            records = t["new_records"] or 0
            print(f"   {t['date']:<12} {t['runs']:>6} {t['successful']:>6} {records:>8}  {bar}")
    else:
        print("   No recent collection data")

    print()

    # =========================================================================
    # 6. Summary Dashboard
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  6. SUMMARY DASHBOARD" + " " * 46 + "|")
    print("+" + "-" * 68 + "+")
    print()

    print("   +---------------------------+---------------------------+")
    print(f"   |  Records:     {total_records:>10}  |  Collection Runs: {total_runs:>6}  |")
    print(f"   |  Sightings:   {total_sightings:>10}  |  Success Rate:  {overall_rate:>6.0f}%  |")
    print("   +---------------------------+---------------------------+")
    print()

    # Health indicator
    if overall_rate >= 80:
        status = "[OK] Healthy"
    elif overall_rate >= 60:
        status = "[!!] Attention Needed"
    else:
        status = "[XX] Critical"

    print(f"   Overall System Status: {status}")
    print()

    # =========================================================================
    # 7. CLI and API Reference
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  7. ACCESS STATS VIA CLI AND API" + " " * 34 + "|")
    print("+" + "-" * 68 + "+")
    print()
    print("   CLI Commands:")
    print("   +--------------------------------------------------------------+")
    print("   |  feedspine stats               # Full stats summary         |")
    print("   |  feedspine stats --json        # JSON output                |")
    print("   |  feedspine stats --feed sec-*  # Filter by feed pattern     |")
    print("   +--------------------------------------------------------------+")
    print()
    print("   API Endpoints:")
    print("   +--------------------------------------------------------------+")
    print("   |  GET /api/v1/stats/            # Full stats                 |")
    print("   |  GET /api/v1/stats/storage     # Storage-only stats         |")
    print("   |  GET /api/v1/stats/collection  # Collection run stats       |")
    print("   +--------------------------------------------------------------+")
    print()

    # =========================================================================
    # Cleanup
    # =========================================================================
    conn.close()

    print("=" * 70)
    print("  Stats and Metrics Example Complete")
    print("=" * 70)
    print()
    print("   Database preserved at: stats_demo.db")
    print("   Inspect with: sqlite3 stats_demo.db 'SELECT * FROM feed_runs'")
    print()


if __name__ == "__main__":
    main()
