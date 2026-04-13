"""API routes package for FeedSpine."""

from feedspine.api.routes.feeds import router as feeds_router
from feedspine.api.routes.observations import router as observations_router
from feedspine.api.routes.runs import router as runs_router
from feedspine.api.routes.sightings import router as sightings_router

__all__ = [
    "feeds_router",
    "runs_router",
    "sightings_router",
    "observations_router",
]
