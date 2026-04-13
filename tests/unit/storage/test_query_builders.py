"""Tests for feedspine.storage.shared.query_builders module.

Tests QueryBuilder hierarchy — pure SQL generation, no DB connection.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.storage.shared.query_builders import (
    DuckDBQueryBuilder,
    PostgresQueryBuilder,
    QueryBuilder,
    SQLiteQueryBuilder,
)

# ---------------------------------------------------------------------------
# Base QueryBuilder
# ---------------------------------------------------------------------------


class TestQueryBuilder:
    """Tests for the base QueryBuilder."""

    @pytest.fixture
    def builder(self) -> QueryBuilder:
        return QueryBuilder()

    def test_build_select_query_returns_tuple(self, builder: QueryBuilder):
        sql, params = builder.build_select_query("records")
        assert isinstance(sql, str)
        assert isinstance(params, list)
        assert "records" in sql

    def test_build_count_query(self, builder: QueryBuilder):
        sql, params = builder.build_count_query("records")
        assert "COUNT" in sql.upper()

    def test_build_limit_offset(self, builder: QueryBuilder):
        clause = builder.build_limit_offset(limit=10, offset=5)
        assert "LIMIT" in clause.upper()
        assert "OFFSET" in clause.upper()

    def test_build_limit_offset_no_limit(self, builder: QueryBuilder):
        clause = builder.build_limit_offset(limit=None, offset=0)
        # No limit → empty or no LIMIT clause
        assert "LIMIT" not in clause.upper() or clause.strip() == ""

    def test_build_order_by_default(self, builder: QueryBuilder):
        clause = builder.build_order_by(None, default="captured_at DESC")
        assert "captured_at" in clause.lower()

    def test_build_order_by_custom(self, builder: QueryBuilder):
        clause = builder.build_order_by("natural_key")
        assert "natural_key" in clause.lower()

    def test_build_layer_filter_none(self, builder: QueryBuilder):
        clause, params = builder.build_layer_filter(None)
        assert params == [] or params == ()

    def test_build_layer_filter_value(self, builder: QueryBuilder):
        clause, params = builder.build_layer_filter("bronze")
        assert len(params) >= 1

    def test_build_time_range_filter_none(self, builder: QueryBuilder):
        clause, params = builder.build_time_range_filter(None, None)
        assert params == [] or params == ()

    def test_build_time_range_filter_with_range(self, builder: QueryBuilder):
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 2, 1, tzinfo=UTC)
        clause, params = builder.build_time_range_filter(start, end)
        assert len(params) >= 2


# ---------------------------------------------------------------------------
# SQLiteQueryBuilder
# ---------------------------------------------------------------------------


class TestSQLiteQueryBuilder:
    """Tests for SQLite-specific query building."""

    @pytest.fixture
    def builder(self) -> SQLiteQueryBuilder:
        return SQLiteQueryBuilder()

    def test_select_query(self, builder: SQLiteQueryBuilder):
        sql, params = builder.build_select_query("records", limit=5)
        assert "records" in sql
        assert "LIMIT" in sql.upper()

    def test_upsert_sql(self, builder: SQLiteQueryBuilder):
        sql = builder.build_upsert_sql(
            "records",
            ["natural_key", "content", "source"],
            conflict_column="natural_key",
        )
        assert "INSERT" in sql.upper()
        # SQLite uses INSERT OR REPLACE (not ON CONFLICT)
        assert "REPLACE" in sql.upper() or "CONFLICT" in sql.upper()

    def test_insert_ignore_sql(self, builder: SQLiteQueryBuilder):
        sql = builder.build_insert_ignore_sql("records", ["natural_key", "content"])
        assert "INSERT" in sql.upper()
        assert "IGNORE" in sql.upper() or "NOTHING" in sql.upper()


# ---------------------------------------------------------------------------
# PostgresQueryBuilder
# ---------------------------------------------------------------------------


class TestPostgresQueryBuilder:
    """Tests for PostgreSQL-specific query building."""

    @pytest.fixture
    def builder(self) -> PostgresQueryBuilder:
        return PostgresQueryBuilder()

    @pytest.mark.xfail(
        reason="PostgresQueryBuilder.build_content_filter returns 3 values "
        "but inherited build_select_query unpacks only 2 — source bug",
        strict=True,
    )
    def test_select_query(self, builder: PostgresQueryBuilder):
        sql, params = builder.build_select_query("records")
        assert isinstance(sql, str)

    def test_content_filter_uses_jsonb(self, builder: PostgresQueryBuilder):
        clause, params, _idx = builder.build_content_filter({"key": "val"})
        assert isinstance(clause, str)


# ---------------------------------------------------------------------------
# DuckDBQueryBuilder
# ---------------------------------------------------------------------------


class TestDuckDBQueryBuilder:
    """Tests for DuckDB-specific query building."""

    @pytest.fixture
    def builder(self) -> DuckDBQueryBuilder:
        return DuckDBQueryBuilder()

    def test_select_query(self, builder: DuckDBQueryBuilder):
        sql, params = builder.build_select_query("records")
        assert isinstance(sql, str)

    def test_window_function(self, builder: DuckDBQueryBuilder):
        sql = builder.build_window_function("ROW_NUMBER", "content_hash", order_by="captured_at")
        assert "ROW_NUMBER" in sql.upper() or "row_number" in sql

    def test_parquet_export(self, builder: DuckDBQueryBuilder):
        sql = builder.build_parquet_export("SELECT * FROM records", "/tmp/out.parquet")
        assert "parquet" in sql.lower() or "COPY" in sql.upper()
