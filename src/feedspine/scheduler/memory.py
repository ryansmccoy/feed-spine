"""Memory-based scheduler implementation.

This module provides an in-memory Scheduler for development and testing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from feedspine.protocols.scheduler import ScheduleInfo


class MemoryScheduler:
    """In-memory scheduler implementation.

    This scheduler stores all schedule state in memory. It's suitable for
    development, testing, and single-process applications.

    Example:
        >>> scheduler = MemoryScheduler()
        >>> await scheduler.initialize()
        >>> await scheduler.register("sec_rss", timedelta(minutes=5))
        >>> async for info in scheduler.get_due():
        ...     print(f"Collecting {info.feed_name}")
        ...     await scheduler.mark_success(info.feed_name)
    """

    def __init__(self) -> None:
        """Create a new MemoryScheduler."""
        self._schedules: dict[str, ScheduleInfo] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the scheduler.

        This is idempotent - calling multiple times is safe.
        """
        self._initialized = True

    async def close(self) -> None:
        """Close the scheduler and clear all schedules.

        This is idempotent - calling multiple times is safe.
        """
        self._schedules.clear()
        self._initialized = False

    async def register(
        self,
        feed_name: str,
        interval: timedelta,
        *,
        enabled: bool = True,
        metadata: dict[str, object] | None = None,
    ) -> ScheduleInfo:
        """Register a feed for scheduled collection.

        Args:
            feed_name: Unique name for the feed.
            interval: Time between collections.
            enabled: Whether to start enabled (default True).
            metadata: Optional schedule-specific data.

        Returns:
            The created ScheduleInfo.

        Raises:
            ValueError: If feed_name is already registered.
        """
        if feed_name in self._schedules:
            raise ValueError(f"Feed '{feed_name}' is already registered")

        info = ScheduleInfo(
            feed_name=feed_name,
            interval=interval,
            enabled=enabled,
            metadata=metadata or {},
        )
        self._schedules[feed_name] = info
        return info

    async def unregister(self, feed_name: str) -> bool:
        """Remove a feed from the schedule.

        Args:
            feed_name: The feed to unregister.

        Returns:
            True if the feed was found and removed, False if not found.
        """
        if feed_name in self._schedules:
            del self._schedules[feed_name]
            return True
        return False

    async def get(self, feed_name: str) -> ScheduleInfo | None:
        """Get schedule info for a feed.

        Args:
            feed_name: The feed to look up.

        Returns:
            The ScheduleInfo if found, None otherwise.
        """
        return self._schedules.get(feed_name)

    async def get_due(self) -> AsyncIterator[ScheduleInfo]:
        """Get all feeds that are due for collection.

        Yields:
            ScheduleInfo for each enabled feed whose next_run is in the past.
        """
        for info in self._schedules.values():
            if info.is_due:
                yield info

    async def get_all(self) -> AsyncIterator[ScheduleInfo]:
        """Get all registered schedules.

        Yields:
            ScheduleInfo for each registered feed.
        """
        for info in self._schedules.values():
            yield info

    async def mark_success(self, feed_name: str) -> None:
        """Mark a feed collection as successful.

        Updates last_run, calculates next_run, increments run_count,
        and resets consecutive_failures to 0.

        Args:
            feed_name: The feed that was collected.

        Raises:
            KeyError: If feed_name is not registered.
        """
        if feed_name not in self._schedules:
            raise KeyError(f"Feed '{feed_name}' is not registered")

        info = self._schedules[feed_name]
        now = datetime.now()

        # Create updated ScheduleInfo (dataclass is immutable by default)
        self._schedules[feed_name] = ScheduleInfo(
            feed_name=info.feed_name,
            interval=info.interval,
            last_run=now,
            next_run=now + info.interval,
            enabled=info.enabled,
            run_count=info.run_count + 1,
            consecutive_failures=0,
            metadata=info.metadata,
        )

    async def mark_failure(self, feed_name: str) -> None:
        """Mark a feed collection as failed.

        Increments consecutive_failures but does NOT update next_run.

        Args:
            feed_name: The feed that failed.

        Raises:
            KeyError: If feed_name is not registered.
        """
        if feed_name not in self._schedules:
            raise KeyError(f"Feed '{feed_name}' is not registered")

        info = self._schedules[feed_name]

        self._schedules[feed_name] = ScheduleInfo(
            feed_name=info.feed_name,
            interval=info.interval,
            last_run=info.last_run,
            next_run=info.next_run,
            enabled=info.enabled,
            run_count=info.run_count,
            consecutive_failures=info.consecutive_failures + 1,
            metadata=info.metadata,
        )

    async def enable(self, feed_name: str) -> None:
        """Enable a schedule.

        Args:
            feed_name: The feed to enable.

        Raises:
            KeyError: If feed_name is not registered.
        """
        if feed_name not in self._schedules:
            raise KeyError(f"Feed '{feed_name}' is not registered")

        info = self._schedules[feed_name]

        self._schedules[feed_name] = ScheduleInfo(
            feed_name=info.feed_name,
            interval=info.interval,
            last_run=info.last_run,
            next_run=info.next_run,
            enabled=True,
            run_count=info.run_count,
            consecutive_failures=info.consecutive_failures,
            metadata=info.metadata,
        )

    async def disable(self, feed_name: str) -> None:
        """Disable a schedule.

        Args:
            feed_name: The feed to disable.

        Raises:
            KeyError: If feed_name is not registered.
        """
        if feed_name not in self._schedules:
            raise KeyError(f"Feed '{feed_name}' is not registered")

        info = self._schedules[feed_name]

        self._schedules[feed_name] = ScheduleInfo(
            feed_name=info.feed_name,
            interval=info.interval,
            last_run=info.last_run,
            next_run=info.next_run,
            enabled=False,
            run_count=info.run_count,
            consecutive_failures=info.consecutive_failures,
            metadata=info.metadata,
        )

    async def update_interval(
        self,
        feed_name: str,
        interval: timedelta,
    ) -> ScheduleInfo:
        """Update the collection interval for a feed.

        Args:
            feed_name: The feed to update.
            interval: The new collection interval.

        Returns:
            The updated ScheduleInfo.

        Raises:
            KeyError: If feed_name is not registered.
        """
        if feed_name not in self._schedules:
            raise KeyError(f"Feed '{feed_name}' is not registered")

        info = self._schedules[feed_name]

        # Recalculate next_run if we have a last_run
        next_run = info.next_run
        if info.last_run is not None:
            next_run = info.last_run + interval

        updated = ScheduleInfo(
            feed_name=info.feed_name,
            interval=interval,
            last_run=info.last_run,
            next_run=next_run,
            enabled=info.enabled,
            run_count=info.run_count,
            consecutive_failures=info.consecutive_failures,
            metadata=info.metadata,
        )
        self._schedules[feed_name] = updated
        return updated
