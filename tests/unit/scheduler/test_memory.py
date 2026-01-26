"""TDD tests for MemoryScheduler.

Following TDD workflow:
1. Write failing tests first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor (REFACTOR)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    pass

# Will fail until we implement MemoryScheduler
pytestmark = pytest.mark.asyncio


class TestSchedulerCreation:
    """Tests for MemoryScheduler instantiation."""

    async def test_create_scheduler(self) -> None:
        """MemoryScheduler can be instantiated."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        assert scheduler is not None

    async def test_initialize_is_idempotent(self) -> None:
        """Calling initialize() multiple times is safe."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.initialize()  # Should not raise

    async def test_close_is_idempotent(self) -> None:
        """Calling close() multiple times is safe."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.close()
        await scheduler.close()  # Should not raise


class TestSchedulerRegistration:
    """Tests for registering feeds with the scheduler."""

    async def test_register_feed(self) -> None:
        """Can register a feed with an interval."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        info = await scheduler.register("sec_rss", timedelta(minutes=5))

        assert info.feed_name == "sec_rss"
        assert info.interval == timedelta(minutes=5)
        assert info.enabled is True
        assert info.run_count == 0
        assert info.consecutive_failures == 0

    async def test_register_with_metadata(self) -> None:
        """Can register a feed with custom metadata."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        info = await scheduler.register(
            "sec_rss",
            timedelta(minutes=5),
            metadata={"priority": "high", "source": "sec.gov"},
        )

        assert info.metadata["priority"] == "high"
        assert info.metadata["source"] == "sec.gov"

    async def test_register_disabled(self) -> None:
        """Can register a feed in disabled state."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        info = await scheduler.register(
            "sec_rss",
            timedelta(minutes=5),
            enabled=False,
        )

        assert info.enabled is False

    async def test_register_duplicate_raises(self) -> None:
        """Registering same feed twice raises ValueError."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        await scheduler.register("sec_rss", timedelta(minutes=5))

        with pytest.raises(ValueError, match="already registered"):
            await scheduler.register("sec_rss", timedelta(minutes=10))

    async def test_unregister_existing(self) -> None:
        """Can unregister an existing feed."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        await scheduler.register("sec_rss", timedelta(minutes=5))
        result = await scheduler.unregister("sec_rss")

        assert result is True
        assert await scheduler.get("sec_rss") is None

    async def test_unregister_nonexistent(self) -> None:
        """Unregistering non-existent feed returns False."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        result = await scheduler.unregister("nonexistent")

        assert result is False


class TestSchedulerGet:
    """Tests for retrieving schedule information."""

    async def test_get_existing(self) -> None:
        """Can get info for a registered feed."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        info = await scheduler.get("sec_rss")

        assert info is not None
        assert info.feed_name == "sec_rss"

    async def test_get_nonexistent(self) -> None:
        """Getting non-existent feed returns None."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        info = await scheduler.get("nonexistent")

        assert info is None

    async def test_get_all_empty(self) -> None:
        """get_all on empty scheduler yields nothing."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        schedules = [s async for s in scheduler.get_all()]

        assert schedules == []

    async def test_get_all_multiple(self) -> None:
        """get_all yields all registered schedules."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("feed_a", timedelta(minutes=5))
        await scheduler.register("feed_b", timedelta(minutes=10))
        await scheduler.register("feed_c", timedelta(hours=1))

        schedules = [s async for s in scheduler.get_all()]

        assert len(schedules) == 3
        names = {s.feed_name for s in schedules}
        assert names == {"feed_a", "feed_b", "feed_c"}


