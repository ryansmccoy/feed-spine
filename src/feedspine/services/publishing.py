"""CollectionEventPublisher — emits collection completion events.

Emits ``feed.collection.completed`` events via spine-core's
``EventStore``.  Must be called LAST per the Collection Completion
Ordering Contract — after domain records are stored and operational
side effects are recorded.
"""

from __future__ import annotations

from datetime import UTC, datetime

from spine.core.logging import get_logger
from spine.ports import EventStore

from feedspine.services.collection import CollectionOutcome

logger = get_logger(__name__)


class CollectionEventPublisher:
    """Emits feed collection completion events via EventStore.

    Args:
        event_store: spine-core append-only event log.
    """

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    def publish_completed(self, outcome: CollectionOutcome) -> str:
        """Emit a ``feed.collection.completed`` event.

        Args:
            outcome: The collection result to publish.

        Returns:
            Event ID from the event store.
        """
        event = {
            "event_type": "feed.collection.completed",
            "source": "feed-spine",
            "occurred_at": datetime.now(UTC).isoformat(),
            "data": {
                "feed_name": outcome.feed_name,
                "records_stored": outcome.records_stored,
                "processed": outcome.stats.processed,
                "new": outcome.stats.new,
                "duplicates": outcome.stats.duplicates,
                "updated": outcome.stats.updated,
                "errors": outcome.stats.errors,
                "duration_ms": outcome.stats.duration_ms,
            },
        }
        event_id = self._event_store.append(event)
        logger.info(
            "Published feed.collection.completed for %r (event_id=%s)",
            outcome.feed_name,
            event_id,
        )
        return event_id
