"""Core configuration, app factory, and utilities."""

from feedspine.core.app import FeedSpineApp, create_feed_spine
from feedspine.core.resources import RateLimiter, ResourcePool, Semaphore

__all__ = [
    # App factory
    "FeedSpineApp",
    "create_feed_spine",
    # Resources
    "RateLimiter",
    "ResourcePool",
    "Semaphore",
]
