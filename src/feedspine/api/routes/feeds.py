"""Feed management API routes.

Provides CRUD operations for feed configurations and manual feed triggers.
Uses ``request.app.state.storage`` for persistence when the backend supports
feed-config operations, falling back to an in-memory demo store otherwise.

Example:
    >>> from feedspine.api.routes.feeds import router
    >>> # Include in FastAPI app:
    >>> # app.include_router(router)
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel, Field
from spine.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/feeds", tags=["feeds"])


# =============================================================================
# Pydantic Models
# =============================================================================


class FeedConfig(BaseModel):
    """Feed configuration model for API requests."""

    name: str = Field(..., min_length=1, max_length=256, description="Human-readable feed name")
    adapter_type: str = Field(
        ...,
        description="Feed adapter type: 'rss', 'json', 'file', 'csv', 'polygon_earnings', 'sec_edgar'",
    )
    url: str | None = Field(None, description="URL for remote feeds (RSS, JSON)")
    path: str | None = Field(None, description="File path for local feeds")
    schedule: str | None = Field(None, description="Cron expression for scheduled runs")
    enabled: bool = Field(True, description="Whether the feed is active")
    config: dict[str, Any] = Field(default_factory=dict, description="Adapter-specific configuration")


class FeedConfigResponse(FeedConfig):
    """Feed configuration response with server-generated fields."""

    id: str = Field(..., description="Unique feed identifier")
    created_at: datetime = Field(..., description="When the feed was created")
    updated_at: datetime = Field(..., description="When the feed was last updated")
    last_run_at: datetime | None = Field(None, description="When the feed last ran")
    last_run_status: str | None = Field(None, description="Status of the last run")


class FeedRunResponse(BaseModel):
    """Response model for feed run triggers."""

    run_id: str
    feed_id: str
    status: str
    message: str


# =============================================================================
# Storage helpers
# =============================================================================


def _has_feed_config_support(storage: Any) -> bool:
    """Check if the storage backend supports feed-config operations."""
    return hasattr(storage, "store_feed_config") and hasattr(storage, "list_feed_configs")


def _row_to_response(row: dict[str, Any]) -> FeedConfigResponse:
    """Convert a storage dict row to a FeedConfigResponse."""
    return FeedConfigResponse(
        id=row["id"],
        name=row["name"],
        adapter_type=row["adapter_type"],
        url=row.get("url"),
        path=row.get("path"),
        schedule=row.get("schedule"),
        enabled=bool(row.get("enabled", True)),
        config=row.get("config") if isinstance(row.get("config"), dict) else {},
        created_at=row.get("created_at", datetime.now(UTC)),
        updated_at=row.get("updated_at", datetime.now(UTC)),
        last_run_at=row.get("last_run_at"),
        last_run_status=row.get("last_run_status"),
    )


def _response_to_row(resp: FeedConfigResponse) -> dict[str, Any]:
    """Convert a FeedConfigResponse to a storage dict."""
    return {
        "id": resp.id,
        "name": resp.name,
        "adapter_type": resp.adapter_type,
        "url": resp.url,
        "path": resp.path,
        "schedule": resp.schedule,
        "enabled": resp.enabled,
        "config": resp.config,
        "created_at": resp.created_at.isoformat() if resp.created_at else None,
        "updated_at": resp.updated_at.isoformat() if resp.updated_at else None,
        "last_run_at": resp.last_run_at.isoformat() if resp.last_run_at else None,
        "last_run_status": resp.last_run_status,
    }


# =============================================================================
# Routes
# =============================================================================


@router.get("", response_model=list[FeedConfigResponse])
async def list_feeds(
    request: Request,
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    adapter_type: str | None = Query(None, description="Filter by adapter type"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> list[FeedConfigResponse]:
    """List all configured feeds with optional filtering."""
    storage = request.app.state.storage
    if _has_feed_config_support(storage):
        rows = await storage.list_feed_configs(
            enabled=enabled,
            adapter_type=adapter_type,
            limit=limit,
            offset=offset,
        )
        return [_row_to_response(r) for r in rows]

    # Fallback: empty list (no demo data needed once storage is wired)
    return []


@router.post("", response_model=FeedConfigResponse, status_code=201)
async def create_feed(request: Request, config: FeedConfig) -> FeedConfigResponse:
    """Create a new feed configuration."""
    storage = request.app.state.storage
    now = datetime.now(UTC)
    feed = FeedConfigResponse(
        id=f"feed-{uuid4().hex[:8]}",
        name=config.name,
        adapter_type=config.adapter_type,
        url=config.url,
        path=config.path,
        schedule=config.schedule,
        enabled=config.enabled,
        config=config.config,
        created_at=now,
        updated_at=now,
        last_run_at=None,
        last_run_status=None,
    )
    if _has_feed_config_support(storage):
        await storage.store_feed_config(_response_to_row(feed))
    return feed


@router.get("/{feed_id}", response_model=FeedConfigResponse)
async def get_feed(request: Request, feed_id: str) -> FeedConfigResponse:
    """Get a feed configuration by ID."""
    storage = request.app.state.storage
    if _has_feed_config_support(storage):
        row = await storage.get_feed_config(feed_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Feed not found: {feed_id}")
        return _row_to_response(row)
    raise HTTPException(status_code=404, detail=f"Feed not found: {feed_id}")


@router.put("/{feed_id}", response_model=FeedConfigResponse)
async def update_feed(request: Request, feed_id: str, config: FeedConfig) -> FeedConfigResponse:
    """Update a feed configuration."""
    storage = request.app.state.storage
    if _has_feed_config_support(storage):
        existing_row = await storage.get_feed_config(feed_id)
        if existing_row is None:
            raise HTTPException(status_code=404, detail=f"Feed not found: {feed_id}")
        now = datetime.now(UTC)
        updated = FeedConfigResponse(
            id=feed_id,
            name=config.name,
            adapter_type=config.adapter_type,
            url=config.url,
            path=config.path,
            schedule=config.schedule,
            enabled=config.enabled,
            config=config.config,
            created_at=existing_row.get("created_at", now),
            updated_at=now,
            last_run_at=existing_row.get("last_run_at"),
            last_run_status=existing_row.get("last_run_status"),
        )
        await storage.store_feed_config(_response_to_row(updated))
        return updated
    raise HTTPException(status_code=404, detail=f"Feed not found: {feed_id}")


@router.patch("/{feed_id}", response_model=FeedConfigResponse)
async def patch_feed(request: Request, feed_id: str, config: FeedConfig) -> FeedConfigResponse:
    """Partially update a feed configuration (alias for PUT)."""
    return await update_feed(request, feed_id, config)


@router.delete("/{feed_id}", status_code=204)
async def delete_feed(request: Request, feed_id: str) -> None:
    """Delete a feed configuration."""
    storage = request.app.state.storage
    if _has_feed_config_support(storage):
        existing = await storage.get_feed_config(feed_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Feed not found: {feed_id}")
        await storage.delete_feed_config(feed_id)
        logger.info("Deleted feed config id=%s", feed_id)
        return
    raise HTTPException(status_code=404, detail=f"Feed not found: {feed_id}")


@router.post("/{feed_id}/run", response_model=FeedRunResponse, status_code=202)
async def run_feed(
    request: Request,
    feed_id: str,
    background_tasks: BackgroundTasks,
) -> FeedRunResponse:
    """Trigger a manual feed collection run."""
    storage = request.app.state.storage

    # Verify feed exists
    feed_name = feed_id
    if _has_feed_config_support(storage):
        existing = await storage.get_feed_config(feed_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Feed not found: {feed_id}")
        feed_name = existing.get("name", feed_id)

    run_id = f"run-{uuid4().hex[:8]}"

    # Start a feed run record if storage supports it
    if hasattr(storage, "start_feed_run"):
        await storage.start_feed_run(run_id, feed_name)

    return FeedRunResponse(
        run_id=run_id,
        feed_id=feed_id,
        status="started",
        message=f"Collection started for feed '{feed_name}'",
    )


@router.post("/{feed_id}/collect", response_model=FeedRunResponse, status_code=202)
async def collect_feed(
    request: Request,
    feed_id: str,
    background_tasks: BackgroundTasks,
) -> FeedRunResponse:
    """Trigger a feed collection (alias for ``/run``)."""
    return await run_feed(request, feed_id, background_tasks)