class TestSchedulerDue:
    """Tests for checking which feeds are due."""

    async def test_newly_registered_is_due(self) -> None:
        """A newly registered feed with no last_run is immediately due."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        due = [s async for s in scheduler.get_due()]

        assert len(due) == 1
        assert due[0].feed_name == "sec_rss"

    async def test_disabled_not_due(self) -> None:
        """Disabled feeds are not returned in get_due()."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5), enabled=False)

        due = [s async for s in scheduler.get_due()]

        assert due == []

    async def test_recently_run_not_due(self) -> None:
        """A feed that just ran is not due until next_run passes."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        # Mark as just run
        await scheduler.mark_success("sec_rss")

        due = [s async for s in scheduler.get_due()]

        assert due == []

    async def test_past_next_run_is_due(self) -> None:
        """A feed whose next_run is in the past is due."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        # Simulate: last ran 10 minutes ago
        past_time = datetime.now() - timedelta(minutes=10)
        with patch("feedspine.scheduler.memory.datetime") as mock_dt:
            # First call for mark_success uses past time
            mock_dt.now.return_value = past_time
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            await scheduler.mark_success("sec_rss")

        # Now check if due (current time)
        due = [s async for s in scheduler.get_due()]

        assert len(due) == 1
        assert due[0].feed_name == "sec_rss"


class TestSchedulerMarkSuccess:
    """Tests for marking feed collections as successful."""

    async def test_mark_success_updates_last_run(self) -> None:
        """mark_success sets last_run to now."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        before = datetime.now()
        await scheduler.mark_success("sec_rss")
        after = datetime.now()

        info = await scheduler.get("sec_rss")
        assert info is not None
        assert info.last_run is not None
        assert before <= info.last_run <= after

    async def test_mark_success_sets_next_run(self) -> None:
        """mark_success sets next_run to last_run + interval."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        await scheduler.mark_success("sec_rss")

        info = await scheduler.get("sec_rss")
        assert info is not None
        assert info.next_run is not None
        assert info.last_run is not None
        # next_run should be ~5 minutes after last_run
        expected_next = info.last_run + timedelta(minutes=5)
        assert info.next_run == expected_next

    async def test_mark_success_increments_run_count(self) -> None:
        """mark_success increments run_count."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        await scheduler.mark_success("sec_rss")
        await scheduler.mark_success("sec_rss")
        await scheduler.mark_success("sec_rss")

        info = await scheduler.get("sec_rss")
        assert info is not None
        assert info.run_count == 3

    async def test_mark_success_resets_failures(self) -> None:
        """mark_success resets consecutive_failures to 0."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        # Simulate some failures
        await scheduler.mark_failure("sec_rss")
        await scheduler.mark_failure("sec_rss")
        info = await scheduler.get("sec_rss")
        assert info is not None
        assert info.consecutive_failures == 2

        # Now succeed
        await scheduler.mark_success("sec_rss")

        info = await scheduler.get("sec_rss")
        assert info is not None
        assert info.consecutive_failures == 0

    async def test_mark_success_nonexistent_raises(self) -> None:
        """mark_success on non-existent feed raises KeyError."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        with pytest.raises(KeyError):
            await scheduler.mark_success("nonexistent")


class TestSchedulerMarkFailure:
    """Tests for marking feed collections as failed."""

    async def test_mark_failure_increments_failures(self) -> None:
        """mark_failure increments consecutive_failures."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        await scheduler.mark_failure("sec_rss")
        await scheduler.mark_failure("sec_rss")

        info = await scheduler.get("sec_rss")
        assert info is not None
        assert info.consecutive_failures == 2

    async def test_mark_failure_does_not_update_next_run(self) -> None:
        """mark_failure does NOT update next_run (allows immediate retry)."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        # Get initial state (next_run should be None for new feed)
        info_before = await scheduler.get("sec_rss")
        assert info_before is not None
        next_run_before = info_before.next_run

        await scheduler.mark_failure("sec_rss")

        info_after = await scheduler.get("sec_rss")
        assert info_after is not None
        assert info_after.next_run == next_run_before

    async def test_mark_failure_nonexistent_raises(self) -> None:
        """mark_failure on non-existent feed raises KeyError."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        with pytest.raises(KeyError):
            await scheduler.mark_failure("nonexistent")


class TestSchedulerEnableDisable:
    """Tests for enabling/disabling schedules."""

    async def test_disable_feed(self) -> None:
        """Can disable an enabled feed."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        await scheduler.disable("sec_rss")

        info = await scheduler.get("sec_rss")
        assert info is not None
        assert info.enabled is False

    async def test_enable_feed(self) -> None:
        """Can enable a disabled feed."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5), enabled=False)

        await scheduler.enable("sec_rss")

        info = await scheduler.get("sec_rss")
        assert info is not None
        assert info.enabled is True

    async def test_disable_nonexistent_raises(self) -> None:
        """disable on non-existent feed raises KeyError."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        with pytest.raises(KeyError):
            await scheduler.disable("nonexistent")

    async def test_enable_nonexistent_raises(self) -> None:
        """enable on non-existent feed raises KeyError."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        with pytest.raises(KeyError):
            await scheduler.enable("nonexistent")


