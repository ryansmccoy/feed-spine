"""Cache backend protocol.

Defines the interface for cache backends (Redis, Memcached, in-memory).

Example:
    >>> from feedspine.protocols.cache import CacheBackend
    >>> # CacheBackend is a Protocol - check if a class implements it
    >>> from feedspine.protocols.cache import CacheBackend
    >>> hasattr(CacheBackend, "get")
    True
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """Cache backend protocol.

    Implementations must provide async get/set/delete operations
    with optional TTL support.
    """

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        ...

    async def set(
        self,
        key: str,
        value: Any,
        ttl: timedelta | int | None = None,
    ) -> None:
        """Set value in cache with optional TTL."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete from cache. Returns True if existed."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        ...

    async def clear(self, pattern: str | None = None) -> int:
        """Clear cache entries. Returns count cleared."""
        ...

    async def initialize(self) -> None:
        """Initialize cache."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
