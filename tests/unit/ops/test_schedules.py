"""Tests for feedspine.ops.schedules — CRUD over spine-core ScheduleStore.

Tests use a real SqliteScheduleStore against an in-memory DB so the
SQL in ops/schedules.py is exercised end-to-end.
"""

from __future__ import annotations

import sqlite3

import pytest

pytest.importorskip("spine", reason="spine-core not installed")

from feedspine.ops import schedules as sched_ops

# ── Schema / fixtures ────────────────────────────────────


_SCHEMA = """
CREATE TABLE IF NOT EXISTS core_schedules (
    id TEXT PRIMARY KEY,
    name TEXT,
    target_type TEXT NOT NULL DEFAULT 'workflow',
    target_name TEXT NOT NULL DEFAULT '',
    params TEXT,
    schedule_type TEXT NOT NULL DEFAULT 'cron',
    cron_expression TEXT,
    interval_seconds INTEGER,
    run_at TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER DEFAULT 100,
    max_instances INTEGER NOT NULL DEFAULT 1,
    misfire_grace_seconds INTEGER DEFAULT 60,
    dispatch_type TEXT,
    dispatch_target TEXT,
    dispatch_config_json TEXT,
    next_run_at TEXT,
    last_run_at TEXT,
    last_run_status TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    created_by TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
"""


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


@pytest.fixture
def store(conn: sqlite3.Connection):
    from spine.data.stores.sqlite.schedule_store import SqliteScheduleStore

    return SqliteScheduleStore(conn)


# ── create_schedule ──────────────────────────────────────


class TestCreateSchedule:
    def test_creates_and_returns(self, store) -> None:
        row = sched_ops.create_schedule(
            store,
            feed_name="sec-filings",
            cron_expression="0 * * * *",
            enabled=True,
        )
        assert row["id"]
        assert row["target_name"] == "feed.collect"
        assert row["cron_expression"] == "0 * * * *"
        assert row["enabled"] in (1, True)

    def test_defaults(self, store) -> None:
        row = sched_ops.create_schedule(store, feed_name="hn")
        assert row["cron_expression"] == "*/15 * * * *"

    def test_disabled(self, store) -> None:
        row = sched_ops.create_schedule(store, feed_name="x", enabled=False)
        assert row["enabled"] in (0, False)


# ── get_schedule ─────────────────────────────────────────


class TestGetSchedule:
    def test_found(self, store) -> None:
        created = sched_ops.create_schedule(store, feed_name="f")
        result = sched_ops.get_schedule(store, created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_not_found(self, store) -> None:
        assert sched_ops.get_schedule(store, "no-such-id") is None


# ── list_schedules ───────────────────────────────────────


class TestListSchedules:
    def test_empty(self, store) -> None:
        assert sched_ops.list_schedules(store) == []

    def test_returns_all(self, store) -> None:
        sched_ops.create_schedule(store, feed_name="a")
        sched_ops.create_schedule(store, feed_name="b")
        assert len(sched_ops.list_schedules(store)) == 2

    def test_filter_enabled(self, store) -> None:
        sched_ops.create_schedule(store, feed_name="on", enabled=True)
        sched_ops.create_schedule(store, feed_name="off", enabled=False)

        on = sched_ops.list_schedules(store, enabled=True)
        off = sched_ops.list_schedules(store, enabled=False)
        assert len(on) == 1
        assert len(off) == 1


# ── update_schedule ──────────────────────────────────────


class TestUpdateSchedule:
    def test_update_cron(self, store) -> None:
        created = sched_ops.create_schedule(store, feed_name="f")
        updated = sched_ops.update_schedule(store, created["id"], cron_expression="0 0 * * *")
        assert updated is not None
        assert updated["cron_expression"] == "0 0 * * *"

    def test_update_enabled(self, store) -> None:
        created = sched_ops.create_schedule(store, feed_name="f", enabled=True)
        updated = sched_ops.update_schedule(store, created["id"], enabled=False)
        assert updated is not None
        assert updated["enabled"] in (0, False)

    def test_update_not_found(self, store) -> None:
        assert sched_ops.update_schedule(store, "bad-id", enabled=True) is None

    def test_noop_update(self, store) -> None:
        created = sched_ops.create_schedule(store, feed_name="f")
        result = sched_ops.update_schedule(store, created["id"])
        assert result is not None  # no crash on empty update


# ── delete_schedule ──────────────────────────────────────


class TestDeleteSchedule:
    def test_delete_existing(self, store) -> None:
        created = sched_ops.create_schedule(store, feed_name="f")
        assert sched_ops.delete_schedule(store, created["id"]) is True
        assert sched_ops.get_schedule(store, created["id"]) is None

    def test_delete_not_found(self, store) -> None:
        assert sched_ops.delete_schedule(store, "no-such-id") is False


# ── list_due_schedules ───────────────────────────────────


class TestListDueSchedules:
    def test_no_due(self, store) -> None:
        sched_ops.create_schedule(store, feed_name="f")
        # next_run_at is NULL → not returned by get_due
        assert sched_ops.list_due_schedules(store) == []

    def test_due_schedule_returned(self, store, conn) -> None:
        created = sched_ops.create_schedule(store, feed_name="f")
        # Set next_run_at in the past so it's due
        conn.execute(
            "UPDATE core_schedules SET next_run_at = '2020-01-01T00:00:00' WHERE id = ?",
            (created["id"],),
        )
        conn.commit()
        due = sched_ops.list_due_schedules(store)
        assert len(due) == 1
        assert due[0]["id"] == created["id"]

    def test_disabled_not_due(self, store, conn) -> None:
        created = sched_ops.create_schedule(store, feed_name="f", enabled=False)
        conn.execute(
            "UPDATE core_schedules SET next_run_at = '2020-01-01T00:00:00' WHERE id = ?",
            (created["id"],),
        )
        conn.commit()
        assert sched_ops.list_due_schedules(store) == []
