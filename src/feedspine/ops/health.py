"""Health monitoring operations — pure business logic.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`.  They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Functions
---------
fetch_all_feed_health
    Get health status for all feeds.
fetch_feed_health
    Get health status for a single feed.
fetch_feed_run_history
    Get recent run history for a feed.
fetch_health_alerts
    Get feeds exceeding failure thresholds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.ops import OperationContext, OperationResult


def _get_health_repo(ctx: OperationContext) -> Any | None:
    """Resolve the health-capable repository from storage."""
    storage = ctx.storage
    if hasattr(storage, "get_all_feed_health"):
        return storage
    if hasattr(storage, "_repo"):
        return storage._repo
    return None


async def fetch_all_feed_health(
    ctx: OperationContext,
    days: int = 7,
) -> OperationResult[dict[str, Any]]:
    """Get health status for all feeds.

    Args:
        ctx: Operation context with storage backend.
        days: Number of days to analyze.

    Returns:
        OperationResult with data containing ``period_days``, ``feeds``
        (list of health dicts), and ``summary`` counts.
    """
    from feedspine.ops import OperationResult

    repo = _get_health_repo(ctx)
    if repo is None or not hasattr(repo, "get_all_feed_health"):
        return OperationResult.fail(
            "Health metrics not available with this storage backend. "
            "Use PostgreSQL or SQLite storage for feed health tracking."
        )

    health_list = repo.get_all_feed_health(days)

    summary = {
        "total": len(health_list),
        "healthy": sum(1 for h in health_list if h["status"] == "healthy"),
        "degraded": sum(1 for h in health_list if h["status"] == "degraded"),
        "failing": sum(1 for h in health_list if h["status"] == "failing"),
        "unknown": sum(1 for h in health_list if h["status"] == "unknown"),
    }

    return OperationResult.ok(
        {
            "period_days": days,
            "feeds": health_list,
            "summary": summary,
        }
    )


async def fetch_feed_health(
    ctx: OperationContext,
    feed_name: str,
    days: int = 7,
) -> OperationResult[dict[str, Any]]:
    """Get health status for a single feed.

    Args:
        ctx: Operation context with storage backend.
        feed_name: Name of the feed to check.
        days: Number of days to analyze.

    Returns:
        OperationResult with health dict for the feed.
    """
    from feedspine.ops import OperationResult

    repo = _get_health_repo(ctx)
    if repo is None or not hasattr(repo, "get_feed_health"):
        return OperationResult.fail("Health metrics not available with this storage backend.")

    health = repo.get_feed_health(feed_name, days)
    return OperationResult.ok(health)


async def fetch_feed_run_history(
    ctx: OperationContext,
    feed_name: str,
    limit: int = 50,
) -> OperationResult[list[dict[str, Any]]]:
    """Get run history for a specific feed.

    Args:
        ctx: Operation context with storage backend.
        feed_name: Name of the feed.
        limit: Maximum number of runs to return.

    Returns:
        OperationResult with list of run dicts.
    """
    from feedspine.ops import OperationResult

    if not hasattr(ctx.storage, "get_feed_runs"):
        return OperationResult.fail("Storage backend doesn't support run history.")

    runs = await ctx.storage.get_feed_runs(feed_name=feed_name, limit=limit)

    run_dicts = []
    for run in runs:
        duration = None
        if hasattr(run, "completed_at") and hasattr(run, "started_at") and run.completed_at and run.started_at:
            duration = (run.completed_at - run.started_at).total_seconds()

        run_dicts.append(
            {
                "run_id": getattr(run, "run_id", None) or getattr(run, "id", None),
                "feed_name": getattr(run, "feed_name", feed_name),
                "started_at": run.started_at.isoformat() if hasattr(run, "started_at") and run.started_at else None,
                "completed_at": run.completed_at.isoformat()
                if hasattr(run, "completed_at") and run.completed_at
                else None,
                "status": getattr(run, "status", "unknown"),
                "fetched_count": getattr(run, "fetched_count", 0) or 0,
                "new_count": getattr(run, "new_count", 0) or getattr(run, "records_new", 0) or 0,
                "error_count": getattr(run, "error_count", 0) or 0,
                "duration_seconds": duration,
            }
        )

    return OperationResult.ok(run_dicts)


async def fetch_health_alerts(
    ctx: OperationContext,
    threshold: int = 3,
    days: int = 7,
) -> OperationResult[list[dict[str, Any]]]:
    """Get feeds exceeding failure thresholds.

    Args:
        ctx: Operation context with storage backend.
        threshold: Consecutive failure count that triggers an alert.
        days: Number of days to analyze.

    Returns:
        OperationResult with list of alert dicts.
    """
    from feedspine.ops import OperationResult

    repo = _get_health_repo(ctx)
    if repo is None or not hasattr(repo, "get_failing_feeds"):
        return OperationResult.fail("Health metrics not available with this storage backend.")

    alerts = repo.get_failing_feeds(threshold, days)
    return OperationResult.ok(alerts)
