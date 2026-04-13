"""Tests for feedspine.storage.schemas module.

Validates DDL schema strings are well-formed.
"""

from __future__ import annotations

import pytest

from feedspine.storage.schemas import POSTGRES_SCHEMA, SQLITE_SCHEMA


class TestSQLiteSchema:
    """Tests for the SQLite DDL schema."""

    def test_is_nonempty_string(self):
        assert isinstance(SQLITE_SCHEMA, str)
        assert len(SQLITE_SCHEMA) > 100

    def test_creates_records_table(self):
        assert "records" in SQLITE_SCHEMA.lower()

    def test_creates_sightings_table(self):
        assert "sightings" in SQLITE_SCHEMA.lower()

    @pytest.mark.parametrize(
        "table",
        ["records", "sightings", "feed_runs"],
    )
    def test_expected_tables(self, table: str):
        assert table in SQLITE_SCHEMA.lower()


class TestPostgresSchema:
    """Tests for the PostgreSQL DDL schema."""

    def test_is_nonempty_string(self):
        assert isinstance(POSTGRES_SCHEMA, str)
        assert len(POSTGRES_SCHEMA) > 100

    def test_uses_jsonb_type(self):
        assert "jsonb" in POSTGRES_SCHEMA.lower()

    def test_creates_records_table(self):
        assert "records" in POSTGRES_SCHEMA.lower()
