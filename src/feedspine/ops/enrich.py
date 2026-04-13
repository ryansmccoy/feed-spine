"""Enrichment operations — pure business logic.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`.  They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Functions
---------
submit_enrichment_batch
    Create enrichment WorkItems for a set of records.
get_batch_status
    Get the status of an enrichment batch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.ops import OperationContext, OperationResult


async def submit_enrichment_batch(
    ctx: OperationContext,
    enricher_name: str,
    record_ids: list[str],
    source_layer: str = "BRONZE",
    target_layer: str = "SILVER",
) -> OperationResult[dict[str, Any]]:
    """Create enrichment WorkItems for the given records.

    Each record gets one WorkItem with ``workflow="feed.enrich"``.
    Items are claimed and processed by ``FeedEnrichmentWorker``.

    Args:
        ctx: Operation context (must have ``work_item_store`` set).
        enricher_name: Enricher to use (passthrough, metadata, entity).
        record_ids: List of record IDs to enrich.
        source_layer: Layer records are currently at.
        target_layer: Layer records should be promoted to.

    Returns:
        OperationResult with ``batch_id`` and ``work_item_ids``.
    """
    from feedspine.enricher.batch import create_enrichment_work_items
    from feedspine.ops import OperationResult

    if ctx.work_item_store is None:
        return OperationResult.fail("WorkItemStore not configured")

    if not record_ids:
        return OperationResult.fail("No record IDs provided")

    batch_id, item_ids = create_enrichment_work_items(
        work_item_store=ctx.work_item_store,
        enricher_name=enricher_name,
        record_ids=record_ids,
        source_layer=source_layer,
        target_layer=target_layer,
    )

    return OperationResult.ok(
        {
            "batch_id": batch_id,
            "work_item_ids": item_ids,
            "enricher": enricher_name,
            "count": len(item_ids),
        }
    )


async def get_batch_status(
    ctx: OperationContext,
    batch_id: str,
) -> OperationResult[dict[str, Any]]:
    """Get the status of an enrichment batch.

    Args:
        ctx: Operation context (must have ``work_item_store`` set).
        batch_id: The batch ID to look up.

    Returns:
        OperationResult with batch status dict.
    """
    from dataclasses import asdict

    from feedspine.models.enrichment_batch import EnrichmentBatch
    from feedspine.ops import OperationResult

    if ctx.work_item_store is None:
        return OperationResult.fail("WorkItemStore not configured")

    items = ctx.work_item_store.list_by_batch(batch_id)
    if not items:
        return OperationResult.fail(f"Batch not found: {batch_id}")

    batch = EnrichmentBatch.from_work_items(batch_id, items)
    data = asdict(batch)
    data["status"] = batch.status
    return OperationResult.ok(data)
