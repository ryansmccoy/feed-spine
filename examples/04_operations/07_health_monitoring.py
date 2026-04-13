#!/usr/bin/env python3
"""
FeedSpine Health Monitoring Example

Demonstrates the feed health monitoring capabilities:
- Calculating feed health metrics (RAG status)
- Getting health for individual feeds
- Aggregating health across all feeds
- Identifying failing feeds with alerts

Health uses RAG (Red/Amber/Green) status based on:
- Success rate (>80% = green, 50-80% = amber, <50% = red)
- Consecutive failures (<3 = green, 3-5 = amber, >5 = red)

Storage:
    Uses FeedRepository with SQLite for persistent run tracking.
    FeedRepository provides feed_runs table for health calculations.

Usage:
    python examples/04_operations/07_health_monitoring.py
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from feedspine.storage.dialect import SQLiteDialect

# FeedRepository for persistent run tracking
from feedspine.storage.feed_repository import FeedRepository


def calculate_health(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate health metrics from feed runs.

    Args:
        runs: List of feed run dictionaries (most recent first)

    Returns:
        Health metrics dictionary with status, success_rate, etc.
    """
    if not runs:
        return {
            "status": "unknown",
            "success_rate": 0.0,
            "total_runs": 0,
            "consecutive_failures": 0,
            "avg_records_per_run": 0.0,
            "last_success": None,
        }

    total = len(runs)
    successes = sum(1 for r in runs if r.get("status") == "completed")
    success_rate = successes / total if total > 0 else 0.0

    # Count consecutive failures from most recent
    consecutive_failures = 0
    for run in runs:
        if run.get("status") == "completed":
            break
        consecutive_failures += 1

    # Calculate average records
    total_records = sum(r.get("records_new", 0) or 0 for r in runs if r.get("status") == "completed")
    successful_runs = max(1, successes)
    avg_records = total_records / successful_runs

    # Find last success
    last_success = None
    for run in runs:
        if run.get("status") == "completed":
            last_success = run.get("completed_at")
            break

    # Determine RAG status
    if success_rate >= 0.8 and consecutive_failures < 3:
        status = "healthy"
    elif success_rate >= 0.5 or consecutive_failures < 5:
        status = "degraded"
    else:
        status = "failing"

    return {
        "status": status,
        "success_rate": success_rate,
        "total_runs": total,
        "consecutive_failures": consecutive_failures,
        "avg_records_per_run": avg_records,
        "last_success": last_success,
    }


