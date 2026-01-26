"""FeedSpine - Main orchestrator for feed capture.

The FeedSpine class is the central entry point for the framework,
coordinating feed adapters, storage, search, and other backends.

Example:
    >>> from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter
    >>> # Basic usage
    >>> storage = MemoryStorage()
    >>> spine = FeedSpine(storage=storage)
    >>> # spine.register_feed(RSSFeedAdapter(...))
    >>> # result = await spine.collect()
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from feedspine.pipeline import Pipeline, PipelineStats

if TYPE_CHECKING:
    from feedspine.models.base import Layer
    from feedspine.models.record import Record
    from feedspine.protocols.cache import CacheBackend
    from feedspine.protocols.feed import FeedAdapter
    from feedspine.protocols.notification import Notifier
    from feedspine.protocols.search import SearchBackend, SearchResponse
    from feedspine.protocols.storage import StorageBackend


@dataclass
class CollectionResult:
    """Result from a collection run.

    Example:
        >>> from feedspine.core.feedspine import CollectionResult
        >>> from feedspine.pipeline import PipelineStats
        >>> result = CollectionResult(
        ...     feed_stats={"feed1": PipelineStats(feed_name="feed1", processed=10)},
        ... )
        >>> result.total_processed
        10
    """

    feed_stats: dict[str, PipelineStats] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total records processed across all feeds."""
        return sum(s.processed for s in self.feed_stats.values())

    @property
    def total_new(self) -> int:
        """Total new records across all feeds."""
        return sum(s.new for s in self.feed_stats.values())

    @property
    def total_duplicates(self) -> int:
        """Total duplicates across all feeds."""
        return sum(s.duplicates for s in self.feed_stats.values())

    @property
    def total_errors(self) -> int:
        """Total errors across all feeds."""
        return sum(s.errors for s in self.feed_stats.values()) + len(self.errors)


