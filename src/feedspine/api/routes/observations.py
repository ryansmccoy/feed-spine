"""Observations API routes.

Provides CRUD operations for observations (specialized records from various sources).
Uses ``request.app.state.storage`` for persistence when the backend supports
observation operations (``store_observation``, ``list_observations``).

Example:
    >>> from feedspine.api.routes.observations import router
    >>> # Include in FastAPI app:
    >>> # app.include_router(router)
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/observations", tags=["observations"])


# =============================================================================
# Pydantic Models
# =============================================================================


class ObservationCreate(BaseModel):
    """Create a generic observation."""

    observation_type: str = Field(..., description="Type of observation")
    source: str = Field(..., description="Source system identifier")
    fingerprint: str = Field(..., description="Unique fingerprint for deduplication")
    data: dict[str, Any] = Field(default_factory=dict, description="Observation payload")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservationUpdate(BaseModel):
    """Request body for PUT /api/v1/observations/{observation_id}."""

    observation_type: str | None = Field(None, description="Updated type")
    source: str | None = Field(None, description="Updated source")
    data: dict[str, Any] | None = Field(None, description="Replacement payload")
    metadata: dict[str, Any] | None = Field(None, description="Replacement metadata")


class ObservationResponse(BaseModel):
    """Generic observation response."""

    id: str
    observation_type: str
    source: str
    created_at: datetime
    fingerprint: str
    data: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservationListResponse(BaseModel):
    """Paginated list of observations."""

    observations: list[ObservationResponse]
    total: int
    limit: int
    offset: int


# =============================================================================
# Storage helpers
# =============================================================================


def _has_observation_support(storage: Any) -> bool:
    """Check if the storage backend supports observation operations."""
    return hasattr(storage, "store_observation") and hasattr(storage, "list_observations")


def _row_to_response(row: dict[str, Any]) -> ObservationResponse:
    """Convert a storage dict to ObservationResponse."""
    return ObservationResponse(
        id=row.get("id", ""),
        observation_type=row.get("observation_type", ""),
        source=row.get("source", ""),
        created_at=row.get("created_at", datetime.now(UTC)),
        fingerprint=row.get("fingerprint", ""),
        data=row.get("data") if isinstance(row.get("data"), dict) else {},
        metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
    )


# =============================================================================
# Routes
# =============================================================================


_query_obs_since = Query(None, description="Filter observations after this datetime")
_query_obs_limit = Query(100, ge=1, le=1000, description="Max observations to return")
_query_obs_offset = Query(0, ge=0, description="Skip observations")


@router.get("", response_model=ObservationListResponse)
async def list_observations(
    request: Request,
    observation_type: str | None = Query(None, description="Filter by observation type"),
    source: str | None = Query(None, description="Filter by source"),
    since: datetime | None = _query_obs_since,
    limit: int = _query_obs_limit,
    offset: int = _query_obs_offset,
) -> ObservationListResponse:
    """List observations with optional filtering."""
    storage = request.app.state.storage

    if _has_observation_support(storage):
        rows = await storage.list_observations(
            observation_type=observation_type,
            source=source,
            since=since,
            limit=limit,
            offset=offset,
        )
        total = 0
        if hasattr(storage, "count_observations"):
            total = await storage.count_observations(
                observation_type=observation_type,
                source=source,
            )
        else:
            total = len(rows)

        return ObservationListResponse(
            observations=[_row_to_response(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    return ObservationListResponse(
        observations=[],
        total=0,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ObservationResponse, status_code=201)
async def create_observation(
    request: Request,
    observation: ObservationCreate,
) -> ObservationResponse:
    """Create a new observation."""
    storage = request.app.state.storage
    obs_id = f"obs-{uuid4().hex[:8]}"
    now = datetime.now(UTC)

    row = {
        "id": obs_id,
        "observation_type": observation.observation_type,
        "source": observation.source,
        "fingerprint": observation.fingerprint,
        "data": observation.data,
        "metadata": observation.metadata,
        "created_at": now.isoformat(),
    }

    if _has_observation_support(storage):
        await storage.store_observation(row)

    return ObservationResponse(
        id=obs_id,
        observation_type=observation.observation_type,
        source=observation.source,
        created_at=now,
        fingerprint=observation.fingerprint,
        data=observation.data,
        metadata=observation.metadata,
    )


@router.get("/{observation_id}", response_model=ObservationResponse)
async def get_observation(request: Request, observation_id: str) -> ObservationResponse:
    """Get an observation by ID."""
    storage = request.app.state.storage

    if _has_observation_support(storage):
        row = await storage.get_observation(observation_id)
        if row:
            return _row_to_response(row)

    raise HTTPException(status_code=404, detail=f"Observation not found: {observation_id}")


@router.put("/{observation_id}", response_model=ObservationResponse)
async def update_observation(
    request: Request,
    observation_id: str,
    body: ObservationUpdate,
) -> ObservationResponse:
    """Update an observation by ID."""
    storage = request.app.state.storage

    if not _has_observation_support(storage):
        raise HTTPException(status_code=501, detail="Observation storage not available")

    existing = await storage.get_observation(observation_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Observation not found: {observation_id}")

    # Build updated row
    updated_row = dict(existing)
    if body.observation_type is not None:
        updated_row["observation_type"] = body.observation_type
    if body.source is not None:
        updated_row["source"] = body.source
    if body.data is not None:
        updated_row["data"] = body.data
    if body.metadata is not None:
        updated_row["metadata"] = body.metadata

    await storage.store_observation(updated_row)
    return _row_to_response(updated_row)


@router.delete("/{observation_id}", status_code=204)
async def delete_observation(request: Request, observation_id: str) -> None:
    """Delete an observation by ID."""
    storage = request.app.state.storage

    if not _has_observation_support(storage):
        raise HTTPException(status_code=501, detail="Observation storage not available")

    if not hasattr(storage, "delete_observation"):
        raise HTTPException(
            status_code=501,
            detail="Delete not supported by current storage backend",
        )

    existing = await storage.get_observation(observation_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Observation not found: {observation_id}")

    await storage.delete_observation(observation_id)
