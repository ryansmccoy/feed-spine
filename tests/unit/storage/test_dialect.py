"""Tests for feedspine.storage.dialect module.

Tests SQL dialect abstraction: SQLiteDialect, PostgreSQLDialect,
get_dialect factory, and Dialect protocol conformance.
"""

from __future__ import annotations

import pytest

from feedspine.storage.dialect import (
    Dialect,
    PostgreSQLDialect,
    SQLiteDialect,
    get_dialect,
)

# ---------------------------------------------------------------------------
# SQLiteDialect
# ---------------------------------------------------------------------------


class TestSQLiteDialect:
    """Tests for SQLite dialect methods."""

    @pytest.fixture
    def d(self) -> SQLiteDialect:
        return SQLiteDialect()

    def test_name(self, d: SQLiteDialect):
        assert d.name == "sqlite"

    def test_placeholder_ignores_index(self, d: SQLiteDialect):
        assert d.placeholder(0) == "?"
        assert d.placeholder(5) == "?"

    def test_placeholders_count(self, d: SQLiteDialect):
        assert d.placeholders(1) == "?"
        assert d.placeholders(3) == "?, ?, ?"

    def test_now(self, d: SQLiteDialect):
        assert d.now() == "datetime('now')"

    def test_interval(self, d: SQLiteDialect):
        result = d.interval(7, "days")
        assert "datetime" in result
        assert "7 days" in result

    def test_insert_or_ignore(self, d: SQLiteDialect):
        sql = d.insert_or_ignore("records", ["a", "b"])
        assert "INSERT OR IGNORE" in sql
        assert "records" in sql
        assert "a, b" in sql
        assert "?, ?" in sql

    def test_upsert(self, d: SQLiteDialect):
        sql = d.upsert("records", ["nk", "content", "version"], ["nk"])
        assert "INSERT INTO records" in sql
        assert "ON CONFLICT (nk)" in sql
        assert "content = excluded.content" in sql
        assert "version = excluded.version" in sql
        # key column should NOT appear in update set
        assert "nk = excluded.nk" not in sql

    def test_json_set(self, d: SQLiteDialect):
        result = d.json_set("content", "$.title", "?")
        assert "json_set" in result
        assert "content" in result

    def test_auto_increment(self, d: SQLiteDialect):
        assert "AUTOINCREMENT" in d.auto_increment()

    def test_timestamp_default_now(self, d: SQLiteDialect):
        assert "datetime('now')" in d.timestamp_default_now()

    def test_boolean_true(self, d: SQLiteDialect):
        assert d.boolean_true() == "1"

    def test_boolean_false(self, d: SQLiteDialect):
        assert d.boolean_false() == "0"

    def test_table_exists_query(self, d: SQLiteDialect):
        sql = d.table_exists_query()
        assert "sqlite_master" in sql


# ---------------------------------------------------------------------------
# PostgreSQLDialect
# ---------------------------------------------------------------------------


class TestPostgreSQLDialect:
    """Tests for PostgreSQL dialect methods."""

    @pytest.fixture
    def d(self) -> PostgreSQLDialect:
        return PostgreSQLDialect()

    def test_name(self, d: PostgreSQLDialect):
        assert d.name == "postgresql"

    def test_placeholder_ignores_index(self, d: PostgreSQLDialect):
        assert d.placeholder(0) == "%s"
        assert d.placeholder(5) == "%s"

    def test_placeholders_count(self, d: PostgreSQLDialect):
        assert d.placeholders(1) == "%s"
        assert d.placeholders(3) == "%s, %s, %s"

    def test_now(self, d: PostgreSQLDialect):
        assert d.now() == "NOW()"

    def test_interval_positive(self, d: PostgreSQLDialect):
        result = d.interval(7, "days")
        assert "NOW() + INTERVAL" in result
        assert "7 days" in result

    def test_interval_negative(self, d: PostgreSQLDialect):
        result = d.interval(-3, "hours")
        assert "NOW() - INTERVAL" in result
        assert "3 hours" in result

    def test_insert_or_ignore(self, d: PostgreSQLDialect):
        sql = d.insert_or_ignore("records", ["a", "b"])
        assert "ON CONFLICT DO NOTHING" in sql
        assert "%s, %s" in sql

    def test_upsert(self, d: PostgreSQLDialect):
        sql = d.upsert("records", ["nk", "content", "version"], ["nk"])
        assert "ON CONFLICT (nk)" in sql
        assert "EXCLUDED.content" in sql
        assert "EXCLUDED.version" in sql

    def test_json_set(self, d: PostgreSQLDialect):
        result = d.json_set("content", "$.title", "%s")
        assert "jsonb_set" in result
        assert "content" in result

    def test_auto_increment(self, d: PostgreSQLDialect):
        assert "SERIAL" in d.auto_increment()

    def test_timestamp_default_now(self, d: PostgreSQLDialect):
        assert "NOW()" in d.timestamp_default_now()

    def test_boolean_true(self, d: PostgreSQLDialect):
        assert d.boolean_true() == "TRUE"

    def test_boolean_false(self, d: PostgreSQLDialect):
        assert d.boolean_false() == "FALSE"

    def test_table_exists_query(self, d: PostgreSQLDialect):
        sql = d.table_exists_query()
        assert "information_schema" in sql


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestDialectProtocol:
    """Tests that concrete dialects satisfy the Dialect protocol."""

    def test_sqlite_is_dialect(self):
        assert isinstance(SQLiteDialect(), Dialect)

    def test_postgresql_is_dialect(self):
        assert isinstance(PostgreSQLDialect(), Dialect)


# ---------------------------------------------------------------------------
# get_dialect factory
# ---------------------------------------------------------------------------


class TestGetDialect:
    """Tests for the get_dialect factory function."""

    def test_get_sqlite(self):
        d = get_dialect("sqlite")
        assert isinstance(d, SQLiteDialect)

    def test_get_postgresql(self):
        d = get_dialect("postgresql")
        assert isinstance(d, PostgreSQLDialect)

    def test_get_postgres_alias(self):
        d = get_dialect("postgres")
        assert isinstance(d, PostgreSQLDialect)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unsupported dialect"):
            get_dialect("oracle")
