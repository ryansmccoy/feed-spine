"""Schedule management API routes.

Provides CRUD endpoints for feed collection schedules backed by
spine-core's ScheduleStore (persistent, survives restarts).

The schedule store is expected on ``request.app.state.schedule_store``.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from feedspine._vendor.logging import get_logger

from feedspine.ops import schedules as sched_ops

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


# ── Models ───────────────────────────────────────────────


class ScheduleCreate(BaseModel):
    """Request body to create a schedule."""

    feed_id: str = Field(..., description="Feed to schedule")
    cron_expression: str = Field(
        "*/15 * * * *",
        description="Cron expression (e.g. '*/15 * * * *' = every 15 min)",
    )
    enabled: bool = Field(True, description="Whether the schedule is active")


class ScheduleUpdate(BaseModel):
    """Request body to patch a schedule."""

    cron_expression: str | None = Field(None, description="New cron expression")
    enabled: bool | None = Field(None, description="Enable/disable")


class ScheduleResponse(BaseModel):
    """Schedule resource returned to callers."""

    id: str
    feed_id: str | None = None
    name: str | None = None
    cron_expression: str | None = None
    enabled: bool = True
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    next_run_at: datetime | str | None = None


def _row_to_response(row: dict) -> ScheduleResponse:
    """Convert a spine-core schedule row to API response."""
    return ScheduleResponse(
        id=row["id"],
        feed_id=row.get("target_name", ""),
        name=row.get("name", ""),
        cron_expression=row.get("cron_expression"),
        enabled=bool(row.get("enabled", True)),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        next_run_at=row.get("next_run_at"),
    )


def _get_store(request: Request):
    """Return the ScheduleStore from app.state."""
    store = getattr(request.app.state, "schedule_store", None)
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Schedule store not configured",
        )
    return store


# ── Endpoints ────────────────────────────────────────────


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    request: Request,
    enabled: bool | None = Query(None, description="Filter by enabled flag"),
) -> list[ScheduleResponse]:
    """List all schedules with optional filtering."""
    store = _get_store(request)
    rows = sched_ops.list_schedules(store, enabled=enabled)
    return [_row_to_response(r) for r in rows]


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    request: Request,
    body: ScheduleCreate,
) -> ScheduleResponse:
    """Create a new collection schedule for a feed."""
    store = _get_store(request)
    row = sched_ops.create_schedule(
        store,
        feed_name=body.feed_id,
        cron_expression=body.cron_expression,
        enabled=body.enabled,
    )
    return _row_to_response(row)


@router.get("/due", response_model=list[ScheduleResponse])
async def list_due_schedules(request: Request) -> list[ScheduleResponse]:
    """Return schedules that are due for execution."""
    store = _get_store(request)
    rows = sched_ops.list_due_schedules(store)
    return [_row_to_response(r) for r in rows]


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(request: Request, schedule_id: str) -> ScheduleResponse:
    """Get a schedule by ID."""
    store = _get_store(request)
    row = sched_ops.get_schedule(store, schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
    return _row_to_response(row)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    request: Request,
    schedule_id: str,
    body: ScheduleUpdate,
) -> ScheduleResponse:
    """Update a schedule's cron expression or enabled flag."""
    store = _get_store(request)
    row = sched_ops.update_schedule(
        store,
        schedule_id,
        cron_expression=body.cron_expression,
        enabled=body.enabled,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
    return _row_to_response(row)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(request: Request, schedule_id: str) -> None:
    """Delete a schedule by ID."""
    store = _get_store(request)
    deleted = sched_ops.delete_schedule(store, schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
