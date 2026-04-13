"""Base feed adapter implementation.

Provides BaseFeedAdapter base class for building feed adapters
that fetch data from various sources with rate limiting and metadata.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from spine.core.logging import get_logger

from feedspine.adapter.rate_limiter import AdapterRateLimiter
from feedspine.core.exceptions import FeedError, FeedSpineError  # noqa: F401
from feedspine.models.record import RecordCandidate
from feedspine.protocols.feed import FeedAdapter  # noqa: F401

logger = get_logger(__name__)


# FeedError is now defined in feedspine.core.exceptions and re-exported here
# for backward compatibility.  All new code should import from
# feedspine.core.exceptions directly.


class BaseFeedAdapter(ABC):
    """
    Abstract base class for feed adapters with rate limiting and metadata.

    Provides rate limiting, fetch-statistics tracking, and lifecycle
    management. Subclasses implement one of two patterns:

    1. **List-based**: Override ``_fetch_items()`` + ``_to_candidate()``
    2. **Generator-based**: Override ``_fetch_candidates()`` (preferred for large feeds)

    Attributes:
        name: Adapter name/identifier.
        source_url: URL of the feed source (optional).
        requests_per_second: Rate limit configuration.
        last_fetch_at: When the last fetch occurred.
        last_fetch_count: Number of items from last fetch.
        last_fetch_errors: Number of errors from last fetch.
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
        self._rate_limiter = AdapterRateLimiter(requests_per_second)
        self._initialized = False

        # Metadata tracking
        self._last_fetch_at: datetime | None = None
        self._last_fetch_count: int = 0
        self._last_fetch_errors: int = 0

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
        return self._rate_limiter.requests_per_second

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

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb) -> None:
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
        await self._rate_limiter.acquire()

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
                except Exception as e:
                    self._last_fetch_errors += 1
                    logger.debug("Skipping invalid item: %s", e)
                    # Skip invalid items, don't stop iteration

        self._last_fetch_at = datetime.now(UTC)

    def _uses_async_generator(self) -> bool:
        """Check if subclass overrides _fetch_candidates for async generator mode."""
        return type(self)._fetch_candidates is not BaseFeedAdapter._fetch_candidates

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
