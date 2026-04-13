"""Cache implementations."""

from feedspine.cache.memory import MemoryCache

__all__ = ["MemoryCache"]

# Redis cache (requires redis>=5.0)
try:
    from feedspine.cache.redis import RedisCache

    __all__.append("RedisCache")
except ImportError:
    RedisCache = None  # type: ignore[misc,assignment]