def main() -> None:
    """Demonstrate health monitoring capabilities."""
    print("=" * 70)
    print("  FeedSpine Health Monitoring Example")
    print("=" * 70)
    print()

    db_path = Path("health_demo.db")

    # Clean up any existing demo database
    if db_path.exists():
        db_path.unlink()

    # Create SQLite connection with FeedRepository
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    repo = FeedRepository(conn, SQLiteDialect())
    repo.ensure_schema()

    print("Using FeedRepository with SQLite for persistent run tracking")
    print()

    # =========================================================================
    # 1. Create Demo Feed Runs
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  1. CREATING DEMO FEED RUNS" + " " * 39 + "|")
    print("+" + "-" * 68 + "+")
    print()

    now = datetime.now(UTC)
    feeds_data = [
        # (feed_name, description, failure_pattern)
        ("sec-press-releases", "Healthy (90% success)", lambda i: i == 3),  # 1 failure
        ("sec-speeches", "Degraded (60% success)", lambda i: i % 3 == 0),  # 4 failures
        ("sec-filings", "Failing (40% success, consecutive)", lambda i: i < 6),  # 6 consecutive
    ]

    for feed_name, description, should_fail in feeds_data:
        print(f"   Creating runs for '{feed_name}' ({description})...")

        for i in range(10):
            run_id = str(uuid4())
            run_time = now - timedelta(hours=i * 2)
            failed = should_fail(i)

            repo.start_feed_run(
                run_id=run_id,
                feed_name=feed_name,
                started_at=run_time,
                metadata={"batch": i},
            )

            if failed:
                repo.complete_feed_run(
                    run_id=run_id,
                    status="failed",
                    records_fetched=0,
                    records_new=0,
                    error_message="Simulated failure for demo",
                )
            else:
                records = 25 if "press" in feed_name else (10 if "speech" in feed_name else 50)
                repo.complete_feed_run(
                    run_id=run_id,
                    status="completed",
                    records_fetched=records,
                    records_new=records // 5,
                )

    repo.commit()
    print()

    # =========================================================================
    # 2. Check Individual Feed Health
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  2. INDIVIDUAL FEED HEALTH" + " " * 41 + "|")
    print("+" + "-" * 68 + "+")
    print()

    feed_names = ["sec-press-releases", "sec-speeches", "sec-filings"]
    all_health = []

    for feed_name in feed_names:
        runs = repo.get_feed_runs(feed_name=feed_name, limit=50)
        health = calculate_health(runs)
        health["feed_name"] = feed_name
        all_health.append(health)

        # Display with RAG indicator
        status = health["status"]
        if status == "healthy":
            indicator = "[OK]"
            color = "HEALTHY"
        elif status == "degraded":
            indicator = "[!!]"
            color = "DEGRADED"
        else:
            indicator = "[XX]"
            color = "FAILING"

        print(f"   {indicator} {feed_name}")
        print(f"      Status:              {color}")
        print(f"      Success rate:        {health['success_rate']:.0%}")
        print(f"      Total runs:          {health['total_runs']}")
        print(f"      Consecutive fails:   {health['consecutive_failures']}")
        print(f"      Avg records/run:     {health['avg_records_per_run']:.1f}")
        print()

    # =========================================================================
    # 3. Health Summary Dashboard
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  3. HEALTH SUMMARY DASHBOARD" + " " * 39 + "|")
    print("+" + "-" * 68 + "+")
    print()

    healthy = sum(1 for h in all_health if h["status"] == "healthy")
    degraded = sum(1 for h in all_health if h["status"] == "degraded")
    failing = sum(1 for h in all_health if h["status"] == "failing")

    print(f"   Total feeds monitored: {len(all_health)}")
    print()
    print("   +---------------------------------------------+")
    print(f"   |  [OK] Healthy:   {healthy:>3}                        |")
    print(f"   |  [!!] Degraded:  {degraded:>3}                        |")
    print(f"   |  [XX] Failing:   {failing:>3}                        |")
    print("   +---------------------------------------------+")
    print()

    # Overall health score (weighted)
    weights = {"healthy": 1.0, "degraded": 0.5, "failing": 0.0}
    total_score = sum(weights[h["status"]] for h in all_health)
    health_score = total_score / len(all_health) * 100

    print(f"   Overall Health Score: {health_score:.0f}%")
    if health_score >= 80:
        print("   Status: [OK] System healthy")
    elif health_score >= 50:
        print("   Status: [!!] Some feeds need attention")
    else:
        print("   Status: [XX] Critical - multiple feeds failing")
    print()

    # =========================================================================
    # 4. Alerts - Failing Feeds
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  4. ALERTS - FEEDS NEEDING ATTENTION" + " " * 30 + "|")
    print("+" + "-" * 68 + "+")
    print()

    alerts = [h for h in all_health if h["consecutive_failures"] >= 3 or h["status"] == "failing"]

    if alerts:
        print(f"   WARNING: {len(alerts)} feed(s) need attention:")
        print()
        for alert in sorted(alerts, key=lambda x: -x["consecutive_failures"]):
            success_pct = f"{alert['success_rate']:.0%}"
            print("   +---------------------------------------------------------------+")
            print(f"   |  ALERT: {alert['feed_name']:<52}|")
            print("   +---------------------------------------------------------------+")
            print(f"   |  Consecutive failures: {alert['consecutive_failures']:<36}|")
            print(f"   |  Success rate: {success_pct:<44}|")
            print("   |  Recommended action: Check feed source, review logs        |")
            print("   +---------------------------------------------------------------+")
            print()
    else:
        print("   [OK] No feeds currently failing")
        print("   All feeds operating within normal parameters")
    print()

    # =========================================================================
    # 5. Recent Run Timeline
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  5. RECENT RUN TIMELINE (Last 24 hours)" + " " * 27 + "|")
    print("+" + "-" * 68 + "+")
    print()

    # Get all recent runs
    all_runs = repo.get_feed_runs(limit=30)

    print("   Time (UTC)          Feed                    Status     Records")
    print("   " + "-" * 62)

    for run in all_runs[:12]:  # Show last 12
        started = run.get("started_at", "")[:19].replace("T", " ")
        feed = run.get("feed_name", "")[:22]
        status = run.get("status", "")
        records = run.get("records_new", 0) or 0

        status_icon = "[+]" if status == "completed" else "[X]"
        print(f"   {started}  {feed:<22}  {status_icon} {status:<8}  {records:>5}")

    print()

    # =========================================================================
    # 6. Health Thresholds Explanation
    # =========================================================================
    print("+" + "-" * 68 + "+")
    print("|  6. HEALTH STATUS THRESHOLDS" + " " * 39 + "|")
    print("+" + "-" * 68 + "+")
    print()
    print("   | Status     | Success Rate | Consecutive Failures |")
    print("   +------------+--------------+----------------------+")
    print("   | [OK] Healthy  | >=80%        | <3                   |")
    print("   | [!!] Degraded | 50-80%       | 3-5                  |")
    print("   | [XX] Failing  | <50%         | >5                   |")
    print()

    # =========================================================================
    # Cleanup
    # =========================================================================
    conn.close()

    # Keep database for inspection (comment out to auto-delete)
    # if db_path.exists():
    #     db_path.unlink()
    #     print(f"   Removed demo database: {db_path}")

    print("=" * 70)
    print("  Health Monitoring Example Complete")
    print("=" * 70)
    print()
    print("   Database preserved at: health_demo.db")
    print("   Inspect with: sqlite3 health_demo.db 'SELECT * FROM feed_runs'")
    print()


if __name__ == "__main__":
    main()
