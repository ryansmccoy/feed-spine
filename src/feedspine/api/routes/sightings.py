"""Sightings API routes.

Thin transport layer for sighting data — delegates to storage protocol
methods (``get_sightings``, ``record_sighting``).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from spine.core.logging import get_logger

from feedspine.models.sighting import Sighting

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/sightings", tags=["sightings"])


# =============================================================================
# Pydantic Models
# =============================================================================


class SightingResponse(BaseModel):
    """Sighting response model."""

    id: str
    natural_key: str
    record_id: str | None = None
    source: str
    seen_at: datetime
    is_new: bool
    raw_data_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SightingListResponse(BaseModel):
    """Paginated list of sightings."""

    sightings: list[SightingResponse]
    total: int
    limit: int
    offset: int


class SightingCreate(BaseModel):
    """Request body for POST /api/v1/sightings."""

    natural_key: str = Field(..., min_length=1, max_length=1024, description="Natural key being sighted")
    source: str = Field(..., min_length=1, max_length=256, description="Feed/source reporting this sighting")
    record_id: str | None = Field(None, description="Associated record ID")
    raw_data_hash: str | None = Field(None, description="Hash of raw data for change detection")
    metadata: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Helpers
# =============================================================================


def _sighting_to_response(s: Any) -> SightingResponse:
    """Convert a Sighting domain object to SightingResponse."""
    return SightingResponse(
        id=getattr(s, "id", ""),
        natural_key=getattr(s, "natural_key", ""),
        record_id=getattr(s, "record_id", None),
        source=getattr(s, "source", ""),
        seen_at=getattr(s, "seen_at", datetime.now(UTC)),
        is_new=getattr(s, "is_new", True),
        raw_data_hash=getattr(s, "raw_data_hash", None),
        metadata=getattr(s, "metadata", {}),
    )


# =============================================================================
# Routes
# =============================================================================


@router.get("", response_model=SightingListResponse)
async def list_sightings(
    request: Request,
    natural_key: str | None = Query(None, description="Filter by natural key"),
    source: str | None = Query(None, description="Filter by source"),
    limit: int = Query(100, ge=1, le=1000, description="Max sightings to return"),
    offset: int = Query(0, ge=0, description="Skip sightings"),
) -> SightingListResponse:
    """List sightings with optional filtering."""
    storage = request.app.state.storage

    if natural_key:
        domain_sightings = await storage.get_sightings(natural_key)
    else:
        domain_sightings = []

    sightings = [_sighting_to_response(s) for s in domain_sightings]

    # Apply source filter
    if source:
        sightings = [s for s in sightings if source.lower() in s.source.lower()]

    # Sort by seen_at descending
    sightings.sort(key=lambda s: s.seen_at, reverse=True)

    total = len(sightings)
    paginated = sightings[offset : offset + limit]

    return SightingListResponse(
        sightings=paginated,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=SightingResponse, status_code=201)
async def create_sighting(request: Request, body: SightingCreate) -> SightingResponse:
    """Record a manual sighting."""
    storage = request.app.state.storage

    sighting = Sighting(
        id=f"sight-{uuid4().hex[:8]}",
        natural_key=body.natural_key,
        record_id=body.record_id,
        source=body.source,
        seen_at=datetime.now(UTC),
        is_new=True,
        raw_data_hash=body.raw_data_hash,
        metadata=body.metadata,
    )

    is_first = await storage.record_sighting(sighting)
    if not is_first:
        sighting = sighting.model_copy(update={"is_new": False})

    return _sighting_to_response(sighting)


@router.delete("/{sighting_id}", status_code=204)
async def delete_sighting(request: Request, sighting_id: str) -> None:
    """Delete a sighting by ID.

    Requires ``delete_sighting`` on the storage backend.
    """
    storage = request.app.state.storage

    if not hasattr(storage, "delete_sighting"):
        raise HTTPException(
            status_code=501,
            detail="Delete not supported by current storage backend",
        )

    deleted = await storage.delete_sighting(sighting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Sighting not found: {sighting_id}")
    logger.info("Deleted sighting id=%s", sighting_id)
