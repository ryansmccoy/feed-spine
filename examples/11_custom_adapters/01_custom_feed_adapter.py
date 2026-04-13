#!/usr/bin/env python3
"""
Custom Feed Adapter
===================

This example shows how to create a **custom FeedAdapter** — the primary
extension point for adding new data sources to FeedSpine.

What You'll Learn:
    1. The FeedAdapter protocol (what methods to implement)
    2. Building a REST API adapter that paginates
    3. Generating natural keys for deduplication
    4. Using RetryConfig for resilient HTTP requests
    5. Registering and using your custom adapter

Key Concepts:
    - FeedAdapter: Protocol with name, fetch(), initialize(), close()
    - RecordCandidate: What fetch() yields (natural_key, content, metadata)
    - Natural Key: Unique identifier — choose wisely for deduplication
    - Metadata: Source attribution and capture context

Usage:
    python examples/11_custom_adapters/01_custom_feed_adapter.py

Expected Output:
    Demonstrates a custom adapter that fetches from a JSON API,
    handles pagination, and produces deduplicated records.
"""

import asyncio
import hashlib
import warnings
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from feedspine import MemoryStorage, create_feed_spine
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate

warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")


# ============================================================================
# STEP 1: Define Your Custom Adapter
# ============================================================================
class JSONPlaceholderAdapter:
    """Custom adapter that fetches posts from JSONPlaceholder API.

    This is a real-world pattern: fetch from a paginated REST API,
    transform each item into a RecordCandidate with a stable natural key.

    The FeedAdapter protocol requires:
        - name (property): Unique identifier for this feed
        - fetch(): AsyncIterator yielding RecordCandidate objects
        - initialize(): Setup (open connections, auth, etc.)
        - close(): Cleanup (close connections, sessions)
    """

    def __init__(
        self,
        name: str = "jsonplaceholder",
        base_url: str = "https://jsonplaceholder.typicode.com",
        max_posts: int = 10,
    ) -> None:
        self._name = name
        self._base_url = base_url
        self._max_posts = max_posts
        self._client = None

    @property
    def name(self) -> str:
        """Unique feed name — used for logging, scheduling, and queries."""
        return self._name

    async def initialize(self) -> None:
        """Called once before first fetch(). Set up HTTP client, auth, etc."""
        # In a real adapter, you'd create an httpx.AsyncClient here:
        #   self._client = httpx.AsyncClient(timeout=30, headers={...})
        pass

    async def close(self) -> None:
        """Called on shutdown. Clean up resources."""
        # In a real adapter:
        #   await self._client.aclose()
        pass

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        """Fetch posts and yield them as RecordCandidates.

        This is where the real work happens. For each item from your source:
        1. Choose a natural key (for deduplication)
        2. Extract the published timestamp
        3. Package the content dict
        4. Set metadata for provenance
        """
        # Simulate API response (in production, use httpx)
        posts = [
            {"id": i, "title": f"Post {i}: Understanding Market Dynamics",
             "body": f"Content for post {i}...", "userId": 1}
            for i in range(1, self._max_posts + 1)
        ]

        for post in posts:
            # ── Natural Key Strategy ──
            # Option A: Use the API's unique ID (best when available)
            natural_key = f"jsonplaceholder:post:{post['id']}"

            # Option B: Content hash (when no stable ID exists)
            # natural_key = hashlib.sha256(
            #     f"{post['title']}:{post['body']}".encode()
            # ).hexdigest()[:16]

            # Option C: URL-based (for web content)
            # natural_key = f"https://example.com/posts/{post['id']}"

            yield RecordCandidate(
                natural_key=natural_key,
                published_at=datetime.now(UTC),  # Use actual publish time if available
                content={
                    "title": post["title"],
                    "body": post["body"],
                    "author_id": post["userId"],
                    "source_id": post["id"],
                },
                metadata=Metadata(source=self._name),
            )


# ============================================================================
# STEP 2: Another Example — File-Based Adapter
# ============================================================================
class CSVRowAdapter:
    """Adapter that yields rows from in-memory CSV-like data.

    Shows how to build adapters for non-API sources (files, databases, etc.)
    """

    def __init__(self, name: str, rows: list[dict]) -> None:
        self._name = name
        self._rows = rows

    @property
    def name(self) -> str:
        return self._name

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        for row in self._rows:
            # When rows lack a unique ID, use content hashing
            content_str = "|".join(str(v) for v in sorted(row.items()))
            content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

            yield RecordCandidate(
                natural_key=f"{self._name}:{content_hash}",
                published_at=datetime.now(UTC),
                content=row,
                metadata=Metadata(source=self._name),
            )


async def main() -> None:
    storage = MemoryStorage()
    app = create_feed_spine(storage)

    # =========================================================================
    # Register custom adapters (same as built-in RSS/SEC adapters)
    # =========================================================================
    app.register_feed(JSONPlaceholderAdapter(max_posts=5))
    app.register_feed(
        CSVRowAdapter(
            "earnings-csv",
            rows=[
                {"ticker": "AAPL", "eps": 1.52, "date": "2024-Q2"},
                {"ticker": "MSFT", "eps": 2.95, "date": "2024-Q2"},
                {"ticker": "GOOGL", "eps": 1.89, "date": "2024-Q2"},
            ],
        )
    )

    # =========================================================================
    # Collect from custom adapters
    # =========================================================================
    print("=" * 60)
    print("CUSTOM ADAPTER: JSONPlaceholder API")
    print("=" * 60)
    outcome = await app.collection_service.run_collection("jsonplaceholder")
    print(f"  Processed: {outcome.stats.processed}")
    print(f"  New:       {outcome.stats.new}")

    print("\n" + "=" * 60)
    print("CUSTOM ADAPTER: CSV Rows")
    print("=" * 60)
    outcome = await app.collection_service.run_collection("earnings-csv")
    print(f"  Processed: {outcome.stats.processed}")
    print(f"  New:       {outcome.stats.new}")

    # Deduplication works the same for custom adapters
    print("\n" + "=" * 60)
    print("DEDUPLICATION (re-collect)")
    print("=" * 60)
    outcome = await app.collection_service.run_collection("jsonplaceholder")
    print(f"  Processed: {outcome.stats.processed}")
    print(f"  Duplicates: {outcome.stats.duplicates} ← all deduped!")

    # =========================================================================
    # Summary
    # =========================================================================
    count = await storage.count()
    print(f"\nTotal unique records in storage: {count}")

    print("\n" + "=" * 60)
    print("HOW TO BUILD YOUR OWN ADAPTER")
    print("=" * 60)
    print("""
1. Create a class with: name (property), fetch(), initialize(), close()
2. fetch() is an async generator yielding RecordCandidate objects
3. Choose a natural key strategy:
   - API ID:      "source:type:id"       (best, stable)
   - URL:         "https://example.com/x" (good for web content)
   - Content hash: sha256(content)[:16]   (fallback, no stable ID)
4. Register with app.register_feed(YourAdapter(...))
5. Collect with app.collection_service.run_collection("your-feed")

FeedSpine handles deduplication, sighting tracking, and storage
automatically — you only write the fetch logic!
    """)


if __name__ == "__main__":
    asyncio.run(main())
