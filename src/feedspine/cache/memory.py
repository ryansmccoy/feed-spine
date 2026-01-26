"""In-memory cache backend with TTL support.

Provides a complete in-memory implementation of CacheBackend,
useful for testing, development, and single-process applications.

Example:
    >>> from feedspine.cache.memory import MemoryCache
    >>> cache = MemoryCache()
    >>> # MemoryCache implements CacheBackend protocol
    >>> hasattr(cache, 'get')
    True
    >>> hasattr(cache, 'set')
    True
"""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class CacheEntry:
    """A cached value with optional expiration.

    Example:
        >>> from feedspine.cache.memory import CacheEntry
        >>> entry = CacheEntry(value="data", expires_at=None)
        >>> entry.is_expired
        False
    """

    value: Any
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired.

        Example:
            >>> from feedspine.cache.memory import CacheEntry
            >>> from datetime import datetime, timedelta, UTC
            >>> past = datetime.now(UTC) - timedelta(hours=1)
            >>> entry = CacheEntry(value="x", expires_at=past)
            >>> entry.is_expired
            True
        """
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at


class MemoryCache:
    """In-memory cache with TTL support.

    Thread-safe for single-process async usage.
    Supports pattern-based clearing and automatic cleanup.

    Example:
        >>> import asyncio
        >>> from feedspine.cache.memory import MemoryCache
        >>> cache = MemoryCache()
        >>> asyncio.run(cache.set("key1", "value1"))
        >>> asyncio.run(cache.get("key1"))
        'value1'
        >>> asyncio.run(cache.exists("key1"))
        True
        >>> asyncio.run(cache.delete("key1"))
        True
        >>> asyncio.run(cache.get("key1")) is None
        True
    """

    def __init__(self, cleanup_interval: float = 60.0) -> None:
        """Initialize the cache.

        Args:
            cleanup_interval: Seconds between automatic cleanup runs.
        """
        self._data: dict[str, CacheEntry] = {}
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: asyncio.Task[None] | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Start background cleanup task.

        Example:
            >>> import asyncio
            >>> from feedspine.cache.memory import MemoryCache
            >>> cache = MemoryCache()
            >>> asyncio.run(cache.initialize())
            >>> cache._initialized
            True
        """
        self._initialized = True
        # Start cleanup task if running in async context
        try:
            loop = asyncio.get_running_loop()
            self._cleanup_task = loop.create_task(self._cleanup_loop())
        except RuntimeError:
            # No running loop - skip background cleanup
            pass

    async def close(self) -> None:
        """Stop cleanup task and clear cache."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
        self._data.clear()
        self._initialized = False

    async def get(self, key: str) -> Any | None:
        """Get value from cache, returning None if expired or missing.

        Example:
            >>> import asyncio
            >>> from feedspine.cache.memory import MemoryCache
            >>> cache = MemoryCache()
            >>> asyncio.run(cache.set("k", "v"))
            >>> asyncio.run(cache.get("k"))
            'v'
            >>> asyncio.run(cache.get("missing")) is None
            True
        """
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._data[key]
            return None
        return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: timedelta | int | None = None,
    ) -> None:
        """Set value in cache with optional TTL.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: Time-to-live (timedelta or seconds as int).

        Example:
            >>> import asyncio
            >>> from datetime import timedelta
            >>> from feedspine.cache.memory import MemoryCache
            >>> cache = MemoryCache()
            >>> asyncio.run(cache.set("a", 1))
            >>> asyncio.run(cache.set("b", 2, ttl=60))
            >>> asyncio.run(cache.set("c", 3, ttl=timedelta(minutes=5)))
        """
        expires_at = None
        if ttl is not None:
            if isinstance(ttl, int):
                ttl = timedelta(seconds=ttl)
            expires_at = datetime.now(UTC) + ttl

        self._data[key] = CacheEntry(value=value, expires_at=expires_at)

    async def delete(self, key: str) -> bool:
        """Delete from cache.

        Returns:
            True if key existed and was deleted.

        Example:
            >>> import asyncio
            >>> from feedspine.cache.memory import MemoryCache
            >>> cache = MemoryCache()
            >>> asyncio.run(cache.set("x", 1))
            >>> asyncio.run(cache.delete("x"))
            True
            >>> asyncio.run(cache.delete("x"))
            False
        """
        if key in self._data:
            del self._data[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired.

        Example:
            >>> import asyncio
            >>> from feedspine.cache.memory import MemoryCache
            >>> cache = MemoryCache()
            >>> asyncio.run(cache.exists("missing"))
            False
            >>> asyncio.run(cache.set("found", 1))
            >>> asyncio.run(cache.exists("found"))
            True
        """
        entry = self._data.get(key)
        if entry is None:
            return False
        if entry.is_expired:
            del self._data[key]
            return False
        return True

    async def clear(self, pattern: str | None = None) -> int:
        """Clear cache entries matching pattern.

        Args:
            pattern: Glob pattern (e.g., "feed:*"). None clears all.

        Returns:
            Number of entries cleared.

        Example:
            >>> import asyncio
            >>> from feedspine.cache.memory import MemoryCache
            >>> cache = MemoryCache()
            >>> asyncio.run(cache.set("feed:1", "a"))
            >>> asyncio.run(cache.set("feed:2", "b"))
            >>> asyncio.run(cache.set("other", "c"))
            >>> asyncio.run(cache.clear("feed:*"))
            2
            >>> asyncio.run(cache.exists("other"))
            True
        """
        if pattern is None:
            count = len(self._data)
            self._data.clear()
            return count

        keys_to_delete = [k for k in self._data if fnmatch.fnmatch(k, pattern)]
        for key in keys_to_delete:
            del self._data[key]
        return len(keys_to_delete)

    async def _cleanup_loop(self) -> None:
        """Background task to remove expired entries."""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self._cleanup_expired()

    async def _cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed.
        """
        expired_keys = [k for k, v in self._data.items() if v.is_expired]
        for key in expired_keys:
            del self._data[key]
        return len(expired_keys)

    # --- Utility Methods ---

    def __len__(self) -> int:
        """Return number of entries (including expired).

        Example:
            >>> import asyncio
            >>> from feedspine.cache.memory import MemoryCache
            >>> cache = MemoryCache()
            >>> len(cache)
            0
            >>> asyncio.run(cache.set("a", 1))
            >>> len(cache)
            1
        """
        return len(self._data)

    async def keys(self, pattern: str | None = None) -> list[str]:
        """Get all keys matching pattern.

        Example:
            >>> import asyncio
            >>> from feedspine.cache.memory import MemoryCache
            >>> cache = MemoryCache()
            >>> asyncio.run(cache.set("a:1", 1))
            >>> asyncio.run(cache.set("a:2", 2))
            >>> asyncio.run(cache.set("b:1", 3))
            >>> sorted(asyncio.run(cache.keys("a:*")))
            ['a:1', 'a:2']
        """
        # Filter out expired
        valid_keys = [k for k, v in self._data.items() if not v.is_expired]

        if pattern is None:
            return valid_keys
        return [k for k in valid_keys if fnmatch.fnmatch(k, pattern)]
