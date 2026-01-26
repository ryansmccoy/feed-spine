"""Feed class - main entry point for feed composition.

This module provides the Feed class, which combines a dataclass-based
configuration with a context manager for Pythonic resource management.

Example:
    >>> import asyncio
    >>> from feedspine.composition import Feed
    >>> from feedspine.storage.memory import MemoryStorage
    >>> from feedspine.composition.testing import MockAdapter

    Basic usage with context manager:

    >>> async def example():
    ...     adapter = MockAdapter(records=[])
    ...     storage = MemoryStorage()
    ...     async with Feed(adapter=adapter, storage=storage) as feed:
    ...         result = await feed.collect()
    ...         print(f"Processed: {result.total_processed}")
    >>> asyncio.run(example())
    Processed: 0
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from feedspine.composition.config import FeedConfig
from feedspine.core.feedspine import CollectionResult
from feedspine.pipeline import PipelineStats

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from feedspine.composition.ops import PipelineOp
    from feedspine.composition.preset import Preset
    from feedspine.models.query import Query
    from feedspine.protocols.enricher import Enricher
    from feedspine.protocols.feed import FeedAdapter
    from feedspine.protocols.storage import StorageBackend

from feedspine.models.record import Record


class Feed:
    """Main entry point for feed collection.

    Feed combines configuration with lifecycle management. Use it as
    a context manager to ensure proper initialization and cleanup.

    Args:
        config: Complete FeedConfig instance.
        adapter: Feed adapter (if not using config).
        storage: Storage backend (if not using config).
        enrichers: Enrichers to apply (if not using config).
        **kwargs: Additional configuration options.

    Example:
        >>> import asyncio
        >>> from feedspine.composition import Feed
        >>> from feedspine.storage.memory import MemoryStorage
        >>> from feedspine.composition.testing import MockAdapter

        Using kwargs (simple case):

        >>> async def example():
        ...     async with Feed(
        ...         adapter=MockAdapter(records=[]),
        ...         storage=MemoryStorage(),
        ...     ) as feed:
        ...         result = await feed.collect()
        ...         return result.total_processed
        >>> asyncio.run(example())
        0

        Using FeedConfig (full control):

        >>> async def example2():
        ...     config = FeedConfig(
        ...         adapter=MockAdapter(records=[]),
        ...         storage=MemoryStorage(),
        ...         batch_size=50,
        ...     )
        ...     async with Feed(config) as feed:
        ...         return feed.config.batch_size
        >>> asyncio.run(example2())
        50
    """

    def __init__(
        self,
        config: FeedConfig | None = None,
        *,
        adapter: FeedAdapter | None = None,
        storage: StorageBackend | None = None,
        enrichers: list[Enricher] | None = None,
        pipeline: list[PipelineOp] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Feed.

        Args:
            config: Complete FeedConfig (takes precedence).
            adapter: Feed adapter (required if no config).
            storage: Storage backend (required if no config).
            enrichers: List of enrichers.
            pipeline: List of pipeline operations.
            **kwargs: Additional config options.

        Raises:
            TypeError: If adapter or storage is missing.
        """
        if config is not None:
            self._config = config
        else:
            if adapter is None:
                msg = "adapter is required when not using config"
                raise TypeError(msg)
            if storage is None:
                msg = "storage is required when not using config"
                raise TypeError(msg)

            # Build config from kwargs
            self._config = FeedConfig(
                adapter=adapter,
                storage=storage,
                enrichers=tuple(enrichers or []),
                pipeline=tuple(pipeline or []),
                **kwargs,
            )

        self._initialized = False

    @property
    def config(self) -> FeedConfig:
        """Get the feed configuration."""
        return self._config

    @property
    def adapter(self) -> FeedAdapter:
        """Get the feed adapter."""
        return self._config.adapter

    @property
    def storage(self) -> StorageBackend:
        """Get the storage backend."""
        return self._config.storage

    @classmethod
    def from_preset(
        cls,
        preset: type[Preset],
        *,
        adapter: FeedAdapter,
        **overrides: Any,
    ) -> Feed:
        """Create Feed from a preset configuration.

        Args:
            preset: Preset class to use.
            adapter: Feed adapter (required).
            **overrides: Override preset defaults.

        Returns:
            Configured Feed instance.

        Example:
            >>> from feedspine.composition import Feed
            >>> from feedspine.composition.preset import MinimalPreset
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> feed = Feed.from_preset(
            ...     MinimalPreset,
            ...     adapter=MockAdapter(records=[]),
            ... )
            >>> feed.config.adapter is not None
            True
        """
        config = preset.build(adapter=adapter, **overrides)
        return cls(config)

    async def __aenter__(self) -> Feed:
        """Initialize all components.

        Returns:
            Self for use in async with statement.

        Example:
            >>> import asyncio
            >>> from feedspine.composition import Feed
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> async def example():
            ...     feed = Feed(
            ...         adapter=MockAdapter(records=[]),
            ...         storage=MemoryStorage(),
            ...     )
            ...     async with feed:
            ...         pass  # Feed is initialized here
            ...     return True
            >>> asyncio.run(example())
            True
        """
        # Initialize storage
        await self._config.storage.initialize()

        # Initialize adapter
        await self._config.adapter.initialize()

        # Initialize enrichers
        for enricher in self._config.enrichers:
            await enricher.initialize()

        # Initialize cache if present
        if self._config.cache is not None:
            await self._config.cache.initialize()

        # Initialize search if present
        if self._config.search is not None:
            await self._config.search.initialize()

        self._initialized = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Clean up all components.

        Args:
            exc_type: Exception type if error occurred.
            exc_val: Exception value if error occurred.
            exc_tb: Traceback if error occurred.
        """
        # Close in reverse order of initialization
        if self._config.search is not None:
            await self._config.search.close()

        if self._config.cache is not None:
            await self._config.cache.close()

        for enricher in reversed(list(self._config.enrichers)):
            await enricher.close()

        await self._config.adapter.close()
        await self._config.storage.close()

        self._initialized = False

    async def collect(
        self,
        *,
        limit: int | None = None,
        resume_from: str | None = None,
    ) -> CollectionResult:
        """Run feed collection.

        Args:
            limit: Maximum records to collect.
            resume_from: Checkpoint ID to resume from.

        Returns:
            CollectionResult with statistics.

        Example:
            >>> import asyncio
            >>> from feedspine.composition import Feed
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>> from feedspine.models.base import Layer, Metadata
            >>> from feedspine.models.record import RecordCandidate
            >>> from datetime import datetime, timezone
            >>>
            >>> async def example():
            ...     records = [
            ...         RecordCandidate(
            ...             natural_key=f"rec-{i}",
            ...             published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...             metadata=Metadata(source="test"),
            ...             content={"value": i},
            ...         )
            ...         for i in range(3)
            ...     ]
            ...     async with Feed(
            ...         adapter=MockAdapter(records=records),
            ...         storage=MemoryStorage(),
            ...     ) as feed:
            ...         result = await feed.collect()
            ...         return result.total_new
            >>> asyncio.run(example())
            3
        """
        if not self._initialized:
            msg = "Feed not initialized. Use 'async with Feed(...) as feed:'"
            raise RuntimeError(msg)

        result = CollectionResult(started_at=datetime.now(UTC))
        stats = PipelineStats(feed_name=self._config.adapter.name)

        try:
            # Fetch records from adapter
            async for candidate in self._config.adapter.fetch():
                # Apply pipeline operations
                record = Record.from_candidate(candidate, str(uuid.uuid4()))

                # Apply configured enrichers (enrichers modify record in-place)
                for enricher in self._config.enrichers:
                    await enricher.enrich(record)

                # Apply pipeline ops
                for op in self._config.pipeline:
                    maybe_record = await op.apply(record)
                    if maybe_record is None:
                        break
                    record = maybe_record
                else:
                    # Store if not filtered out
                    await self._config.storage.store(record)
                    stats.new += 1
                    stats.processed += 1

                # Check limit
                if limit is not None and stats.processed >= limit:
                    break

        except Exception as e:
            stats.errors += 1
            result.errors.append(str(e))
            raise

        finally:
            result.feed_stats[self._config.adapter.name] = stats
            result.completed_at = datetime.now(UTC)

        return result

    async def query(
        self,
        query: Query | None = None,
        **filters: Any,
    ) -> AsyncIterator[Record]:
        """Query collected records.

        Args:
            query: Query object for complex queries.
            **filters: Simple key=value filters.

        Yields:
            Matching Record instances.

        Example:
            >>> import asyncio
            >>> from feedspine.composition import Feed
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>> from feedspine.models.base import Layer, Metadata
            >>> from feedspine.models.record import RecordCandidate
            >>> from datetime import datetime, timezone
            >>>
            >>> async def example():
            ...     records = [
            ...         RecordCandidate(
            ...             natural_key=f"rec-{i}",
            ...             published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...             metadata=Metadata(source="test"),
            ...             content={"category": "A" if i % 2 == 0 else "B"},
            ...         )
            ...         for i in range(4)
            ...     ]
            ...     async with Feed(
            ...         adapter=MockAdapter(records=records),
            ...         storage=MemoryStorage(),
            ...     ) as feed:
            ...         await feed.collect()
            ...         count = 0
            ...         async for _ in feed.query():
            ...             count += 1
            ...         return count
            >>> asyncio.run(example())
            4
        """
        if not self._initialized:
            msg = "Feed not initialized. Use 'async with Feed(...) as feed:'"
            raise RuntimeError(msg)

        # Build filter dict
        if query is not None:
            spec = query.build()
            filter_dict = spec.filters
            query_limit = spec.limit
            query_offset = spec.offset
        else:
            filter_dict = filters
            query_limit = 100
            query_offset = 0

        # Query storage
        async for record in self._config.storage.query(
            filters=filter_dict,
            limit=query_limit,
            offset=query_offset,
        ):
            yield record


async def collect(
    adapter: FeedAdapter,
    storage: StorageBackend,
    *,
    enrichers: list[Enricher] | None = None,
    **kwargs: Any,
) -> CollectionResult:
    """Convenience function for one-shot collection.

    This is the simplest way to collect a feed - no context manager needed.

    Args:
        adapter: Feed adapter.
        storage: Storage backend.
        enrichers: Optional enrichers.
        **kwargs: Additional options.

    Returns:
        CollectionResult with statistics.

    Example:
        >>> import asyncio
        >>> from feedspine.composition import collect
        >>> from feedspine.storage.memory import MemoryStorage
        >>> from feedspine.composition.testing import MockAdapter
        >>>
        >>> async def example():
        ...     result = await collect(
        ...         MockAdapter(records=[]),
        ...         MemoryStorage(),
        ...     )
        ...     return result.total_processed
        >>> asyncio.run(example())
        0
    """
    async with Feed(
        adapter=adapter,
        storage=storage,
        enrichers=enrichers,
        **kwargs,
    ) as feed:
        return await feed.collect()
