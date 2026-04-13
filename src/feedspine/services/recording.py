"""CollectionOutcomeRecorder — operational side-effect recording.

Records operational facts after a feed collection completes.  Follows
the *Collection Completion Ordering Contract*:

1. Domain records (already written by ``FeedCollectionService``)
2. Operational records (this module — watermark, source tracking)
3. WorkItem completion (handled by the Runner)
4. Event emission (handled by ``CollectionEventPublisher``)

Currently supports:

- **Watermark advancement** via ``WatermarkStore.advance()``

Additional operational recording (manifest entries, quality checks,
reject tracking, anomaly detection) will be added as spine-core
repository write APIs become available.
"""

from __future__ import annotations

from datetime import UTC, datetime

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feedspine._vendor.ports import WatermarkStore

from feedspine._vendor.logging import get_logger

from feedspine.services.collection import CollectionOutcome

logger = get_logger(__name__)


class CollectionOutcomeRecorder:
    """Records operational facts from a collection outcome.

    Args:
        watermark_store: Cursor tracking store for forward-only advancement.
    """

    def __init__(
        self,
        watermark_store: WatermarkStore,
    ) -> None:
        self._watermark_store = watermark_store

    def record(self, outcome: CollectionOutcome) -> None:
        """Record all operational side effects for a collection outcome.

        Args:
            outcome: The collection result to record.
        """
        self._advance_watermark(outcome)

    def _advance_watermark(self, outcome: CollectionOutcome) -> None:
        """Advance the high-water mark for the collected feed."""
        cursor = (outcome.completed_at or datetime.now(UTC)).isoformat()
        self._watermark_store.advance(
            domain="feed-spine",
            source="collection",
            partition_key=outcome.feed_name,
            high_water=cursor,
            metadata={
                "records_stored": outcome.records_stored,
                "processed": outcome.stats.processed,
                "new": outcome.stats.new,
                "duplicates": outcome.stats.duplicates,
                "updated": outcome.stats.updated,
                "errors": outcome.stats.errors,
            },
        )
        logger.debug(
            "Watermark advanced for feed %r: %s",
            outcome.feed_name,
            cursor,
        )
