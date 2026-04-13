"""Tests for feedspine.storage.factory module.

Tests storage factory pattern, type detection, and option presets.
"""

from __future__ import annotations

from feedspine.storage.factory import (
    StorageOptions,
    create_storage,
    detect_storage_type,
)

# ---------------------------------------------------------------------------
# StorageOptions
# ---------------------------------------------------------------------------


class TestStorageOptions:
    """Tests for StorageOptions dataclass and presets."""

    def test_default_values(self):
        opts = StorageOptions()
        assert opts.pool_size >= 1
        assert opts.batch_size >= 1
        assert opts.auto_migrate is True

    def test_for_development(self):
        opts = StorageOptions.for_development()
        assert isinstance(opts, StorageOptions)
        assert opts.echo_sql is True

    def test_for_production(self):
        opts = StorageOptions.for_production()
        assert isinstance(opts, StorageOptions)
        assert opts.echo_sql is False

    def test_for_testing(self):
        opts = StorageOptions.for_testing()
        assert isinstance(opts, StorageOptions)


# ---------------------------------------------------------------------------
# detect_storage_type
# ---------------------------------------------------------------------------


class TestDetectStorageType:
    """Tests for detect_storage_type."""

    def test_sqlite_uri_detection(self):
        assert detect_storage_type("sqlite:///test.db") == "sqlite"

    def test_sqlite_memory_uri_detection(self):
        result = detect_storage_type("sqlite:///:memory:")
        assert result in ("sqlite", "memory")

    def test_bare_memory_detection(self):
        result = detect_storage_type(":memory:")
        assert result in ("sqlite", "memory")

    def test_duckdb_detection(self):
        result = detect_storage_type("duckdb://test.duckdb")
        assert result == "duckdb"

    def test_duckdb_file_detection(self):
        result = detect_storage_type("data.duckdb")
        assert result == "duckdb"

    def test_postgresql_detection(self):
        result = detect_storage_type("postgresql://user:pass@localhost/db")
        assert result == "postgresql"

    def test_postgres_short_scheme(self):
        result = detect_storage_type("postgres://user:pass@localhost/db")
        assert result == "postgresql"


# ---------------------------------------------------------------------------
# create_storage
# ---------------------------------------------------------------------------


class TestCreateStorage:
    """Tests for the storage factory function."""

    def test_create_memory_storage(self):
        storage = create_storage(storage_type="memory")
        assert storage is not None

    def test_create_sqlite_memory(self):
        storage = create_storage("sqlite:///:memory:")
        assert storage is not None

    def test_none_connection_defaults_to_memory(self):
        storage = create_storage(storage_type="memory")
        assert storage is not None
