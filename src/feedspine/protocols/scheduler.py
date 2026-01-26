"""Scheduler protocol for automated feed collection.

This module defines the protocol for scheduling feeds at intervals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass
class ScheduleInfo:
    """Information about a scheduled feed.

    Attributes:
        feed_name: The registered name of the feed.
        interval: Time between collections.
        last_run: When the feed was last collected (None if never).
        next_run: When the feed should next be collected.
        enabled: Whether the schedule is active.
        run_count: Total number of times this feed has been collected.
        consecutive_failures: Number of failures since last success.
        metadata: Additional schedule-specific data.

    Example:
        >>> info = ScheduleInfo(
        ...     feed_name="sec_filings",
        ...     interval=timedelta(minutes=10),
        ...     last_run=datetime(2024, 1, 15, 10, 0),
        ...     next_run=datetime(2024, 1, 15, 10, 10),
        ... )
        >>> info.is_due
        True  # if current time is past next_run
    """

    feed_name: str
    interval: timedelta
    last_run: datetime | None = None
    next_run: datetime | None = None
    enabled: bool = True
    run_count: int = 0
    consecutive_failures: int = 0
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_due(self) -> bool:
        """Check if the feed is due for collection.

        Returns:
            True if next_run is in the past or None (never run).
        """
        if not self.enabled:
            return False
        if self.next_run is None:
            return True  # Never run, so due immediately
        return datetime.now() >= self.next_run


@runtime_checkable
class Scheduler(Protocol):
    """Protocol for feed scheduling.

    The Scheduler manages when feeds should be collected. It supports:
    - Registering feeds with collection intervals
    - Tracking run history (last run, next run, failures)
    - Querying which feeds are due for collection
    - Enabling/disabling individual schedules

    Example:
        >>> scheduler = MemoryScheduler()
        >>> await scheduler.initialize()
        >>> await scheduler.register("sec_rss", timedelta(minutes=5))
        >>> async for info in scheduler.get_due():
        ...     print(f"Collecting {info.feed_name}")
        ...     await scheduler.mark_success("sec_rss")
    """

    async def initialize(self) -> None:
        """Initialize the scheduler.

        Called once before use. Implementations may set up
        connections, load persisted schedules, etc.
        """
        ...

    async def close(self) -> None:
        """Close the scheduler and release resources.

        Called when done. Implementations may persist state,
        close connections, etc.
        """
        ...

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
            feed_name: Unique name for the feed (must match FeedSpine registration).
            interval: Time between collections.
            enabled: Whether to start enabled (default True).
            metadata: Optional schedule-specific data.

        Returns:
            The created ScheduleInfo.

        Raises:
            ValueError: If feed_name is already registered.
        """
        ...

    async def unregister(self, feed_name: str) -> bool:
        """Remove a feed from the schedule.

        Args:
            feed_name: The feed to unregister.

        Returns:
            True if the feed was found and removed, False if not found.
        """
        ...

    async def get(self, feed_name: str) -> ScheduleInfo | None:
        """Get schedule info for a feed.

        Args:
            feed_name: The feed to look up.

        Returns:
            The ScheduleInfo if found, None otherwise.
        """
        ...

    async def get_due(self) -> AsyncIterator[ScheduleInfo]:
        """Get all feeds that are due for collection.

        Yields:
            ScheduleInfo for each enabled feed whose next_run is in the past.
        """
        ...

    async def get_all(self) -> AsyncIterator[ScheduleInfo]:
        """Get all registered schedules.

        Yields:
            ScheduleInfo for each registered feed.
        """
        ...

    async def mark_success(self, feed_name: str) -> None:
        """Mark a feed collection as successful.

        Updates last_run, calculates next_run, increments run_count,
        and resets consecutive_failures to 0.

        Args:
            feed_name: The feed that was collected.

        Raises:
            KeyError: If feed_name is not registered.
        """
        ...

    async def mark_failure(self, feed_name: str) -> None:
        """Mark a feed collection as failed.

        Increments consecutive_failures but does NOT update next_run.
        This allows immediate retry on the next check.

        Args:
            feed_name: The feed that failed.

        Raises:
            KeyError: If feed_name is not registered.
        """
        ...

    async def enable(self, feed_name: str) -> None:
        """Enable a schedule.

        Args:
            feed_name: The feed to enable.

        Raises:
            KeyError: If feed_name is not registered.
        """
        ...

    async def disable(self, feed_name: str) -> None:
        """Disable a schedule.

        Disabled feeds will not appear in get_due().

        Args:
            feed_name: The feed to disable.

        Raises:
            KeyError: If feed_name is not registered.
        """
        ...

    async def update_interval(
        self,
        feed_name: str,
        interval: timedelta,
    ) -> ScheduleInfo:
        """Update the collection interval for a feed.

        The next_run is recalculated based on last_run + new interval.

        Args:
            feed_name: The feed to update.
            interval: The new collection interval.

        Returns:
            The updated ScheduleInfo.

        Raises:
            KeyError: If feed_name is not registered.
        """
        ...