class TestSchedulerUpdateInterval:
    """Tests for updating feed intervals."""

    async def test_update_interval(self) -> None:
        """Can update the interval for a feed."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))

        info = await scheduler.update_interval("sec_rss", timedelta(minutes=10))

        assert info.interval == timedelta(minutes=10)

    async def test_update_interval_recalculates_next_run(self) -> None:
        """Updating interval recalculates next_run based on last_run."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()
        await scheduler.register("sec_rss", timedelta(minutes=5))
        await scheduler.mark_success("sec_rss")

        # Get last_run
        info = await scheduler.get("sec_rss")
        assert info is not None
        last_run = info.last_run
        assert last_run is not None

        # Update interval
        info = await scheduler.update_interval("sec_rss", timedelta(minutes=20))

        # next_run should now be last_run + 20 minutes
        assert info.next_run == last_run + timedelta(minutes=20)

    async def test_update_interval_nonexistent_raises(self) -> None:
        """update_interval on non-existent feed raises KeyError."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        await scheduler.initialize()

        with pytest.raises(KeyError):
            await scheduler.update_interval("nonexistent", timedelta(minutes=10))


class TestScheduleInfoIsDue:
    """Tests for ScheduleInfo.is_due property."""

    def test_is_due_when_never_run(self) -> None:
        """ScheduleInfo with no next_run is due."""
        from feedspine.protocols.scheduler import ScheduleInfo

        info = ScheduleInfo(
            feed_name="test",
            interval=timedelta(minutes=5),
            enabled=True,
        )

        assert info.is_due is True

    def test_is_due_when_disabled(self) -> None:
        """Disabled ScheduleInfo is not due."""
        from feedspine.protocols.scheduler import ScheduleInfo

        info = ScheduleInfo(
            feed_name="test",
            interval=timedelta(minutes=5),
            enabled=False,
        )

        assert info.is_due is False

    def test_is_due_when_past(self) -> None:
        """ScheduleInfo with past next_run is due."""
        from feedspine.protocols.scheduler import ScheduleInfo

        info = ScheduleInfo(
            feed_name="test",
            interval=timedelta(minutes=5),
            next_run=datetime.now() - timedelta(minutes=1),
            enabled=True,
        )

        assert info.is_due is True

    def test_not_due_when_future(self) -> None:
        """ScheduleInfo with future next_run is not due."""
        from feedspine.protocols.scheduler import ScheduleInfo

        info = ScheduleInfo(
            feed_name="test",
            interval=timedelta(minutes=5),
            next_run=datetime.now() + timedelta(minutes=5),
            enabled=True,
        )

        assert info.is_due is False


class TestSchedulerProtocolCompliance:
    """Tests that MemoryScheduler implements the Scheduler protocol."""

    async def test_implements_protocol(self) -> None:
        """MemoryScheduler implements the Scheduler protocol."""
        from feedspine.protocols.scheduler import Scheduler
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()
        assert isinstance(scheduler, Scheduler)

    async def test_has_all_required_methods(self) -> None:
        """MemoryScheduler has all protocol-required methods."""
        from feedspine.scheduler import MemoryScheduler

        scheduler = MemoryScheduler()

        # All protocol methods should exist
        assert hasattr(scheduler, "initialize")
        assert hasattr(scheduler, "close")
        assert hasattr(scheduler, "register")
        assert hasattr(scheduler, "unregister")
        assert hasattr(scheduler, "get")
        assert hasattr(scheduler, "get_due")
        assert hasattr(scheduler, "get_all")
        assert hasattr(scheduler, "mark_success")
        assert hasattr(scheduler, "mark_failure")
        assert hasattr(scheduler, "enable")
        assert hasattr(scheduler, "disable")
        assert hasattr(scheduler, "update_interval")
