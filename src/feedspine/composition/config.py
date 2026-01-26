"""Feed configuration dataclass.

This module provides the FeedConfig dataclass for type-safe, immutable
feed configuration. Unlike builder patterns, configuration errors are
caught at definition time with full IDE support.

Example:
    >>> from feedspine.composition.config import FeedConfig
    >>> from feedspine.storage.memory import MemoryStorage
    >>> from feedspine.composition.testing import MockAdapter

    Create a basic configuration:

    >>> adapter = MockAdapter(records=[])
    >>> storage = MemoryStorage()
    >>> config = FeedConfig(adapter=adapter, storage=storage)
    >>> config.rate_limit is None
    True

    Create immutable variants with modifications:

    >>> config2 = config.with_rate_limit(10.0)
    >>> config2.rate_limit
    10.0
    >>> config.rate_limit is None  # Original unchanged
    True
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from feedspine.composition.ops import PipelineOp
    from feedspine.core.checkpoint import CheckpointStore
    from feedspine.protocols.cache import CacheBackend
    from feedspine.protocols.enricher import Enricher
    from feedspine.protocols.feed import FeedAdapter
    from feedspine.protocols.notification import Notifier
    from feedspine.protocols.search import SearchBackend
    from feedspine.protocols.storage import StorageBackend


@dataclass(frozen=True)
class FeedConfig:
    """Immutable feed configuration.

    All parameters are explicit and type-safe. IDE autocomplete shows
    exactly what's available. The frozen=True ensures immutability,
    making configurations safe to share and reuse.

    Args:
        adapter: Feed adapter that fetches records from a source.
        storage: Storage backend for persisting records.
        enrichers: Sequence of enrichers to process records.
        cache: Optional cache backend for performance.
        search: Optional search backend for full-text search.
        notifier: Optional notifier for alerts.
        rate_limit: Maximum requests per second (None = unlimited).
        concurrency: Number of concurrent operations.
        checkpoint_interval: Save checkpoint every N records (None = disabled).
        checkpoint_store: Where to save checkpoints.
        batch_size: Number of records to process in each batch.
        pipeline: Sequence of pipeline operations.
        metadata: Additional metadata for the feed.

    Example:
        >>> from feedspine.composition.config import FeedConfig
        >>> from feedspine.storage.memory import MemoryStorage
        >>> from feedspine.composition.testing import MockAdapter
        >>>
        >>> config = FeedConfig(
        ...     adapter=MockAdapter(records=[]),
        ...     storage=MemoryStorage(),
        ...     rate_limit=10.0,
        ...     batch_size=50,
        ... )
        >>> config.rate_limit
        10.0
        >>> config.batch_size
        50
    """

    # Required components
    adapter: FeedAdapter
    storage: StorageBackend

    # Optional components
    enrichers: Sequence[Enricher] = field(default_factory=tuple)
    cache: CacheBackend | None = None
    search: SearchBackend | None = None
    notifier: Notifier | None = None

    # Behavior configuration
    rate_limit: float | None = None
    concurrency: int = 1
    checkpoint_interval: int | None = None
    checkpoint_store: CheckpointStore | None = None
    batch_size: int = 100

    # Pipeline operations
    pipeline: Sequence[PipelineOp] = field(default_factory=tuple)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_enricher(self, enricher: Enricher) -> FeedConfig:
        """Return new config with an additional enricher.

        Args:
            enricher: Enricher to add to the pipeline.

        Returns:
            New FeedConfig with the enricher appended.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter, MockEnricher
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> len(config.enrichers)
            0
            >>> config2 = config.with_enricher(MockEnricher())
            >>> len(config2.enrichers)
            1
        """
        return dataclasses.replace(self, enrichers=(*self.enrichers, enricher))

    def with_enrichers(self, *enrichers: Enricher) -> FeedConfig:
        """Return new config with additional enrichers.

        Args:
            enrichers: Enrichers to add to the pipeline.

        Returns:
            New FeedConfig with the enrichers appended.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter, MockEnricher
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> config2 = config.with_enrichers(MockEnricher(), MockEnricher())
            >>> len(config2.enrichers)
            2
        """
        return dataclasses.replace(self, enrichers=(*self.enrichers, *enrichers))

    def with_rate_limit(self, rps: float) -> FeedConfig:
        """Return new config with rate limit.

        Args:
            rps: Maximum requests per second.

        Returns:
            New FeedConfig with rate limit set.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> config.rate_limit is None
            True
            >>> config2 = config.with_rate_limit(5.0)
            >>> config2.rate_limit
            5.0
        """
        return dataclasses.replace(self, rate_limit=rps)

    def with_concurrency(self, n: int) -> FeedConfig:
        """Return new config with concurrency limit.

        Args:
            n: Maximum concurrent operations.

        Returns:
            New FeedConfig with concurrency set.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> config.concurrency
            1
            >>> config2 = config.with_concurrency(4)
            >>> config2.concurrency
            4
        """
        return dataclasses.replace(self, concurrency=n)

    def with_checkpoint(
        self,
        interval: int = 100,
        store: CheckpointStore | None = None,
    ) -> FeedConfig:
        """Return new config with checkpointing enabled.

        Args:
            interval: Save checkpoint every N records.
            store: Where to save checkpoints.

        Returns:
            New FeedConfig with checkpointing configured.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> config.checkpoint_interval is None
            True
            >>> config2 = config.with_checkpoint(interval=50)
            >>> config2.checkpoint_interval
            50
        """
        return dataclasses.replace(
            self,
            checkpoint_interval=interval,
            checkpoint_store=store,
        )

    def with_cache(self, cache: CacheBackend) -> FeedConfig:
        """Return new config with cache backend.

        Args:
            cache: Cache backend to use.

        Returns:
            New FeedConfig with cache set.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.cache.memory import MemoryCache
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> config.cache is None
            True
            >>> config2 = config.with_cache(MemoryCache())
            >>> config2.cache is not None
            True
        """
        return dataclasses.replace(self, cache=cache)

    def with_search(self, search: SearchBackend) -> FeedConfig:
        """Return new config with search backend.

        Args:
            search: Search backend to use.

        Returns:
            New FeedConfig with search set.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.search.memory import MemorySearch
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> config.search is None
            True
            >>> config2 = config.with_search(MemorySearch())
            >>> config2.search is not None
            True
        """
        return dataclasses.replace(self, search=search)

    def with_notifier(self, notifier: Notifier) -> FeedConfig:
        """Return new config with notifier.

        Args:
            notifier: Notifier for alerts.

        Returns:
            New FeedConfig with notifier set.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.notifier.console import ConsoleNotifier
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> config.notifier is None
            True
            >>> config2 = config.with_notifier(ConsoleNotifier())
            >>> config2.notifier is not None
            True
        """
        return dataclasses.replace(self, notifier=notifier)

    def with_pipeline(self, *ops: PipelineOp) -> FeedConfig:
        """Return new config with pipeline operations.

        Args:
            ops: Pipeline operations to apply.

        Returns:
            New FeedConfig with pipeline operations set.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> len(config.pipeline)
            0
        """
        return dataclasses.replace(self, pipeline=(*self.pipeline, *ops))

    def with_metadata(self, **kwargs: Any) -> FeedConfig:
        """Return new config with additional metadata.

        Args:
            kwargs: Metadata key-value pairs.

        Returns:
            New FeedConfig with metadata merged.

        Example:
            >>> from feedspine.composition.config import FeedConfig
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> config = FeedConfig(
            ...     adapter=MockAdapter(records=[]),
            ...     storage=MemoryStorage(),
            ... )
            >>> config2 = config.with_metadata(source="sec", version="1.0")
            >>> config2.metadata["source"]
            'sec'
        """
        return dataclasses.replace(self, metadata={**self.metadata, **kwargs})
