"""Tests for feedspine.storage.repository module.

Tests BaseRepository and SAConnectionBridge with in-memory SQLite.
"""

from __future__ import annotations

import sqlite3

import pytest

from feedspine.storage.repository import BaseRepository, Connection

# ---------------------------------------------------------------------------
# Connection protocol
# ---------------------------------------------------------------------------


class TestConnectionProtocol:
    """Tests for the Connection runtime-checkable protocol."""

    def test_sqlite3_connection_is_connection(self):
        """stdlib sqlite3.Connection satisfies the Connection protocol."""
        conn = sqlite3.connect(":memory:")
        try:
            assert isinstance(conn, Connection)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# BaseRepository with sqlite3
# ---------------------------------------------------------------------------


class TestBaseRepository:
    """Tests for BaseRepository using in-memory SQLite."""

    @pytest.fixture
    def repo(self) -> BaseRepository:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, name TEXT, value INTEGER)")
        conn.commit()
        return BaseRepository(conn)

    def test_execute(self, repo: BaseRepository):
        repo.execute("INSERT INTO items (id, name, value) VALUES (?, ?, ?)", ("1", "a", 10))
        repo.commit()

    def test_query(self, repo: BaseRepository):
        repo.execute("INSERT INTO items (id, name, value) VALUES (?, ?, ?)", ("1", "a", 10))
        repo.commit()
        rows = repo.query("SELECT * FROM items")
        assert len(rows) == 1
        assert rows[0]["id"] == "1"

    def test_query_one(self, repo: BaseRepository):
        repo.execute("INSERT INTO items (id, name, value) VALUES (?, ?, ?)", ("1", "a", 10))
        repo.commit()
        row = repo.query_one("SELECT * FROM items WHERE id = ?", ("1",))
        assert row is not None
        assert row["name"] == "a"

    def test_query_one_missing(self, repo: BaseRepository):
        row = repo.query_one("SELECT * FROM items WHERE id = ?", ("missing",))
        assert row is None

    def test_insert(self, repo: BaseRepository):
        repo.insert("items", {"id": "2", "name": "b", "value": 20})
        repo.commit()
        rows = repo.query("SELECT * FROM items WHERE id = ?", ("2",))
        assert len(rows) == 1

    def test_insert_many(self, repo: BaseRepository):
        count = repo.insert_many(
            "items",
            [
                {"id": "3", "name": "c", "value": 30},
                {"id": "4", "name": "d", "value": 40},
            ],
        )
        repo.commit()
        assert count == 2

    def test_ph_placeholder(self, repo: BaseRepository):
        """ph() returns placeholder string for the dialect."""
        result = repo.ph(3)
        assert isinstance(result, str)
        # Should contain 3 placeholders
        assert result.count("?") == 3 or result.count("$") == 3
