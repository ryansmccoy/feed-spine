"""Feed-spine application factory — spine-core wiring.

Provides ``create_feed_spine()`` which constructs a fully-wired
``FeedSpineApp`` using spine-core's execution engine.

Example:
    >>> from feedspine.core.app import create_feed_spine
    >>> from feedspine.storage.memory import MemoryStorage
    >>> app = create_feed_spine(MemoryStorage())
    >>> app.runtime.name
    'feed-collection'
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine._vendor.events import EventBus

    from feedspine.enricher.worker import FeedEnrichmentWorker
    from feedspine.models.base import Layer
    from feedspine.models.record import Record
    from feedspine.protocols.enricher import Enricher
    from feedspine.protocols.feed import FeedAdapter
    from feedspine.protocols.run_log import RunLogStore
    from feedspine.protocols.search import SearchBackend
    from feedspine.protocols.storage import StorageBackend
    from feedspine.services.collection import FeedCollectionService
    from feedspine.services.publishing import CollectionEventPublisher
    from feedspine.services.recording import CollectionOutcomeRecorder
    from feedspine.workflows.collect import FeedCollectionRuntime


@dataclass
class FeedSpineApp:
    """Wired feed-spine application holding all components.

    Created by ``create_feed_spine()``.  Holds references to the service
    layer, runtime, and domain query infrastructure.
    """

    storage: StorageBackend
    collection_service: FeedCollectionService
    recorder: CollectionOutcomeRecorder
    publisher: CollectionEventPublisher
    runtime: FeedCollectionRuntime
    feeds: dict[str, FeedAdapter] = field(default_factory=dict)
    enrichers: dict[str, Enricher] = field(default_factory=dict)
    enrichment_worker: FeedEnrichmentWorker | None = None
    search_backend: SearchBackend | None = None

    def register_feed(self, adapter: FeedAdapter) -> None:
        """Register a feed adapter with the application.

        Args:
            adapter: Feed adapter to register.

        Raises:
            ValueError: If adapter name is already registered.
        """
        if adapter.name in self.feeds:
            raise ValueError(f"Feed '{adapter.name}' is already registered")
        self.feeds[adapter.name] = adapter

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
        async for record in self.storage.query(layer=layer):
            if limit is not None and count >= limit:
                break
            yield record
            count += 1


def create_feed_spine(
    storage: StorageBackend,
    *,
    event_store: Any | None = None,
    watermark_store: Any | None = None,
    work_item_store: Any | None = None,
    search: SearchBackend | None = None,
    event_bus: EventBus | None = None,
    run_log: RunLogStore | None = None,
    feeds: dict[str, FeedAdapter] | None = None,
    enrichers: dict[str, Enricher] | None = None,
) -> FeedSpineApp:
    """Factory: create a wired FeedSpineApp.

    Follows scheduler-spine's ``create_runner()`` pattern — constructs
    all services and the runtime, wiring them together.

    Args:
        storage: Domain record storage backend.
        event_store: spine-core ``EventStore`` for event emission.
            If None, a no-op publisher is used.
        watermark_store: spine-core ``WatermarkStore`` for cursor tracking.
            If None, an in-memory watermark store is created.
        work_item_store: spine-core ``WorkItemStore`` for enrichment
            work items.  If None, enrichment worker is not created.
        search: Optional search backend for full-text queries.
        event_bus: Optional event bus backend.
        run_log: Optional RunLogStore for pipeline event tracking.
            MemoryStorage satisfies this protocol.
        feeds: Optional pre-registered feed adapters (name → adapter).
        enrichers: Optional pre-registered enrichers (name → enricher).

    Returns:
        Fully wired ``FeedSpineApp``.
    """
    from feedspine.enricher.worker import FeedEnrichmentWorker
    from feedspine.services.collection import FeedCollectionService
    from feedspine.services.publishing import CollectionEventPublisher
    from feedspine.services.recording import CollectionOutcomeRecorder
    from feedspine.workflows.collect import FeedCollectionRuntime

    feed_registry = dict(feeds) if feeds else {}
    enricher_registry = dict(enrichers) if enrichers else {}

    # --- Service layer ---
    collection_service = FeedCollectionService(
        feed_registry=feed_registry,
        storage=storage,
        event_bus=event_bus,
        run_log=run_log,
    )

    # Watermark store — use provided or in-memory default
    if watermark_store is None:
        from feedspine._vendor.ports import WatermarkStore

        watermark_store = WatermarkStore()

    recorder = CollectionOutcomeRecorder(
        watermark_store=watermark_store,
    )

    # Event store — use provided or no-op
    if event_store is not None:
        publisher = CollectionEventPublisher(event_store=event_store)
    else:
        publisher = _NoOpPublisher()  # type: ignore[assignment]

    # --- Runtime ---
    runtime = FeedCollectionRuntime(
        collection_service=collection_service,
        recorder=recorder,
        publisher=publisher,
    )

    # --- Enrichment worker (optional) ---
    worker = None
    if work_item_store is not None and enricher_registry:
        worker = FeedEnrichmentWorker(
            storage=storage,
            enricher_registry=enricher_registry,
        )

    return FeedSpineApp(
        storage=storage,
        collection_service=collection_service,
        recorder=recorder,
        publisher=publisher,
        runtime=runtime,
        feeds=feed_registry,
        enrichers=enricher_registry,
        enrichment_worker=worker,
        search_backend=search,
    )


class _NoOpPublisher:
    """Placeholder publisher when no EventStore is provided."""

    def publish_completed(self, outcome: Any) -> str:
        return "noop"
