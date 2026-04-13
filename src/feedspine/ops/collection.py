"""Collection operations — pure business logic.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`.  They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Functions
---------
submit_collection
    Create collection WorkItems for specified feeds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.ops import OperationContext, OperationResult


async def submit_collection(
    ctx: OperationContext,
    feed_names: list[str],
) -> OperationResult[list[dict[str, Any]]]:
    """Create collection WorkItems for the specified feeds.

    Each feed gets one WorkItem with ``workflow="feed.collect"``.
    Items are processed by the spine-core execution engine asynchronously.

    Args:
        ctx: Operation context (must have ``work_item_store`` set).
        feed_names: List of feed names to collect.

    Returns:
        OperationResult with list of ``{"feed_name": ..., "work_item_id": ...}`` dicts.
    """
    from datetime import UTC, datetime

    from feedspine.ops import OperationResult

    if ctx.work_item_store is None:
        return OperationResult.fail("WorkItemStore not configured")

    if not feed_names:
        return OperationResult.fail("No feed names provided")

    now_iso = datetime.now(UTC).isoformat()
    created: list[dict[str, Any]] = []

    for name in feed_names:
        item = ctx.work_item_store.create(
            domain="feed-spine",
            workflow="feed.collect",
            partition_key=name,
            params_json={"feed_name": name},
            desired_at=now_iso,
            execution_mode="runner_dispatch",
            owner_service="feed-spine",
        )
        created.append({"feed_name": name, "work_item_id": item["id"]})

    return OperationResult.ok(created)
