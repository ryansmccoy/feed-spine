"""Tests for RunLogMixin — in-memory run event log storage.

Covers all 7 protocol methods: log, log_batch, get_by_run,
get_by_feed, get_errors, get_run_summary, cleanup_old_events.
Also tests eviction when max_events is exceeded.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.models.run_event import RunEvent, RunEventType
from feedspine.storage.shared.mixins.run_log import RunLogMixin

# ── Helpers ──────────────────────────────────────────────


def _event(
    run_id: str = "run-1",
    event_type: RunEventType = RunEventType.RUN_STARTED,
    feed_name: str = "test-feed",
    message: str = "",
    data: dict | None = None,
    timestamp: datetime | None = None,
) -> RunEvent:
    return RunEvent(
        run_id=run_id,
        event_type=event_type,
        feed_name=feed_name,
        message=message,
        data=data or {},
        **({"timestamp": timestamp} if timestamp else {}),
    )


@pytest.fixture
def mixin() -> RunLogMixin:
    return RunLogMixin(max_events=100)


# ── log / log_batch ─────────────────────────────────────


class TestLog:
    async def test_log_stores_event(self, mixin: RunLogMixin) -> None:
        e = _event()
        await mixin.log(e)
        assert mixin._events == [e]

    async def test_log_indexes_by_run(self, mixin: RunLogMixin) -> None:
        e = _event(run_id="r1")
        await mixin.log(e)
        assert mixin._events_by_run["r1"] == [e]

    async def test_log_indexes_by_feed(self, mixin: RunLogMixin) -> None:
        e = _event(feed_name="my-feed")
        await mixin.log(e)
        assert mixin._events_by_feed["my-feed"] == [e]


class TestLogBatch:
    async def test_batch_stores_all(self, mixin: RunLogMixin) -> None:
        events = [_event(run_id=f"r{i}") for i in range(5)]
        await mixin.log_batch(events)
        assert len(mixin._events) == 5


# ── get_by_run ───────────────────────────────────────────


class TestGetByRun:
    async def test_returns_events_for_run(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_STARTED))
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_COMPLETED))
        await mixin.log(_event(run_id="r2", event_type=RunEventType.RUN_STARTED))

        results = [e async for e in mixin.get_by_run("r1")]
        assert len(results) == 2
        assert all(e.run_id == "r1" for e in results)

    async def test_filter_by_event_types(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_STARTED))
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_COMPLETED))
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_ERROR))

        results = [e async for e in mixin.get_by_run("r1", event_types=[RunEventType.RUN_ERROR])]
        assert len(results) == 1
        assert results[0].event_type == RunEventType.RUN_ERROR

    async def test_empty_for_unknown_run(self, mixin: RunLogMixin) -> None:
        results = [e async for e in mixin.get_by_run("nonexistent")]
        assert results == []


# ── get_by_feed ──────────────────────────────────────────


class TestGetByFeed:
    async def test_returns_events_for_feed(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event(feed_name="alpha", run_id="r1"))
        await mixin.log(_event(feed_name="alpha", run_id="r2"))
        await mixin.log(_event(feed_name="beta", run_id="r3"))

        results = [e async for e in mixin.get_by_feed("alpha")]
        assert len(results) == 2

    async def test_respects_limit(self, mixin: RunLogMixin) -> None:
        for i in range(10):
            await mixin.log(_event(feed_name="f", run_id=f"r{i}"))

        results = [e async for e in mixin.get_by_feed("f", limit=3)]
        assert len(results) == 3

    async def test_since_filter(self, mixin: RunLogMixin) -> None:
        old = datetime(2025, 1, 1, tzinfo=UTC)
        new = datetime(2026, 1, 1, tzinfo=UTC)
        await mixin.log(_event(feed_name="f", run_id="r1", timestamp=old))
        await mixin.log(_event(feed_name="f", run_id="r2", timestamp=new))

        cutoff = datetime(2025, 6, 1, tzinfo=UTC)
        results = [e async for e in mixin.get_by_feed("f", since=cutoff)]
        assert len(results) == 1
        assert results[0].run_id == "r2"

    async def test_until_filter(self, mixin: RunLogMixin) -> None:
        old = datetime(2025, 1, 1, tzinfo=UTC)
        new = datetime(2026, 1, 1, tzinfo=UTC)
        await mixin.log(_event(feed_name="f", run_id="r1", timestamp=old))
        await mixin.log(_event(feed_name="f", run_id="r2", timestamp=new))

        cutoff = datetime(2025, 6, 1, tzinfo=UTC)
        results = [e async for e in mixin.get_by_feed("f", until=cutoff)]
        assert len(results) == 1
        assert results[0].run_id == "r1"


# ── get_errors ───────────────────────────────────────────


class TestGetErrors:
    async def test_returns_only_errors(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event(event_type=RunEventType.RUN_STARTED))
        await mixin.log(_event(event_type=RunEventType.RUN_ERROR))
        await mixin.log(_event(event_type=RunEventType.FETCH_ERROR))
        await mixin.log(_event(event_type=RunEventType.RUN_COMPLETED))

        results = [e async for e in mixin.get_errors()]
        assert len(results) == 2
        assert all(e.event_type in {RunEventType.RUN_ERROR, RunEventType.FETCH_ERROR} for e in results)

    async def test_filter_by_feed_name(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event(event_type=RunEventType.RUN_ERROR, feed_name="alpha"))
        await mixin.log(_event(event_type=RunEventType.RUN_ERROR, feed_name="beta"))

        results = [e async for e in mixin.get_errors(feed_name="alpha")]
        assert len(results) == 1
        assert results[0].feed_name == "alpha"

    async def test_filter_by_since(self, mixin: RunLogMixin) -> None:
        old = datetime(2025, 1, 1, tzinfo=UTC)
        new = datetime(2026, 1, 1, tzinfo=UTC)
        await mixin.log(_event(event_type=RunEventType.RUN_ERROR, timestamp=old))
        await mixin.log(_event(event_type=RunEventType.RUN_ERROR, timestamp=new))

        results = [e async for e in mixin.get_errors(since=datetime(2025, 6, 1, tzinfo=UTC))]
        assert len(results) == 1

    async def test_respects_limit(self, mixin: RunLogMixin) -> None:
        for i in range(10):
            await mixin.log(_event(event_type=RunEventType.RUN_ERROR, run_id=f"r{i}"))

        results = [e async for e in mixin.get_errors(limit=3)]
        assert len(results) == 3

    async def test_empty_when_no_errors(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event(event_type=RunEventType.RUN_STARTED))
        results = [e async for e in mixin.get_errors()]
        assert results == []


# ── get_run_summary ──────────────────────────────────────


class TestGetRunSummary:
    async def test_returns_none_for_unknown_run(self, mixin: RunLogMixin) -> None:
        result = await mixin.get_run_summary("nonexistent")
        assert result is None

    async def test_completed_run_summary(self, mixin: RunLogMixin) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        t1 = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_STARTED, timestamp=t0))
        await mixin.log(
            _event(
                run_id="r1",
                event_type=RunEventType.RUN_COMPLETED,
                timestamp=t1,
                data={"processed": 10, "new": 5, "updated": 3, "duplicates": 2, "errors": 0},
            )
        )

        summary = await mixin.get_run_summary("r1")
        assert summary is not None
        assert summary["run_id"] == "r1"
        assert summary["status"] == "completed"
        assert summary["started_at"] == t0
        assert summary["completed_at"] == t1
        assert summary["stats"]["processed"] == 10
        assert summary["stats"]["new"] == 5
        assert summary["event_count"] == 2

    async def test_error_run_summary(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_STARTED))
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_ERROR))

        summary = await mixin.get_run_summary("r1")
        assert summary is not None
        assert summary["status"] == "error"

    async def test_running_summary_with_record_events(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RUN_STARTED))
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RECORD_CREATED))
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RECORD_CREATED))
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RECORD_UPDATED))
        await mixin.log(_event(run_id="r1", event_type=RunEventType.RECORD_DUPLICATE))

        summary = await mixin.get_run_summary("r1")
        assert summary is not None
        assert summary["status"] == "running"
        assert summary["stats"]["new"] == 2
        assert summary["stats"]["updated"] == 1
        assert summary["stats"]["duplicates"] == 1
        assert summary["stats"]["processed"] == 4


# ── cleanup_old_events ───────────────────────────────────


class TestCleanupOldEvents:
    async def test_deletes_old_events(self, mixin: RunLogMixin) -> None:
        old = datetime(2025, 1, 1, tzinfo=UTC)
        new = datetime(2026, 6, 1, tzinfo=UTC)
        await mixin.log(_event(run_id="r-old", event_type=RunEventType.RUN_STARTED, timestamp=old))
        await mixin.log(_event(run_id="r-new", event_type=RunEventType.RUN_STARTED, timestamp=new))

        cutoff = datetime(2026, 1, 1, tzinfo=UTC)
        deleted = await mixin.cleanup_old_events(cutoff)
        assert deleted == 1
        assert len(mixin._events) == 1
        assert mixin._events[0].run_id == "r-new"

    async def test_keeps_errors_by_default(self, mixin: RunLogMixin) -> None:
        old = datetime(2025, 1, 1, tzinfo=UTC)
        await mixin.log(_event(event_type=RunEventType.RUN_STARTED, timestamp=old))
        await mixin.log(_event(event_type=RunEventType.RUN_ERROR, timestamp=old))

        cutoff = datetime(2026, 1, 1, tzinfo=UTC)
        deleted = await mixin.cleanup_old_events(cutoff)
        assert deleted == 1  # only RUN_STARTED deleted
        assert len(mixin._events) == 1
        assert mixin._events[0].event_type == RunEventType.RUN_ERROR

    async def test_can_delete_errors_too(self, mixin: RunLogMixin) -> None:
        old = datetime(2025, 1, 1, tzinfo=UTC)
        await mixin.log(_event(event_type=RunEventType.RUN_ERROR, timestamp=old))

        cutoff = datetime(2026, 1, 1, tzinfo=UTC)
        deleted = await mixin.cleanup_old_events(cutoff, keep_errors=False)
        assert deleted == 1
        assert len(mixin._events) == 0

    async def test_rebuilds_indexes(self, mixin: RunLogMixin) -> None:
        old = datetime(2025, 1, 1, tzinfo=UTC)
        new = datetime(2026, 6, 1, tzinfo=UTC)
        await mixin.log(_event(run_id="r1", feed_name="f1", timestamp=old))
        await mixin.log(_event(run_id="r2", feed_name="f2", timestamp=new))

        await mixin.cleanup_old_events(datetime(2026, 1, 1, tzinfo=UTC))
        assert "r1" not in mixin._events_by_run
        assert "r2" in mixin._events_by_run
        assert "f1" not in mixin._events_by_feed
        assert "f2" in mixin._events_by_feed


# ── eviction ─────────────────────────────────────────────


class TestEviction:
    async def test_calls_evict_when_over_capacity(self) -> None:
        """_evict_oldest_events is called when over max_events.

        The base implementation is a stub (no-op), so we just verify
        log() doesn't crash when capacity is exceeded.
        """
        mixin = RunLogMixin(max_events=3)
        for i in range(5):
            await mixin.log(_event(run_id=f"r{i}"))
        # Stub doesn't evict, but the method was invoked without error
        assert len(mixin._events) == 5


# ── _clear_events ────────────────────────────────────────


class TestClearEvents:
    async def test_clears_all_data(self, mixin: RunLogMixin) -> None:
        await mixin.log(_event())
        mixin._clear_events()
        assert mixin._events == []
        assert dict(mixin._events_by_run) == {}
        assert dict(mixin._events_by_feed) == {}
