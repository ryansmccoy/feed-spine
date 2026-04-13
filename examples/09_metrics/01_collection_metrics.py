#!/usr/bin/env python3
"""
FeedSpine Metrics: Track Collection Performance
================================================

Demonstrates capturing operational metrics during feed collection,
including timing, item counts, error rates, and histogram summaries.

What You'll Learn:
    1. Create a CollectionMetrics instance
    2. Time fetch/parse/store operations with context managers
    3. Record item counts by source and category
    4. Record errors for monitoring
    5. Generate a summary report with percentile histograms

Why Metrics Matter:
    When running feed collection in production, you need to know:
    - How long each phase (fetch, parse, store) takes
    - Which feeds produce the most items or errors
    - Performance distribution (p50, p95, p99) for SLA tracking

Usage:
    python examples/09_metrics/01_collection_metrics.py
"""

from __future__ import annotations

import logging
import random
import time

from feedspine.metrics import CollectionMetrics

# Suppress logger warnings for simulated errors in this demo
logging.getLogger("feedspine.metrics").setLevel(logging.ERROR)


def main() -> None:
    """Demonstrate metrics collection during a simulated feed run."""
    print("=" * 60)
    print("  FeedSpine Metrics Collection Example")
    print("=" * 60)

    metrics = CollectionMetrics()
    metrics.start()

    # =========================================================================
    # 1. Simulate collecting from multiple feeds
    # =========================================================================
    feeds = [
        ("sec-daily", "8-K", 150),
        ("sec-quarterly", "10-K", 30),
        ("hacker-news", "article", 90),
    ]

    print("\n--- Simulating feed collection ---")

    for feed_name, category, target_items in feeds:
        print(f"\nCollecting from '{feed_name}'...")

        # Time the fetch phase
        with metrics.time_operation("fetch", adapter=feed_name):
            time.sleep(random.uniform(0.05, 0.15))  # Simulate network I/O

        # Time the parse phase
        with metrics.time_operation("parse", adapter=feed_name):
            time.sleep(random.uniform(0.01, 0.05))  # Simulate parsing

        # Record items collected
        actual = random.randint(target_items - 10, target_items + 10)
        metrics.record_items(feed_name, category=category, count=actual)
        print(f"  Fetched and parsed {actual} items ({category})")

        # Simulate occasional errors
        if random.random() < 0.3:
            metrics.record_error(feed_name, error_type="network_timeout")
            print(f"  Warning: encountered network_timeout")

    # =========================================================================
    # 2. Simulate a second pass (shows histograms with multiple data points)
    # =========================================================================
    print("\n--- Second collection pass ---")
    for feed_name, category, target_items in feeds:
        with metrics.time_operation("fetch", adapter=feed_name):
            time.sleep(random.uniform(0.03, 0.12))
        with metrics.time_operation("parse", adapter=feed_name):
            time.sleep(random.uniform(0.01, 0.04))
        actual = random.randint(target_items - 5, target_items + 5)
        metrics.record_items(feed_name, category=category, count=actual)

    # =========================================================================
    # 3. Generate and display summary
    # =========================================================================
    summary = metrics.summary()

    print("\n" + "=" * 60)
    print(str(summary))

    # =========================================================================
    # 4. Show histogram details
    # =========================================================================
    if summary.operation_histograms:
        print("\nOperation Histograms:")
        print("-" * 50)
        for key, hist in sorted(summary.operation_histograms.items()):
            print(f"  {key}:")
            print(f"    count={hist['count']:.0f}  "
                  f"min={hist['min']*1000:.1f}ms  "
                  f"mean={hist['mean']*1000:.1f}ms  "
                  f"p95={hist['p95']*1000:.1f}ms  "
                  f"max={hist['max']*1000:.1f}ms")

    # =========================================================================
    # 5. JSON-serializable output for monitoring integration
    # =========================================================================
    data = summary.to_dict()
    print(f"\nJSON-serializable keys: {list(data.keys())}")
    print(f"Total items processed: {data['total_items']:,}")
    print(f"Total errors: {data['total_errors']}")

    print("\n  Metrics example complete")


if __name__ == "__main__":
    main()
