"""In-memory FetchContext storage mixin.

Provides HTTP caching state management for feed fetching.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feedspine.models.fetch_context import FetchContext


class FetchContextMixin:
    """Mixin providing in-memory FetchContext storage.

    Implements the FetchContextStore protocol for HTTP caching.

    Attributes:
        _fetch_contexts: Contexts indexed by URL hash.
    """

    def __init__(self) -> None:
        self._fetch_contexts: dict[str, FetchContext] = {}

    def _clear_fetch_contexts(self) -> None:
        """Clear all fetch context data."""
        self._fetch_contexts.clear()

    async def initialize(self) -> None:
        """Initialize the store (no-op for in-memory)."""

    async def close(self) -> None:
        """Clean up resources (no-op for in-memory)."""

    def _url_to_key(self, url: str) -> str:
        """Convert URL to storage key."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    async def get(self, endpoint_url: str) -> FetchContext | None:
        """Get FetchContext for an endpoint URL."""
        key = self._url_to_key(endpoint_url)
        return self._fetch_contexts.get(key)

    async def save(self, ctx: FetchContext) -> None:
        """Save or update a FetchContext."""
        key = self._url_to_key(ctx.endpoint_url)
        self._fetch_contexts[key] = ctx

    async def delete(self, endpoint_url: str) -> bool:
        """Delete FetchContext for an endpoint. Returns True if deleted."""
        key = self._url_to_key(endpoint_url)
        if key in self._fetch_contexts:
            del self._fetch_contexts[key]
            return True
        return False

    async def list_all(self) -> list[FetchContext]:
        """List all stored FetchContexts."""
        return list(self._fetch_contexts.values())

    async def get_stale(self, max_age_hours: int = 24) -> list[FetchContext]:
        """Get contexts that haven't been fetched recently."""
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        stale = []
        for ctx in self._fetch_contexts.values():
            if ctx.last_fetch_at is None or ctx.last_fetch_at < cutoff:
                stale.append(ctx)
        return stale

    async def get_unhealthy(self, min_failures: int = 3) -> list[FetchContext]:
        """Get contexts with repeated failures."""
        return [ctx for ctx in self._fetch_contexts.values() if ctx.consecutive_failures >= min_failures]

    async def get_stats(self) -> dict[str, int | float]:
        """Get aggregate statistics across all fetch contexts."""
        contexts = list(self._fetch_contexts.values())
        if not contexts:
            return {
                "total_endpoints": 0,
                "total_fetches": 0,
                "total_304s": 0,
                "overall_cache_hit_rate": 0.0,
                "unhealthy_count": 0,
            }

        total_fetches = sum(c.total_fetches for c in contexts)
        total_304s = sum(c.total_304s for c in contexts)

        return {
            "total_endpoints": len(contexts),
            "total_fetches": total_fetches,
            "total_304s": total_304s,
            "overall_cache_hit_rate": total_304s / total_fetches if total_fetches > 0 else 0.0,
            "unhealthy_count": sum(1 for c in contexts if not c.is_healthy),
        }
