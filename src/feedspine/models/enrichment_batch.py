"""EnrichmentBatch — non-persisted projection over work items.

Replaces the old ``EnrichmentJob`` model. Status is derived from the
aggregate state distribution of child work items sharing a ``batch_id``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EnrichmentBatch:
    """Read-only aggregate computed from WorkItem rows for a batch.

    Attributes:
        batch_id: Grouping identifier for the batch.
        enricher: Name of the enricher being run.
        total: Total work items in the batch.
        succeeded: Items that completed successfully.
        queued: Items waiting to be claimed.
        leased: Items currently being processed.
        dead_lettered: Items that exhausted retries.
        canceled: Items that were cancelled.
        created_at: Earliest creation timestamp in the batch.
    """

    batch_id: str
    enricher: str
    total: int
    succeeded: int
    queued: int
    leased: int
    dead_lettered: int
    cancelled: int = 0
    created_at: str | None = None

    @property
    def status(self) -> str:
        """Derive batch status from child work-item state distribution."""
        if self.total == 0:
            return "EMPTY"
        if self.cancelled == self.total:
            return "CANCELLED"
        if self.total == self.succeeded:
            return "COMPLETED"
        terminal = self.succeeded + self.dead_lettered + self.cancelled
        if terminal == self.total and self.dead_lettered > 0:
            return "COMPLETED_WITH_FAILURES"
        if self.succeeded > 0 and (self.queued > 0 or self.leased > 0):
            return "PARTIAL_SUCCESS"
        if self.leased > 0:
            return "IN_PROGRESS"
        return "QUEUED"

    @classmethod
    def from_work_items(
        cls,
        batch_id: str,
        items: list[dict[str, Any]],
    ) -> EnrichmentBatch:
        """Build a projection from a list of work-item dicts.

        Typically called with the result of
        ``WorkItemStore.list_by_batch(batch_id)``.
        """

        def _enricher(items: list[dict[str, Any]]) -> str:
            if not items:
                return "unknown"
            params = items[0].get("params_json")
            if isinstance(params, str):
                params = json.loads(params)
            if isinstance(params, dict):
                return params.get("enricher", "unknown")
            return "unknown"

        return cls(
            batch_id=batch_id,
            enricher=_enricher(items),
            total=len(items),
            succeeded=sum(1 for i in items if i.get("state") == "SUCCEEDED"),
            queued=sum(1 for i in items if i.get("state") == "QUEUED"),
            leased=sum(1 for i in items if i.get("state") == "LEASED"),
            dead_lettered=sum(1 for i in items if i.get("state") == "DEAD_LETTERED"),
            cancelled=sum(1 for i in items if i.get("state") == "CANCELLED"),
            created_at=min(
                (i["created_at"] for i in items if i.get("created_at")),
                default=None,
            ),
        )
