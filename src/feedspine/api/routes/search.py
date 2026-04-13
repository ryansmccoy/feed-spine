"""Search API routes.

Provides search endpoints for indexed records.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from feedspine.api.models import SearchResponse
from feedspine.ops import OperationContext
from feedspine.ops.query import execute_search

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def _make_ctx(request: Request) -> OperationContext:
    """Build an OperationContext from the FastAPI request."""
    return OperationContext(
        storage=request.app.state.storage,
        search=getattr(request.app.state, "search", None),
        caller="api",
    )


@router.get("", response_model=SearchResponse)
async def search_records(
    request: Request,
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Skip results"),
) -> SearchResponse:
    """Search indexed records."""
    ctx = _make_ctx(request)
    result = await execute_search(ctx, query=q, search_type="fulltext", limit=limit, offset=offset)
    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    return {
        "results": result.data["results"],
        "total_count": result.data["total_count"],
        "query_time_ms": result.data["query_time_ms"],
    }