class FeedSpine:
    """Main orchestrator for feed capture.

    FeedSpine coordinates feed adapters, storage backends, search indexes,
    and other components to provide a unified interface for feed collection
    and querying.

    Args:
        storage: Required storage backend for records.
        cache: Optional cache backend for performance.
        search: Optional search backend for full-text search.
        notifier: Optional notifier for alerts.

    Example:
        >>> import asyncio
        >>> from feedspine.core.feedspine import FeedSpine
        >>> from feedspine.storage.memory import MemoryStorage
        >>> async def example():
        ...     storage = MemoryStorage()
        ...     async with FeedSpine(storage=storage) as spine:
        ...         print(spine.list_feeds())
        >>> asyncio.run(example())
        []
    """

    def __init__(
        self,
        storage: StorageBackend,
        *,
        cache: CacheBackend | None = None,
        search: SearchBackend | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        """Initialize FeedSpine orchestrator.

        Args:
            storage: Required storage backend for records.
            cache: Optional cache backend for performance.
            search: Optional search backend for full-text search.
            notifier: Optional notifier for alerts.
        """
        self._storage = storage
        self._cache = cache
        self._search = search
        self._notifier = notifier
        self._feeds: dict[str, FeedAdapter] = {}
        self._initialized = False

    @property
    def storage(self) -> StorageBackend:
        """Get the storage backend."""
        return self._storage

    @property
    def cache(self) -> CacheBackend | None:
        """Get the cache backend (if configured)."""
        return self._cache

    @property
    def search_backend(self) -> SearchBackend | None:
        """Get the search backend (if configured)."""
        return self._search

    @property
    def feeds(self) -> dict[str, FeedAdapter]:
        """Get registered feed adapters."""
        return self._feeds

    def register_feed(self, adapter: FeedAdapter) -> None:
        """Register a feed adapter.

        Args:
            adapter: Feed adapter to register.

        Raises:
            ValueError: If adapter name is already registered.

        Example:
            >>> from feedspine.core.feedspine import FeedSpine
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.adapter.base import BaseFeedAdapter
            >>> storage = MemoryStorage()
            >>> spine = FeedSpine(storage=storage)
            >>> # spine.register_feed(adapter)
        """
        if adapter.name in self._feeds:
            raise ValueError(f"Feed '{adapter.name}' is already registered")

        self._feeds[adapter.name] = adapter

    def unregister_feed(self, name: str) -> bool:
        """Unregister a feed adapter by name.

        Args:
            name: Name of the feed adapter to unregister.

        Returns:
            True if the feed was unregistered, False if not found.

        Example:
            >>> from feedspine.core.feedspine import FeedSpine
            >>> from feedspine.storage.memory import MemoryStorage
            >>> storage = MemoryStorage()
            >>> spine = FeedSpine(storage=storage)
            >>> spine.unregister_feed("nonexistent")
            False
        """
        if name in self._feeds:
            del self._feeds[name]
            return True
        return False

    def unregister_all_feeds(self) -> int:
        """Unregister all feed adapters.

        Returns:
            Number of feeds that were unregistered.
        """
        count = len(self._feeds)
        self._feeds.clear()
        return count

    def list_feeds(self) -> list[str]:
        """List registered feed names.

        Returns:
            List of registered feed adapter names.
        """
        return list(self._feeds.keys())

    async def collect(
        self,
        feeds: list[str] | None = None,
    ) -> CollectionResult:
        """Collect from registered feeds.

        Args:
            feeds: Optional list of feed names to collect from.
                   If None, collects from all registered feeds.

        Returns:
            CollectionResult with stats for each feed.

        Raises:
            ValueError: If specified feed is not registered.

        Example:
            >>> import asyncio
            >>> from feedspine.core.feedspine import FeedSpine
            >>> from feedspine.storage.memory import MemoryStorage
            >>> async def example():
            ...     storage = MemoryStorage()
            ...     await storage.initialize()
            ...     spine = FeedSpine(storage=storage)
            ...     result = await spine.collect()
            ...     return result.total_processed
            >>> asyncio.run(example())
            0
        """
        # Determine which feeds to collect from
        feed_names = feeds if feeds is not None else list(self._feeds.keys())

        # Validate feed names
        for name in feed_names:
            if name not in self._feeds:
                raise ValueError(f"Unknown feed: '{name}'")

        result = CollectionResult()
        pipeline = Pipeline(storage=self._storage, notifier=self._notifier)

        for name in feed_names:
            adapter = self._feeds[name]
            try:
                # Initialize the adapter before collecting
                await adapter.initialize()
                stats = await pipeline.run(adapter)
                result.feed_stats[name] = stats
            except Exception as e:
                result.errors.append(f"{name}: {e}")
            finally:
                # Always close the adapter after collecting
                try:
                    await adapter.close()
                except Exception:
                    pass  # Ignore close errors

        result.completed_at = datetime.now(UTC)
        return result

    async def query(
        self,
        *,
        layer: Layer | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Record]:
        """Query stored records.

        Args:
            layer: Optional layer filter.
            limit: Optional maximum records to return.

        Yields:
            Record instances matching the query.
        """
        count = 0
        async for record in self._storage.query(layer=layer):
            if limit is not None and count >= limit:
                break
            yield record
            count += 1

    async def search(self, query: str, **kwargs: Any) -> SearchResponse:
        """Search for records using full-text search.

        Args:
            query: Search query string.
            **kwargs: Additional search options.

        Returns:
            SearchResponse with matching records.

        Raises:
            ValueError: If no search backend is configured.
        """
        if self._search is None:
            raise ValueError("No search backend configured")

        return await self._search.search(query, **kwargs)

    async def initialize(self) -> None:
        """Initialize all components.

        Calls initialize() on storage and optional backends.
        """
        if self._initialized:
            return

        await self._storage.initialize()

        if self._cache is not None:
            await self._cache.initialize()

        if self._search is not None:
            await self._search.initialize()

        if self._notifier is not None:
            await self._notifier.initialize()

        # Initialize registered feeds
        for adapter in self._feeds.values():
            await adapter.initialize()

        self._initialized = True

    async def close(self) -> None:
        """Close all components.

        Calls close() on storage and optional backends.
        """
        # Close registered feeds
        for adapter in self._feeds.values():
            await adapter.close()

        if self._notifier is not None:
            await self._notifier.close()

        if self._search is not None:
            await self._search.close()

        if self._cache is not None:
            await self._cache.close()

        await self._storage.close()
        self._initialized = False

    async def __aenter__(self) -> FeedSpine:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def info(self) -> dict[str, Any]:
        """Get orchestrator metadata.

        Returns:
            Dictionary with orchestrator info.
        """
        return {
            "feeds": self.list_feeds(),
            "feed_count": len(self._feeds),
            "has_cache": self._cache is not None,
            "has_search": self._search is not None,
            "has_notifier": self._notifier is not None,
            "initialized": self._initialized,
        }
