"""Feed health API routes.

Provides endpoints for monitoring feed health with RAG status indicators.
Delegates all business logic to :mod:`feedspine.ops.health`.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from feedspine.ops import OperationContext

router = APIRouter(prefix="/api/v1/health", tags=["health"])


# ── Response Models ──────────────────────────────────────


class FeedHealthModel(BaseModel):
    """Health status for a single feed."""

    feed_name: str
    status: str = Field(description="RAG status: healthy, degraded, failing, unknown")
    total_runs: int
    success_rate: float = Field(ge=0, le=1)
    last_success_at: str | None = None
    consecutive_failures: int
    avg_records_per_run: float


class FeedHealthSummary(BaseModel):
    """Summary of all feed health status."""

    period_days: int
    total_feeds: int
    healthy_count: int
    degraded_count: int
    failing_count: int
    unknown_count: int
    feeds: list[FeedHealthModel]


class FeedHealthAlert(BaseModel):
    """Alert for a failing feed."""

    feed_name: str
    status: str
    consecutive_failures: int
    success_rate: float
    last_success_at: str | None = None


class AlertsResponse(BaseModel):
    """Response containing health alerts."""

    threshold: int
    period_days: int
    alert_count: int
    alerts: list[FeedHealthAlert]


class FeedRunModel(BaseModel):
    """A single feed run record."""

    run_id: str | None = None
    feed_name: str
    started_at: str | None = None
    completed_at: str | None = None
    status: str
    fetched_count: int = 0
    new_count: int = 0
    error_count: int = 0
    duration_seconds: float | None = None


class FeedHistoryResponse(BaseModel):
    """Response containing feed run history."""

    feed_name: str
    total_runs: int
    runs: list[FeedRunModel]


# ── Helper Functions ─────────────────────────────────────


def _make_ctx(request: Request) -> OperationContext:
    """Build an OperationContext from the request's app state."""
    return OperationContext(
        storage=request.app.state.storage,
        caller="api",
    )


def _health_to_model(health: dict[str, Any]) -> FeedHealthModel:
    """Convert health dict to pydantic model."""
    return FeedHealthModel(
        feed_name=health["feed_name"],
        status=health["status"],
        total_runs=health["total_runs"],
        success_rate=health["success_rate"],
        last_success_at=health.get("last_success_at"),
        consecutive_failures=health["consecutive_failures"],
        avg_records_per_run=health.get("avg_records_per_run", 0.0),
    )


# ── Endpoints ────────────────────────────────────────────


@router.get("", response_model=FeedHealthSummary)
async def get_health_overview(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
) -> FeedHealthSummary:
    """Detailed health overview (delegates to ``/feeds`` summary)."""
    return await get_feed_health_summary(request, days=days)


@router.get("/feeds", response_model=FeedHealthSummary)
async def get_feed_health_summary(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
) -> FeedHealthSummary:
    """Get health summary for all feeds.

    Returns RAG status (Red/Amber/Green) for each feed based on:
    - Success rate over the time period
    - Number of consecutive failures

    RAG status logic:
    - 🟢 Healthy: ≥80% success rate AND <3 consecutive failures
    - 🟡 Degraded: 50-80% success rate OR 3-4 consecutive failures
    - 🔴 Failing: <50% success rate OR ≥5 consecutive failures
    - ⚪ Unknown: No runs in the time period
    """
    from feedspine.ops.health import fetch_all_feed_health

    result = await fetch_all_feed_health(_make_ctx(request), days=days)

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    data = result.data
    summary = data["summary"]

    return FeedHealthSummary(
        period_days=days,
        total_feeds=summary["total"],
        healthy_count=summary["healthy"],
        degraded_count=summary["degraded"],
        failing_count=summary["failing"],
        unknown_count=summary["unknown"],
        feeds=[_health_to_model(h) for h in data["feeds"]],
    )


@router.get("/feeds/{feed_name}", response_model=FeedHealthModel)
async def get_feed_health(
    feed_name: str,
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
) -> FeedHealthModel:
    """Get health status for a specific feed.

    Returns detailed health metrics including:
    - RAG status
    - Success rate
    - Run count
    - Last successful run
    - Consecutive failure count
    """
    from feedspine.ops.health import fetch_feed_health

    result = await fetch_feed_health(_make_ctx(request), feed_name=feed_name, days=days)

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    return _health_to_model(result.data)


@router.get("/feeds/{feed_name}/history", response_model=FeedHistoryResponse)
async def get_feed_run_history(
    feed_name: str,
    request: Request,
    limit: int = Query(50, le=500, description="Max runs to return"),
) -> FeedHistoryResponse:
    """Get run history for a specific feed.

    Returns a list of recent runs with status timeline,
    useful for debugging collection issues.
    """
    from feedspine.ops.health import fetch_feed_run_history

    result = await fetch_feed_run_history(
        _make_ctx(request),
        feed_name=feed_name,
        limit=limit,
    )

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    run_models = [FeedRunModel(**r) for r in result.data]

    return FeedHistoryResponse(
        feed_name=feed_name,
        total_runs=len(run_models),
        runs=run_models,
    )


@router.get("/alerts", response_model=AlertsResponse)
async def get_health_alerts(
    request: Request,
    consecutive_failures_threshold: int = Query(3, ge=1, description="Failure count threshold for alerts"),
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
) -> AlertsResponse:
    """Get alerts for failing feeds.

    Returns feeds that have exceeded the consecutive failure threshold
    or have failing status.
    """
    from feedspine.ops.health import fetch_health_alerts

    result = await fetch_health_alerts(
        _make_ctx(request),
        threshold=consecutive_failures_threshold,
        days=days,
    )

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    alert_models = [
        FeedHealthAlert(
            feed_name=a["feed_name"],
            status=a["status"],
            consecutive_failures=a["consecutive_failures"],
            success_rate=a["success_rate"],
            last_success_at=a.get("last_success_at"),
        )
        for a in result.data
    ]

    return AlertsResponse(
        threshold=consecutive_failures_threshold,
        period_days=days,
        alert_count=len(alert_models),
        alerts=alert_models,
    )
