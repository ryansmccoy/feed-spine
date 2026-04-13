"""Route registration for the FeedSpine API.

Centralises router inclusion so ``fastapi.py`` remains a clean
app-factory / lifecycle module. Each domain router is imported from
:mod:`feedspine.api.routes` and registered with a single call to
:func:`include_all_routers`.

Usage::

    from feedspine.api.route_registry import include_all_routers

    app = FastAPI(...)
    include_all_routers(app)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def include_all_routers(app: FastAPI) -> None:
    """Register every API router on *app*.

    The routers are imported lazily inside this function so that the
    heavy ``feedspine.api.routes.*`` tree is only loaded when the API
    is actually being built.
    """
    from feedspine.api.routes.collect import router as collect_router
    from feedspine.api.routes.enrich import router as enrich_router
    from feedspine.api.routes.export import router as export_router
    from feedspine.api.routes.feeds import router as feeds_router
    from feedspine.api.routes.health import router as health_router
    from feedspine.api.routes.metrics import prometheus_router
    from feedspine.api.routes.metrics import router as metrics_router
    from feedspine.api.routes.observations import router as observations_router
    from feedspine.api.routes.records import router as records_router
    from feedspine.api.routes.runs import router as runs_router
    from feedspine.api.routes.schedules import router as schedules_router
    from feedspine.api.routes.search import router as search_router
    from feedspine.api.routes.sightings import router as sightings_router
    from feedspine.api.routes.stats import router as stats_router
    from feedspine.api.routes.storage import router as storage_router
    from feedspine.api.routes.syndication import router as syndication_router
    from feedspine.api.routes.timeline import router as timeline_router

    routers = [
        collect_router,
        enrich_router,
        export_router,
        feeds_router,
        health_router,
        metrics_router,
        observations_router,
        records_router,
        runs_router,
        schedules_router,
        search_router,
        sightings_router,
        stats_router,
        storage_router,
        syndication_router,
        timeline_router,
        prometheus_router,
    ]

    for router in routers:
        app.include_router(router)
