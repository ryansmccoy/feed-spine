"""Enrichment API routes — WorkItem-based batch enrichment.

Creates one WorkItem per record × enricher via
``create_enrichment_work_items()``.  Status is tracked through the
``EnrichmentBatch`` projection.

Delegates all business logic to :mod:`feedspine.ops.enrich`.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from feedspine.api.models import EnrichmentStatsResponse
from feedspine.ops import OperationContext

router = APIRouter(prefix="/api/v1/enrich", tags=["enrichment"])


# ── Request/Response Models ──────────────────────────────


class EnrichRequest(BaseModel):
    """Request to enrich records."""

    enricher: str = Field(..., description="Enricher to use: passthrough, metadata, entity")
    record_ids: list[str] = Field(..., description="Record IDs to enrich", min_length=1)
    source_layer: str = Field("BRONZE", description="Layer records are currently at")
    target_layer: str = Field("SILVER", description="Layer records should be promoted to")


class EnrichResponse(BaseModel):
    """Response from batch enrichment creation."""

    batch_id: str
    work_items_created: int


class BatchStatusResponse(BaseModel):
    """Enrichment batch status."""

    batch_id: str
    enricher: str
    status: str
    total: int
    succeeded: int
    queued: int
    leased: int
    dead_lettered: int
    cancelled: int
    created_at: str | None = None


# ── Helper ───────────────────────────────────────────────


def _make_ctx(request: Request) -> OperationContext:
    """Build an OperationContext from the request's app state."""
    return OperationContext(
        storage=request.app.state.storage,
        work_item_store=getattr(request.app.state, "work_item_store", None),
        caller="api",
    )


# ── Endpoints ────────────────────────────────────────────


@router.get("/enrichers", response_model=list[dict])
async def list_enrichers(request: Request) -> list[dict]:
    """List available enrichment plugins.

    Returns the known enricher names that can be referenced in
    ``POST /api/v1/enrich/`` requests.
    """
    known = ["passthrough", "metadata", "entity"]
    return [{"name": n, "description": f"{n} enricher"} for n in known]


@router.post("/", response_model=EnrichResponse, status_code=202)
async def enrich_records(
    request: Request,
    payload: EnrichRequest,
) -> EnrichResponse:
    """Create enrichment WorkItems for the given records.

    Each record gets one WorkItem with ``workflow="feed.enrich"``.
    Items are claimed and processed by ``FeedEnrichmentWorker``.
    """
    from feedspine.ops.enrich import submit_enrichment_batch

    result = await submit_enrichment_batch(
        _make_ctx(request),
        enricher_name=payload.enricher,
        record_ids=payload.record_ids,
        source_layer=payload.source_layer,
        target_layer=payload.target_layer,
    )

    if not result.success:
        raise HTTPException(status_code=503, detail=result.error)

    return EnrichResponse(
        batch_id=result.data["batch_id"],
        work_items_created=result.data["count"],
    )


@router.get("/batches/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(request: Request, batch_id: str) -> BatchStatusResponse:
    """Get the status of an enrichment batch."""
    from feedspine.ops.enrich import get_batch_status as _get_batch_status

    result = await _get_batch_status(_make_ctx(request), batch_id=batch_id)

    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)

    return BatchStatusResponse(**result.data)


@router.get("/stats", response_model=EnrichmentStatsResponse)
async def enrichment_stats(
    request: Request,
) -> EnrichmentStatsResponse:
    """Get enrichment statistics (layer distribution, record counts).

    Shows the current distribution of records across layers and other stats.
    """
    from feedspine.ops.stats import fetch_layer_distribution

    result = await fetch_layer_distribution(
        OperationContext(storage=request.app.state.storage, caller="api"),
    )

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    return {
        "total_records": result.data["total"],
        "by_layer": {k.upper(): v for k, v in result.data["by_layer"].items()},
    }
