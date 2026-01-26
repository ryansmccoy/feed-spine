"""Tests for feedspine.storage.memory - MemoryStorage implementation.

This module tests the in-memory storage backend which serves as:
1. The reference implementation for StorageBackend protocol
2. A fast backend for testing and development
3. An example for other storage implementations
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.sighting import Sighting
from feedspine.storage.memory import MemoryStorage

# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def make_candidate(key: str = "test-key") -> RecordCandidate:
    """Create a test candidate with default values.

    Args:
        key: Natural key for the candidate

    Returns:
        RecordCandidate ready for promotion to Record
    """
    return RecordCandidate(
        natural_key=key,
        published_at=datetime.now(UTC),
        content={"title": f"Title for {key}"},
        metadata=Metadata(source="test"),
    )


def make_record(key: str = "test-key", layer: Layer = Layer.BRONZE) -> Record:
    """Create a test record with default values.

    Args:
        key: Natural key for the record
        layer: Layer to assign (default BRONZE)

    Returns:
        Record ready for storage operations
    """
    candidate = make_candidate(key)
    record = Record.from_candidate(candidate, record_id=str(uuid4()))
    if layer != Layer.BRONZE:
        record = record.model_copy(update={"layer": layer})
    return record


@pytest.fixture
async def storage() -> MemoryStorage:
    """Fresh MemoryStorage instance for each test.

    Handles initialization and cleanup automatically.
    """
    s = MemoryStorage()
    await s.initialize()
    yield s
    await s.close()


# =============================================================================
# Basic CRUD Operations
# =============================================================================


class TestMemoryStorageStore:
    """Tests for store operation."""

    async def test_store_and_get(self, storage: MemoryStorage) -> None:
        """Can store and retrieve a record."""
        record = make_record("key-1")
        await storage.store(record)

        retrieved = await storage.get(record.id)
        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.natural_key == record.natural_key

    async def test_store_overwrites_existing(self, storage: MemoryStorage) -> None:
        """Storing with same ID overwrites existing record."""
        record = make_record("key-1")
        await storage.store(record)

        # Update and store again
        updated = record.model_copy(update={"content": {"title": "Updated Title"}})
        await storage.store(updated)

        retrieved = await storage.get(record.id)
        assert retrieved is not None
        assert retrieved.content["title"] == "Updated Title"


class TestMemoryStorageGet:
    """Tests for get operations."""

    async def test_get_nonexistent_returns_none(self, storage: MemoryStorage) -> None:
        """Getting nonexistent record returns None."""
        result = await storage.get("does-not-exist")
        assert result is None

    async def test_get_by_natural_key(self, storage: MemoryStorage) -> None:
        """Can retrieve by natural key."""
        record = make_record("unique-key")
        await storage.store(record)

        retrieved = await storage.get_by_natural_key("unique-key")
        assert retrieved is not None
        assert retrieved.id == record.id

    async def test_get_by_natural_key_nonexistent(self, storage: MemoryStorage) -> None:
        """Getting by nonexistent natural key returns None."""
        result = await storage.get_by_natural_key("nonexistent")
        assert result is None


class TestMemoryStorageExists:
    """Tests for existence checks."""

    async def test_exists_by_id(self, storage: MemoryStorage) -> None:
        """Exists check works by ID."""
        record = make_record()
        assert not await storage.exists(record.id)

        await storage.store(record)
        assert await storage.exists(record.id)

    async def test_exists_by_natural_key(self, storage: MemoryStorage) -> None:
        """Natural key exists check works."""
        record = make_record("check-key")
        assert not await storage.exists_by_natural_key("check-key")

        await storage.store(record)
        assert await storage.exists_by_natural_key("check-key")


class TestMemoryStorageDelete:
    """Tests for delete operation."""

    async def test_delete_existing(self, storage: MemoryStorage) -> None:
        """Can delete an existing record."""
        record = make_record()
        await storage.store(record)

        assert await storage.delete(record.id)
        assert not await storage.exists(record.id)

    async def test_delete_nonexistent(self, storage: MemoryStorage) -> None:
        """Deleting nonexistent record returns False."""
        assert not await storage.delete("nonexistent")

    async def test_delete_removes_natural_key_mapping(self, storage: MemoryStorage) -> None:
        """Deleting also removes natural key index."""
        record = make_record("indexed-key")
        await storage.store(record)

        await storage.delete(record.id)
        assert not await storage.exists_by_natural_key("indexed-key")


# =============================================================================
# Query Operations
# =============================================================================


class TestMemoryStorageQuery:
    """Tests for query operations."""

    async def test_query_all(self, storage: MemoryStorage) -> None:
        """Can query all records."""
        for i in range(5):
            await storage.store(make_record(f"key-{i}"))

        records = [r async for r in storage.query()]
        assert len(records) == 5

    async def test_query_by_layer(self, storage: MemoryStorage) -> None:
        """Can filter by layer."""
        await storage.store(make_record("bronze-1", Layer.BRONZE))
        await storage.store(make_record("silver-1", Layer.SILVER))
        await storage.store(make_record("silver-2", Layer.SILVER))

        bronze = [r async for r in storage.query(layer=Layer.BRONZE)]
        silver = [r async for r in storage.query(layer=Layer.SILVER)]

        assert len(bronze) == 1
        assert len(silver) == 2

    async def test_query_by_multiple_layers(self, storage: MemoryStorage) -> None:
        """Can filter by multiple layers (if supported)."""
        await storage.store(make_record("bronze-1", Layer.BRONZE))
        await storage.store(make_record("silver-1", Layer.SILVER))
        await storage.store(make_record("gold-1", Layer.GOLD))

        # Query bronze only
        bronze = [r async for r in storage.query(layer=Layer.BRONZE)]
        assert len(bronze) == 1
        assert all(r.layer == Layer.BRONZE for r in bronze)

    async def test_query_pagination(self, storage: MemoryStorage) -> None:
        """Pagination works correctly."""
        for i in range(10):
            await storage.store(make_record(f"key-{i:02d}"))

        page1 = [r async for r in storage.query(limit=3, offset=0)]
        page2 = [r async for r in storage.query(limit=3, offset=3)]

        assert len(page1) == 3
        assert len(page2) == 3
        # Pages should not overlap
        page1_ids = {r.id for r in page1}
        page2_ids = {r.id for r in page2}
        assert not page1_ids.intersection(page2_ids)

    async def test_query_limit_only(self, storage: MemoryStorage) -> None:
        """Can limit without offset."""
        for i in range(10):
            await storage.store(make_record(f"key-{i}"))

        limited = [r async for r in storage.query(limit=5)]
        assert len(limited) == 5

    async def test_query_empty_storage(self, storage: MemoryStorage) -> None:
        """Query on empty storage returns empty iterator."""
        records = [r async for r in storage.query()]
        assert len(records) == 0


class TestMemoryStorageCount:
    """Tests for count operation."""

    async def test_count_all(self, storage: MemoryStorage) -> None:
        """Count returns total record count."""
        for i in range(5):
            await storage.store(make_record(f"key-{i}"))

        assert await storage.count() == 5

    async def test_count_by_layer(self, storage: MemoryStorage) -> None:
        """Count can filter by layer."""
        await storage.store(make_record("bronze-1", Layer.BRONZE))
        await storage.store(make_record("bronze-2", Layer.BRONZE))
        await storage.store(make_record("silver-1", Layer.SILVER))

        assert await storage.count(layer=Layer.BRONZE) == 2
        assert await storage.count(layer=Layer.SILVER) == 1
        assert await storage.count(layer=Layer.GOLD) == 0

    async def test_count_empty_storage(self, storage: MemoryStorage) -> None:
        """Count on empty storage returns 0."""
        assert await storage.count() == 0


# =============================================================================
# Sighting Operations
# =============================================================================


class TestMemoryStorageSightings:
    """Tests for sighting tracking operations."""

    async def test_record_sighting(self, storage: MemoryStorage) -> None:
        """Can record a sighting."""
        sighting = Sighting(
            id="s1",
            natural_key="tracked-key",
            source="test-source",
            is_new=True,
        )
        await storage.record_sighting(sighting)

        sightings = await storage.get_sightings("tracked-key")
        assert len(sightings) == 1
        assert sightings[0].id == "s1"

    async def test_first_sighting_returns_true(self, storage: MemoryStorage) -> None:
        """First sighting of a key returns True."""
        sighting = Sighting(
            id="s1",
            natural_key="brand-new-key",
            source="test",
            is_new=True,
        )
        is_new = await storage.record_sighting(sighting)
        assert is_new

    async def test_subsequent_sighting_returns_false(self, storage: MemoryStorage) -> None:
        """Subsequent sightings return False after first.

        Note: The record_sighting method checks if this is the first
        sighting ever for this natural_key, regardless of is_new flag.
        """
        # First sighting - should return True (first time seen)
        sighting1 = Sighting(
            id="s1",
            natural_key="repeated-key",
            source="test",
            is_new=True,
        )
        first_result = await storage.record_sighting(sighting1)
        assert first_result  # First sighting is always new

        # Second sighting - should return False (already seen)
        sighting2 = Sighting(
            id="s2",
            natural_key="repeated-key",
            source="test",
            is_new=False,
        )
        is_new = await storage.record_sighting(sighting2)
        assert not is_new  # Not new anymore

    async def test_get_sightings(self, storage: MemoryStorage) -> None:
        """Can retrieve sighting history for a key."""
        for i in range(3):
            sighting = Sighting(
                id=f"s{i}",
                natural_key="multi-sight-key",
                source="test",
                is_new=i == 0,
            )
            await storage.record_sighting(sighting)

        sightings = await storage.get_sightings("multi-sight-key")
        assert len(sightings) == 3

    async def test_get_sightings_empty(self, storage: MemoryStorage) -> None:
        """Getting sightings for unknown key returns empty list."""
        sightings = await storage.get_sightings("never-seen")
        assert sightings == []


# =============================================================================
# Lifecycle Operations
# =============================================================================


class TestMemoryStorageLifecycle:
    """Tests for storage lifecycle (initialize/close)."""

    async def test_initialize_idempotent(self) -> None:
        """Initialize can be called multiple times safely."""
        storage = MemoryStorage()
        await storage.initialize()
        await storage.initialize()  # Should not raise
        await storage.close()

    async def test_close_idempotent(self) -> None:
        """Close can be called multiple times safely."""
        storage = MemoryStorage()
        await storage.initialize()
        await storage.close()
        await storage.close()  # Should not raise

    async def test_close_clears_data(self) -> None:
        """Close clears in-memory data (intentional cleanup behavior)."""
        storage = MemoryStorage()
        await storage.initialize()

        record = make_record()
        await storage.store(record)

        # Verify stored
        assert await storage.exists(record.id)

        await storage.close()

        # After close, memory storage clears its data
        # This is correct behavior for cleanup
        retrieved = await storage.get(record.id)
        assert retrieved is None  # Data cleared on close


# =============================================================================
# Protocol Compliance (basic verification)
# =============================================================================


class TestMemoryStorageProtocolCompliance:
    """Verify MemoryStorage implements StorageBackend correctly."""

    def test_has_required_methods(self) -> None:
        """MemoryStorage has all required protocol methods."""
        storage = MemoryStorage()

        # Check all required methods exist
        assert hasattr(storage, "initialize")
        assert hasattr(storage, "close")
        assert hasattr(storage, "store")
        assert hasattr(storage, "get")
        assert hasattr(storage, "get_by_natural_key")
        assert hasattr(storage, "exists")
        assert hasattr(storage, "exists_by_natural_key")
        assert hasattr(storage, "delete")
        assert hasattr(storage, "query")
        assert hasattr(storage, "count")
        assert hasattr(storage, "record_sighting")
        assert hasattr(storage, "get_sightings")

    def test_methods_are_async(self) -> None:
        """All async methods are properly async."""
        import inspect

        storage = MemoryStorage()
        async_methods = [
            "initialize",
            "close",
            "store",
            "get",
            "get_by_natural_key",
            "exists",
            "exists_by_natural_key",
            "delete",
            "count",
            "record_sighting",
            "get_sightings",
        ]

        for method_name in async_methods:
            method = getattr(storage, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} should be async"

    def test_query_is_async_generator(self) -> None:
        """Query method returns async generator."""
        import inspect

        storage = MemoryStorage()
        assert inspect.isasyncgenfunction(storage.query)
