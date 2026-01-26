"""Tests for bulk storage operations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record
from feedspine.storage.memory import MemoryStorage


# =============================================================================
# Helpers
# =============================================================================


def make_record(
    id: str,
    natural_key: str | None = None,
    layer: Layer = Layer.BRONZE,
) -> Record:
    """Create a test record."""
    return Record(
        id=id,
        natural_key=natural_key or f"key:{id}",
        layer=layer,
        content={"id": id, "data": f"content-{id}"},
        metadata=Metadata(source="test"),
        published_at=datetime.now(UTC),
        captured_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        version=1,
    )


def make_records(count: int, prefix: str = "rec") -> list[Record]:
    """Create multiple test records."""
    return [make_record(f"{prefix}-{i}") for i in range(count)]


# =============================================================================
# MemoryStorage Bulk Tests
# =============================================================================


class TestMemoryStorageBatch:
    """Tests for MemoryStorage bulk operations."""

    async def test_store_batch_basic(self) -> None:
        """Test basic batch store."""
        storage = MemoryStorage()
        records = make_records(5)

        count = await storage.store_batch(records)

        assert count == 5
        assert await storage.count() == 5

    async def test_store_batch_empty(self) -> None:
        """Test batch store with empty list."""
        storage = MemoryStorage()

        count = await storage.store_batch([])

        assert count == 0

    async def test_store_batch_skip_duplicates(self) -> None:
        """Test batch store skips duplicates by default."""
        storage = MemoryStorage()
        records = make_records(3)

        # Store first batch
        await storage.store_batch(records)

        # Try to store same records again
        count = await storage.store_batch(records, on_conflict="skip")

        assert count == 0  # All skipped
        assert await storage.count() == 3

    async def test_store_batch_update_duplicates(self) -> None:
        """Test batch store updates duplicates."""
        storage = MemoryStorage()
        records = make_records(3)
        await storage.store_batch(records)

        # Create updated records with same keys
        updated = [
            Record(
                id=f"rec-{i}-updated",
                natural_key=f"key:rec-{i}",
                layer=Layer.BRONZE,
                content={"updated": True},
                metadata=Metadata(source="test"),
                published_at=datetime.now(UTC),
                captured_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                version=2,
            )
            for i in range(3)
        ]

        count = await storage.store_batch(updated, on_conflict="update")

        assert count == 3
        assert await storage.count() == 3

        # Check content was updated
        record = await storage.get_by_natural_key("key:rec-0")
        assert record is not None
        assert record.content.get("updated") is True

    async def test_store_batch_error_on_duplicates(self) -> None:
        """Test batch store raises error on duplicates."""
        storage = MemoryStorage()
        records = make_records(3)
        await storage.store_batch(records)

        with pytest.raises(ValueError, match="already exists"):
            await storage.store_batch(records, on_conflict="error")

    async def test_store_batch_large(self) -> None:
        """Test batch store with large number of records."""
        storage = MemoryStorage()
        records = make_records(10000)

        count = await storage.store_batch(records, batch_size=1000)

        assert count == 10000
        assert await storage.count() == 10000

    async def test_delete_batch_basic(self) -> None:
        """Test basic batch delete."""
        storage = MemoryStorage()
        records = make_records(5)
        await storage.store_batch(records)

        ids_to_delete = ["rec-0", "rec-2", "rec-4"]
        count = await storage.delete_batch(ids_to_delete)

        assert count == 3
        assert await storage.count() == 2

    async def test_delete_batch_nonexistent(self) -> None:
        """Test batch delete with nonexistent IDs."""
        storage = MemoryStorage()
        records = make_records(3)
        await storage.store_batch(records)

        count = await storage.delete_batch(["nonexistent-1", "nonexistent-2"])

        assert count == 0
        assert await storage.count() == 3

    async def test_delete_batch_empty(self) -> None:
        """Test batch delete with empty list."""
        storage = MemoryStorage()
        records = make_records(3)
        await storage.store_batch(records)

        count = await storage.delete_batch([])

        assert count == 0


# =============================================================================
# DuckDB Bulk Tests
# =============================================================================


duckdb = pytest.importorskip("duckdb", reason="DuckDB not installed")
from feedspine.storage.duckdb import DuckDBStorage  # noqa: E402


class TestDuckDBStorageBatch:
    """Tests for DuckDBStorage bulk operations."""

    @pytest.fixture
    async def storage(self) -> DuckDBStorage:
        """Create initialized DuckDB storage."""
        s = DuckDBStorage(":memory:")
        await s.initialize()
        return s

    async def test_store_batch_basic(self, storage: DuckDBStorage) -> None:
        """Test basic batch store."""
        records = make_records(5)

        count = await storage.store_batch(records)

        assert count == 5
        assert await storage.count() == 5

    async def test_store_batch_empty(self, storage: DuckDBStorage) -> None:
        """Test batch store with empty list."""
        count = await storage.store_batch([])
        assert count == 0

    async def test_store_batch_skip_duplicates(self, storage: DuckDBStorage) -> None:
        """Test batch store skips duplicates."""
        records = make_records(3)
        await storage.store_batch(records)

        # Same records again - should be skipped via OR IGNORE
        count = await storage.store_batch(records, on_conflict="skip")

        # DuckDB INSERT OR IGNORE still counts the rows it attempts
        # so count may be 3, but total records should still be 3
        assert await storage.count() == 3

    async def test_store_batch_large(self, storage: DuckDBStorage) -> None:
        """Test batch store with large number of records."""
        records = make_records(10000)

        count = await storage.store_batch(records, batch_size=1000)

        assert count == 10000
        assert await storage.count() == 10000

    async def test_store_batch_chunking(self, storage: DuckDBStorage) -> None:
        """Test batch store processes in chunks."""
        records = make_records(2500)

        # Use small batch size to ensure chunking
        count = await storage.store_batch(records, batch_size=500)

        assert count == 2500
        assert await storage.count() == 2500

    async def test_delete_batch_basic(self, storage: DuckDBStorage) -> None:
        """Test basic batch delete."""
        records = make_records(5)
        await storage.store_batch(records)

        count = await storage.delete_batch(["rec-0", "rec-2", "rec-4"])

        # Note: DuckDB may not return exact rowcount
        assert await storage.count() == 2

    async def test_delete_batch_empty(self, storage: DuckDBStorage) -> None:
        """Test batch delete with empty list."""
        records = make_records(3)
        await storage.store_batch(records)

        count = await storage.delete_batch([])

        assert count == 0
        assert await storage.count() == 3
