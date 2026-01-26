"""Tests for file-based feed adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

from feedspine.adapter.file import (
    DiffableFileFeedAdapter,
    FileFeedAdapter,
    FileSnapshot,
    SnapshotDiff,
)
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


class MockFileFeedAdapter(FileFeedAdapter):
    """Mock file adapter for testing."""

    def __init__(
        self,
        name: str = "mock-file",
        source_url: str = "test://file",
        content: bytes = b"",
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, source_url=source_url, **kwargs)
        self._content = content

    def set_content(self, content: bytes) -> None:
        """Set the file content for next fetch."""
        self._content = content

    async def _fetch_file(self) -> bytes:
        return self._content

    async def _parse_file(self, content: bytes) -> AsyncIterator[dict[str, Any]]:
        # Simple line-based parser
        for i, line in enumerate(content.decode().strip().split("\n")):
            if line:
                parts = line.split(",")
                yield {"id": parts[0], "data": parts[1] if len(parts) > 1 else ""}

    def _row_to_candidate(
        self,
        row: dict[str, Any],
        index: int,
    ) -> RecordCandidate:
        return RecordCandidate(
            natural_key=f"file:{row['id']}",
            content=row,
            metadata=Metadata(source=self.name),
            published_at=datetime.now(UTC),
        )


class MockDiffableAdapter(DiffableFileFeedAdapter):
    """Mock diffable adapter for testing."""

    def __init__(
        self,
        name: str = "mock-diff",
        source_url: str = "test://diff",
        content: bytes = b"",
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, source_url=source_url, **kwargs)
        self._content = content

    def set_content(self, content: bytes) -> None:
        self._content = content

    async def _fetch_file(self) -> bytes:
        return self._content

    async def _parse_file(self, content: bytes) -> AsyncIterator[dict[str, Any]]:
        for line in content.decode().strip().split("\n"):
            if line:
                parts = line.split(",")
                yield {"id": parts[0], "value": parts[1] if len(parts) > 1 else ""}

    def _row_to_candidate(
        self,
        row: dict[str, Any],
        index: int,
    ) -> RecordCandidate:
        return RecordCandidate(
            natural_key=f"diff:{row['id']}",
            content=row,
            metadata=Metadata(source=self.name),
            published_at=datetime.now(UTC),
        )

    def _get_key_from_row(self, row: dict[str, Any]) -> str:
        return row["id"]


# =============================================================================
# FileSnapshot Tests
# =============================================================================


class TestFileSnapshot:
    """Tests for FileSnapshot class."""

    def test_create_snapshot(self) -> None:
        """Test creating a file snapshot."""
        snapshot = FileSnapshot(
            path="/data/index.idx",
            content_hash="abc123",
            fetched_at=datetime.now(UTC),
            row_count=1000,
        )
        assert snapshot.path == "/data/index.idx"
        assert snapshot.content_hash == "abc123"
        assert snapshot.row_count == 1000

    def test_snapshot_equality(self) -> None:
        """Test snapshot equality based on hash."""
        s1 = FileSnapshot(
            path="/a", content_hash="hash1", fetched_at=datetime.now(UTC)
        )
        s2 = FileSnapshot(
            path="/b", content_hash="hash1", fetched_at=datetime.now(UTC)
        )
        s3 = FileSnapshot(
            path="/a", content_hash="hash2", fetched_at=datetime.now(UTC)
        )

        assert s1 == s2  # Same hash
        assert s1 != s3  # Different hash

    def test_has_changed_no_previous(self) -> None:
        """Test has_changed with no previous snapshot."""
        current = FileSnapshot(
            path="/data", content_hash="new", fetched_at=datetime.now(UTC)
        )
        assert current.has_changed(None) is True

    def test_has_changed_same_hash(self) -> None:
        """Test has_changed with same hash."""
        old = FileSnapshot(
            path="/data", content_hash="same", fetched_at=datetime.now(UTC)
        )
        new = FileSnapshot(
            path="/data", content_hash="same", fetched_at=datetime.now(UTC)
        )
        assert new.has_changed(old) is False

    def test_has_changed_different_hash(self) -> None:
        """Test has_changed with different hash."""
        old = FileSnapshot(
            path="/data", content_hash="old", fetched_at=datetime.now(UTC)
        )
        new = FileSnapshot(
            path="/data", content_hash="new", fetched_at=datetime.now(UTC)
        )
        assert new.has_changed(old) is True


# =============================================================================
# SnapshotDiff Tests
# =============================================================================


class TestSnapshotDiff:
    """Tests for SnapshotDiff class."""

    def test_empty_diff(self) -> None:
        """Test empty diff has no changes."""
        diff = SnapshotDiff()
        assert diff.has_changes is False
        assert diff.summary == {
            "added": 0,
            "removed": 0,
            "modified": 0,
            "unchanged": 0,
        }

    def test_add_new(self) -> None:
        """Test adding new items."""
        diff = SnapshotDiff()
        diff.add_new("key1", {"data": "new"})
        diff.add_new("key2", {"data": "also new"})

        assert diff.has_changes is True
        assert len(diff.added) == 2
        assert "key1" in diff.added

    def test_add_removed(self) -> None:
        """Test adding removed items."""
        diff = SnapshotDiff()
        diff.add_removed("key1", {"data": "old"})

        assert diff.has_changes is True
        assert len(diff.removed) == 1

    def test_add_modified(self) -> None:
        """Test adding modified items."""
        diff = SnapshotDiff()
        diff.add_modified("key1", {"v": 1}, {"v": 2})

        assert diff.has_changes is True
        assert len(diff.modified) == 1
        assert diff.modified["key1"] == ({"v": 1}, {"v": 2})

    def test_increment_unchanged(self) -> None:
        """Test incrementing unchanged count."""
        diff = SnapshotDiff()
        diff.increment_unchanged()
        diff.increment_unchanged()

        assert diff.unchanged_count == 2
        assert diff.has_changes is False  # Unchanged doesn't count as change

    def test_summary(self) -> None:
        """Test diff summary."""
        diff = SnapshotDiff()
        diff.add_new("a", {})
        diff.add_new("b", {})
        diff.add_removed("c", {})
        diff.add_modified("d", {}, {})
        diff.increment_unchanged()
        diff.increment_unchanged()
        diff.increment_unchanged()

        assert diff.summary == {
            "added": 2,
            "removed": 1,
            "modified": 1,
            "unchanged": 3,
        }


# =============================================================================
# FileFeedAdapter Tests
# =============================================================================


class TestFileFeedAdapter:
    """Tests for FileFeedAdapter class."""

    async def test_fetch_basic(self) -> None:
        """Test basic file fetch."""
        adapter = MockFileFeedAdapter(content=b"id1,data1\nid2,data2\nid3,data3")

        candidates = [c async for c in adapter.fetch()]

        assert len(candidates) == 3
        assert candidates[0].natural_key == "file:id1"
        assert candidates[1].content["data"] == "data2"

    async def test_compute_hash(self) -> None:
        """Test hash computation."""
        adapter = MockFileFeedAdapter()
        hash1 = adapter.compute_hash(b"content1")
        hash2 = adapter.compute_hash(b"content1")
        hash3 = adapter.compute_hash(b"content2")

        assert hash1 == hash2  # Same content = same hash
        assert hash1 != hash3  # Different content = different hash
        assert len(hash1) == 64  # SHA-256 hex

    async def test_snapshot_tracking(self) -> None:
        """Test that snapshots are tracked."""
        adapter = MockFileFeedAdapter(content=b"id1,data1")

        assert adapter.last_snapshot is None

        _ = [c async for c in adapter.fetch()]

        assert adapter.last_snapshot is not None
        assert adapter.last_snapshot.row_count == 1

    async def test_change_detection_unchanged(self) -> None:
        """Test change detection skips unchanged files."""
        adapter = MockFileFeedAdapter(
            content=b"id1,data1",
            track_changes=True,
        )

        # First fetch
        candidates1 = [c async for c in adapter.fetch()]
        assert len(candidates1) == 1

        # Second fetch with same content - should skip
        candidates2 = [c async for c in adapter.fetch()]
        assert len(candidates2) == 0

    async def test_change_detection_changed(self) -> None:
        """Test change detection processes changed files."""
        adapter = MockFileFeedAdapter(
            content=b"id1,data1",
            track_changes=True,
        )

        # First fetch
        _ = [c async for c in adapter.fetch()]

        # Change content
        adapter.set_content(b"id1,data1\nid2,data2")

        # Second fetch should process new file
        candidates = [c async for c in adapter.fetch()]
        assert len(candidates) == 2

    async def test_change_detection_disabled(self) -> None:
        """Test that disabling change detection always fetches."""
        adapter = MockFileFeedAdapter(
            content=b"id1,data1",
            track_changes=False,
        )

        # First fetch
        c1 = [c async for c in adapter.fetch()]
        assert len(c1) == 1

        # Second fetch without change - should still fetch
        c2 = [c async for c in adapter.fetch()]
        assert len(c2) == 1

    async def test_has_changed(self) -> None:
        """Test has_changed method."""
        adapter = MockFileFeedAdapter(content=b"original")

        # No previous snapshot
        assert await adapter.has_changed() is True

        # Fetch to create snapshot
        _ = [c async for c in adapter.fetch()]

        # Same content
        assert await adapter.has_changed() is False

        # Different content
        adapter.set_content(b"changed")
        assert await adapter.has_changed() is True

    async def test_emit_only_new(self) -> None:
        """Test emit_only_new deduplication."""
        adapter = MockFileFeedAdapter(
            content=b"id1,v1\nid2,v1",
            emit_only_new=True,
            track_changes=False,
        )

        # First fetch
        c1 = [c async for c in adapter.fetch()]
        assert len(c1) == 2

        # Second fetch with same keys - should skip
        c2 = [c async for c in adapter.fetch()]
        assert len(c2) == 0

        # Add new key
        adapter.set_content(b"id1,v1\nid2,v1\nid3,v1")
        c3 = [c async for c in adapter.fetch()]
        assert len(c3) == 1
        assert c3[0].natural_key == "file:id3"

    async def test_clear_seen_keys(self) -> None:
        """Test clearing seen keys resets deduplication."""
        adapter = MockFileFeedAdapter(
            content=b"id1,data",
            emit_only_new=True,
            track_changes=False,
        )

        _ = [c async for c in adapter.fetch()]
        c1 = [c async for c in adapter.fetch()]
        assert len(c1) == 0

        adapter.clear_seen_keys()
        c2 = [c async for c in adapter.fetch()]
        assert len(c2) == 1


# =============================================================================
# DiffableFileFeedAdapter Tests
# =============================================================================


class TestDiffableFileFeedAdapter:
    """Tests for DiffableFileFeedAdapter class."""

    async def test_compute_diff_initial(self) -> None:
        """Test diff computation with no previous data."""
        adapter = MockDiffableAdapter(content=b"a,1\nb,2\nc,3")

        diff = await adapter.compute_diff()

        assert len(diff.added) == 3
        assert len(diff.removed) == 0
        assert len(diff.modified) == 0

    async def test_compute_diff_with_additions(self) -> None:
        """Test diff with new records added."""
        adapter = MockDiffableAdapter(content=b"a,1\nb,2")

        # Initial diff
        diff1 = await adapter.compute_diff()
        adapter.commit_snapshot()

        # Add new record
        adapter.set_content(b"a,1\nb,2\nc,3")
        diff2 = await adapter.compute_diff()

        assert len(diff2.added) == 1
        assert "c" in diff2.added
        assert diff2.unchanged_count == 2

    async def test_compute_diff_with_removals(self) -> None:
        """Test diff with records removed."""
        adapter = MockDiffableAdapter(content=b"a,1\nb,2\nc,3")

        diff1 = await adapter.compute_diff()
        adapter.commit_snapshot()

        # Remove a record
        adapter.set_content(b"a,1\nc,3")
        diff2 = await adapter.compute_diff()

        assert len(diff2.removed) == 1
        assert "b" in diff2.removed

    async def test_compute_diff_with_modifications(self) -> None:
        """Test diff with modified records."""
        adapter = MockDiffableAdapter(content=b"a,1\nb,2")

        diff1 = await adapter.compute_diff()
        adapter.commit_snapshot()

        # Modify a record
        adapter.set_content(b"a,1\nb,CHANGED")
        diff2 = await adapter.compute_diff()

        assert len(diff2.modified) == 1
        assert "b" in diff2.modified
        assert diff2.modified["b"] == ({"id": "b", "value": "2"}, {"id": "b", "value": "CHANGED"})

    async def test_fetch_diff_only(self) -> None:
        """Test fetching only changed records."""
        adapter = MockDiffableAdapter(content=b"a,1\nb,2\nc,3")

        # Initial fetch gets all
        candidates1 = [c async for c in adapter.fetch_diff_only()]
        assert len(candidates1) == 3

        # Add one, modify one
        adapter.set_content(b"a,1\nb,CHANGED\nc,3\nd,4")
        candidates2 = [c async for c in adapter.fetch_diff_only()]

        # Should get new (d) and modified (b)
        assert len(candidates2) == 2
        keys = {c.natural_key for c in candidates2}
        assert "diff:d" in keys
        assert "diff:b" in keys

    async def test_reset_baseline(self) -> None:
        """Test resetting diff baseline."""
        adapter = MockDiffableAdapter(content=b"a,1\nb,2")

        _ = await adapter.compute_diff()
        adapter.commit_snapshot()

        # Reset
        adapter.reset_baseline()

        # Should treat all as new again
        diff = await adapter.compute_diff()
        assert len(diff.added) == 2


# =============================================================================
# Large File Tests
# =============================================================================


class TestLargeFileHandling:
    """Tests for handling large files (100k+ rows)."""

    async def test_large_file_fetch(self) -> None:
        """Test fetching a large file."""
        # Generate 10,000 rows (scaled down for test speed)
        rows = [f"id{i},data{i}" for i in range(10000)]
        content = "\n".join(rows).encode()

        adapter = MockFileFeedAdapter(content=content)
        candidates = [c async for c in adapter.fetch()]

        assert len(candidates) == 10000

    async def test_large_file_diff(self) -> None:
        """Test diffing large files."""
        # Initial file with 1000 rows
        rows1 = [f"id{i},v1" for i in range(1000)]
        adapter = MockDiffableAdapter(content="\n".join(rows1).encode())

        _ = await adapter.compute_diff()
        adapter.commit_snapshot()

        # Modified file: change 10 rows, add 5, remove 5
        rows2 = [f"id{i},v1" for i in range(995)]  # Remove last 5
        rows2[10:20] = [f"id{i},CHANGED" for i in range(10, 20)]  # Modify 10
        rows2.extend([f"id{i},new" for i in range(1000, 1005)])  # Add 5

        adapter.set_content("\n".join(rows2).encode())
        diff = await adapter.compute_diff()

        assert len(diff.added) == 5
        assert len(diff.removed) == 5
        assert len(diff.modified) == 10
