"""Records API routes.

Provides CRUD endpoints for record management:
- List records with filtering
- Get record by ID or natural key
- Create, update, and delete records
- Get record version history
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from spine.core.logging import get_logger

from feedspine.api.models import RecordCreate, RecordResponse, RecordUpdate, RecordVersionsResponse
from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/records", tags=["records"])


@router.get("", response_model=list[RecordResponse])
async def list_records(
    request: Request,
    layer: str | None = Query(None, description="Filter by layer"),
    limit: int = Query(100, le=1000, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Skip records"),
) -> list[dict[str, Any]]:
    """List records with optional filtering."""
    layer_filter = Layer(layer) if layer else None

    records = []
    async for record in request.app.state.storage.query(
        layer=layer_filter,
        limit=limit,
        offset=offset,
    ):
        records.append(record.model_dump(mode="json"))

    return records


@router.get("/{record_id}", response_model=RecordResponse)
async def get_record(request: Request, record_id: str) -> dict[str, Any]:
    """Get a record by ID."""
    record = await request.app.state.storage.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    result: dict[str, Any] = record.model_dump(mode="json")
    return result


@router.get("/by-key/{natural_key:path}", response_model=RecordResponse)
async def get_record_by_key(request: Request, natural_key: str) -> dict[str, Any]:
    """Get a record by natural key."""
    record = await request.app.state.storage.get_by_natural_key(natural_key)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    result: dict[str, Any] = record.model_dump(mode="json")
    return result


@router.get("/{record_id}/versions", response_model=RecordVersionsResponse)
async def get_record_versions(
    request: Request,
    record_id: str,
    limit: int = Query(50, le=100, description="Max versions to return"),
) -> dict[str, Any]:
    """Get version history for a record.

    Returns the list of versions for the specified record, ordered by
    version number descending (newest first).

    Note: Version tracking must be enabled in the storage backend.
    Currently this endpoint returns metadata about the current record
    version. Full version history requires SQLAlchemy storage with
    versioning enabled.
    """
    # Check record exists
    record = await request.app.state.storage.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Return current version info (full history requires versioned storage)
    current_version = {
        "version": record.version,
        "record_id": record.id,
        "natural_key": record.natural_key,
        "layer": record.layer.value if hasattr(record.layer, "value") else str(record.layer),
        "captured_at": record.captured_at.isoformat() if record.captured_at else None,
        "first_seen_at": record.first_seen_at.isoformat() if record.first_seen_at else None,
        "last_seen_at": record.last_seen_at.isoformat() if record.last_seen_at else None,
        "seen_count": record.seen_count,
    }

    return {
        "record_id": record_id,
        "current_version": record.version,
        "versions": [current_version],
        "total_versions": 1,
        "note": "Full version history available with versioned storage backend",
    }


@router.post("", response_model=RecordResponse, status_code=201)
async def create_record(request: Request, body: RecordCreate) -> dict[str, Any]:
    """Create a new record via the API.

    Builds a ``RecordCandidate``, converts it to a ``Record``, and stores it.
    If a record with the same ``natural_key`` already exists, returns 409.
    """
    storage = request.app.state.storage

    # Check for duplicate natural key
    existing = await storage.get_by_natural_key(body.natural_key)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Record with natural_key already exists: {body.natural_key}",
        )

    candidate = RecordCandidate(
        natural_key=body.natural_key,
        published_at=datetime.now(UTC),
        content=body.content,
        metadata=Metadata(source=body.source, extra=body.metadata),
    )
    record_id = str(uuid4())
    record = Record.from_candidate(candidate, record_id)

    # Apply layer if not default
    layer_val = Layer(body.layer)
    if layer_val != Layer.BRONZE:
        record = record.model_copy(update={"layer": layer_val})

    await storage.store(record)

    result: dict[str, Any] = record.model_dump(mode="json")
    return result


@router.patch("/{record_id}", response_model=RecordResponse)
async def update_record(request: Request, record_id: str, body: RecordUpdate) -> dict[str, Any]:
    """Partially update a record's content, metadata, or layer."""
    storage = request.app.state.storage

    record = await storage.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    updates: dict[str, Any] = {"updated_at": datetime.now(UTC)}

    if body.content is not None:
        merged = {**record.content, **body.content}
        updates["content"] = merged
        updates["version"] = record.version + 1

    if body.metadata is not None:
        existing_extra = getattr(record.metadata, "extra", {}) or {}
        merged_extra = {**existing_extra, **body.metadata}
        updates["metadata"] = record.metadata.model_copy(update={"extra": merged_extra})

    if body.layer is not None:
        updates["layer"] = Layer(body.layer)

    updated = record.model_copy(update=updates)
    await storage.store(updated)

    result: dict[str, Any] = updated.model_dump(mode="json")
    return result


@router.delete("/{record_id}", status_code=204)
async def delete_record(request: Request, record_id: str) -> None:
    """Delete a record by ID."""
    storage = request.app.state.storage

    record = await storage.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    await storage.delete(record_id)
    logger.info("Deleted record id=%s", record_id)


@router.post("/mark-all-read", response_model=dict[str, int])
async def mark_all_read(request: Request) -> dict[str, int]:
    """Mark all records as read.

    Sets a ``read`` flag in metadata for every record. Returns the
    count of records updated.
    """
    storage = request.app.state.storage
    updated = 0

    async for record in storage.query(limit=10_000):
        extra = getattr(record.metadata, "extra", {}) or {}
        if extra.get("read"):
            continue
        merged = {**extra, "read": True}
        patched = record.model_copy(update={"metadata": record.metadata.model_copy(update={"extra": merged})})
        await storage.store(patched)
        updated += 1

    return {"updated": updated}
