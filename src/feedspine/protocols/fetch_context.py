"""FetchContext storage protocol.

Defines the interface for persisting FetchContext objects,
which track HTTP caching state per endpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from feedspine.models.fetch_context import FetchContext


@runtime_checkable
class FetchContextStore(Protocol):
    """Protocol for storing FetchContext objects.

    Implementations persist HTTP caching state (ETag, Last-Modified)
    across runs to enable conditional fetching.
    """

    async def get(self, endpoint_url: str) -> FetchContext | None:
        """Get FetchContext for an endpoint URL, or None."""
        ...

    async def save(self, ctx: FetchContext) -> None:
        """Save or update a FetchContext."""
        ...

    async def delete(self, endpoint_url: str) -> bool:
        """Delete FetchContext for an endpoint. Returns True if deleted."""
        ...

    async def list_all(self) -> list[FetchContext]:
        """List all stored FetchContexts."""
        ...

    async def get_stale(self, max_age_hours: int = 24) -> list[FetchContext]:
        """Get contexts not fetched within *max_age_hours*."""
        ...

    async def get_unhealthy(self, min_failures: int = 3) -> list[FetchContext]:
        """Get contexts with >= *min_failures* consecutive failures."""
        ...

    async def initialize(self) -> None:
        """Initialize the store (create tables, etc.)."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...


__all__ = ["FetchContextStore"]
