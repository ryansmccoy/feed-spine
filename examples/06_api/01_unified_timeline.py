#!/usr/bin/env python3
"""
FeedSpine Unified Feed Timeline Example
========================================

Demonstrates the unified feed timeline API that provides a merged,
time-sorted view of records across all feeds.

What You'll Learn:
    1. Query the unified timeline via API
    2. Filter by layer (bronze/silver/gold)
    3. Time-range filtering
    4. Pagination and cursor-based navigation

API Endpoint:
    GET /api/v1/feed

Query Parameters:
    - layer: Filter by medallion layer (bronze, silver, gold)
    - since: ISO datetime for records after this time
    - until: ISO datetime for records before this time
    - limit: Page size (default 50, max 500)
    - offset: Pagination offset

Why Use the Unified Timeline?
    - Single view across all feed sources
    - Time-sorted for chronological analysis
    - Layer filtering for data quality tiers
    - Automatic deduplication by natural key

Prerequisites:
    1. Start the FeedSpine API server:
       feedspine serve

    2. Have some data in storage (run collection first)

Usage:
    python examples/07_api/01_unified_timeline.py
"""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen


def main() -> None:
    """Demonstrate unified timeline API queries."""
    print("=" * 60)
    print("FeedSpine Unified Timeline API Example")
    print("=" * 60)
    print()

    base_url = "http://localhost:8000"
    api_base = f"{base_url}/api/v1"

    # -------------------------------------------------------------------------
    # 1. Check API Health
    # -------------------------------------------------------------------------
    print("1. Checking API health...")
    demo_mode = False
    try:
        with urlopen(f"{base_url}/health", timeout=5) as response:
            health = json.loads(response.read())
            print(f"   API Status: {health.get('status', 'unknown')}")
    except URLError:
        print("   ⚠️  API not running (start with: feedspine serve)")
        print()
        print("   Switching to demo mode (showing example responses)...")
        demo_mode = True
    print()

    # -------------------------------------------------------------------------
    # 2. Query Unified Timeline (Default)
    # -------------------------------------------------------------------------
    print("2. Querying unified timeline (default params)...")

    if demo_mode:
        # Show example response structure
        print("   Total records: 127")
        print("   Page size: 50")
        print("   Has more: True")
        print()
        print("   📋 Recent timeline items (demo):")
        demo_items = [
            ("sec-rss:0001234567-24-000001", "bronze", "SEC EDGAR"),
            ("sec-rss:0001234567-24-000002", "bronze", "SEC EDGAR"),
            ("hn:38452912", "bronze", "Hacker News"),
        ]
        for nk, layer, source in demo_items:
            print(f"      • {nk}")
            print(f"        Layer: {layer}")
            print(f"        Source: {source}")
            print()
    else:
        url = f"{api_base}/feed"
        try:
            req = Request(url)
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read())
                print(f"   Total records: {data.get('total', 0)}")
                print(f"   Page size: {data.get('limit', 50)}")
                print(f"   Has more: {data.get('has_more', False)}")
                print()

                items = data.get("items", [])
                if items:
                    print("   📋 Recent timeline items:")
                    for item in items[:5]:
                        print(f"      • {item.get('natural_key')}")
                        print(f"        Layer: {item.get('layer')}")
                        print(f"        Source: {item.get('source', 'N/A')}")
                        if title := item.get("title"):
                            print(f"        Title: {title[:50]}...")
                        print()
                else:
                    print("   No records found. Run a collection first:")
                    print("   feedspine collect sec-rss --limit 10")
        except URLError as e:
            print(f"   ❌ Error: {e}")
    print()

    # -------------------------------------------------------------------------
    # 3. Filter by Layer
    # -------------------------------------------------------------------------
    print("3. Filtering by layer (bronze)...")

    if demo_mode:
        print("   Bronze records: 85")
        print("   • sec-rss:0001234567-24-000001 - bronze")
        print("   • sec-rss:0001234567-24-000002 - bronze")
        print("   • hn:38452912 - bronze")
    else:
        url = f"{api_base}/feed?layer=bronze&limit=10"
        try:
            req = Request(url)
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read())
                items = data.get("items", [])
                print(f"   Bronze records: {data.get('total', 0)}")
                for item in items[:3]:
                    print(f"   • {item.get('natural_key')} - {item.get('layer')}")
        except URLError as e:
            print(f"   ❌ Error: {e}")
    print()

    # -------------------------------------------------------------------------
    # 4. Time-Range Query
    # -------------------------------------------------------------------------
    print("4. Time-range filtering (last 24 hours)...")

    from datetime import UTC, datetime, timedelta

    if demo_mode:
        print("   Records in last 24h: 42")
        print("   • sec-rss:0001234567-24-000001")
        print("     Captured: 2026-02-15T08:30:00+00:00")
        print("   • sec-rss:0001234567-24-000002")
        print("     Captured: 2026-02-15T07:15:00+00:00")
    else:
        since = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
        url = f"{api_base}/feed?since={since}&limit=20"

        try:
            req = Request(url)
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read())
                print(f"   Records in last 24h: {data.get('total', 0)}")
                items = data.get("items", [])
                for item in items[:3]:
                    captured = item.get("captured_at", "unknown")
                    print(f"   • {item.get('natural_key')}")
                    print(f"     Captured: {captured}")
        except URLError as e:
            print(f"   ❌ Error: {e}")
    print()

    # -------------------------------------------------------------------------
    # 5. Pagination
    # -------------------------------------------------------------------------
    print("5. Pagination example...")

    if demo_mode:
        print("   Page 0: 10 items (offset 0)")
        print("   Page 1: 10 items (offset 10)")
        print("   Page 2: 10 items (offset 20)")
        print("   Total fetched: 30")
    else:
        page = 0
        offset = 0
        limit = 10
        total_fetched = 0

        while total_fetched < 30:  # Stop after 30 records
            url = f"{api_base}/feed?limit={limit}&offset={offset}"
            try:
                req = Request(url)
                with urlopen(req, timeout=30) as response:
                    data = json.loads(response.read())
                    items = data.get("items", [])

                    if not items:
                        print(f"   Page {page}: No more records")
                        break

                    total_fetched += len(items)
                    print(f"   Page {page}: {len(items)} items (offset {offset})")

                    if not data.get("has_more", False):
                        break

                    offset += limit
                    page += 1
            except URLError as e:
                print(f"   ❌ Error: {e}")
                break

        print(f"   Total fetched: {total_fetched}")
    print()

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("=" * 60)
    print("✅ Timeline API example complete!")
    print("=" * 60)
    print("""
Key Concepts:
  • GET /api/v1/feed - unified timeline endpoint
  • layer param - filter by medallion tier
  • since/until - time-range filtering
  • limit/offset - pagination support

Response Fields:
  • items: List of TimelineItem objects
  • total: Total matching records
  • has_more: Whether more pages exist

Next: 02_rss_atom_syndication.py - RSS/Atom feed output
""")


if __name__ == "__main__":
    main()
