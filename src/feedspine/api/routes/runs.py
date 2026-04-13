"""Feed run history API routes — WorkItem-based projections.

Queries ``WorkItem`` rows with ``domain="feed-spine"`` and
``workflow="feed.collect"`` to build ``FeedRunProjection`` views.
"""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from feedspine.models.feed_run import FeedRunProjection
from feedspine.ops import OperationContext
from feedspine.ops.runs import query_feed_runs

router = APIRouter(prefix="/api/v1", tags=["runs"])


# =============================================================================
# Response Models
# =============================================================================


class RunSummaryResponse(BaseModel):
    """Summary of a feed collection run."""

    work_item_id: int
    feed_name: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    items_processed: int = 0
    items_new: int = 0
    items_duplicate: int = 0
    items_failed: int = 0
    errors: list[str] = Field(default_factory=list)


class RunListResponse(BaseModel):
    """Paginated list of feed runs."""

    runs: list[RunSummaryResponse]
    total: int
    limit: int
    offset: int


# =============================================================================
# Routes
# =============================================================================


@router.get("/feeds/{feed_name}/runs", response_model=RunListResponse)
async def list_runs_for_feed(
    request: Request,
    feed_name: str,
    status: str | None = Query(None, description="Filter by status: QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> RunListResponse:
    """List collection runs for a specific feed."""
    ctx = _make_ctx(request)
    result = await query_feed_runs(ctx, feed_name=feed_name, status=status, limit=500)

    if not result.success:
        raise HTTPException(status_code=503, detail=result.error)

    projections = result.data or []
    total = len(projections)
    page = projections[offset : offset + limit]

    return RunListResponse(
        runs=[RunSummaryResponse(**asdict(p)) for p in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    request: Request,
    feed_name: str | None = Query(None, description="Filter by feed name"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> RunListResponse:
    """List all collection runs across feeds."""
    ctx = _make_ctx(request)
    result = await query_feed_runs(ctx, feed_name=feed_name, status=status, limit=500)

    if not result.success:
        raise HTTPException(status_code=503, detail=result.error)

    projections = result.data or []
    total = len(projections)
    page = projections[offset : offset + limit]

    return RunListResponse(
        runs=[RunSummaryResponse(**asdict(p)) for p in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{work_item_id}", response_model=RunSummaryResponse)
async def get_run(request: Request, work_item_id: int) -> RunSummaryResponse:
    """Get a single run by its WorkItem ID."""
    work_item_store = getattr(request.app.state, "work_item_store", None)
    if work_item_store is None:
        raise HTTPException(status_code=503, detail="WorkItemStore not configured")

    item = work_item_store.get_by_id(work_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {work_item_id}")

    if item.get("workflow") != "feed.collect":
        raise HTTPException(status_code=404, detail=f"Run not found: {work_item_id}")

    projection = FeedRunProjection.from_work_item(item)
    return RunSummaryResponse(**asdict(projection))


# =============================================================================
# Helpers
# =============================================================================


def _make_ctx(request: Request) -> OperationContext:
    """Build an OperationContext from the FastAPI request."""
    return OperationContext(
        storage=getattr(request.app.state, "storage", None),
        work_item_store=getattr(request.app.state, "work_item_store", None),
        caller="api",
    )
