"""Preset configurations for common feed patterns.

Presets provide reusable, customizable configurations for specific
domains or use cases. They eliminate boilerplate while remaining
fully configurable.

Example:
    >>> from feedspine.composition.preset import Preset
    >>> from feedspine.storage.memory import MemoryStorage

    Define a custom preset:

    >>> class MyPreset(Preset):
    ...     storage_class = MemoryStorage
    ...     rate_limit = 5.0
    ...     batch_size = 50
    >>>
    >>> MyPreset.rate_limit
    5.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Sequence

    from feedspine.composition.config import FeedConfig
    from feedspine.composition.ops import PipelineOp
    from feedspine.core.checkpoint import CheckpointStore
    from feedspine.protocols.cache import CacheBackend
    from feedspine.protocols.enricher import Enricher
    from feedspine.protocols.feed import FeedAdapter
    from feedspine.protocols.notification import Notifier
    from feedspine.protocols.search import SearchBackend
    from feedspine.protocols.storage import StorageBackend


class Preset:
    """Base class for feed presets.

    Presets define default configurations for specific use cases.
    Override class variables to customize, then use `build()` to
    create a FeedConfig.

    Class Variables:
        storage_class: Storage backend class to instantiate.
        storage_kwargs: Arguments passed to storage constructor.
        enricher_classes: Enricher classes to instantiate.
        cache_class: Optional cache backend class.
        search_class: Optional search backend class.
        notifier_class: Optional notifier class.
        rate_limit: Default rate limit (requests/second).
        concurrency: Default concurrency level.
        checkpoint_interval: Default checkpoint interval.
        checkpoint_store_class: Default checkpoint store class.
        batch_size: Default batch size.
        pipeline_ops: Default pipeline operations.

    Example:
        >>> from feedspine.composition.preset import Preset
        >>> from feedspine.storage.memory import MemoryStorage
        >>> from feedspine.composition.testing import MockAdapter
        >>>
        >>> class SimplePreset(Preset):
        ...     storage_class = MemoryStorage
        ...     rate_limit = 10.0
        >>>
        >>> adapter = MockAdapter(records=[])
        >>> config = SimplePreset.build(adapter=adapter)
        >>> config.rate_limit
        10.0
    """

    # Storage configuration
    storage_class: ClassVar[type[StorageBackend] | None] = None
    storage_kwargs: ClassVar[dict[str, Any]] = {}

    # Enrichers
    enricher_classes: ClassVar[Sequence[type[Enricher]]] = ()

    # Optional backends
    cache_class: ClassVar[type[CacheBackend] | None] = None
    search_class: ClassVar[type[SearchBackend] | None] = None
    notifier_class: ClassVar[type[Notifier] | None] = None

    # Behavior defaults
    rate_limit: ClassVar[float | None] = None
    concurrency: ClassVar[int] = 1
    checkpoint_interval: ClassVar[int | None] = None
    checkpoint_store_class: ClassVar[type[CheckpointStore] | None] = None
    batch_size: ClassVar[int] = 100

    # Pipeline operations
    pipeline_ops: ClassVar[Sequence[PipelineOp]] = ()

    @classmethod
    def build(
        cls,
        *,
        adapter: FeedAdapter,
        storage: StorageBackend | None = None,
        storage_path: str | None = None,
        **overrides: Any,
    ) -> FeedConfig:
        """Build a FeedConfig from this preset.

        Args:
            adapter: Feed adapter (required).
            storage: Override storage backend.
            storage_path: Path for storage (if storage_class accepts path).
            **overrides: Override any preset defaults.

        Returns:
            Configured FeedConfig instance.

        Raises:
            ValueError: If storage cannot be determined.

        Example:
            >>> from feedspine.composition.preset import Preset
            >>> from feedspine.storage.memory import MemoryStorage
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> class TestPreset(Preset):
            ...     storage_class = MemoryStorage
            ...     batch_size = 25
            >>>
            >>> adapter = MockAdapter(records=[])
            >>> config = TestPreset.build(adapter=adapter)
            >>> config.batch_size
            25
            >>> config2 = TestPreset.build(adapter=adapter, batch_size=50)
            >>> config2.batch_size
            50
        """
        # Import here to avoid circular imports
        from feedspine.composition.config import FeedConfig

        # Determine storage
        if storage is not None:
            resolved_storage = storage
        elif cls.storage_class is not None:
            kwargs = dict(cls.storage_kwargs)
            if storage_path is not None:
                kwargs["path"] = storage_path
            resolved_storage = cls.storage_class(**kwargs)
        else:
            msg = "Either storage or storage_class must be provided"
            raise ValueError(msg)

        # Build enrichers
        enrichers: list[Enricher] = []
        for enricher_cls in cls.enricher_classes:
            enrichers.append(enricher_cls())

        # Build optional backends
        cache = cls.cache_class() if cls.cache_class else None
        search = cls.search_class() if cls.search_class else None
        notifier = cls.notifier_class() if cls.notifier_class else None
        checkpoint_store = cls.checkpoint_store_class() if cls.checkpoint_store_class else None

        # Create config with defaults
        config = FeedConfig(
            adapter=adapter,
            storage=resolved_storage,
            enrichers=tuple(enrichers),
            cache=cache,
            search=search,
            notifier=notifier,
            rate_limit=cls.rate_limit,
            concurrency=cls.concurrency,
            checkpoint_interval=cls.checkpoint_interval,
            checkpoint_store=checkpoint_store,
            batch_size=cls.batch_size,
            pipeline=tuple(cls.pipeline_ops),
        )

        # Apply overrides via with_* methods where possible
        for key, value in overrides.items():
            if key == "enrichers" and isinstance(value, list | tuple):
                for e in value:
                    config = config.with_enricher(e)
            elif key == "rate_limit":
                config = config.with_rate_limit(value)
            elif key == "concurrency":
                config = config.with_concurrency(value)
            elif key == "cache":
                config = config.with_cache(value)
            elif key == "search":
                config = config.with_search(value)
            elif key == "notifier":
                config = config.with_notifier(value)
            elif key == "checkpoint_interval":
                config = config.with_checkpoint(interval=value)
            elif key == "batch_size":
                import dataclasses

                config = dataclasses.replace(config, batch_size=value)
            elif key == "pipeline":
                config = config.with_pipeline(*value)
            else:
                # For other keys, use dataclasses.replace
                import dataclasses

                config = dataclasses.replace(config, **{key: value})

        return config


class MinimalPreset(Preset):
    """Minimal preset for testing and simple use cases.

    Uses in-memory storage with no bells and whistles.

    Example:
        >>> from feedspine.composition.preset import MinimalPreset
        >>> from feedspine.composition.testing import MockAdapter
        >>>
        >>> adapter = MockAdapter(records=[])
        >>> config = MinimalPreset.build(adapter=adapter)
        >>> config.rate_limit is None
        True
    """

    # Will be set dynamically to avoid import issues
    storage_class = None

    @classmethod
    def build(
        cls,
        *,
        adapter: FeedAdapter,
        storage: StorageBackend | None = None,
        storage_path: str | None = None,
        **overrides: Any,
    ) -> FeedConfig:
        """Build minimal config with MemoryStorage default."""
        if storage is None and cls.storage_class is None:
            from feedspine.storage.memory import MemoryStorage

            storage = MemoryStorage()
        return super().build(
            adapter=adapter,
            storage=storage,
            storage_path=storage_path,
            **overrides,
        )
