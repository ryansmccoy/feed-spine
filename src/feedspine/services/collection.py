"""FeedCollectionService — domain execution for feed collection.

Owns the core domain logic: adapter lookup → pipeline construction →
record storage via StorageBackend.  Does NOT write operational records
(watermarks, manifests, etc.) or emit events — those responsibilities
belong to ``CollectionOutcomeRecorder`` and ``CollectionEventPublisher``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from spine.events import EventBus

from feedspine.pipeline.core import Pipeline
from feedspine.pipeline.stats import PipelineStats
from feedspine.protocols.feed import FeedAdapter
from feedspine.protocols.run_log import RunLogStore
from feedspine.protocols.storage import StorageBackend


@dataclass(frozen=True)
class CollectionOutcome:
    """Result of a single feed collection attempt."""

    feed_name: str
    stats: PipelineStats
    records_stored: int
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class FeedCollectionService:
    """Runs feed collection: adapter → pipeline → storage.

    Does NOT write operational records or emit events.
    Those responsibilities belong to ``CollectionOutcomeRecorder``
    and ``CollectionEventPublisher`` respectively.

    Args:
        feed_registry: Mapping of feed name → adapter instance.
        storage: Domain record storage backend.
        event_bus: Optional event bus for pipeline events.
    """

    def __init__(
        self,
        feed_registry: dict[str, FeedAdapter],
        storage: StorageBackend,
        event_bus: EventBus | None = None,
        run_log: RunLogStore | None = None,
    ) -> None:
        self._feeds = feed_registry
        self._storage = storage
        self._event_bus = event_bus
        self._run_log = run_log

    @property
    def available_feeds(self) -> list[str]:
        """Return names of all registered feed adapters."""
        return list(self._feeds.keys())

    async def run_collection(self, feed_name: str) -> CollectionOutcome:
        """Run collection for a single feed.

        Args:
            feed_name: Name of the registered feed to collect.

        Returns:
            CollectionOutcome with pipeline statistics.

        Raises:
            KeyError: If feed_name is not registered.
        """
        if feed_name not in self._feeds:
            raise KeyError(f"Feed not registered: {feed_name!r}")
        adapter = self._feeds[feed_name]
        pipeline = Pipeline(storage=self._storage, event_bus=self._event_bus, run_log=self._run_log)
        started = datetime.now(UTC)
        stats = await pipeline.run(adapter)
        return CollectionOutcome(
            feed_name=feed_name,
            stats=stats,
            records_stored=stats.new,
            started_at=started,
            completed_at=datetime.now(UTC),
        )
