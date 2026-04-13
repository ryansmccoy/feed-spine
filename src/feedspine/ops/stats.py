"""Statistics operations — pure business logic.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`.  They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Functions
---------
fetch_storage_summary
    Get comprehensive storage summary with record/sighting/observation counts.
fetch_layer_distribution
    Get record counts by layer.
fetch_feed_runs
    Get recent feed run history.
fetch_collection_stats
    Get aggregated collection run statistics.
fetch_feed_collection_stats
    Get per-feed collection statistics.
check_storage_health
    Validate storage connectivity.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.ops import OperationContext, OperationResult


async def _call_or_sync(method: Any, **kwargs: Any) -> Any:
    """Call a method, awaiting if it's a coroutine."""
    result = method(**kwargs)
    if asyncio.iscoroutine(result):
        return await result
    return result


async def fetch_storage_summary(
    ctx: OperationContext,
    collection_days: int = 30,
) -> OperationResult[dict[str, Any]]:
    """Get comprehensive storage summary.

    Args:
        ctx: Operation context with storage backend.
        collection_days: Days to aggregate for collection stats.

    Returns:
        OperationResult with dict containing records, sightings,
        observations, feed_configs, and collection stats.
    """
    from feedspine.ops import OperationResult

    storage = ctx.storage

    # If storage has a rich summary method, use it
    if hasattr(storage, "get_storage_summary"):
        summary = await _call_or_sync(storage.get_storage_summary)
        return OperationResult.ok(summary)

    # Fall back to basic counts
    total_records = await storage.count()
    layer_counts = await _get_layer_counts(storage)

    return OperationResult.ok(
        {
            "records": {"total": total_records, "by_layer": layer_counts},
            "sightings": {"total": 0},
            "observations": {"total": 0},
            "feed_configs": {"total": 0},
            "collection": {
                "days": collection_days,
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "total_records_collected": 0,
                "total_errors": 0,
                "avg_records_per_run": 0.0,
                "feeds_active": 0,
                "runs_per_day": 0.0,
            },
            "schema_version": None,
        }
    )


async def fetch_layer_distribution(
    ctx: OperationContext,
) -> OperationResult[dict[str, Any]]:
    """Get record counts by layer.

    Args:
        ctx: Operation context with storage backend.

    Returns:
        OperationResult with ``total`` and ``by_layer`` dict.
    """
    from feedspine.ops import OperationResult

    total = await ctx.storage.count()
    layer_counts = await _get_layer_counts(ctx.storage)

    return OperationResult.ok(
        {
            "total": total,
            "by_layer": layer_counts,
            "storage_type": type(ctx.storage).__name__,
        }
    )


async def fetch_feed_runs(
    ctx: OperationContext,
    feed_name: str | None = None,
    limit: int = 10,
) -> OperationResult[list[dict[str, Any]]]:
    """Get recent feed run history.

    Args:
        ctx: Operation context with storage backend.
        feed_name: Optional feed name filter.
        limit: Maximum runs to return.

    Returns:
        OperationResult with list of run dicts.
    """
    from feedspine.ops import OperationResult

    if not hasattr(ctx.storage, "get_feed_runs"):
        return OperationResult.fail(
            "Feed run history not available with this storage backend. "
            "Use PostgreSQL storage for full feed run tracking."
        )

    runs = await ctx.storage.get_feed_runs(feed_name=feed_name, limit=limit)

    run_dicts = []
    for run in runs:
        duration = None
        if run.completed_at and run.started_at:
            duration = (run.completed_at - run.started_at).total_seconds()

        run_dicts.append(
            {
                "feed_name": run.feed_name,
                "started_at": run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else None,
                "status": run.status,
                "fetched_count": run.fetched_count or 0,
                "new_count": run.new_count or 0,
                "error_count": run.error_count or 0,
                "duration_seconds": duration,
            }
        )

    return OperationResult.ok(run_dicts)


async def fetch_collection_stats(
    ctx: OperationContext,
    days: int = 30,
) -> OperationResult[dict[str, Any]]:
    """Get aggregated collection run statistics.

    Args:
        ctx: Operation context with storage backend.
        days: Number of days to aggregate.

    Returns:
        OperationResult with collection stats dict.
    """
    from feedspine.ops import OperationResult

    if not hasattr(ctx.storage, "get_collection_stats"):
        return OperationResult.fail(
            "Collection stats not available with this storage backend. "
            "Use PostgreSQL or SQLite storage for full stats tracking."
        )

    stats = await _call_or_sync(ctx.storage.get_collection_stats, days=days)
    return OperationResult.ok(stats)


async def fetch_feed_collection_stats(
    ctx: OperationContext,
    feed_name: str | None = None,
    days: int = 30,
) -> OperationResult[dict[str, Any]]:
    """Get per-feed collection statistics.

    Args:
        ctx: Operation context with storage backend.
        feed_name: Optional feed name filter.
        days: Number of days to aggregate.

    Returns:
        OperationResult with ``days``, ``feeds`` list, and ``total_feeds``.
    """
    from feedspine.ops import OperationResult

    if not hasattr(ctx.storage, "get_feed_collection_stats"):
        return OperationResult.fail("Feed collection stats not available with this storage backend.")

    feeds_list = await _call_or_sync(
        ctx.storage.get_feed_collection_stats,
        feed_name=feed_name,
        days=days,
    )

    return OperationResult.ok(
        {
            "days": days,
            "feeds": feeds_list,
            "total_feeds": len(feeds_list),
        }
    )


async def check_storage_health(
    ctx: OperationContext,
) -> OperationResult[dict[str, Any]]:
    """Validate storage connectivity and return basic info.

    Args:
        ctx: Operation context with storage backend.

    Returns:
        OperationResult with storage type and record count.
    """
    from feedspine.ops import OperationResult

    count = await ctx.storage.count()
    return OperationResult.ok(
        {
            "backend": type(ctx.storage).__name__,
            "record_count": count,
        }
    )


async def _get_layer_counts(storage: Any) -> dict[str, int]:
    """Get record counts for each layer.

    Uses a single GROUP BY query when the backend supports it,
    falling back to per-layer queries otherwise.
    """
    if hasattr(storage, "count_by_layer"):
        return await storage.count_by_layer()

    from feedspine.models.base import Layer

    layer_counts: dict[str, int] = {}
    for layer in Layer:
        count = await storage.count(layer=layer)
        if count > 0:
            layer_counts[layer.value] = count
    return layer_counts
