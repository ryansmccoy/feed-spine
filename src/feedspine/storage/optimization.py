"""
Query Optimization Utilities for Large Datasets.

Cursor-based pagination and batch processing utilities.

Analysis and scaling utilities have been extracted to:
- :mod:`feedspine.storage.analysis` — query plan analysis, index recommendations
- :mod:`feedspine.storage.scaling` — time partitioning, scaling strategies
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from feedspine._vendor.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# Cursor-Based Pagination (10x faster than OFFSET for large datasets)
# =============================================================================


@dataclass
class Cursor:
    """
    Opaque cursor for pagination.

    Why cursor > OFFSET:
    - OFFSET 1000000 still scans 1M rows
    - Cursor uses index to jump directly
    - Consistent results with concurrent writes

    Example:
        cursor = None
        while True:
            page, cursor = await storage.get_page(cursor, limit=100)
            if not page:
                break
            process(page)
    """

    key: str
    captured_at: datetime

    def encode(self) -> str:
        """Encode cursor to string for API responses."""
        import base64
        import json

        data = {
            "k": self.key,
            "t": self.captured_at.isoformat(),
        }
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

    @classmethod
    def decode(cls, encoded: str) -> Cursor:
        """Decode cursor from string."""
        import base64
        import json

        data = json.loads(base64.urlsafe_b64decode(encoded))
        return cls(
            key=data["k"],
            captured_at=datetime.fromisoformat(data["t"]),
        )


@dataclass
class Page[T]:
    """
    Page of results with cursor.

    Attributes:
        items: List of items in this page
        next_cursor: Cursor for next page (None if last page)
        has_more: Whether more pages exist
        total_estimate: Estimated total count (optional)
    """

    items: list[T]
    next_cursor: Cursor | None = None
    has_more: bool = False
    total_estimate: int | None = None


async def paginate_with_cursor[T](
    query_fn: Callable[[Cursor | None, int], tuple[list[T], bool]],
    cursor: Cursor | None = None,
    page_size: int = 100,
) -> Page[T]:
    """
    Generic cursor-based pagination.

    Args:
        query_fn: Function that takes (cursor, limit) and returns (items, has_more)
        cursor: Starting cursor (None for first page)
        page_size: Items per page

    Returns:
        Page with items and next cursor
    """
    items, has_more = await query_fn(cursor, page_size + 1)

    # Check if there are more results
    if len(items) > page_size:
        items = items[:page_size]
        has_more = True

    # Build next cursor from last item
    next_cursor = None
    if has_more and items:
        last = items[-1]
        if hasattr(last, "key") and hasattr(last, "captured_at"):
            next_cursor = Cursor(key=last.key, captured_at=last.captured_at)

    return Page(items=items, next_cursor=next_cursor, has_more=has_more)


# =============================================================================
# Batch Processing (Memory-Efficient)
# =============================================================================


@dataclass
class BatchConfig:
    """
    Configuration for batch processing.

    Attributes:
        batch_size: Records per batch
        max_memory_mb: Stop if memory exceeds this
        progress_interval: Log progress every N batches
        on_batch_complete: Callback after each batch
    """

    batch_size: int = 1000
    max_memory_mb: int = 512
    progress_interval: int = 10
    on_batch_complete: Callable[[int, int], None] | None = None


def batch_iterator[T](
    items: Iterator[T],
    batch_size: int = 1000,
) -> Iterator[list[T]]:
    """
    Yield items in batches.

    Memory-efficient: only holds one batch at a time.

    Example:
        for batch in batch_iterator(records, batch_size=1000):
            storage.batch_upsert(batch)
    """
    batch: list[T] = []

    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


async def process_in_batches[T](
    items: Iterator[T],
    processor: Callable[[list[T]], Any],
    config: BatchConfig | None = None,
) -> int:
    """
    Process items in batches with progress tracking.

    Args:
        items: Iterator of items to process
        processor: Function to process each batch
        config: Batch configuration

    Returns:
        Total items processed
    """
    config = config or BatchConfig()
    total = 0

    for batch_num, batch in enumerate(batch_iterator(items, config.batch_size), 1):
        await processor(batch)
        total += len(batch)

        if config.on_batch_complete:
            config.on_batch_complete(batch_num, total)

        if batch_num % config.progress_interval == 0:
            logger.info(f"Processed {total:,} records ({batch_num} batches)")

    return total


# =============================================================================
# Re-exports for backward compatibility
# =============================================================================
from feedspine.storage.analysis import (  # noqa: E402, F401
    IndexRecommendation,
    QueryPlan,
    analyze_query_plan,
    recommend_indexes_for_queries,
)
from feedspine.storage.scaling import (  # noqa: E402, F401
    SCALING_STRATEGIES,
    TimePartition,
    generate_monthly_partitions,
    generate_partition_sql,
    get_scaling_recommendations,
)
