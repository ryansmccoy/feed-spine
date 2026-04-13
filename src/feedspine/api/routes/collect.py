"""Collection API routes — WorkItem-based.

Triggers feed collection by creating a spine-core WorkItem with
``workflow="feed.collect"``.  The execution engine picks it up
asynchronously.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from feedspine.ops import OperationContext
from feedspine.ops.collection import submit_collection

router = APIRouter(prefix="/api/v1", tags=["collection"])


class CollectResponse(BaseModel):
    work_item_id: int
    status: str = "QUEUED"
    feed_name: str


def _make_ctx(request: Request) -> OperationContext:
    """Build an OperationContext from the FastAPI request."""
    return OperationContext(
        storage=request.app.state.storage,
        work_item_store=getattr(request.app.state, "work_item_store", None),
        caller="api",
    )


@router.post("/feeds/{feed_name}/collect", response_model=CollectResponse, status_code=202)
async def trigger_collection(
    request: Request,
    feed_name: str,
) -> CollectResponse:
    """Create a WorkItem to collect from the named feed.

    Returns immediately with 202 Accepted. The spine-core execution
    engine will claim and run the work item asynchronously.
    """
    ctx = _make_ctx(request)
    result = await submit_collection(ctx, feed_names=[feed_name])
    if not result.success:
        raise HTTPException(status_code=503, detail=result.error)

    items = result.data
    item = items[0]
    return CollectResponse(
        work_item_id=item["work_item_id"],
        status="QUEUED",
        feed_name=feed_name,
    )
