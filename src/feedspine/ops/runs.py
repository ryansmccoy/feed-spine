"""Feed-run query operations — pure business logic.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`.  They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Functions
---------
query_feed_runs
    Query feed collection runs from the WorkItem store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.models.feed_run import FeedRunProjection
    from feedspine.ops import OperationContext, OperationResult


_ALL_STATES = ["QUEUED", "LEASED", "SUCCEEDED", "DEAD_LETTERED", "CANCELLED"]

_STATUS_TO_STATES: dict[str, list[str]] = {
    "QUEUED": ["QUEUED"],
    "RUNNING": ["LEASED"],
    "SUCCEEDED": ["SUCCEEDED"],
    "FAILED": ["DEAD_LETTERED"],
    "CANCELLED": ["CANCELLED"],
}


async def query_feed_runs(
    ctx: OperationContext,
    *,
    feed_name: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> OperationResult[list[FeedRunProjection]]:
    """Query feed collection runs from the WorkItem store.

    Queries ``WorkItem`` rows with ``domain="feed-spine"`` and
    ``workflow="feed.collect"``, then builds
    :class:`~feedspine.models.feed_run.FeedRunProjection` views.

    Args:
        ctx: Operation context — must have ``work_item_store`` set.
        feed_name: Optional filter by feed name (matches ``partition_key``).
        status: Optional user-facing status filter
            (``QUEUED``, ``RUNNING``, ``SUCCEEDED``, ``FAILED``, ``CANCELLED``).
        limit: Maximum number of runs to return.

    Returns:
        OperationResult with a list of FeedRunProjection, sorted newest first.
    """
    from feedspine.models.feed_run import FeedRunProjection
    from feedspine.ops import OperationResult

    if ctx.work_item_store is None:
        return OperationResult.fail("WorkItemStore not configured on OperationContext")

    # Resolve state filter
    if status:
        state_filter = _STATUS_TO_STATES.get(status.upper(), [])
        if not state_filter:
            return OperationResult.ok([], metadata={"total": 0})
    else:
        state_filter = _ALL_STATES

    items: list[dict[str, Any]] = []
    for state in state_filter:
        items.extend(ctx.work_item_store.list_by_state(state, domain="feed-spine", limit=500))

    # Filter to feed.collect workflow
    items = [i for i in items if i.get("workflow") == "feed.collect"]

    # Filter by feed name if specified
    if feed_name:
        items = [i for i in items if i.get("partition_key") == feed_name]

    # Build projections, sorted newest first
    projections = [FeedRunProjection.from_work_item(i) for i in items]
    projections.sort(key=lambda p: p.started_at or "", reverse=True)
    projections = projections[:limit]

    return OperationResult.ok(
        projections,
        metadata={"total": len(projections)},
    )
