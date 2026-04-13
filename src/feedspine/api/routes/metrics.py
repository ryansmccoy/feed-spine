"""Metrics API routes.

Provides Prometheus-compatible metrics and JSON metrics endpoints.
"""

from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import Response

from feedspine.api.models import FeedStatsResponse, MetricsJsonResponse, StorageStatsResponse
from feedspine.models.base import Layer

router = APIRouter(prefix="/api/v1", tags=["metrics"])


async def _layer_counts(storage: Any) -> dict[str, int]:
    """Get per-layer counts via GROUP BY when available."""
    if hasattr(storage, "count_by_layer"):
        return await storage.count_by_layer()
    from feedspine.models.base import Layer

    return {layer.value: c for layer in Layer if (c := await storage.count(layer=layer)) > 0}


@router.get("/stats", response_model=StorageStatsResponse)
async def get_stats(request: Request) -> StorageStatsResponse:
    """Get storage statistics."""
    total = await request.app.state.storage.count()

    # Count per layer — single query
    layer_counts = await _layer_counts(request.app.state.storage)

    return {
        "total_records": total,
        "by_layer": layer_counts,
    }


@router.get("/metrics/json", response_model=MetricsJsonResponse)
async def get_metrics_json(request: Request) -> MetricsJsonResponse:
    """Get detailed metrics as JSON.

    Returns storage metrics including counts, layer distribution,
    and backend information.
    """
    total = await request.app.state.storage.count()

    # Count per layer — single query
    layer_counts = await _layer_counts(request.app.state.storage)

    return {
        "total_records": total,
        "by_layer": layer_counts,
        "storage_backend": type(request.app.state.storage).__name__,
        "search_enabled": request.app.state.search is not None,
    }


@router.get("/stats/feeds", response_model=FeedStatsResponse)
async def get_feed_stats(
    request: Request,
    feed_name: str | None = None,
    limit: int = 10,
) -> FeedStatsResponse:
    """Get per-feed collection statistics.

    Returns recent feed runs with their stats (fetched, new, errors, duration).
    """
    storage = request.app.state.storage

    # Check if storage supports feed runs
    if not hasattr(storage, "get_feed_runs"):
        return {
            "error": "Feed run history not available with this storage backend",
            "supported_backends": ["PostgreSQL", "SQLAlchemy"],
            "runs": [],
        }

    runs = await storage.get_feed_runs(feed_name=feed_name, limit=limit)

    return {
        "feed_name": feed_name,
        "runs": [
            {
                "feed_name": run.feed_name,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "status": run.status,
                "fetched_count": run.fetched_count or 0,
                "new_count": run.new_count or 0,
                "error_count": run.error_count or 0,
                "duration_seconds": (
                    (run.completed_at - run.started_at).total_seconds() if run.completed_at and run.started_at else None
                ),
            }
            for run in runs
        ],
        "total_runs": len(runs),
    }


# Prometheus-compatible endpoint lives at root /metrics (no version prefix)
prometheus_router = APIRouter(tags=["metrics"])


@prometheus_router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    """Prometheus-compatible metrics endpoint.

    Returns metrics in Prometheus text exposition format.

    Example output:
        # HELP feedspine_records_total Total number of records in storage
        # TYPE feedspine_records_total gauge
        feedspine_records_total 1234
        # HELP feedspine_records_by_layer Records per layer
        # TYPE feedspine_records_by_layer gauge
        feedspine_records_by_layer{layer="raw"} 500
        feedspine_records_by_layer{layer="enriched"} 700
    """
    total = await request.app.state.storage.count()

    lines = [
        "# HELP feedspine_records_total Total number of records in storage",
        "# TYPE feedspine_records_total gauge",
        f"feedspine_records_total {total}",
        "",
        "# HELP feedspine_records_by_layer Records per layer",
        "# TYPE feedspine_records_by_layer gauge",
    ]

    for layer in Layer:
        count = await request.app.state.storage.count(layer=layer)
        lines.append(f'feedspine_records_by_layer{{layer="{layer.value}"}} {count}')

    # Add search backend status
    search_status = 1 if request.app.state.search else 0
    lines.extend(
        [
            "",
            "# HELP feedspine_search_enabled Whether search backend is configured",
            "# TYPE feedspine_search_enabled gauge",
            f"feedspine_search_enabled {search_status}",
        ]
    )

    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
