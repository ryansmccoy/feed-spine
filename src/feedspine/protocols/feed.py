"""Feed adapter protocol.

Defines the interface for feed adapters that parse various data sources
into RecordCandidates.

Example:
    >>> from feedspine.protocols.feed import FeedAdapter
    >>> # FeedAdapter is a Protocol - check interface
    >>> hasattr(FeedAdapter, "fetch")
    True
    >>> hasattr(FeedAdapter, "name")
    True
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from feedspine.models.record import RecordCandidate


@runtime_checkable
class FeedAdapter(Protocol):
    """Feed adapter protocol.

    Implementations parse various feed formats into RecordCandidates.
    Examples: RSS/Atom feeds, REST APIs, file watchers, webhooks.
    """

    @property
    def name(self) -> str:
        """Unique name for this feed."""
        ...

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        """Fetch and yield record candidates."""
        ...

    async def initialize(self) -> None:
        """Initialize the feed adapter."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
