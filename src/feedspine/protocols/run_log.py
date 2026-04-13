"""RunLogStore protocol for pipeline event persistence."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from feedspine.models.run_event import RunEvent, RunEventType


@runtime_checkable
class RunLogStore(Protocol):
    """Protocol for storing and querying run events.

    Implementations should support querying by run_id, feed_name,
    event_type, and time range.
    """

    async def log(self, event: RunEvent) -> None:
        """Log a single event."""
        ...

    async def log_batch(self, events: list[RunEvent]) -> None:
        """Log multiple events in a batch."""
        ...

    async def get_by_run(
        self,
        run_id: str,
        *,
        event_types: list[RunEventType] | None = None,
    ) -> AsyncIterator[RunEvent]:
        """Get all events for a specific run in chronological order."""
        ...

    async def get_by_feed(
        self,
        feed_name: str,
        *,
        limit: int = 100,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> AsyncIterator[RunEvent]:
        """Get events for a specific feed across runs."""
        ...

    async def get_errors(
        self,
        *,
        limit: int = 50,
        feed_name: str | None = None,
        since: datetime | None = None,
    ) -> AsyncIterator[RunEvent]:
        """Get error events for debugging."""
        ...

    async def get_run_summary(self, run_id: str) -> dict | None:
        """Get summary statistics for a run, or None if not found."""
        ...

    async def cleanup_old_events(
        self,
        older_than: datetime,
        *,
        keep_errors: bool = True,
    ) -> int:
        """Remove events older than the given time. Returns count deleted."""
        ...
