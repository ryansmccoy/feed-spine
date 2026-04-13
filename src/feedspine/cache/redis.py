"""Redis cache backend implementing CacheBackend protocol.

Requires: pip install feedspine[redis]  (redis>=5.0)

Provides async Redis-backed caching with TTL, pattern-based
clear, and connection pooling via redis.asyncio.

Example:
    >>> from feedspine.cache.redis import RedisCache
    >>> cache = RedisCache("redis://localhost:6379/0")
    >>> await cache.initialize()
    >>> await cache.set("key", {"data": 1}, ttl=60)
    >>> await cache.get("key")
    {'data': 1}
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from feedspine._vendor.logging import get_logger

logger = get_logger(__name__)


class RedisCache:
    """Redis-backed cache implementing CacheBackend protocol.

    Uses redis.asyncio for non-blocking operations. Supports TTL,
    pattern-based clear, and JSON serialization for values.

    Args:
        url: Redis connection URL. Defaults to ``FEEDSPINE_REDIS_URL`` setting.
        key_prefix: Prefix for all cache keys (avoids collisions).
        default_ttl: Default TTL for set() when none specified (seconds or timedelta).
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        key_prefix: str = "feedspine:",
        default_ttl: int | timedelta | None = None,
    ) -> None:
        if url is None:
            from feedspine.core.config import get_settings

            url = get_settings().redis_url
        self._url = url
        self._key_prefix = key_prefix
        self._default_ttl = (
            default_ttl if isinstance(default_ttl, timedelta | type(None)) else timedelta(seconds=default_ttl)
        )
        self._client: Any = None  # redis.asyncio.Redis

    def _prefixed(self, key: str) -> str:
        """Add prefix to cache key."""
        return f"{self._key_prefix}{key}"

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise ImportError("redis package required. Install with: pip install feedspine[redis]") from exc

        self._client = aioredis.from_url(self._url, decode_responses=True)
        # Verify connection
        await self._client.ping()
        logger.info("Redis cache connected: %s", self._url)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, key: str) -> Any | None:
        """Get value from cache. Returns None if not found or expired."""
        if not self._client:
            raise RuntimeError("Cache not initialized. Call initialize() first.")

        raw = await self._client.get(self._prefixed(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(
        self,
        key: str,
        value: Any,
        ttl: timedelta | int | None = None,
    ) -> None:
        """Set value in cache with optional TTL.

        Args:
            key: Cache key.
            value: Value to cache (must be JSON-serializable).
            ttl: Time-to-live. int = seconds, timedelta, or None for default.
        """
        if not self._client:
            raise RuntimeError("Cache not initialized. Call initialize() first.")

        serialized = json.dumps(value, default=str)
        effective_ttl = ttl if ttl is not None else self._default_ttl

        if isinstance(effective_ttl, int):
            effective_ttl = timedelta(seconds=effective_ttl)

        if effective_ttl:
            await self._client.setex(
                self._prefixed(key),
                int(effective_ttl.total_seconds()),
                serialized,
            )
        else:
            await self._client.set(self._prefixed(key), serialized)

    async def delete(self, key: str) -> bool:
        """Delete from cache. Returns True if key existed."""
        if not self._client:
            raise RuntimeError("Cache not initialized. Call initialize() first.")

        result = await self._client.delete(self._prefixed(key))
        return result > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._client:
            raise RuntimeError("Cache not initialized. Call initialize() first.")

        return bool(await self._client.exists(self._prefixed(key)))

    async def clear(self, pattern: str | None = None) -> int:
        """Clear cache entries matching pattern.

        Args:
            pattern: Glob pattern (e.g. "feed:*"). None clears all prefixed keys.

        Returns:
            Number of keys cleared.
        """
        if not self._client:
            raise RuntimeError("Cache not initialized. Call initialize() first.")

        full_pattern = self._prefixed(pattern) if pattern else f"{self._key_prefix}*"

        # SCAN + DELETE in batches to avoid blocking
        deleted = 0
        async for key in self._client.scan_iter(match=full_pattern, count=100):
            await self._client.delete(key)
            deleted += 1
        return deleted
