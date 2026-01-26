"""Tests for feedspine.core.checkpoint."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from feedspine.core.checkpoint import (
    Checkpoint,
    CheckpointManager,
    FileCheckpointStore,
    MemoryCheckpointStore,
)


class TestCheckpointBasic:
    """Basic Checkpoint tests."""

    def test_create_minimal(self) -> None:
        """Can create with required fields."""
        cp = Checkpoint(collection_id="run-001", feed_name="my-feed")
        assert cp.collection_id == "run-001"
        assert cp.feed_name == "my-feed"
        assert cp.records_processed == 0
        assert cp.is_complete is False

    def test_create_full(self) -> None:
        """Can create with all fields."""
        cp = Checkpoint(
            collection_id="run-001",
            feed_name="my-feed",
            position={"page": 5},
            records_processed=1000,
            records_new=900,
            records_duplicate=100,
            records_failed=0,
        )
        assert cp.position == {"page": 5}
        assert cp.records_processed == 1000
        assert cp.records_new == 900


class TestCheckpointUpdate:
    """Checkpoint update tests."""

    def test_update_records(self) -> None:
        """Can update record counts."""
        cp = Checkpoint(collection_id="run-001", feed_name="feed")
        updated = cp.update(records_processed=100, records_new=80)
        assert updated.records_processed == 100
        assert updated.records_new == 80
        assert cp.records_processed == 0  # Original unchanged

    def test_update_position(self) -> None:
        """Can update position."""
        cp = Checkpoint(collection_id="run-001", feed_name="feed")
        updated = cp.update(position={"cursor": "abc123"})
        assert updated.position == {"cursor": "abc123"}

    def test_update_preserves_id(self) -> None:
        """Update preserves collection_id and feed_name."""
        cp = Checkpoint(collection_id="run-001", feed_name="my-feed")
        updated = cp.update(records_processed=50)
        assert updated.collection_id == "run-001"
        assert updated.feed_name == "my-feed"


class TestCheckpointComplete:
    """Checkpoint completion tests."""

    def test_mark_complete(self) -> None:
        """Can mark checkpoint as complete."""
        cp = Checkpoint(collection_id="run-001", feed_name="feed")
        assert cp.is_complete is False
        completed = cp.mark_complete()
        assert completed.is_complete is True
        assert cp.is_complete is False  # Original unchanged


class TestCheckpointSerialization:
    """Checkpoint serialization tests."""

    def test_to_dict(self) -> None:
        """Can convert to dict."""
        cp = Checkpoint(
            collection_id="run-001",
            feed_name="feed",
            records_processed=100,
        )
        d = cp.to_dict()
        assert d["collection_id"] == "run-001"
        assert d["feed_name"] == "feed"
        assert d["records_processed"] == 100

    def test_from_dict(self) -> None:
        """Can create from dict."""
        d = {
            "collection_id": "run-001",
            "feed_name": "feed",
            "position": {"page": 2},
            "records_processed": 50,
            "records_new": 40,
            "records_duplicate": 10,
            "records_failed": 0,
            "started_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T01:00:00+00:00",
            "metadata": {},
            "is_complete": False,
        }
        cp = Checkpoint.from_dict(d)
        assert cp.collection_id == "run-001"
        assert cp.position == {"page": 2}
        assert cp.records_processed == 50

    def test_roundtrip(self) -> None:
        """Can roundtrip through dict."""
        original = Checkpoint(
            collection_id="run-001",
            feed_name="feed",
            position={"cursor": "xyz"},
            records_processed=100,
        )
        restored = Checkpoint.from_dict(original.to_dict())
        assert restored.collection_id == original.collection_id
        assert restored.position == original.position
        assert restored.records_processed == original.records_processed


class TestMemoryCheckpointStore:
    """MemoryCheckpointStore tests."""

    @pytest.fixture
    def store(self) -> MemoryCheckpointStore:
        """Create a memory store."""
        return MemoryCheckpointStore()

    async def test_save_and_load(self, store: MemoryCheckpointStore) -> None:
        """Can save and load checkpoint."""
        cp = Checkpoint(collection_id="run-001", feed_name="feed")
        await store.save(cp)
        loaded = await store.load("run-001")
        assert loaded is not None
        assert loaded.collection_id == "run-001"

    async def test_load_missing(self, store: MemoryCheckpointStore) -> None:
        """Loading missing checkpoint returns None."""
        loaded = await store.load("does-not-exist")
        assert loaded is None

    async def test_delete(self, store: MemoryCheckpointStore) -> None:
        """Can delete checkpoint."""
        cp = Checkpoint(collection_id="run-001", feed_name="feed")
        await store.save(cp)
        assert await store.delete("run-001") is True
        assert await store.load("run-001") is None

    async def test_delete_missing(self, store: MemoryCheckpointStore) -> None:
        """Deleting missing checkpoint returns False."""
        assert await store.delete("does-not-exist") is False

    async def test_list_incomplete(self, store: MemoryCheckpointStore) -> None:
        """Can list incomplete checkpoints."""
        cp1 = Checkpoint(collection_id="run-001", feed_name="feed-a")
        cp2 = Checkpoint(collection_id="run-002", feed_name="feed-a")
        cp3 = Checkpoint(collection_id="run-003", feed_name="feed-b")
        cp4 = Checkpoint(collection_id="run-004", feed_name="feed-a").mark_complete()

        await store.save(cp1)
        await store.save(cp2)
        await store.save(cp3)
        await store.save(cp4)

        # All incomplete
        all_incomplete = await store.list_incomplete()
        assert len(all_incomplete) == 3

        # Filter by feed
        feed_a = await store.list_incomplete("feed-a")
        assert len(feed_a) == 2


class TestFileCheckpointStore:
    """FileCheckpointStore tests."""

    @pytest.fixture
    def store(self) -> FileCheckpointStore:
        """Create a file store in temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield FileCheckpointStore(Path(tmpdir))

    async def test_save_and_load(self, store: FileCheckpointStore) -> None:
        """Can save and load checkpoint."""
        cp = Checkpoint(collection_id="run-001", feed_name="feed")
        await store.save(cp)
        loaded = await store.load("run-001")
        assert loaded is not None
        assert loaded.collection_id == "run-001"

    async def test_load_missing(self, store: FileCheckpointStore) -> None:
        """Loading missing checkpoint returns None."""
        loaded = await store.load("does-not-exist")
        assert loaded is None

    async def test_delete(self, store: FileCheckpointStore) -> None:
        """Can delete checkpoint."""
        cp = Checkpoint(collection_id="run-001", feed_name="feed")
        await store.save(cp)
        assert await store.delete("run-001") is True
        assert await store.load("run-001") is None


