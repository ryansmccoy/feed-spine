"""RSS/Atom Syndication Route for FeedSpine.

Provides RSS 2.0 and Atom 1.0 feeds of the unified timeline, enabling
standard feed reader consumption of collected data.

Endpoints:
    GET /api/v1/syndication/rss   — RSS 2.0 feed
    GET /api/v1/syndication/atom  — Atom 1.0 feed

Example:
    >>> from feedspine.api.routes.syndication import router
    >>> app.include_router(router)
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from feedspine.ops import OperationContext
from feedspine.ops.feed import fetch_timeline
from feedspine.ops.feed_formats import generate_atom_feed, generate_rss_feed

router = APIRouter(prefix="/api/v1/syndication", tags=["syndication"])


def _make_ctx(request: Request) -> OperationContext:
    """Build an OperationContext from the FastAPI request."""
    return OperationContext(
        storage=request.app.state.storage,
        search=getattr(request.app.state, "search", None),
        caller="api",
    )


@router.get("", response_model=dict)
async def list_syndication_formats(request: Request) -> dict:
    """List available syndication feed formats.

    Returns the available feed format endpoints and their URLs.
    """
    base = str(request.base_url).rstrip("/")
    return {
        "formats": [
            {"name": "rss", "url": f"{base}/api/v1/syndication/rss", "media_type": "application/rss+xml"},
            {"name": "atom", "url": f"{base}/api/v1/syndication/atom", "media_type": "application/atom+xml"},
        ],
    }


@router.get("/rss", response_class=Response)
async def rss_feed(
    request: Request,
    layer: str | None = Query(None, description="Filter by layer (bronze/silver/gold)"),
    limit: int = Query(50, ge=1, le=200, description="Number of items"),
) -> Response:
    """RSS 2.0 feed of the unified timeline.

    Standard RSS feed consumable by any feed reader (Feedly, Inoreader,
    Thunderbird, etc.).

    Examples:
        GET /api/v1/syndication/rss
        GET /api/v1/syndication/rss?layer=silver&limit=25
    """
    ctx = _make_ctx(request)
    result = await fetch_timeline(ctx, layer=layer, limit=limit)

    items = result.data.items if result.success else []
    xml = generate_rss_feed(items, layer=layer or "all")

    return Response(
        content=xml,
        media_type="application/rss+xml; charset=utf-8",
    )


@router.get("/atom", response_class=Response)
async def atom_feed(
    request: Request,
    layer: str | None = Query(None, description="Filter by layer (bronze/silver/gold)"),
    limit: int = Query(50, ge=1, le=200, description="Number of entries"),
) -> Response:
    """Atom 1.0 feed of the unified timeline.

    Atom 1.0 feed format — generally preferred over RSS for its richer
    metadata support. Consumable by any Atom-compatible reader.

    Examples:
        GET /api/v1/syndication/atom
        GET /api/v1/syndication/atom?layer=gold&limit=10
    """
    ctx = _make_ctx(request)
    result = await fetch_timeline(ctx, layer=layer, limit=limit)

    items = result.data.items if result.success else []
    xml = generate_atom_feed(items, layer=layer or "all")

    return Response(
        content=xml,
        media_type="application/atom+xml; charset=utf-8",
    )
