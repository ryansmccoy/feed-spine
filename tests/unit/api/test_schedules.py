"""Tests for schedule API routes — CRUD + /due endpoint.

Uses a real SqliteScheduleStore against in-memory SQLite so the full
transport → ops → store path is exercised.
"""

from __future__ import annotations

import sqlite3

import pytest

pytest.importorskip("spine", reason="spine-core not installed")
fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")

from fastapi.testclient import TestClient  # noqa: E402

# ── Schema ───────────────────────────────────────────────

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


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def schedule_store():
    from spine.data.stores.sqlite.schedule_store import SqliteScheduleStore

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return SqliteScheduleStore(conn)


@pytest.fixture
def test_client(schedule_store) -> TestClient:
    from feedspine.api.fastapi import create_app
    from feedspine.storage.memory import MemoryStorage

    storage = MemoryStorage()
    app = create_app(storage=storage, search=None)
    app.state.schedule_store = schedule_store
    return TestClient(app)


# ── GET /api/v1/schedules ────────────────────────────────


class TestListSchedules:
    def test_empty_list(self, test_client: TestClient) -> None:
        r = test_client.get("/api/v1/schedules")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_created(self, test_client: TestClient) -> None:
        test_client.post(
            "/api/v1/schedules",
            json={"feed_id": "alpha", "cron_expression": "0 * * * *"},
        )
        r = test_client.get("/api/v1/schedules")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["feed_id"] == "feed.collect"  # target_name

    def test_filter_enabled(self, test_client: TestClient) -> None:
        test_client.post("/api/v1/schedules", json={"feed_id": "a", "enabled": True})
        test_client.post("/api/v1/schedules", json={"feed_id": "b", "enabled": False})

        on = test_client.get("/api/v1/schedules?enabled=true").json()
        off = test_client.get("/api/v1/schedules?enabled=false").json()
        assert len(on) == 1
        assert len(off) == 1


# ── POST /api/v1/schedules ───────────────────────────────


class TestCreateSchedule:
    def test_create_returns_201(self, test_client: TestClient) -> None:
        r = test_client.post(
            "/api/v1/schedules",
            json={"feed_id": "sec-filings", "cron_expression": "0 * * * *"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["id"]
        assert data["cron_expression"] == "0 * * * *"

    def test_create_defaults(self, test_client: TestClient) -> None:
        r = test_client.post("/api/v1/schedules", json={"feed_id": "x"})
        assert r.status_code == 201
        assert r.json()["cron_expression"] == "*/15 * * * *"
        assert r.json()["enabled"] is True


# ── GET /api/v1/schedules/{id} ───────────────────────────


class TestGetSchedule:
    def test_found(self, test_client: TestClient) -> None:
        created = test_client.post("/api/v1/schedules", json={"feed_id": "f"}).json()
        r = test_client.get(f"/api/v1/schedules/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_not_found(self, test_client: TestClient) -> None:
        r = test_client.get("/api/v1/schedules/no-such-id")
        assert r.status_code == 404


# ── PATCH /api/v1/schedules/{id} ─────────────────────────


class TestUpdateSchedule:
    def test_update_cron(self, test_client: TestClient) -> None:
        created = test_client.post("/api/v1/schedules", json={"feed_id": "f"}).json()
        r = test_client.patch(
            f"/api/v1/schedules/{created['id']}",
            json={"cron_expression": "0 0 * * *"},
        )
        assert r.status_code == 200
        assert r.json()["cron_expression"] == "0 0 * * *"

    def test_update_enabled(self, test_client: TestClient) -> None:
        created = test_client.post("/api/v1/schedules", json={"feed_id": "f"}).json()
        r = test_client.patch(
            f"/api/v1/schedules/{created['id']}",
            json={"enabled": False},
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_update_not_found(self, test_client: TestClient) -> None:
        r = test_client.patch(
            "/api/v1/schedules/bad-id",
            json={"enabled": True},
        )
        assert r.status_code == 404


# ── DELETE /api/v1/schedules/{id} ────────────────────────


class TestDeleteSchedule:
    def test_delete_existing(self, test_client: TestClient) -> None:
        created = test_client.post("/api/v1/schedules", json={"feed_id": "f"}).json()
        r = test_client.delete(f"/api/v1/schedules/{created['id']}")
        assert r.status_code == 204
        # Confirm it's gone
        assert test_client.get(f"/api/v1/schedules/{created['id']}").status_code == 404

    def test_delete_not_found(self, test_client: TestClient) -> None:
        r = test_client.delete("/api/v1/schedules/no-such")
        assert r.status_code == 404


# ── GET /api/v1/schedules/due ────────────────────────────


class TestDueSchedules:
    def test_none_due(self, test_client: TestClient) -> None:
        test_client.post("/api/v1/schedules", json={"feed_id": "f"})
        r = test_client.get("/api/v1/schedules/due")
        assert r.status_code == 200
        assert r.json() == []

    def test_due_returned(self, test_client: TestClient, schedule_store) -> None:
        created = test_client.post("/api/v1/schedules", json={"feed_id": "f"}).json()
        # Set next_run_at in the past
        schedule_store._conn.execute(
            "UPDATE core_schedules SET next_run_at = '2020-01-01T00:00:00' WHERE id = ?",
            (created["id"],),
        )
        schedule_store._conn.commit()
        r = test_client.get("/api/v1/schedules/due")
        assert r.status_code == 200
        assert len(r.json()) == 1


# ── 503 when store missing ───────────────────────────────


class TestMissingStore:
    def test_503_when_no_store(self) -> None:
        from feedspine.api.fastapi import create_app
        from feedspine.storage.memory import MemoryStorage

        app = create_app(storage=MemoryStorage(), search=None)
        # deliberately do NOT set app.state.schedule_store
        client = TestClient(app)
        r = client.get("/api/v1/schedules")
        assert r.status_code == 503
