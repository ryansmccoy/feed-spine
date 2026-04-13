"""Tests for feedspine.storage.backends.sqlite - SQLite storage backend.

SQLite provides zero-config, embedded storage for single-user applications,
local development, and small-to-medium datasets.

Tests cover:
- Standard StorageBackend protocol compliance
- SQLite-specific features (WAL mode, vacuum, stats)
- Record CRUD operations
- Query/pagination
- Sighting tracking
- Batch operations
- Version control
- Persistence across sessions
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.sighting import Sighting
from feedspine.storage.backends.sqlite import SQLiteStorage

# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def make_candidate(key: str = "test-key") -> RecordCandidate:
    """Create a test candidate with default values."""
    return RecordCandidate(
        natural_key=key,
        published_at=datetime.now(UTC),
        content={"title": f"Title for {key}", "company": "Test Corp"},
        metadata=Metadata(source="test"),
    )


def make_record(key: str = "test-key", layer: Layer = Layer.BRONZE) -> Record:
    """Create a test record with default values."""
    candidate = make_candidate(key)
    record = Record.from_candidate(candidate, record_id=str(uuid4()))
    if layer != Layer.BRONZE:
        record = record.model_copy(update={"layer": layer})
    return record


def make_sighting(
    key: str = "test-key",
    source: str = "test-source",
    is_new: bool = True,
) -> Sighting:
    """Create a test sighting with required fields."""
    return Sighting(
        id=str(uuid4()),
        natural_key=key,
        source=source,
        is_new=is_new,
        seen_at=datetime.now(UTC),
        metadata={},
    )


@pytest.fixture
async def storage(tmp_path: Path) -> SQLiteStorage:
    """Fresh SQLiteStorage instance using temp file."""
    db_path = tmp_path / "test.db"
    s = SQLiteStorage(str(db_path))
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def memory_storage() -> SQLiteStorage:
    """In-memory SQLite for fast tests."""
    s = SQLiteStorage(":memory:")
    await s.initialize()
    yield s
    await s.close()


# =============================================================================
# Initialization and Lifecycle
# =============================================================================


class TestSQLiteStorageLifecycle:
    """Tests for storage initialization and cleanup."""

    async def test_creates_tables_on_initialize(self, tmp_path: Path) -> None:
        """Initialize creates all required tables."""
        db_path = tmp_path / "init.db"
        storage = SQLiteStorage(str(db_path))
        await storage.initialize()

        # Verify tables exist
        with storage._cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            table_names = [r[0] for r in cursor.fetchall()]

        assert "records" in table_names
        assert "sightings" in table_names
        assert "feed_runs" in table_names
        assert "record_versions" in table_names
        assert "_feedspine_meta" in table_names

        await storage.close()

    async def test_memory_mode(self) -> None:
        """Can create in-memory database."""
        storage = SQLiteStorage(":memory:")
        await storage.initialize()
        assert storage._conn is not None
        await storage.close()

    async def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        """File-backed storage uses WAL journal mode."""
        db_path = tmp_path / "wal.db"
        storage = SQLiteStorage(str(db_path))
        await storage.initialize()

        with storage._cursor() as cursor:
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]

        assert mode == "wal"
        await storage.close()

    async def test_schema_version_stored(self, memory_storage: SQLiteStorage) -> None:
        """Schema version is stored in _feedspine_meta."""
        with memory_storage._cursor() as cursor:
            cursor.execute("SELECT value FROM _feedspine_meta WHERE key = 'schema_version'")
            version = cursor.fetchone()[0]

        assert version == str(SQLiteStorage.SCHEMA_VERSION)

    async def test_close_releases_connection(self, memory_storage: SQLiteStorage) -> None:
        """Close releases database connection."""
        await memory_storage.close()
        assert memory_storage._conn is None

    async def test_cursor_raises_when_not_initialized(self) -> None:
        """Using _cursor before initialize raises RuntimeError."""
        storage = SQLiteStorage(":memory:")
        with pytest.raises(RuntimeError, match="not initialized"), storage._cursor():
            pass


# =============================================================================
# Basic CRUD Operations
# =============================================================================


class TestSQLiteStorageStore:
    """Tests for store operation."""

    async def test_store_and_get(self, memory_storage: SQLiteStorage) -> None:
        """Can store and retrieve a record."""
        record = make_record("key-1")
        await memory_storage.store(record)

        retrieved = await memory_storage.get(record.id)
        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.natural_key == record.natural_key

    async def test_store_preserves_all_fields(self, memory_storage: SQLiteStorage) -> None:
        """All record fields are preserved after storage."""
        record = make_record("full-record")
        await memory_storage.store(record)

        retrieved = await memory_storage.get(record.id)
        assert retrieved is not None
        assert retrieved.layer == record.layer
        assert retrieved.content == record.content
        assert retrieved.published_at == record.published_at

    async def test_store_upserts_on_natural_key(self, memory_storage: SQLiteStorage) -> None:
        """Storing with same natural_key upserts (updates content, increments version)."""
        record = make_record("key-1")
        await memory_storage.store(record)

        updated = record.model_copy(update={"content": {"title": "Updated Title"}})
        await memory_storage.store(updated)

        retrieved = await memory_storage.get_by_natural_key("key-1")
        assert retrieved is not None
        assert retrieved.content["title"] == "Updated Title"
        assert retrieved.version == 2  # version incremented by upsert
        assert retrieved.seen_count == 2  # seen_count incremented

    async def test_store_different_layers(self, memory_storage: SQLiteStorage) -> None:
        """Can store records at different layers."""
        bronze = make_record("bronze-1", Layer.BRONZE)
        silver = make_record("silver-1", Layer.SILVER)
        gold = make_record("gold-1", Layer.GOLD)

        await memory_storage.store(bronze)
        await memory_storage.store(silver)
        await memory_storage.store(gold)

        assert await memory_storage.count(layer=Layer.BRONZE) == 1
        assert await memory_storage.count(layer=Layer.SILVER) == 1
        assert await memory_storage.count(layer=Layer.GOLD) == 1


class TestSQLiteStorageGet:
    """Tests for get operations."""

    async def test_get_nonexistent_returns_none(self, memory_storage: SQLiteStorage) -> None:
        """Getting nonexistent record returns None."""
        result = await memory_storage.get("does-not-exist")
        assert result is None

    async def test_get_by_layer(self, memory_storage: SQLiteStorage) -> None:
        """Can get record from specific layer."""
        record = make_record("layer-test", Layer.SILVER)
        await memory_storage.store(record)

        found = await memory_storage.get(record.id, layer=Layer.SILVER)
        assert found is not None

        not_found = await memory_storage.get(record.id, layer=Layer.BRONZE)
        assert not_found is None

    async def test_get_by_natural_key(self, memory_storage: SQLiteStorage) -> None:
        """Can retrieve by natural key."""
        record = make_record("unique-key")
        await memory_storage.store(record)

        retrieved = await memory_storage.get_by_natural_key("unique-key")
        assert retrieved is not None
        assert retrieved.id == record.id

    async def test_get_by_natural_key_nonexistent(self, memory_storage: SQLiteStorage) -> None:
        """Getting by nonexistent natural key returns None."""
        result = await memory_storage.get_by_natural_key("nonexistent")
        assert result is None


class TestSQLiteStorageExists:
    """Tests for existence checks."""

    async def test_exists_by_id(self, memory_storage: SQLiteStorage) -> None:
        """Exists check works by ID."""
        record = make_record()
        assert not await memory_storage.exists(record.id)

        await memory_storage.store(record)
        assert await memory_storage.exists(record.id)

    async def test_exists_by_layer(self, memory_storage: SQLiteStorage) -> None:
        """Exists check respects layer filter."""
        record = make_record("layer-check", Layer.GOLD)
        await memory_storage.store(record)

        assert await memory_storage.exists(record.id, layer=Layer.GOLD)
        assert not await memory_storage.exists(record.id, layer=Layer.BRONZE)

    async def test_exists_by_natural_key(self, memory_storage: SQLiteStorage) -> None:
        """Natural key exists check works."""
        record = make_record("check-key")
        assert not await memory_storage.exists_by_natural_key("check-key")

        await memory_storage.store(record)
        assert await memory_storage.exists_by_natural_key("check-key")


class TestSQLiteStorageDelete:
    """Tests for delete operation."""

    async def test_delete_existing(self, memory_storage: SQLiteStorage) -> None:
        """Can delete existing record."""
        record = make_record("to-delete")
        await memory_storage.store(record)

        result = await memory_storage.delete(record.id)
        assert result is True
        assert not await memory_storage.exists(record.id)

    async def test_delete_nonexistent(self, memory_storage: SQLiteStorage) -> None:
        """Deleting nonexistent returns False."""
        result = await memory_storage.delete("does-not-exist")
        assert result is False

    async def test_delete_by_layer(self, memory_storage: SQLiteStorage) -> None:
        """Can delete from specific layer."""
        record = make_record("layer-delete", Layer.SILVER)
        await memory_storage.store(record)

        # Try deleting from wrong layer
        assert not await memory_storage.delete(record.id, layer=Layer.BRONZE)
        assert await memory_storage.exists(record.id)

        # Delete from correct layer
        assert await memory_storage.delete(record.id, layer=Layer.SILVER)
        assert not await memory_storage.exists(record.id)


# =============================================================================
# Query Operations
# =============================================================================


class TestSQLiteStorageQuery:
    """Tests for query operations."""

    async def test_query_all(self, memory_storage: SQLiteStorage) -> None:
        """Query without filters returns all records."""
        for i in range(5):
            await memory_storage.store(make_record(f"key-{i}"))

        records = [r async for r in memory_storage.query()]
        assert len(records) == 5

    async def test_query_by_layer(self, memory_storage: SQLiteStorage) -> None:
        """Query respects layer filter."""
        await memory_storage.store(make_record("bronze-1", Layer.BRONZE))
        await memory_storage.store(make_record("bronze-2", Layer.BRONZE))
        await memory_storage.store(make_record("silver-1", Layer.SILVER))

        bronze_records = [r async for r in memory_storage.query(layer=Layer.BRONZE)]
        assert len(bronze_records) == 2

        silver_records = [r async for r in memory_storage.query(layer=Layer.SILVER)]
        assert len(silver_records) == 1

    async def test_query_with_limit(self, memory_storage: SQLiteStorage) -> None:
        """Query respects limit."""
        for i in range(10):
            await memory_storage.store(make_record(f"key-{i}"))

        records = [r async for r in memory_storage.query(limit=3)]
        assert len(records) == 3

    async def test_query_with_offset(self, memory_storage: SQLiteStorage) -> None:
        """Query respects offset."""
        for i in range(10):
            await memory_storage.store(make_record(f"key-{i}"))

        records = [r async for r in memory_storage.query(limit=5, offset=5)]
        assert len(records) == 5

    async def test_query_pagination(self, memory_storage: SQLiteStorage) -> None:
        """Can paginate through results."""
        for i in range(20):
            await memory_storage.store(make_record(f"key-{i:02d}"))

        page1 = [r async for r in memory_storage.query(limit=10, offset=0)]
        page2 = [r async for r in memory_storage.query(limit=10, offset=10)]

        assert len(page1) == 10
        assert len(page2) == 10

        # No duplicates
        all_ids = {r.id for r in page1} | {r.id for r in page2}
        assert len(all_ids) == 20


class TestSQLiteStorageCount:
    """Tests for count operation."""

    async def test_count_empty(self, memory_storage: SQLiteStorage) -> None:
        """Empty storage returns zero count."""
        assert await memory_storage.count() == 0

    async def test_count_all(self, memory_storage: SQLiteStorage) -> None:
        """Count returns total records."""
        for i in range(5):
            await memory_storage.store(make_record(f"key-{i}"))
        assert await memory_storage.count() == 5

    async def test_count_by_layer(self, memory_storage: SQLiteStorage) -> None:
        """Count respects layer filter."""
        await memory_storage.store(make_record("bronze-1", Layer.BRONZE))
        await memory_storage.store(make_record("bronze-2", Layer.BRONZE))
        await memory_storage.store(make_record("silver-1", Layer.SILVER))

        assert await memory_storage.count(layer=Layer.BRONZE) == 2
        assert await memory_storage.count(layer=Layer.SILVER) == 1
        assert await memory_storage.count(layer=Layer.GOLD) == 0


# =============================================================================
# Sighting Operations
# =============================================================================


class TestSQLiteStorageSightings:
    """Tests for sighting operations."""

    async def test_record_first_sighting(self, memory_storage: SQLiteStorage) -> None:
        """First sighting returns True (is_new)."""
        sighting = make_sighting(key="seen-key", source="test-source")
        result = await memory_storage.record_sighting(sighting)
        assert result is True

    async def test_record_duplicate_sighting(self, memory_storage: SQLiteStorage) -> None:
        """Duplicate sighting returns False when is_new=False."""
        sighting = make_sighting(key="dup-key", source="test-source")
        first = await memory_storage.record_sighting(sighting)

        sighting2 = make_sighting(key="dup-key", source="test-source", is_new=False)
        second = await memory_storage.record_sighting(sighting2)

        assert first is True
        assert second is False

    async def test_get_sightings(self, memory_storage: SQLiteStorage) -> None:
        """Can retrieve all sightings for a natural key."""
        key = "multi-sight"
        for i in range(3):
            await memory_storage.record_sighting(make_sighting(key=key, source=f"source-{i}"))

        sightings = await memory_storage.get_sightings(key)
        assert len(sightings) == 3
        sources = {s.source for s in sightings}
        assert sources == {"source-0", "source-1", "source-2"}

    async def test_get_sightings_empty(self, memory_storage: SQLiteStorage) -> None:
        """Getting sightings for unseen key returns empty list."""
        sightings = await memory_storage.get_sightings("never-seen")
        assert sightings == []


# =============================================================================
# Batch Operations
# =============================================================================


class TestSQLiteStorageBatch:
    """Tests for batch operations."""

    async def test_store_batch_skip_conflict(self, memory_storage: SQLiteStorage) -> None:
        """Batch store with skip conflict skips duplicates."""
        records = [make_record(f"batch-{i}") for i in range(5)]
        stored = await memory_storage.store_batch(records, on_conflict="skip")
        assert stored == 5

        # Storing again should skip all
        stored = await memory_storage.store_batch(records, on_conflict="skip")
        assert stored == 0

    async def test_store_batch_update_conflict(self, memory_storage: SQLiteStorage) -> None:
        """Batch store with update conflict invokes upsert path."""
        records = [make_record(f"batch-{i}") for i in range(3)]
        await memory_storage.store_batch(records, on_conflict="skip")

        # Update content and re-store via update path
        updated = [r.model_copy(update={"content": {"title": "Updated"}}) for r in records]
        await memory_storage.store_batch(updated, on_conflict="update")

        # Verify content was actually updated
        for r in records:
            retrieved = await memory_storage.get_by_natural_key(r.natural_key)
            assert retrieved is not None
            assert retrieved.content["title"] == "Updated"

    async def test_store_batch_empty(self, memory_storage: SQLiteStorage) -> None:
        """Batch store with empty list returns 0."""
        stored = await memory_storage.store_batch([])
        assert stored == 0


# =============================================================================
# Version Control Operations
# =============================================================================


class TestSQLiteStorageVersions:
    """Tests for version control operations."""

    async def test_save_and_get_version(self, memory_storage: SQLiteStorage) -> None:
        """Can save and retrieve a version."""
        await memory_storage.save_version(
            "rec-1",
            version=1,
            content={"title": "Original"},
            content_hash="abc123",
            source="test",
            change_type="created",
        )

        latest = await memory_storage.get_latest_version("rec-1")
        assert latest is not None
        assert latest["version"] == 1

    async def test_multiple_versions(self, memory_storage: SQLiteStorage) -> None:
        """Can store and retrieve multiple versions."""
        for v in range(1, 4):
            await memory_storage.save_version(
                "rec-1",
                version=v,
                content={"title": f"Version {v}"},
                content_hash=f"hash-{v}",
                source="test",
                change_type="updated",
                parent_version=v - 1 if v > 1 else None,
            )

        all_versions = await memory_storage.get_all_versions("rec-1")
        assert len(all_versions) == 3
        assert all_versions[0]["version"] == 1
        assert all_versions[-1]["version"] == 3

    async def test_get_latest_version_returns_highest(self, memory_storage: SQLiteStorage) -> None:
        """get_latest_version returns the highest version number."""
        for v in [1, 3, 2]:  # Out of order
            await memory_storage.save_version(
                "rec-1",
                version=v,
                content={"v": v},
                content_hash=f"h{v}",
                source="test",
                change_type="updated",
            )

        latest = await memory_storage.get_latest_version("rec-1")
        assert latest is not None
        assert latest["version"] == 3

    async def test_get_latest_version_nonexistent(self, memory_storage: SQLiteStorage) -> None:
        """get_latest_version returns None for nonexistent key."""
        result = await memory_storage.get_latest_version("nonexistent")
        assert result is None


# =============================================================================
# Convenience Methods
# =============================================================================


class TestSQLiteStorageConvenience:
    """Tests for vacuum, stats, and other helpers."""

    async def test_vacuum_runs(self, memory_storage: SQLiteStorage) -> None:
        """Vacuum completes without error."""
        await memory_storage.store(make_record("vac-1"))
        await memory_storage.delete(
            (await memory_storage.get_by_natural_key("vac-1")).id  # type: ignore[union-attr]
        )
        await memory_storage.vacuum()

    async def test_get_stats_empty(self, memory_storage: SQLiteStorage) -> None:
        """Stats on empty database."""
        stats = await memory_storage.get_stats()
        assert stats["records"] == 0
        assert stats["sightings"] == 0
        assert stats["versions"] == 0
        assert stats["by_layer"] == {}

    async def test_get_stats_with_data(self, memory_storage: SQLiteStorage) -> None:
        """Stats reflect stored data."""
        await memory_storage.store(make_record("s1", Layer.BRONZE))
        await memory_storage.store(make_record("s2", Layer.BRONZE))
        await memory_storage.store(make_record("s3", Layer.SILVER))

        stats = await memory_storage.get_stats()
        assert stats["records"] == 3
        assert stats["by_layer"]["bronze"] == 2
        assert stats["by_layer"]["silver"] == 1


# =============================================================================
# Protocol Compliance
# =============================================================================


class TestSQLiteProtocolCompliance:
    """Tests verifying StorageBackend protocol compliance."""

    def test_implements_record_store_protocol(self) -> None:
        """SQLiteStorage implements RecordStore protocol."""
        from feedspine.protocols.storage import RecordStore

        assert isinstance(SQLiteStorage(":memory:"), RecordStore)

    def test_implements_sighting_store_protocol(self) -> None:
        """SQLiteStorage implements SightingStore protocol."""
        from feedspine.protocols.storage import SightingStore

        assert isinstance(SQLiteStorage(":memory:"), SightingStore)

    def test_implements_lifecycle_protocol(self) -> None:
        """SQLiteStorage implements StorageLifecycle protocol."""
        from feedspine.protocols.storage import StorageLifecycle

        assert isinstance(SQLiteStorage(":memory:"), StorageLifecycle)

    def test_implements_full_storage_backend(self) -> None:
        """SQLiteStorage implements full StorageBackend protocol."""
        from feedspine.protocols.storage import StorageBackend

        assert isinstance(SQLiteStorage(":memory:"), StorageBackend)

    def test_has_all_required_methods(self) -> None:
        """SQLiteStorage has all required protocol methods."""
        storage = SQLiteStorage(":memory:")

        # Record operations
        assert hasattr(storage, "store")
        assert hasattr(storage, "get")
        assert hasattr(storage, "get_by_natural_key")
        assert hasattr(storage, "exists")
        assert hasattr(storage, "exists_by_natural_key")
        assert hasattr(storage, "delete")

        # Query operations
        assert hasattr(storage, "query")
        assert hasattr(storage, "count")

        # Sighting operations
        assert hasattr(storage, "record_sighting")
        assert hasattr(storage, "get_sightings")

        # Lifecycle
        assert hasattr(storage, "initialize")
        assert hasattr(storage, "close")

        # Batch
        assert hasattr(storage, "store_batch")


# =============================================================================
# Persistence Tests
# =============================================================================


class TestSQLitePersistence:
    """Tests for data persistence across sessions."""

    async def test_data_persists_after_close(self, tmp_path: Path) -> None:
        """Data persists after closing and reopening."""
        db_path = tmp_path / "persist.db"

        # First session - store data
        storage1 = SQLiteStorage(str(db_path))
        await storage1.initialize()
        record = make_record("persist-test")
        await storage1.store(record)
        await storage1.close()

        # Second session - verify data
        storage2 = SQLiteStorage(str(db_path))
        await storage2.initialize()
        retrieved = await storage2.get(record.id)
        await storage2.close()

        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.natural_key == "persist-test"

    async def test_sightings_persist(self, tmp_path: Path) -> None:
        """Sightings persist across sessions."""
        db_path = tmp_path / "persist2.db"

        storage1 = SQLiteStorage(str(db_path))
        await storage1.initialize()
        await storage1.record_sighting(make_sighting(key="persist-sight"))
        await storage1.close()

        storage2 = SQLiteStorage(str(db_path))
        await storage2.initialize()
        sightings = await storage2.get_sightings("persist-sight")
        await storage2.close()

        assert len(sightings) == 1
