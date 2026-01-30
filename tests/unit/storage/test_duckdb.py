"""Tests for feedspine.storage.duckdb - DuckDB storage backend.

DuckDB provides OLAP-optimized storage with SQL analytics capabilities.
Designed for analytical queries, Parquet export, and data warehouse integration.

Tests cover:
- Standard StorageBackend protocol compliance
- DuckDB-specific SQL analytics features
- Parquet export functionality
- JSON content querying
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.sighting import Sighting

# DuckDB is optional - skip all tests if not available
duckdb = pytest.importorskip("duckdb", reason="DuckDB not installed")

from feedspine.storage.duckdb import DuckDBStorage  # noqa: E402

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
    )


@pytest.fixture
async def storage(tmp_path: Path) -> DuckDBStorage:
    """Fresh DuckDBStorage instance using temp file."""
    db_path = tmp_path / "test.duckdb"
    s = DuckDBStorage(str(db_path))
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def memory_storage() -> DuckDBStorage:
    """In-memory DuckDB for fast tests."""
    s = DuckDBStorage(":memory:")
    await s.initialize()
    yield s
    await s.close()


# =============================================================================
# Initialization and Lifecycle
# =============================================================================


class TestDuckDBStorageLifecycle:
    """Tests for storage initialization and cleanup."""

    async def test_creates_tables_on_initialize(self, tmp_path: Path) -> None:
        """Initialize creates required tables."""
        db_path = tmp_path / "init.duckdb"
        storage = DuckDBStorage(str(db_path))
        await storage.initialize()

        # Verify tables exist via internal query
        result = storage._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [r[0] for r in result]

        assert "records" in table_names
        assert "sightings" in table_names

        await storage.close()

    async def test_memory_mode(self) -> None:
        """Can create in-memory database."""
        storage = DuckDBStorage(":memory:")
        await storage.initialize()

        assert storage._conn is not None

        await storage.close()

    async def test_close_releases_connection(self, memory_storage: DuckDBStorage) -> None:
        """Close releases database connection."""
        await memory_storage.close()
        # Connection should be closed
        assert memory_storage._conn is None


# =============================================================================
# Basic CRUD Operations
# =============================================================================


class TestDuckDBStorageStore:
    """Tests for store operation."""

    async def test_store_and_get(self, memory_storage: DuckDBStorage) -> None:
        """Can store and retrieve a record."""
        record = make_record("key-1")
        await memory_storage.store(record)

        retrieved = await memory_storage.get(record.id)
        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.natural_key == record.natural_key

    async def test_store_preserves_all_fields(self, memory_storage: DuckDBStorage) -> None:
        """All record fields are preserved after storage."""
        record = make_record("full-record")
        await memory_storage.store(record)

        retrieved = await memory_storage.get(record.id)
        assert retrieved is not None
        assert retrieved.layer == record.layer
        assert retrieved.content == record.content
        assert retrieved.published_at == record.published_at

    async def test_store_overwrites_existing(self, memory_storage: DuckDBStorage) -> None:
        """Storing with same ID overwrites existing record."""
        record = make_record("key-1")
        await memory_storage.store(record)

        updated = record.model_copy(update={"content": {"title": "Updated Title"}})
        await memory_storage.store(updated)

        retrieved = await memory_storage.get(record.id)
        assert retrieved is not None
        assert retrieved.content["title"] == "Updated Title"

    async def test_store_different_layers(self, memory_storage: DuckDBStorage) -> None:
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


class TestDuckDBStorageGet:
    """Tests for get operations."""

    async def test_get_nonexistent_returns_none(self, memory_storage: DuckDBStorage) -> None:
        """Getting nonexistent record returns None."""
        result = await memory_storage.get("does-not-exist")
        assert result is None

    async def test_get_by_layer(self, memory_storage: DuckDBStorage) -> None:
        """Can get record from specific layer."""
        record = make_record("layer-test", Layer.SILVER)
        await memory_storage.store(record)

        # Should find in SILVER
        found = await memory_storage.get(record.id, layer=Layer.SILVER)
        assert found is not None

        # Should not find in BRONZE
        not_found = await memory_storage.get(record.id, layer=Layer.BRONZE)
        assert not_found is None

    async def test_get_by_natural_key(self, memory_storage: DuckDBStorage) -> None:
        """Can retrieve by natural key."""
        record = make_record("unique-key")
        await memory_storage.store(record)

        retrieved = await memory_storage.get_by_natural_key("unique-key")
        assert retrieved is not None
        assert retrieved.id == record.id

    async def test_get_by_natural_key_nonexistent(self, memory_storage: DuckDBStorage) -> None:
        """Getting by nonexistent natural key returns None."""
        result = await memory_storage.get_by_natural_key("nonexistent")
        assert result is None


class TestDuckDBStorageExists:
    """Tests for existence checks."""

    async def test_exists_by_id(self, memory_storage: DuckDBStorage) -> None:
        """Exists check works by ID."""
        record = make_record()
        assert not await memory_storage.exists(record.id)

        await memory_storage.store(record)
        assert await memory_storage.exists(record.id)

    async def test_exists_by_layer(self, memory_storage: DuckDBStorage) -> None:
        """Exists check respects layer filter."""
        record = make_record("layer-check", Layer.GOLD)
        await memory_storage.store(record)

        assert await memory_storage.exists(record.id, layer=Layer.GOLD)
        assert not await memory_storage.exists(record.id, layer=Layer.BRONZE)

    async def test_exists_by_natural_key(self, memory_storage: DuckDBStorage) -> None:
        """Natural key exists check works."""
        record = make_record("check-key")
        assert not await memory_storage.exists_by_natural_key("check-key")

        await memory_storage.store(record)
        assert await memory_storage.exists_by_natural_key("check-key")


class TestDuckDBStorageDelete:
    """Tests for delete operation."""

    async def test_delete_existing(self, memory_storage: DuckDBStorage) -> None:
        """Can delete existing record."""
        record = make_record("to-delete")
        await memory_storage.store(record)

        result = await memory_storage.delete(record.id)
        assert result is True
        assert not await memory_storage.exists(record.id)

    async def test_delete_nonexistent(self, memory_storage: DuckDBStorage) -> None:
        """Deleting nonexistent returns False."""
        result = await memory_storage.delete("does-not-exist")
        assert result is False

    async def test_delete_by_layer(self, memory_storage: DuckDBStorage) -> None:
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


class TestDuckDBStorageQuery:
    """Tests for query operations."""

    async def test_query_all(self, memory_storage: DuckDBStorage) -> None:
        """Query without filters returns all records."""
        for i in range(5):
            await memory_storage.store(make_record(f"key-{i}"))

        records = [r async for r in memory_storage.query()]
        assert len(records) == 5

    async def test_query_by_layer(self, memory_storage: DuckDBStorage) -> None:
        """Query respects layer filter."""
        await memory_storage.store(make_record("bronze-1", Layer.BRONZE))
        await memory_storage.store(make_record("bronze-2", Layer.BRONZE))
        await memory_storage.store(make_record("silver-1", Layer.SILVER))

        bronze_records = [r async for r in memory_storage.query(layer=Layer.BRONZE)]
        assert len(bronze_records) == 2

        silver_records = [r async for r in memory_storage.query(layer=Layer.SILVER)]
        assert len(silver_records) == 1

    async def test_query_with_limit(self, memory_storage: DuckDBStorage) -> None:
        """Query respects limit."""
        for i in range(10):
            await memory_storage.store(make_record(f"key-{i}"))

        records = [r async for r in memory_storage.query(limit=3)]
        assert len(records) == 3

    async def test_query_with_offset(self, memory_storage: DuckDBStorage) -> None:
        """Query respects offset."""
        for i in range(10):
            await memory_storage.store(make_record(f"key-{i}"))

        records = [r async for r in memory_storage.query(limit=5, offset=5)]
        assert len(records) == 5

    async def test_query_pagination(self, memory_storage: DuckDBStorage) -> None:
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


class TestDuckDBStorageCount:
    """Tests for count operation."""

    async def test_count_empty(self, memory_storage: DuckDBStorage) -> None:
        """Empty storage returns zero count."""
        assert await memory_storage.count() == 0

    async def test_count_all(self, memory_storage: DuckDBStorage) -> None:
        """Count returns total records."""
        for i in range(5):
            await memory_storage.store(make_record(f"key-{i}"))

        assert await memory_storage.count() == 5

    async def test_count_by_layer(self, memory_storage: DuckDBStorage) -> None:
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


class TestDuckDBStorageSightings:
    """Tests for sighting operations."""

    async def test_record_first_sighting(self, memory_storage: DuckDBStorage) -> None:
        """First sighting returns True."""
        sighting = make_sighting(key="seen-key", source="test-source")

        result = await memory_storage.record_sighting(sighting)
        assert result is True

    async def test_record_duplicate_sighting(self, memory_storage: DuckDBStorage) -> None:
        """Duplicate sighting returns False."""
        sighting = make_sighting(key="dup-key", source="test-source")

        first = await memory_storage.record_sighting(sighting)
        # Create another with same key+source but new id
        sighting2 = make_sighting(key="dup-key", source="test-source")
        second = await memory_storage.record_sighting(sighting2)

        assert first is True
        assert second is False

    async def test_get_sightings(self, memory_storage: DuckDBStorage) -> None:
        """Can retrieve all sightings for a natural key."""
        key = "multi-sight"
        for i in range(3):
            await memory_storage.record_sighting(make_sighting(key=key, source=f"source-{i}"))

        sightings = await memory_storage.get_sightings(key)
        assert len(sightings) == 3
        sources = {s.source for s in sightings}
        assert sources == {"source-0", "source-1", "source-2"}

    async def test_get_sightings_empty(self, memory_storage: DuckDBStorage) -> None:
        """Getting sightings for unseen key returns empty list."""
        sightings = await memory_storage.get_sightings("never-seen")
        assert sightings == []


class TestDuckDBStorageRecordSightingTracking:
    """Tests for record-level sighting tracking (first_seen_at, last_seen_at, seen_count)."""

    async def test_record_sighting_on_existing_updates_fields(
        self, memory_storage: DuckDBStorage
    ) -> None:
        """record_sighting_on_existing updates tracking fields on stored record."""
        record = make_record("sight-key")
        await memory_storage.store(record)

        # Record a sighting
        updated = await memory_storage.record_sighting_on_existing(record.natural_key)

        assert updated is not None
        assert updated.seen_count == 2  # 1 (initial) + 1 (sighting)
        assert updated.last_seen_at >= record.first_seen_at

    async def test_record_sighting_on_existing_preserves_first_seen(
        self, memory_storage: DuckDBStorage
    ) -> None:
        """Multiple sightings preserve original first_seen_at."""
        record = make_record("preserve-key")
        await memory_storage.store(record)
        original_first_seen = record.first_seen_at

        # Record multiple sightings
        for _ in range(3):
            await memory_storage.record_sighting_on_existing(record.natural_key)

        retrieved = await memory_storage.get_by_natural_key("preserve-key")
        assert retrieved is not None
        assert retrieved.first_seen_at == original_first_seen
        assert retrieved.seen_count == 4  # 1 + 3

    async def test_record_sighting_on_existing_nonexistent_returns_none(
        self, memory_storage: DuckDBStorage
    ) -> None:
        """record_sighting_on_existing returns None for nonexistent key."""
        result = await memory_storage.record_sighting_on_existing("does-not-exist")
        assert result is None

    async def test_stored_record_has_sighting_fields(
        self, memory_storage: DuckDBStorage
    ) -> None:
        """Newly stored records have sighting tracking fields initialized."""
        record = make_record("new-record")
        await memory_storage.store(record)

        retrieved = await memory_storage.get(record.id)
        assert retrieved is not None
        assert retrieved.first_seen_at is not None
        assert retrieved.last_seen_at is not None
        assert retrieved.seen_count == 1

    async def test_sighting_tracking_in_sql_queries(
        self, memory_storage: DuckDBStorage
    ) -> None:
        """Can query sighting tracking fields via SQL."""
        # Store records and record sightings
        record = make_record("sql-sight-key")
        await memory_storage.store(record)

        # Record some sightings
        for _ in range(5):
            await memory_storage.record_sighting_on_existing(record.natural_key)

        # Query using SQL
        results = await memory_storage.execute_sql(
            "SELECT natural_key, seen_count, first_seen_at, last_seen_at "
            "FROM records WHERE natural_key = 'sql-sight-key'"
        )
        assert len(results) == 1
        assert results[0]["seen_count"] == 6  # 1 initial + 5 sightings
        assert results[0]["first_seen_at"] is not None
        assert results[0]["last_seen_at"] >= results[0]["first_seen_at"]


# =============================================================================
# DuckDB-Specific Analytics Features
# =============================================================================


class TestDuckDBAnalytics:
    """Tests for DuckDB-specific SQL analytics capabilities."""

    async def test_raw_sql_query(self, memory_storage: DuckDBStorage) -> None:
        """Can execute raw SQL for analytics."""
        # Store test data
        for i in range(5):
            record = make_record(f"analytics-{i}", Layer.GOLD)
            record = record.model_copy(
                update={"content": {"company": "Acme Corp", "revenue": (i + 1) * 1000}}
            )
            await memory_storage.store(record)

        # Execute analytics query (layer values are lowercase)
        results = await memory_storage.execute_sql(
            "SELECT COUNT(*) as cnt FROM records WHERE layer = 'gold'"
        )
        assert results[0]["cnt"] == 5

    async def test_json_content_query(self, memory_storage: DuckDBStorage) -> None:
        """Can query JSON content fields."""
        await memory_storage.store(
            make_record("json-1").model_copy(
                update={"content": {"company": "Apple", "sector": "Tech"}}
            )
        )
        await memory_storage.store(
            make_record("json-2").model_copy(
                update={"content": {"company": "Microsoft", "sector": "Tech"}}
            )
        )
        await memory_storage.store(
            make_record("json-3").model_copy(
                update={"content": {"company": "Exxon", "sector": "Energy"}}
            )
        )

        # Query by JSON field
        results = await memory_storage.execute_sql("""
            SELECT content->>'company' as company
            FROM records
            WHERE content->>'sector' = 'Tech'
            ORDER BY company
        """)

        companies = [r["company"] for r in results]
        assert companies == ["Apple", "Microsoft"]

    async def test_aggregation_query(self, memory_storage: DuckDBStorage) -> None:
        """Can run aggregation queries."""
        # Store records at different layers
        for i in range(3):
            await memory_storage.store(make_record(f"bronze-{i}", Layer.BRONZE))
        for i in range(2):
            await memory_storage.store(make_record(f"silver-{i}", Layer.SILVER))
        await memory_storage.store(make_record("gold-1", Layer.GOLD))

        results = await memory_storage.execute_sql("""
            SELECT layer, COUNT(*) as count
            FROM records
            GROUP BY layer
            ORDER BY count DESC
        """)

        assert len(results) == 3
        # Most records in bronze (layer value is lowercase 'bronze')
        assert results[0]["layer"] == "bronze"
        assert results[0]["count"] == 3


class TestDuckDBParquet:
    """Tests for Parquet export functionality."""

    async def test_export_to_parquet(self, memory_storage: DuckDBStorage, tmp_path: Path) -> None:
        """Can export records to Parquet file."""
        # Store test data
        for i in range(10):
            await memory_storage.store(make_record(f"parquet-{i}", Layer.GOLD))

        output_path = tmp_path / "export.parquet"
        row_count = await memory_storage.export_to_parquet(output_path, layer=Layer.GOLD)

        assert row_count == 10
        assert output_path.exists()

    async def test_export_parquet_with_query(
        self, memory_storage: DuckDBStorage, tmp_path: Path
    ) -> None:
        """Can export custom query results to Parquet."""
        # Store test data with different content
        await memory_storage.store(
            make_record("export-1").model_copy(update={"content": {"category": "A", "value": 100}})
        )
        await memory_storage.store(
            make_record("export-2").model_copy(update={"content": {"category": "B", "value": 200}})
        )

        output_path = tmp_path / "custom.parquet"
        row_count = await memory_storage.export_query_to_parquet(
            "SELECT id, content->>'category' as category FROM records",
            output_path,
        )

        assert row_count == 2
        assert output_path.exists()

    async def test_export_empty_returns_zero(
        self, memory_storage: DuckDBStorage, tmp_path: Path
    ) -> None:
        """Exporting empty dataset returns zero rows."""
        output_path = tmp_path / "empty.parquet"
        row_count = await memory_storage.export_to_parquet(output_path)

        assert row_count == 0


# =============================================================================
# Protocol Compliance
# =============================================================================


class TestDuckDBProtocolCompliance:
    """Tests verifying StorageBackend protocol compliance."""

    def test_implements_storage_protocol(self) -> None:
        """DuckDBStorage implements StorageBackend protocol."""
        from feedspine.protocols.storage import StorageBackend

        assert isinstance(DuckDBStorage(":memory:"), StorageBackend)

    def test_has_all_required_methods(self) -> None:
        """DuckDBStorage has all required protocol methods."""
        storage = DuckDBStorage(":memory:")

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


# =============================================================================
# Persistence Tests
# =============================================================================


class TestDuckDBPersistence:
    """Tests for data persistence across sessions."""

    async def test_data_persists_after_close(self, tmp_path: Path) -> None:
        """Data persists after closing and reopening."""
        db_path = tmp_path / "persist.duckdb"

        # First session - store data
        storage1 = DuckDBStorage(str(db_path))
        await storage1.initialize()
        record = make_record("persist-test")
        await storage1.store(record)
        await storage1.close()

        # Second session - verify data
        storage2 = DuckDBStorage(str(db_path))
        await storage2.initialize()
        retrieved = await storage2.get(record.id)
        await storage2.close()

        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.natural_key == "persist-test"
