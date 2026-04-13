"""Batch enrichment work-item creator.

Creates one WorkItem per record × enricher using ``runner_dispatch``
execution mode (dispatched by spine-core Runner to an Executor).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from feedspine._vendor.execution import BackoffPolicy, DispatchConfig

if TYPE_CHECKING:
    from typing import Any

    class WorkItemStore:
        """Stub for type checking — actual impl from spine-core."""
        def create(self, **kwargs: Any) -> int: ...


def create_enrichment_work_items(
    work_item_store: WorkItemStore,
    enricher_name: str,
    record_ids: list[str],
    *,
    batch_id: str | None = None,
    source_layer: str = "BRONZE",
    target_layer: str = "SILVER",
    max_attempts: int = 3,
) -> tuple[str, list[int]]:
    """Create one WorkItem per record for enrichment.

    Called from both:
    - POST /enrich API handler (manual trigger)
    - Event-rule callback on ``feed.collection.completed`` (automatic)

    Args:
        work_item_store: spine-core work-item store.
        enricher_name: Name of the enricher to run.
        record_ids: Record IDs to enrich.
        batch_id: Optional grouping ID. Generated if omitted.
        source_layer: Layer records are currently at.
        target_layer: Layer records should be promoted to.
        max_attempts: Max retry attempts per work item.

    Returns:
        ``(batch_id, list_of_created_work_item_ids)``
    """
    batch_id = batch_id or uuid4().hex[:12]
    bp = BackoffPolicy(
        strategy="exponential",
        base_seconds=5.0,
        max_seconds=300.0,
    )
    now_iso = datetime.now(UTC).isoformat()
    item_ids: list[int] = []

    for record_id in record_ids:
        item = work_item_store.create(
            domain="feed-spine",
            workflow="feed.enrich",
            partition_key=record_id,
            params_json={
                "record_id": record_id,
                "enricher": enricher_name,
                "source_layer": source_layer,
                "target_layer": target_layer,
                "batch_id": batch_id,
            },
            execution_mode="runner_dispatch",
            dispatch_config=DispatchConfig(type="feed.enrich"),
            group_key=f"feed-spine:enrich:{enricher_name}",
            max_attempts=max_attempts,
            backoff_policy=bp,
            desired_at=now_iso,
            owner_service="feed-spine",
            batch_id=batch_id,
        )
        item_ids.append(item["id"])

    return batch_id, item_ids
