"""PipelineContext - Dependencies and state for pipeline operations.

Provides the PipelineContext class that encapsulates the storage,
notification, and logging dependencies needed by pipeline stages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feedspine._vendor.events import EventBus

    from feedspine.models.run_event import RunEvent
    from feedspine.pipeline.dedup import DedupIndex
    from feedspine.protocols.run_log import RunLogStore
    from feedspine.protocols.storage import StorageBackend


class PipelineContext:
    """Container for pipeline dependencies and shared state.

    Encapsulates the external services that pipeline stages need
    (storage, event bus, run log, dedup index) so stages accept a
    single context object rather than multiple individual dependencies.

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
        dedup_index: DedupIndex | None = None,
    ) -> None:
        """Initialize the pipeline context.

        Args:
            storage: Storage backend for records and sightings.
            event_bus: Optional event bus for new record alerts.
            run_log: Optional run log store for event tracking.
            dedup_index: Optional cross-feed dedup index.
        """
        self._storage = storage
        self._event_bus = event_bus
        self._run_log = run_log
        self._dedup_index = dedup_index

    @property
    def storage(self) -> StorageBackend:
        """Get the storage backend."""
        return self._storage

    @property
    def event_bus(self) -> EventBus | None:
        """Get the event bus (if configured)."""
        return self._event_bus

    @property
    def run_log(self) -> RunLogStore | None:
        """Get the run log store (if configured)."""
        return self._run_log

    @property
    def dedup_index(self) -> DedupIndex | None:
        """Get the cross-feed dedup index (if configured)."""
        return self._dedup_index

    async def log_event(self, event: RunEvent) -> None:
        """Log an event if run_log is configured.

        Args:
            event: The run event to log.
        """
        if self._run_log is not None:
            await self._run_log.log(event)
