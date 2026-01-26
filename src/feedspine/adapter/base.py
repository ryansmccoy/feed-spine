"""Base feed adapter implementation.

Provides the FeedAdapter protocol and BaseFeedAdapter base class
for building feed adapters that fetch data from various sources.

Example:
    >>> from feedspine.adapter.base import BaseFeedAdapter, FeedAdapter
    >>> # FeedAdapter is the protocol
    >>> hasattr(FeedAdapter, "fetch")
    True
    >>> # BaseFeedAdapter is the base implementation
    >>> hasattr(BaseFeedAdapter, "fetch")
    True
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from feedspine.models.record import RecordCandidate


class FeedError(Exception):
    """Error during feed fetch operation.

    Example:
        >>> from feedspine.adapter.base import FeedError
        >>> err = FeedError("Connection failed", source="rss-feed")
        >>> err.source
        'rss-feed'
    """

    def __init__(
        self,
        message: str,
        source: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.cause = cause


@runtime_checkable
class FeedAdapter(Protocol):
    """Protocol defining feed adapter interface.

    All feed adapters must implement this protocol to work with Pipeline.

    Example:
        >>> from feedspine.adapter.base import FeedAdapter
        >>> # Check protocol requirements
        >>> hasattr(FeedAdapter, "name")
        True
        >>> hasattr(FeedAdapter, "fetch")
        True
    """

    @property
    def name(self) -> str:
        """Feed adapter name/identifier."""
        ...

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        """Fetch candidates from the feed source.

        Yields:
            RecordCandidate instances for each item in the feed.
        """
        ...

    async def initialize(self) -> None:
        """Initialize the adapter (setup connections, etc.)."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...


class BaseFeedAdapter(ABC):
    """Base class for feed adapters.

    Provides common functionality for rate limiting, error handling,
    and metadata tracking. Subclasses can implement either:
    
    1. _fetch_items() + _to_candidate() for list-based fetching
    2. _fetch_candidates() for async generator fetching (preferred for large feeds)

    Example (list-based):
        >>> class MyAdapter(BaseFeedAdapter):
        ...     async def _fetch_items(self):
        ...         return [{"id": "1", "title": "Test"}]
        ...     def _to_candidate(self, item):
        ...         return RecordCandidate(
        ...             natural_key=item["id"],
        ...             published_at=datetime.now(UTC),
        ...             content={"title": item["title"]},
        ...             metadata=Metadata(source=self.name),
        ...         )

    Example (async generator):
        >>> class MyStreamingAdapter(BaseFeedAdapter):
        ...     async def _fetch_candidates(self):
        ...         async for item in self._stream_items():
        ...             yield RecordCandidate(...)
    """

    def __init__(
        self,
        name: str,
        source_url: str | None = None,
        requests_per_second: float = 1.0,
    ) -> None:
        """Initialize the base adapter.

        Args:
            name: Adapter name/identifier.
            source_url: URL of the feed source (optional).
            requests_per_second: Rate limit for requests.
        """
        self._name = name
        self._source_url = source_url
        self._requests_per_second = requests_per_second
        self._initialized = False

        # Metadata tracking
        self._last_fetch_at: datetime | None = None
        self._last_fetch_count: int = 0
        self._last_fetch_errors: int = 0
        self._last_request_time: float = 0.0

    @property
    def name(self) -> str:
        """Feed adapter name."""
        return self._name

    @property
    def source_url(self) -> str | None:
        """Feed source URL."""
        return self._source_url

    @property
    def requests_per_second(self) -> float:
        """Configured rate limit."""
        return self._requests_per_second

    @property
    def last_fetch_at(self) -> datetime | None:
        """When the last fetch occurred."""
        return self._last_fetch_at

    @property
    def last_fetch_count(self) -> int:
        """Number of items from last fetch."""
        return self._last_fetch_count

    @property
    def last_fetch_errors(self) -> int:
        """Number of errors from last fetch."""
        return self._last_fetch_errors

    @property
    def info(self) -> dict[str, Any]:
        """Feed source information."""
        return {
            "name": self._name,
            "source_url": self._source_url,
            "last_fetch_at": self._last_fetch_at,
            "last_fetch_count": self._last_fetch_count,
            "last_fetch_errors": self._last_fetch_errors,
        }

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True

    async def close(self) -> None:
        """Clean up resources."""
        self._initialized = False

    async def __aenter__(self) -> BaseFeedAdapter:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        """Fetch candidates from the feed.

        Handles rate limiting, error tracking, and item conversion.
        
        Supports two modes:
        1. If _fetch_candidates() is overridden, uses async generator directly
        2. Otherwise, uses _fetch_items() + _to_candidate() list-based approach

        Yields:
            RecordCandidate for each valid item.

        Raises:
            FeedError: If fetch fails completely.
        """
        # Apply rate limiting
        await self._apply_rate_limit()

        # Reset counters
        self._last_fetch_count = 0
        self._last_fetch_errors = 0

        # Check if subclass uses async generator approach
        if self._uses_async_generator():
            try:
                async for candidate in self._fetch_candidates():
                    self._last_fetch_count += 1
                    yield candidate
            except Exception as e:
                raise FeedError(
                    str(e),
                    source=self._name,
                    cause=e,
                ) from e
        else:
            # List-based approach
            try:
                items = await self._fetch_items()
            except Exception as e:
                raise FeedError(
                    str(e),
                    source=self._name,
                    cause=e,
                ) from e

            for item in items:
                try:
                    candidate = self._to_candidate(item)
                    self._last_fetch_count += 1
                    yield candidate
                except Exception:
                    self._last_fetch_errors += 1
                    # Skip invalid items, don't stop iteration

        self._last_fetch_at = datetime.now(UTC)
    
    def _uses_async_generator(self) -> bool:
        """Check if subclass overrides _fetch_candidates for async generator mode."""
        return type(self)._fetch_candidates is not BaseFeedAdapter._fetch_candidates

    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        if self._last_request_time > 0 and self._requests_per_second > 0:
            min_interval = 1.0 / self._requests_per_second
            elapsed = time.time() - self._last_request_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

        self._last_request_time = time.time()

    @abstractmethod
    async def _fetch_items(self) -> list[Any]:
        """Fetch raw items from the source (list-based mode).

        Subclasses implement this to fetch from their specific source.
        Override _fetch_candidates() instead for async generator mode.

        Returns:
            List of raw items to convert to candidates.
        """
        ...

    @abstractmethod
    def _to_candidate(self, item: Any) -> RecordCandidate:
        """Convert a raw item to a RecordCandidate.

        Subclasses implement this for their specific item format.
        Not needed if using _fetch_candidates() async generator mode.

        Args:
            item: Raw item from _fetch_items().

        Returns:
            RecordCandidate for the item.

        Raises:
            ValueError: If item cannot be converted.
        """
        ...
    
    async def _fetch_candidates(self) -> AsyncIterator[RecordCandidate]:
        """Fetch candidates directly as async generator (streaming mode).
        
        Override this method for feeds that benefit from streaming,
        such as large index files or paginated APIs.
        
        When this is overridden, _fetch_items() and _to_candidate()
        are not used.
        
        Yields:
            RecordCandidate for each item.
        """
        # Default implementation - never called if not overridden
        # This is just to make the method non-abstract
        raise NotImplementedError("Override _fetch_candidates or _fetch_items/_to_candidate")
