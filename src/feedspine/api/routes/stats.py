"""Stats API routes for FeedSpine.

Provides comprehensive statistics endpoints including:
- Storage summary with record/sighting/observation counts
- Collection run aggregations
- Per-feed collection metrics
- Prometheus-compatible metrics export

Delegates all business logic to :mod:`feedspine.ops.stats`.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from feedspine.api.models import ObservationStatsResponse, RecordStatsResponse
from feedspine.ops import OperationContext

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


# =============================================================================
# Models
# =============================================================================


class LayerCounts(BaseModel):
    """Record counts by layer."""

    bronze: int = 0
    silver: int = 0
    gold: int = 0


class RecordStats(BaseModel):
    """Record statistics."""

    total: int = Field(description="Total record count across all layers")
    by_layer: LayerCounts = Field(default_factory=LayerCounts)


class SightingStats(BaseModel):
    """Sighting statistics."""

    total: int = Field(description="Total sighting count")


class ObservationStats(BaseModel):
    """Observation statistics."""

    total: int = Field(description="Total observation count")


class FeedConfigStats(BaseModel):
    """Feed configuration statistics."""

    total: int = Field(description="Total configured feeds")


class CollectionStats(BaseModel):
    """Collection run statistics."""

    days: int = Field(description="Time window in days")
    total_runs: int = Field(description="Total collection runs")
    successful_runs: int = Field(description="Successful runs")
    failed_runs: int = Field(description="Failed runs")
    total_records_collected: int = Field(description="Total records collected")
    total_errors: int = Field(description="Total errors across all runs")
    avg_records_per_run: float = Field(description="Average records per run")
    feeds_active: int = Field(description="Number of active feeds")
    runs_per_day: float = Field(description="Average runs per day")


class StorageSummary(BaseModel):
    """Comprehensive storage summary."""

    records: RecordStats
    sightings: SightingStats
    observations: ObservationStats
    feed_configs: FeedConfigStats
    collection: CollectionStats
    schema_version: str | None = None


class FeedCollectionStats(BaseModel):
    """Per-feed collection statistics."""

    feed_name: str = Field(description="Feed name")
    total_runs: int = Field(description="Total runs for this feed")
    successful_runs: int = Field(description="Successful runs")
    total_records: int = Field(description="Total records collected")
    avg_records_per_run: float = Field(description="Average records per run")
    last_run_at: str | None = Field(description="Last run timestamp (ISO 8601)")
    success_rate: float = Field(description="Success rate (0.0-1.0)")


class FeedCollectionStatsResponse(BaseModel):
    """Response for per-feed collection stats."""

    days: int = Field(description="Time window in days")
    feeds: list[FeedCollectionStats] = Field(description="Per-feed statistics")
    total_feeds: int = Field(description="Number of feeds with data")


# =============================================================================
# Helper
# =============================================================================


def _make_ctx(request: Request) -> OperationContext:
    """Build an OperationContext from the request's app state."""
    return OperationContext(
        storage=request.app.state.storage,
        caller="api",
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/summary", response_model=StorageSummary)
async def get_storage_summary(request: Request) -> StorageSummary:
    """Get comprehensive storage summary.

    Returns unified statistics including records, sightings, observations,
    feed configurations, and collection run metrics.
    """
    from feedspine.ops.stats import fetch_storage_summary

    result = await fetch_storage_summary(_make_ctx(request))

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    return _dict_to_summary(result.data)


@router.get("/collection", response_model=CollectionStats)
async def get_collection_stats(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to aggregate"),
) -> CollectionStats:
    """Get aggregated collection run statistics.

    Returns metrics across all collection runs for the specified time window.
    """
    from feedspine.ops.stats import fetch_collection_stats

    result = await fetch_collection_stats(_make_ctx(request), days=days)

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    return CollectionStats(**result.data)


@router.get("/collection/feeds", response_model=FeedCollectionStatsResponse)
async def get_feed_collection_stats(
    request: Request,
    feed_name: str | None = Query(None, description="Filter by feed name"),
    days: int = Query(30, ge=1, le=365, description="Number of days to aggregate"),
) -> FeedCollectionStatsResponse:
    """Get per-feed collection statistics.

    Returns collection metrics broken down by feed, sorted by total records
    collected (descending).
    """
    from feedspine.ops.stats import fetch_feed_collection_stats

    result = await fetch_feed_collection_stats(
        _make_ctx(request),
        feed_name=feed_name,
        days=days,
    )

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    data = result.data
    return FeedCollectionStatsResponse(
        days=data["days"],
        feeds=[FeedCollectionStats(**f) for f in data["feeds"]],
        total_feeds=data["total_feeds"],
    )


@router.get("/records", response_model=RecordStatsResponse)
async def get_record_stats(request: Request) -> RecordStatsResponse:
    """Get record counts by layer.

    Returns a breakdown of record counts across Bronze, Silver, and Gold layers.
    """
    from feedspine.ops.stats import fetch_layer_distribution

    result = await fetch_layer_distribution(_make_ctx(request))

    if not result.success:
        raise HTTPException(status_code=501, detail=result.error)

    return {
        "total": result.data["total"],
        "by_layer": result.data["by_layer"],
    }


@router.get("/observations", response_model=ObservationStatsResponse)
async def get_observation_stats(request: Request) -> ObservationStatsResponse:
    """Get observation statistics.

    Returns observation counts, optionally broken down by type and source.
    """
    import asyncio

    storage = request.app.state.storage

    if not hasattr(storage, "count_observations"):
        return {"total": 0, "note": "Observations not supported by this storage backend"}

    result = storage.count_observations()
    if asyncio.iscoroutine(result):
        result = await result

    return {"total": result}


# =============================================================================
# Helpers
# =============================================================================


def _dict_to_summary(data: dict[str, Any]) -> StorageSummary:
    """Convert dict from repository to StorageSummary model."""
    records_data = data.get("records", {})
    by_layer = records_data.get("by_layer", {})

    return StorageSummary(
        records=RecordStats(
            total=records_data.get("total", 0),
            by_layer=LayerCounts(
                bronze=by_layer.get("bronze", 0),
                silver=by_layer.get("silver", 0),
                gold=by_layer.get("gold", 0),
            ),
        ),
        sightings=SightingStats(
            total=data.get("sightings", {}).get("total", 0),
        ),
        observations=ObservationStats(
            total=data.get("observations", {}).get("total", 0),
        ),
        feed_configs=FeedConfigStats(
            total=data.get("feed_configs", {}).get("total", 0),
        ),
        collection=CollectionStats(**data.get("collection", {})),
        schema_version=data.get("schema_version"),
    )
