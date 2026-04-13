#!/usr/bin/env python3
"""
FeedSpine Search: Index and Query Records
==========================================

Demonstrates full-text search over collected feed records using
the in-memory MemorySearch backend.

What You'll Learn:
    1. Create a FeedSpineApp with a search backend attached
    2. Collect records from an RSS feed
    3. Index collected records into the search backend
    4. Run full-text search queries with pagination
    5. Inspect search results (scores, highlights)

Search Backends:
    - MemorySearch: In-memory linear scan (dev/testing, no extra deps)
    - ElasticsearchSearch: Production full-text search (requires ES)

Usage:
    python examples/08_search/01_memory_search.py
"""

from __future__ import annotations

import asyncio
import os

from feedspine import MemorySearch, MemoryStorage, RSSFeedAdapter, create_feed_spine
from feedspine.protocols.search import SearchType


async def main() -> None:
    """Demonstrate search indexing and querying with MemorySearch."""
    print("=" * 60)
    print("  FeedSpine Search Example — MemorySearch")
    print("=" * 60)

    search = MemorySearch()
    await search.initialize()

    # In demo mode, skip network access and use synthetic data
    demo_mode = os.environ.get("FEEDSPINE_DEMO_MODE", "").lower() in ("1", "true", "yes")
    use_synthetic = demo_mode

    if not demo_mode:
        # =====================================================================
        # Live mode: collect from a real RSS feed, then index
        # =====================================================================
        try:
            storage = MemoryStorage()
            app = create_feed_spine(storage, search=search)
            app.register_feed(
                RSSFeedAdapter(
                    name="hacker-news",
                    url="https://news.ycombinator.com/rss",
                )
            )

            print("\n--- Collecting records from Hacker News RSS ---")
            outcome = await app.collection_service.run_collection("hacker-news")
            print(f"Collected {outcome.stats.new} new records")

            # Index collected records into search
            print("\n--- Indexing records for search ---")
            indexed_count = 0
            async for record in app.query(limit=50):
                content = {
                    "title": record.title or "",
                    "natural_key": record.natural_key,
                }
                metadata = {
                    "feed": record.feed_name,
                    "layer": record.layer.value if record.layer else "bronze",
                }
                await search.index(
                    record_id=record.record_id,
                    content=content,
                    metadata=metadata,
                )
                indexed_count += 1
            print(f"Indexed {indexed_count} records")
        except Exception as exc:
            print(f"Live feed unavailable ({exc}), falling back to synthetic data")
            use_synthetic = True

    if use_synthetic:
        await _index_synthetic_records(search)

    # =========================================================================
    # Run search queries
    # =========================================================================
    await _run_queries(search)


async def _index_synthetic_records(search: MemorySearch) -> None:
    """Index a few synthetic records for offline demo."""
    records = [
        ("rec-1", {"title": "Python 3.14 Released", "body": "New release with pattern matching improvements"}),
        ("rec-2", {"title": "Rust vs Go performance benchmarks", "body": "Comparing systems languages"}),
        ("rec-3", {"title": "Machine learning pipeline best practices", "body": "How to build ML pipelines"}),
        ("rec-4", {"title": "PostgreSQL 17 features overview", "body": "New database features and improvements"}),
        ("rec-5", {"title": "Python type checking with mypy", "body": "Static analysis for Python code"}),
        ("rec-6", {"title": "Building REST APIs with FastAPI", "body": "Modern Python web framework guide"}),
    ]
    for rid, content in records:
        await search.index(rid, content, metadata={"feed": "synthetic"})
    print(f"Indexed {len(records)} synthetic records")


async def _run_queries(search: MemorySearch) -> None:
    """Run example search queries and display results."""
    queries = ["python", "performance", "API"]

    for query in queries:
        print(f"\n--- Search: '{query}' ---")
        response = await search.search(
            query,
            search_type=SearchType.FULLTEXT,
            limit=5,
        )
        print(f"Found {response.total_count} results ({response.query_time_ms:.1f}ms)")

        for i, result in enumerate(response.results, 1):
            highlights_str = ""
            if result.highlights:
                for field_name, snippets in result.highlights.items():
                    highlights_str = f" [{field_name}: {snippets[0]}]"
            print(f"  {i}. {result.record_id} (score={result.score:.2f}){highlights_str}")

        if response.total_count == 0:
            print("  (no matches)")

    # Demonstrate pagination
    print("\n--- Pagination demo ---")
    page1 = await search.search("python", limit=2, offset=0)
    page2 = await search.search("python", limit=2, offset=2)
    print(f"Total results: {page1.total_count}")
    print(f"Page 1: {len(page1.results)} results")
    print(f"Page 2: {len(page2.results)} results")

    print("\n✓ Search example complete")


if __name__ == "__main__":
    asyncio.run(main())
