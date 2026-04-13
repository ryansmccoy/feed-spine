#!/usr/bin/env python3
"""
Pipeline Processing — Deduplication, Versioning & Events
==========================================================

This example demonstrates FeedSpine's **pipeline processing engine** —
the core system that deduplicates, versions, and tracks records as they
flow from feeds into storage.

What You'll Learn:
    1. Processing individual record candidates
    2. Understanding deduplication (CREATED, DUPLICATE, UPDATED)
    3. Content versioning — how changed content triggers version bumps
    4. Running a full feed through the pipeline
    5. Interpreting pipeline statistics

Key Concepts:
    - RecordCandidate: Input to the pipeline (not yet persisted)
    - ProcessResult: Output with action (CREATED/DUPLICATE/UPDATED)
    - ProcessAction: Enum describing what happened to a candidate
    - PipelineStats: Aggregate statistics for a pipeline run
    - natural_key: Unique identifier used for deduplication

Usage:
    python examples/14_pipeline/01_pipeline_processing.py

Expected Output:
    Shows record creation, deduplication, and version updates.
"""

import asyncio
import warnings
from datetime import UTC, datetime

from feedspine import MemoryStorage, RecordCandidate
from feedspine.models.base import Metadata
from feedspine.pipeline import Pipeline
from feedspine.pipeline.action import ProcessAction

warnings.filterwarnings("ignore", message="WatermarkStore.*in-memory")


async def main() -> None:
    storage = MemoryStorage()
    await storage.initialize()
    pipeline = Pipeline(storage=storage)

    # =========================================================================
    # STEP 1: Process a New Record (CREATED)
    # =========================================================================
    print("=" * 60)
    print("STEP 1: Process New Record → CREATED")
    print("=" * 60)

    candidate = RecordCandidate(
        natural_key="sec-filing-0001234567-24-001234",
        published_at=datetime(2024, 6, 15, 14, 30, tzinfo=UTC),
        content={
            "form_type": "10-K",
            "company": "Acme Corp",
            "cik": "0001234567",
            "period_of_report": "2024-03-31",
        },
        metadata=Metadata(source="sec-rss"),
    )

    result = await pipeline.process(candidate, source="sec-rss")
    print(f"  Action:      {result.action}")
    print(f"  Is new:      {result.is_new}")
    assert result.action == ProcessAction.CREATED
    assert result.record is not None
    print(f"  Record ID:   {result.record.id}")
    print(f"  Natural key: {result.record.natural_key}")

    # =========================================================================
    # STEP 2: Process Same Record Again (DUPLICATE)
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 2: Submit Same Record → DUPLICATE")
    print("=" * 60)

    result2 = await pipeline.process(candidate, source="sec-rss")
    print(f"  Action:       {result2.action}")
    print(f"  Is duplicate: {result2.is_duplicate}")
    assert result2.action == ProcessAction.DUPLICATE

    # =========================================================================
    # STEP 3: Process Updated Content (UPDATED)
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 3: Submit Changed Content → UPDATED")
    print("=" * 60)

    updated_candidate = RecordCandidate(
        natural_key="sec-filing-0001234567-24-001234",  # Same key!
        published_at=datetime(2024, 6, 15, 15, 0, tzinfo=UTC),
        content={
            "form_type": "10-K/A",  # Amended!
            "company": "Acme Corp",
            "cik": "0001234567",
            "period_of_report": "2024-03-31",
            "amendment_flag": True,
        },
        metadata=Metadata(source="sec-rss"),
    )

    result3 = await pipeline.process(updated_candidate, source="sec-rss")
    print(f"  Action:    {result3.action}")
    print(f"  Is update: {result3.is_update}")
    assert result3.action == ProcessAction.UPDATED
    print(f"  Previous hash: {result3.previous_content_hash}")

    # =========================================================================
    # STEP 4: Run a Full Feed Through the Pipeline
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 4: Full Feed Pipeline Run")
    print("=" * 60)

    # Create a simple in-memory adapter for demonstration
    class DemoFeed:
        """Feed that yields a mix of new and duplicate items."""

        name = "demo-earnings"

        async def initialize(self) -> None:
            pass

        async def close(self) -> None:
            pass

        async def fetch(self):
            items = [
                ("AAPL-2024-Q2", {"ticker": "AAPL", "eps": 1.52, "quarter": "Q2"}),
                ("MSFT-2024-Q2", {"ticker": "MSFT", "eps": 2.95, "quarter": "Q2"}),
                ("AAPL-2024-Q2", {"ticker": "AAPL", "eps": 1.52, "quarter": "Q2"}),  # Duplicate
                ("GOOG-2024-Q2", {"ticker": "GOOG", "eps": 1.89, "quarter": "Q2"}),
                ("AAPL-2024-Q2", {"ticker": "AAPL", "eps": 1.53, "quarter": "Q2"}),  # Update
            ]
            for key, content in items:
                yield RecordCandidate(
                    natural_key=key,
                    published_at=datetime.now(UTC),
                    content=content,
                    metadata=Metadata(source="demo-earnings"),
                )

    stats = await pipeline.run(DemoFeed())

    print(f"\n  Feed:       {stats.feed_name}")
    print(f"  Processed:  {stats.processed}")
    print(f"  New:        {stats.new}")
    print(f"  Duplicates: {stats.duplicates}")
    print(f"  Updated:    {stats.updated}")
    print(f"  Errors:     {stats.errors}")
    print(f"  Duration:   {stats.duration_ms:.0f}ms")
    print(f"  Dedup rate: {stats.dedup_rate:.0%}")

    # =========================================================================
    # STEP 5: Verify Storage State
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 5: Verify Storage State")
    print("=" * 60)

    total = await storage.count()
    print(f"\n  Total unique records: {total}")
    print("  (new records + original SEC filing + amended SEC filing)")


if __name__ == "__main__":
    asyncio.run(main())