class TestCheckpointManager:
    """CheckpointManager tests."""

    @pytest.fixture
    def store(self) -> MemoryCheckpointStore:
        """Create a memory store."""
        return MemoryCheckpointStore()

    @pytest.fixture
    def manager(self, store: MemoryCheckpointStore) -> CheckpointManager:
        """Create a checkpoint manager."""
        return CheckpointManager(store, save_interval=10)

    def test_start(self, manager: CheckpointManager) -> None:
        """Can start a new checkpoint."""
        cp = manager.start("run-001", "my-feed")
        assert cp.collection_id == "run-001"
        assert cp.feed_name == "my-feed"

    def test_start_with_position(self, manager: CheckpointManager) -> None:
        """Can start with initial position."""
        cp = manager.start("run-001", "feed", position={"page": 1})
        assert cp.position == {"page": 1}

    async def test_resume(self, store: MemoryCheckpointStore, manager: CheckpointManager) -> None:
        """Can resume from existing checkpoint."""
        # Save a checkpoint directly
        existing = Checkpoint(
            collection_id="run-001",
            feed_name="feed",
            records_processed=50,
        )
        await store.save(existing)

        # Resume
        cp = await manager.resume("run-001")
        assert cp is not None
        assert cp.records_processed == 50

    async def test_resume_missing(self, manager: CheckpointManager) -> None:
        """Resume returns None for missing checkpoint."""
        cp = await manager.resume("does-not-exist")
        assert cp is None

    def test_update(self, manager: CheckpointManager) -> None:
        """Can update current checkpoint."""
        manager.start("run-001", "feed")
        cp = manager.update(records_processed=100, records_new=80)
        assert cp.records_processed == 100
        assert cp.records_new == 80

    def test_update_without_start_raises(self, manager: CheckpointManager) -> None:
        """Update without start raises error."""
        with pytest.raises(RuntimeError):
            manager.update(records_processed=100)

    async def test_save(self, store: MemoryCheckpointStore, manager: CheckpointManager) -> None:
        """Can save checkpoint."""
        manager.start("run-001", "feed")
        manager.update(records_processed=50)
        await manager.save()

        loaded = await store.load("run-001")
        assert loaded is not None
        assert loaded.records_processed == 50

    async def test_maybe_save_below_interval(self, manager: CheckpointManager) -> None:
        """maybe_save doesn't save below interval."""
        manager.start("run-001", "feed")
        manager.update(records_processed=5)  # Below interval of 10
        saved = await manager.maybe_save()
        assert saved is False

    async def test_maybe_save_at_interval(self, manager: CheckpointManager) -> None:
        """maybe_save saves at interval."""
        manager.start("run-001", "feed")
        manager.update(records_processed=15)  # Above interval of 10
        saved = await manager.maybe_save()
        assert saved is True

    async def test_complete(self, store: MemoryCheckpointStore, manager: CheckpointManager) -> None:
        """Can mark complete."""
        manager.start("run-001", "feed")
        manager.update(records_processed=100)
        cp = await manager.complete()
        assert cp.is_complete is True

        loaded = await store.load("run-001")
        assert loaded is not None
        assert loaded.is_complete is True

    def test_current_property(self, manager: CheckpointManager) -> None:
        """current property returns current checkpoint."""
        assert manager.current is None
        manager.start("run-001", "feed")
        assert manager.current is not None
        assert manager.current.collection_id == "run-001"

    def test_position_property(self, manager: CheckpointManager) -> None:
        """position property returns current position."""
        assert manager.position == {}
        manager.start("run-001", "feed", position={"page": 5})
        assert manager.position == {"page": 5}
