"""Unified Feed Timeline API route.

Provides a merged, time-sorted view of records across all feeds.
Supports pagination, layer filtering, and time-range queries.

Example:
    >>> from feedspine.api.routes.timeline import router
    >>> # Include in FastAPI app:
    >>> # app.include_router(router)
"""

from datetime import datetime

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from feedspine.api.models import FeedSourcesResponse

router = APIRouter(prefix="/api/v1/timeline", tags=["timeline"])


# =============================================================================
# Response Models
# =============================================================================


class TimelineItem(BaseModel):
    """A single item in the unified feed timeline."""

    id: str = Field(..., description="Record identifier")
    natural_key: str = Field(..., description="Record natural key")
    layer: str = Field(..., description="Medallion layer (bronze/silver/gold)")
    published_at: datetime | None = Field(None, description="When the content was published")
    captured_at: datetime | None = Field(None, description="When the record was captured")
    source: str | None = Field(None, description="Feed source name")
    source_type: str | None = Field(None, description="Feed adapter type")
    title: str | None = Field(None, description="Title or summary extracted from content")
    content_preview: str | None = Field(None, description="Truncated content preview")
    seen_count: int = Field(1, description="Number of times this record was seen")
    version: int = Field(1, description="Record version number")


class TimelineResponse(BaseModel):
    """Paginated timeline response."""

    items: list[TimelineItem] = Field(default_factory=list, description="Timeline items")
    total: int = Field(0, description="Total matching records")
    limit: int = Field(50, description="Page size")
    offset: int = Field(0, description="Offset")
    has_more: bool = Field(False, description="Whether more records exist")


# =============================================================================
# Routes
# =============================================================================


def _make_ctx(request: Request):
    """Build an OperationContext from the FastAPI request."""
    from feedspine.ops import OperationContext

    return OperationContext(
        storage=request.app.state.storage,
        search=getattr(request.app.state, "search", None),
        caller="api",
    )


@router.get("", response_model=TimelineResponse)
async def get_timeline(
    request: Request,
    layer: str | None = Query(None, description="Filter by layer (bronze/silver/gold)"),
    source: str | None = Query(None, description="Filter by feed source name"),
    since: datetime | None = Query(None, description="Only items captured after this timestamp"),
    until: datetime | None = Query(None, description="Only items captured before this timestamp"),
    limit: int = Query(50, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    order: str = Query("desc", description="Sort order: asc or desc by captured_at"),
) -> TimelineResponse:
    """Unified feed timeline — merged, time-sorted records across all feeds."""
    from feedspine.ops.feed import fetch_timeline

    ctx = _make_ctx(request)
    result = await fetch_timeline(
        ctx,
        layer=layer,
        source=source,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    if not result.success:
        return TimelineResponse()

    tl = result.data
    return TimelineResponse(
        items=[
            TimelineItem(
                id=item.id,
                natural_key=item.natural_key,
                layer=item.layer or "",
                published_at=item.published_at,
                captured_at=item.captured_at,
                source=item.source,
                source_type=item.source_type,
                title=item.title,
                content_preview=item.content_preview,
                version=item.version,
            )
            for item in tl.items
        ],
        total=tl.total,
        limit=tl.limit,
        offset=tl.offset,
        has_more=tl.has_more,
    )


@router.get("/sources", response_model=FeedSourcesResponse)
async def list_sources(request: Request) -> FeedSourcesResponse:
    """List available feed sources."""
    from feedspine.ops.feed import fetch_sources

    ctx = _make_ctx(request)
    result = await fetch_sources(ctx)

    if not result.success:
        return FeedSourcesResponse(sources=[], total=0)

    sources = result.data or []
    return FeedSourcesResponse(
        sources=[
            {
                "name": s.name,
                "total_runs": s.total_runs,
                "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                "status": s.status,
            }
            for s in sources
        ],
        total=len(sources),
    )
