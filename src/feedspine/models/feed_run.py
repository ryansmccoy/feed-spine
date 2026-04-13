"""FeedRunProjection — non-persisted view over spine-core WorkItems.

Replaces the old ``FeedRun`` model.  Status and metrics are derived
from a single ``core_work_items`` row whose workflow is ``feed.collect``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FeedRunProjection:
    """Read-only projection of a feed collection work item.

    Built from a ``WorkItemStore`` dict whose ``workflow == "feed.collect"``.
    Metrics are extracted from ``result_json`` (populated by
    ``FeedCollectionRuntime`` on completion).

    Attributes:
        work_item_id: The spine-core work item ID.
        feed_name: Feed adapter name (from ``params_json``).
        status: Mapped from WorkItem ``state``.
        started_at: When the item was leased (``locked_at``).
        completed_at: Completion timestamp.
        items_processed: Total records processed.
        items_new: New records stored.
        items_duplicate: Deduplicated records.
        items_failed: Records with errors.
        errors: Error description if failed.
    """

    work_item_id: int
    feed_name: str
    status: str
    started_at: str | None
    completed_at: str | None
    items_processed: int = 0
    items_new: int = 0
    items_duplicate: int = 0
    items_failed: int = 0
    errors: str | None = None

    @classmethod
    def from_work_item(cls, item: dict[str, Any]) -> FeedRunProjection:
        """Build a projection from a WorkItem dict.

        Args:
            item: Dict returned by ``WorkItemStore`` methods
                (``get_by_id``, ``claim``, ``list_by_batch``, etc.).

        Returns:
            Populated projection with metrics from ``result_json``.
        """
        params = item.get("params_json")
        if isinstance(params, str):
            params = json.loads(params)
        params = params or {}

        result = item.get("result_json")
        if isinstance(result, str):
            result = json.loads(result)
        result = result or {}

        return cls(
            work_item_id=item["id"],
            feed_name=params.get("feed_name", "unknown"),
            status=_map_state(item.get("state", "QUEUED")),
            started_at=item.get("locked_at"),
            completed_at=item.get("completed_at"),
            items_processed=result.get("processed", 0),
            items_new=result.get("new", result.get("records_stored", 0)),
            items_duplicate=result.get("duplicates", 0),
            items_failed=result.get("errors", 0),
            errors=item.get("last_error"),
        )


def _map_state(state: str) -> str:
    """Map WorkItem state to a user-facing status string."""
    return {
        "QUEUED": "QUEUED",
        "LEASED": "RUNNING",
        "SUCCEEDED": "SUCCEEDED",
        "DEAD_LETTERED": "FAILED",
        "CANCELLED": "CANCELLED",
    }.get(state, state)
