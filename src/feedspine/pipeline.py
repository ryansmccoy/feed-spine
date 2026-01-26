"""Pipeline - Core feed processing orchestrator.

The Pipeline handles the complete flow of:
1. Fetching records from feed adapters
2. Deduplicating using natural keys
3. Storing new records in Bronze layer
4. Tracking sightings for duplicates
5. Optionally notifying on new records

Example:
    >>> from feedspine.pipeline import Pipeline, PipelineStats
    >>> from feedspine import MemoryStorage
    >>> # Pipeline orchestrates feed processing
    >>> hasattr(Pipeline, "process")
    True
    >>> hasattr(Pipeline, "run")
    True
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from feedspine.models.record import Record
from feedspine.models.sighting import Sighting
from feedspine.protocols.notification import Notification, Severity

if TYPE_CHECKING:
    from feedspine.models.record import RecordCandidate
    from feedspine.protocols.feed import FeedAdapter
    from feedspine.protocols.notification import Notifier
    from feedspine.protocols.storage import StorageBackend


@dataclass
class PipelineStats:
    """Statistics from a pipeline run.

    Example:
        >>> from feedspine.pipeline import PipelineStats
        >>> stats = PipelineStats(
        ...     feed_name="sec_rss",
        ...     processed=100,
        ...     new=80,
        ...     duplicates=20,
        ...     errors=0,
        ...     duration_ms=250.0,
        ... )
        >>> stats.dedup_rate
        0.2
    """

    feed_name: str
    processed: int = 0
    new: int = 0
    duplicates: int = 0
    errors: int = 0
    duration_ms: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def dedup_rate(self) -> float:
        """Calculate deduplication rate (0.0 to 1.0).

        Example:
            >>> from feedspine.pipeline import PipelineStats
            >>> stats = PipelineStats("test", processed=100, duplicates=25)
            >>> stats.dedup_rate
            0.25
        """
        if self.processed == 0:
            return 0.0
        return self.duplicates / self.processed


class Pipeline:
    """Core feed processing pipeline.

    Orchestrates the flow from feed adapters through deduplication
    to storage, with optional notifications.

    Example:
        >>> import asyncio
        >>> from feedspine.pipeline import Pipeline
        >>> from feedspine import MemoryStorage, RecordCandidate
        >>> from datetime import datetime, UTC
        >>> async def example():
        ...     storage = MemoryStorage()
        ...     await storage.initialize()
        ...     pipeline = Pipeline(storage=storage)
        ...     candidate = RecordCandidate(
        ...         natural_key="test-001",
        ...         title="Test",
        ...         published_at=datetime.now(UTC),
        ...         metadata={"source": "test"},
        ...     )
        ...     record = await pipeline.process(candidate, source="test")
        ...     return record.natural_key
        >>> asyncio.run(example())
        'test-001'
    """

    def __init__(
        self,
        storage: StorageBackend,
        notifier: Notifier | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            storage: Storage backend for records and sightings.
            notifier: Optional notifier for new record alerts.
        """
        self._storage = storage
        self._notifier = notifier

    @property
    def storage(self) -> StorageBackend:
        """Get the storage backend."""
        return self._storage

    @property
    def notifier(self) -> Notifier | None:
        """Get the notifier (if configured)."""
        return self._notifier

    async def process(
        self,
        candidate: RecordCandidate,
        source: str,
    ) -> Record | None:
        """Process a single record candidate.

        Args:
            candidate: The record candidate to process.
            source: Source identifier for sighting tracking.

        Returns:
            The stored Record if new, None if duplicate.

        Raises:
            TypeError: If candidate is None.
            ValueError: If candidate is invalid.

        Example:
            >>> import asyncio
            >>> from feedspine.pipeline import Pipeline
            >>> from feedspine import MemoryStorage, RecordCandidate
            >>> from datetime import datetime, UTC
            >>> async def example():
            ...     storage = MemoryStorage()
            ...     await storage.initialize()
            ...     pipeline = Pipeline(storage=storage)
            ...     c = RecordCandidate(
            ...         natural_key="acc-001",
            ...         title="Filing",
            ...         published_at=datetime.now(UTC),
            ...         metadata={"source": "test"},
            ...     )
            ...     r = await pipeline.process(c, source="test")
            ...     return r is not None
            >>> asyncio.run(example())
            True
        """
        if candidate is None:
            raise TypeError("candidate cannot be None")

        # Check if already exists
        existing = await self._storage.get_by_natural_key(candidate.natural_key)

        if existing is not None:
            # Record sighting for duplicate
            sighting = Sighting(
                id=str(uuid.uuid4()),
                natural_key=candidate.natural_key,
                source=source,
                record_id=existing.id,
                is_new=False,
            )
            await self._storage.record_sighting(sighting)
            return None

        # Create new record from candidate with generated UUID
        record_id = str(uuid.uuid4())
        record = Record.from_candidate(candidate, record_id)

        # Store the record
        await self._storage.store(record)

        # Record first sighting
        sighting = Sighting(
            id=str(uuid.uuid4()),
            natural_key=record.natural_key,
            source=source,
            record_id=record.id,
            is_new=True,
        )
        await self._storage.record_sighting(sighting)

        # Notify if configured
        if self._notifier is not None:
            title = record.content.get("title", record.natural_key)
            notification = Notification(
                title="New Record",
                message=f"New record: {title}",
                severity=Severity.INFO,
                data={"record_id": record.id, "natural_key": record.natural_key},
            )
            await self._notifier.send(notification)

        return record

    async def run(self, feed: FeedAdapter) -> PipelineStats:
        """Run the pipeline for a feed adapter.

        Fetches all candidates from the feed and processes them.

        Args:
            feed: The feed adapter to process.

        Returns:
            Statistics about the pipeline run.

        Example:
            >>> import asyncio
            >>> from feedspine.pipeline import Pipeline
            >>> from feedspine import MemoryStorage
            >>> async def example():
            ...     storage = MemoryStorage()
            ...     await storage.initialize()
            ...     pipeline = Pipeline(storage=storage)
            ...     # Would need a feed adapter here
            ...     return True
            >>> asyncio.run(example())
            True
        """
        start_time = time.perf_counter()
        stats = PipelineStats(feed_name=feed.name)

        async for candidate in feed.fetch():
            stats.processed += 1
            try:
                result = await self.process(candidate, source=feed.name)
                if result is not None:
                    stats.new += 1
                else:
                    stats.duplicates += 1
            except Exception:
                stats.errors += 1

        stats.duration_ms = (time.perf_counter() - start_time) * 1000
        return stats
