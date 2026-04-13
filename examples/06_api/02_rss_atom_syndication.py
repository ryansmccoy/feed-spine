#!/usr/bin/env python3
"""
FeedSpine RSS/Atom Syndication Example
======================================

Demonstrates generating RSS 2.0 and Atom 1.0 feeds from FeedSpine data,
enabling standard feed reader consumption of collected data.

What You'll Learn:
    1. Get RSS 2.0 feed output
    2. Get Atom 1.0 feed output
    3. Layer filtering for syndication
    4. Use with feed readers

API Endpoints:
    GET /api/v1/syndication/rss   — RSS 2.0 feed
    GET /api/v1/syndication/atom  — Atom 1.0 feed

Query Parameters:
    - layer: Filter by medallion layer (bronze, silver, gold)
    - limit: Maximum items in feed (default 50, max 100)

Why Syndication?
    - Subscribe in any RSS reader (Feedly, NewsBlur, etc.)
    - Monitor collected data changes
    - Push notifications via IFTTT/Zapier
    - Integration with existing RSS workflows

Prerequisites:
    1. Start the FeedSpine API server:
       feedspine serve

    2. Have some data in storage (run collection first)

Usage:
    python examples/07_api/02_rss_atom_syndication.py
"""

from __future__ import annotations

from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.dom.minidom import parseString


def main() -> None:
    """Demonstrate RSS/Atom syndication endpoints."""
    print("=" * 60)
    print("FeedSpine RSS/Atom Syndication Example")
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
        import json

        with urlopen(f"{base_url}/health", timeout=5) as response:
            health = json.loads(response.read())
            print(f"   API Status: {health.get('status', 'unknown')}")
    except URLError:
        print("   ⚠️  API not running (start with: feedspine serve)")
        print()
        print("   Switching to demo mode (showing example output)...")
        demo_mode = True
    print()

    # -------------------------------------------------------------------------
    # 2. Get RSS 2.0 Feed
    # -------------------------------------------------------------------------
    print("2. Fetching RSS 2.0 feed...")

    if demo_mode:
        print("   Content-Type: application/rss+xml")
        print()
        print("   📰 RSS 2.0 Output (excerpt):")
        print('   <?xml version="1.0" ?>')
        print('   <rss version="2.0">')
        print("     <channel>")
        print("       <title>FeedSpine Timeline</title>")
        print("       <link>http://localhost:8000/api/v1/feed</link>")
        print("       <description>Unified feed timeline</description>")
        print("       <item>")
        print("         <title>SEC Filing: 0001234567-24-000001</title>")
        print("         <pubDate>Sat, 15 Feb 2026 08:30:00 +0000</pubDate>")
        print("       </item>")
        print("       ...")
        print("     </channel>")
        print("   </rss>")
        print()
        print("   Total items: 10")
    else:
        url = f"{api_base}/syndication/rss?limit=10"
        try:
            req = Request(url)
            req.add_header("Accept", "application/rss+xml")
            with urlopen(req, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "")
                print(f"   Content-Type: {content_type}")

                rss_content = response.read().decode("utf-8")

                # Pretty print first part of RSS
                try:
                    dom = parseString(rss_content)
                    pretty = dom.toprettyxml(indent="  ")
                    lines = pretty.split("\n")[:25]
                    print()
                    print("   📰 RSS 2.0 Output (excerpt):")
                    for line in lines:
                        if line.strip():
                            print(f"   {line}")
                    print("   ...")
                except Exception:
                    print(f"   {rss_content[:500]}...")

                # Count items
                item_count = rss_content.count("<item>")
                print()
                print(f"   Total items: {item_count}")
        except URLError as e:
            print(f"   ❌ Error: {e}")
    print()

    # -------------------------------------------------------------------------
    # 3. Get Atom 1.0 Feed
    # -------------------------------------------------------------------------
    print("3. Fetching Atom 1.0 feed...")

    if demo_mode:
        print("   Content-Type: application/atom+xml")
        print()
        print("   📰 Atom 1.0 Output (excerpt):")
        print('   <?xml version="1.0" ?>')
        print('   <feed xmlns="http://www.w3.org/2005/Atom">')
        print("     <title>FeedSpine Timeline</title>")
        print("     <id>feedspine:timeline</id>")
        print("     <updated>2026-02-15T08:30:00Z</updated>")
        print("     <entry>")
        print("       <title>SEC Filing: 0001234567-24-000001</title>")
        print("       <updated>2026-02-15T08:30:00Z</updated>")
        print("     </entry>")
        print("     ...")
        print("   </feed>")
        print()
        print("   Total entries: 10")
    else:
        url = f"{api_base}/syndication/atom?limit=10"
        try:
            req = Request(url)
            req.add_header("Accept", "application/atom+xml")
            with urlopen(req, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "")
                print(f"   Content-Type: {content_type}")

                atom_content = response.read().decode("utf-8")

                # Pretty print first part of Atom
                try:
                    dom = parseString(atom_content)
                    pretty = dom.toprettyxml(indent="  ")
                    lines = pretty.split("\n")[:25]
                    print()
                    print("   📰 Atom 1.0 Output (excerpt):")
                    for line in lines:
                        if line.strip():
                            print(f"   {line}")
                    print("   ...")
                except Exception:
                    print(f"   {atom_content[:500]}...")

                # Count entries
                entry_count = atom_content.count("<entry>")
                print()
                print(f"   Total entries: {entry_count}")
        except URLError as e:
            print(f"   ❌ Error: {e}")
    print()

    # -------------------------------------------------------------------------
    # 4. Layer-Filtered RSS
    # -------------------------------------------------------------------------
    print("4. Layer-filtered RSS (gold layer only)...")

    if demo_mode:
        print("   Gold layer items: 3")
    else:
        url = f"{api_base}/syndication/rss?layer=gold&limit=10"
        try:
            req = Request(url)
            with urlopen(req, timeout=30) as response:
                rss_content = response.read().decode("utf-8")
                item_count = rss_content.count("<item>")
                print(f"   Gold layer items: {item_count}")
        except URLError as e:
            print(f"   ❌ Error: {e}")
    print()

    # -------------------------------------------------------------------------
    # 5. Feed Reader URLs
    # -------------------------------------------------------------------------
    print("5. Feed Reader URLs")
    print("   Add these URLs to your favorite feed reader:")
    print()
    print(f"   RSS 2.0:  {api_base}/syndication/rss")
    print(f"   Atom 1.0: {api_base}/syndication/atom")
    print()
    print("   Bronze only: {url}?layer=bronze")
    print("   Silver only: {url}?layer=silver")
    print("   Gold only:   {url}?layer=gold")
    print()

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("=" * 60)
    print("✅ Syndication example complete!")
    print("=" * 60)
    print("""
Key Concepts:
  • /api/v1/syndication/rss - RSS 2.0 feed
  • /api/v1/syndication/atom - Atom 1.0 feed
  • layer param - filter by medallion tier
  • limit param - control feed size

Use Cases:
  • Subscribe in RSS readers (Feedly, NewsBlur)
  • IFTTT/Zapier integrations
  • Monitoring dashboards
  • External system notifications

Feed Standards:
  • RSS 2.0: pubDate in RFC 822 format
  • Atom 1.0: updated in RFC 3339 format
  • Both comply with standard specifications
""")


if __name__ == "__main__":
    main()
