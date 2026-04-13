"""In-memory run event log storage mixin.

Provides event logging for observability and debugging.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.models.run_event import RunEvent, RunEventType


class RunLogMixin:
    """Mixin providing in-memory run event log storage.

    Implements the RunLogStore protocol for event logging.

    Attributes:
        _events: All events in chronological order.
        _events_by_run: Events indexed by run_id.
        _events_by_feed: Events indexed by feed_name.
        _max_events: Maximum events to retain.
    """

    def __init__(self, max_events: int = 10000) -> None:
        self._events: list[RunEvent] = []
        self._events_by_run: dict[str, list[RunEvent]] = defaultdict(list)
        self._events_by_feed: dict[str, list[RunEvent]] = defaultdict(list)
        self._max_events = max_events

    def _clear_events(self) -> None:
        """Clear all event data."""
        self._events.clear()
        self._events_by_run.clear()
        self._events_by_feed.clear()

    async def log(self, event: RunEvent) -> None:
        """Log a single run event."""
        self._events.append(event)
        self._events_by_run[event.run_id].append(event)
        self._events_by_feed[event.feed_name].append(event)

        if len(self._events) > self._max_events:
            await self._evict_oldest_events()

    async def log_batch(self, events: list[RunEvent]) -> None:
        """Log multiple events in a batch."""
        for event in events:
            await self.log(event)

    async def get_by_run(
        self,
        run_id: str,
        *,
        event_types: list[RunEventType] | None = None,
    ) -> AsyncIterator[RunEvent]:
        """Get all events for a specific run."""
        events = self._events_by_run.get(run_id, [])
        for event in events:
            if event_types is None or event.event_type in event_types:
                yield event

    async def get_by_feed(
        self,
        feed_name: str,
        *,
        limit: int = 100,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> AsyncIterator[RunEvent]:
        """Get events for a specific feed across runs."""
        events = self._events_by_feed.get(feed_name, [])

        filtered = []
        for event in events:
            if since and event.timestamp < since:
                continue
            if until and event.timestamp > until:
                continue
            filtered.append(event)

        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        for event in filtered[:limit]:
            yield event

    async def get_errors(
        self,
        *,
        limit: int = 50,
        feed_name: str | None = None,
        since: datetime | None = None,
    ) -> AsyncIterator[RunEvent]:
        """Get error events for debugging."""
        from feedspine.models.run_event import RunEventType

        error_types = {RunEventType.RUN_ERROR, RunEventType.FETCH_ERROR}

        errors = []
        for event in self._events:
            if event.event_type not in error_types:
                continue
            if feed_name and event.feed_name != feed_name:
                continue
            if since and event.timestamp < since:
                continue
            errors.append(event)

        errors.sort(key=lambda e: e.timestamp, reverse=True)
        for event in errors[:limit]:
            yield event

    async def get_run_summary(self, run_id: str) -> dict[str, Any] | None:
        """Get summary statistics for a run."""
        from feedspine.models.run_event import RunEventType

        events = self._events_by_run.get(run_id)
        if not events:
            return None

        started_at = None
        completed_at = None
        status = "running"
        stats = {"processed": 0, "new": 0, "updated": 0, "duplicates": 0, "errors": 0}
        feed_name = events[0].feed_name if events else None

        for event in events:
            if event.event_type == RunEventType.RUN_STARTED:
                started_at = event.timestamp
            elif event.event_type == RunEventType.RUN_COMPLETED:
                completed_at = event.timestamp
                status = "completed"
                stats = {
                    "processed": event.data.get("processed", 0),
                    "new": event.data.get("new", 0),
                    "updated": event.data.get("updated", 0),
                    "duplicates": event.data.get("duplicates", 0),
                    "errors": event.data.get("errors", 0),
                }
            elif event.event_type == RunEventType.RUN_ERROR:
                status = "error"
            elif event.event_type == RunEventType.RECORD_CREATED:
                stats["new"] += 1
                stats["processed"] += 1
            elif event.event_type == RunEventType.RECORD_UPDATED:
                stats["updated"] += 1
                stats["processed"] += 1
            elif event.event_type == RunEventType.RECORD_DUPLICATE:
                stats["duplicates"] += 1
                stats["processed"] += 1

        return {
            "run_id": run_id,
            "feed_name": feed_name,
            "started_at": started_at,
            "completed_at": completed_at,
            "status": status,
            "stats": stats,
            "event_count": len(events),
        }

    async def cleanup_old_events(
        self,
        older_than: datetime,
        *,
        keep_errors: bool = True,
    ) -> int:
        """Remove old events to manage storage."""
        from feedspine.models.run_event import RunEventType

        error_types = {RunEventType.RUN_ERROR, RunEventType.FETCH_ERROR}

        kept = []
        deleted_count = 0

        for event in self._events:
            should_keep = event.timestamp >= older_than
            if not should_keep and keep_errors and event.event_type in error_types:
                should_keep = True

            if should_keep:
                kept.append(event)
            else:
                deleted_count += 1

        self._events = kept
        self._events_by_run = defaultdict(list)
        self._events_by_feed = defaultdict(list)

        for event in self._events:
            self._events_by_run[event.run_id].append(event)
            self._events_by_feed[event.feed_name].append(event)

        return deleted_count

    async def _evict_oldest_events(self) -> None:
        """Evict oldest events when over capacity."""
        evict_count = self._max_events // 10
        evicted = self._events[:evict_count]
        self._events = self._events[evict_count:]

        for event in evicted:
            run_events = self._events_by_run.get(event.run_id, [])
            if event in run_events:
                run_events.remove(event)
            feed_events = self._events_by_feed.get(event.feed_name, [])
            if event in feed_events:
                feed_events.remove(event)

    async def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get summaries of recent runs."""
        run_ids = []
        seen: set[str] = set()
        for event in reversed(self._events):
            if event.run_id not in seen:
                seen.add(event.run_id)
                run_ids.append(event.run_id)
                if len(run_ids) >= limit:
                    break

        summaries = []
        for run_id in run_ids:
            summary = await self.get_run_summary(run_id)
            if summary:
                summaries.append(summary)

        return summaries

    @property
    def event_count(self) -> int:
        """Return the number of events stored."""
        return len(self._events)
