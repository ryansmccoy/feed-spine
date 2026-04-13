"""Pipeline - Core feed processing orchestrator (facade).

Provides the Pipeline class as a thin facade over the decomposed
pipeline modules: context, stages, and runner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from feedspine.pipeline.context import PipelineContext
from feedspine.pipeline.runner import run_feed
from feedspine.pipeline.stages import process_candidate

if TYPE_CHECKING:
    from spine.events import EventBus

    from feedspine.models.record import RecordCandidate
    from feedspine.protocols.feed import FeedAdapter
    from feedspine.protocols.run_log import RunLogStore
    from feedspine.protocols.storage import StorageBackend

# Re-export for internal package use
from feedspine.pipeline.action import ProcessAction  # noqa: F401
from feedspine.pipeline.result import ProcessResult  # noqa: F401
from feedspine.pipeline.stats import PipelineStats  # noqa: F401


class Pipeline:
    """Core feed processing orchestrator with deduplication and update detection.

    Thin facade that delegates to:

    - ``PipelineContext``: dependency container (storage, notifier, run_log)
    - ``process_candidate()``: deduplication logic (in stages module)
    - ``run_feed()``: feed orchestration (in runner module)

    Deduplication uses natural-key lookup + content-hash comparison to
    classify each candidate as CREATED, DUPLICATE, or UPDATED.

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
        ...     result = await pipeline.process(candidate, source="test")
        ...     return result.is_new
        >>> asyncio.run(example())
        True

    Attributes:
        storage: StorageBackend for records and sightings.
        event_bus: Optional EventBus for new record alerts.
        run_log: Optional RunLogStore for event tracking.
    """

    def __init__(
        self,
        storage: StorageBackend,
        event_bus: EventBus | None = None,
        run_log: RunLogStore | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            storage: Storage backend for records and sightings.
            event_bus: Optional event bus for new record alerts.
            run_log: Optional run log store for event tracking.
        """
        self._ctx = PipelineContext(
            storage=storage,
            event_bus=event_bus,
            run_log=run_log,
        )

    @property
    def storage(self) -> StorageBackend:
        """Get the storage backend."""
        return self._ctx.storage

    @property
    def event_bus(self) -> EventBus | None:
        """Get the event bus (if configured)."""
        return self._ctx.event_bus

    @property
    def run_log(self) -> RunLogStore | None:
        """Get the run log store (if configured)."""
        return self._ctx.run_log

    async def process(
        self,
        candidate: RecordCandidate,
        source: str,
    ) -> ProcessResult:
        """Process a single record candidate with content hash-based update detection.

        Delegates to ``process_candidate()`` in the stages module.

        Args:
            candidate: The record candidate to process.
            source: Source identifier for sighting tracking.

        Returns:
            ProcessResult containing the action taken and the record.

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
            ...     result = await pipeline.process(c, source="test")
            ...     return result.is_new
            >>> asyncio.run(example())
            True
        """
        return await process_candidate(self._ctx, candidate, source)

    async def run(self, feed: FeedAdapter) -> PipelineStats:
        """Run the pipeline for a feed adapter.

        Delegates to ``run_feed()`` in the runner module.

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
        return await run_feed(self._ctx, feed)
