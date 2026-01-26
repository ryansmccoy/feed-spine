"""File-based feed adapter for snapshot/index files.

Provides adapters for feeds that deliver data as complete files
(e.g., SEC daily/quarterly index files) rather than streaming updates.

Key features:
- Content hash-based change detection
- Diff computation between file versions
- Efficient bulk record generation
- Support for large files (100k+ rows)

Example:
    >>> from feedspine.adapter.file import FileFeedAdapter
    >>> # FileFeedAdapter handles file-based feeds
    >>> hasattr(FileFeedAdapter, "fetch_file")
    True
"""

from __future__ import annotations

import hashlib
from abc import abstractmethod
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from feedspine.adapter.base import BaseFeedAdapter
from feedspine.models.record import RecordCandidate


class FileSnapshot:
    """Represents a snapshot of a file at a point in time.

    Used for change detection and diff computation.

    Attributes:
        path: File path or URL.
        content_hash: SHA-256 hash of file contents.
        fetched_at: When the file was fetched.
        row_count: Number of rows/records in the file.
        metadata: Additional file metadata.

    Example:
        >>> snapshot = FileSnapshot(
        ...     path="/data/index.idx",
        ...     content_hash="abc123...",
        ...     fetched_at=datetime.now(UTC),
        ...     row_count=50000,
        ... )
        >>> snapshot.row_count
        50000
    """

    def __init__(
        self,
        path: str,
        content_hash: str,
        fetched_at: datetime,
        row_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.content_hash = content_hash
        self.fetched_at = fetched_at
        self.row_count = row_count
        self.metadata = metadata or {}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileSnapshot):
            return False
        return self.content_hash == other.content_hash

    def has_changed(self, other: FileSnapshot | None) -> bool:
        """Check if this snapshot differs from another.

        Args:
            other: Previous snapshot to compare against.

        Returns:
            True if content has changed (or other is None).
        """
        if other is None:
            return True
        return self.content_hash != other.content_hash


class FileFeedAdapter(BaseFeedAdapter):
    """Base adapter for file-based feeds (index files, CSVs, etc.).

    Extends BaseFeedAdapter with file-specific functionality:
    - Content hash computation for change detection
    - Snapshot tracking for diff computation
    - Batch processing for large files

    Subclasses implement:
    - _fetch_file(): Download/read the file
    - _parse_file(): Parse file contents into rows
    - _row_to_candidate(): Convert row to RecordCandidate

    Example:
        >>> from feedspine.adapter.file import FileFeedAdapter
        >>> class MyIndexAdapter(FileFeedAdapter):
        ...     async def _fetch_file(self):
        ...         return b"row1\\nrow2\\nrow3"
        ...     async def _parse_file(self, content):
        ...         for line in content.decode().split("\\n"):
        ...             yield {"line": line}
        ...     def _row_to_candidate(self, row, index):
        ...         return RecordCandidate(
        ...             natural_key=f"line-{index}",
        ...             content=row,
        ...             metadata=Metadata(source="test"),
        ...             published_at=datetime.now(UTC),
        ...         )
    """

    def __init__(
        self,
        name: str,
        source_url: str | None = None,
        *,
        track_changes: bool = True,
        emit_only_new: bool = False,
    ) -> None:
        """Initialize file feed adapter.

        Args:
            name: Adapter name/identifier.
            source_url: URL or path of the file source.
            track_changes: Whether to track file changes via hash.
            emit_only_new: If True, only emit records not seen before.
                          Requires storage integration.
        """
        super().__init__(name=name, source_url=source_url)
        self.track_changes = track_changes
        self.emit_only_new = emit_only_new
        self._last_snapshot: FileSnapshot | None = None
        self._seen_keys: set[str] = set()

    @property
    def last_snapshot(self) -> FileSnapshot | None:
        """Get the last file snapshot (for change detection)."""
        return self._last_snapshot

    @abstractmethod
    async def _fetch_file(self) -> bytes:
        """Fetch the file contents.

        Returns:
            Raw file contents as bytes.

        Raises:
            FeedError: If fetch fails.
        """
        ...

    @abstractmethod
    async def _parse_file(self, content: bytes) -> AsyncIterator[dict[str, Any]]:
        """Parse file contents into rows.

        Args:
            content: Raw file contents.

        Yields:
            Parsed row as dictionary.
        """
        ...

    @abstractmethod
    def _row_to_candidate(
        self,
        row: dict[str, Any],
        index: int,
    ) -> RecordCandidate:
        """Convert a parsed row to a RecordCandidate.

        Args:
            row: Parsed row data.
            index: Row index (0-based).

        Returns:
            RecordCandidate for this row.
        """
        ...

    def compute_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content: Content to hash.

        Returns:
            Hex-encoded SHA-256 hash.

        Example:
            >>> adapter = FileFeedAdapter.__new__(FileFeedAdapter)
            >>> adapter.compute_hash(b"test content")[:16]
            '6ae8a75555209fd6'
        """
        return hashlib.sha256(content).hexdigest()

    async def _fetch_items(self) -> list[Any]:
        """Fetch and parse file, returning items.

        Implements BaseFeedAdapter's abstract method.
        Note: This collects all items into memory. For large files,
        use fetch() directly which streams records.
        """
        content = await self._fetch_file()

        # Create snapshot
        content_hash = self.compute_hash(content)
        items = []

        async for row in self._parse_file(content):
            items.append(row)

        # Update snapshot after successful parse
        self._last_snapshot = FileSnapshot(
            path=self.name,
            content_hash=content_hash,
            fetched_at=datetime.now(UTC),
            row_count=len(items),
        )

        return items

    def _to_candidate(self, item: dict[str, Any]) -> RecordCandidate:
        """Convert item to candidate.

        This is called by BaseFeedAdapter.fetch() for each item.
        We delegate to _row_to_candidate with an index.
        """
        # Get index from item if present, otherwise use counter
        index = item.pop("_row_index", 0)
        return self._row_to_candidate(item, index)

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        """Fetch file and yield record candidates.

        Overrides BaseFeedAdapter to add:
        - Change detection (skip if file unchanged)
        - Row indexing for _row_to_candidate
        - Optional filtering of seen records

        Yields:
            RecordCandidate for each row in the file.
        """
        content = await self._fetch_file()
        content_hash = self.compute_hash(content)

        # Check if file has changed
        if (
            self.track_changes
            and self._last_snapshot
            and content_hash == self._last_snapshot.content_hash
        ):
            # File unchanged, yield nothing
            self._last_fetch_at = datetime.now(UTC)
            self._last_fetch_count = 0
            return

        # Parse and yield
        row_count = 0
        async for row in self._parse_file(content):
            candidate = self._row_to_candidate(row, row_count)

            # Optional: skip if we've seen this key before
            if self.emit_only_new:
                if candidate.natural_key in self._seen_keys:
                    row_count += 1
                    continue
                self._seen_keys.add(candidate.natural_key)

            row_count += 1
            yield candidate

        # Update snapshot
        self._last_snapshot = FileSnapshot(
            path=self.name,
            content_hash=content_hash,
            fetched_at=datetime.now(UTC),
            row_count=row_count,
        )

        self._last_fetch_at = datetime.now(UTC)
        self._last_fetch_count = row_count

    async def has_changed(self) -> bool:
        """Check if file has changed since last fetch.

        Fetches just enough to compute hash, then compares.

        Returns:
            True if file has changed or never fetched.

        Example:
            >>> # First call always returns True (no previous snapshot)
            >>> # Subsequent calls compare hashes
        """
        content = await self._fetch_file()
        new_hash = self.compute_hash(content)

        if self._last_snapshot is None:
            return True

        return new_hash != self._last_snapshot.content_hash

    def clear_seen_keys(self) -> None:
        """Clear the set of seen natural keys.

        Call this to reset deduplication state,
        e.g., when starting a new collection period.
        """
        self._seen_keys.clear()


class SnapshotDiff:
    """Represents differences between two file snapshots.

    Used for incremental processing of large index files.

    Attributes:
        added: Records that are new in the current snapshot.
        removed: Records that were in previous but not current.
        modified: Records present in both but with different content.
        unchanged: Records identical in both snapshots.

    Example:
        >>> diff = SnapshotDiff()
        >>> diff.add_new("key-1", {"data": "new"})
        >>> len(diff.added)
        1
    """

    def __init__(self) -> None:
        self.added: dict[str, dict[str, Any]] = {}
        self.removed: dict[str, dict[str, Any]] = {}
        self.modified: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        self.unchanged_count: int = 0

    def add_new(self, key: str, data: dict[str, Any]) -> None:
        """Record a newly added item."""
        self.added[key] = data

    def add_removed(self, key: str, data: dict[str, Any]) -> None:
        """Record a removed item."""
        self.removed[key] = data

    def add_modified(
        self,
        key: str,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
    ) -> None:
        """Record a modified item."""
        self.modified[key] = (old_data, new_data)

    def increment_unchanged(self) -> None:
        """Increment unchanged count."""
        self.unchanged_count += 1

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.added or self.removed or self.modified)

    @property
    def summary(self) -> dict[str, int]:
        """Get summary of changes.

        Returns:
            Dict with counts for added, removed, modified, unchanged.
        """
        return {
            "added": len(self.added),
            "removed": len(self.removed),
            "modified": len(self.modified),
            "unchanged": self.unchanged_count,
        }


class DiffableFileFeedAdapter(FileFeedAdapter):
    """File adapter with diff computation between versions.

    Extends FileFeedAdapter to compute and track differences
    between consecutive file versions.

    Useful for:
    - SEC daily index files (find new filings)
    - Quarterly updates (find what changed)
    - Any file that grows or changes over time

    Example:
        >>> from feedspine.adapter.file import DiffableFileFeedAdapter
        >>> class MyDiffAdapter(DiffableFileFeedAdapter):
        ...     def _get_key_from_row(self, row):
        ...         return row["id"]
        ...     # ... implement other abstract methods
    """

    def __init__(
        self,
        name: str,
        source_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, source_url, **kwargs)
        self._previous_data: dict[str, dict[str, Any]] = {}
        self._current_data: dict[str, dict[str, Any]] = {}

    @abstractmethod
    def _get_key_from_row(self, row: dict[str, Any]) -> str:
        """Extract unique key from row for diff comparison.

        Args:
            row: Parsed row data.

        Returns:
            Unique key for this row.
        """
        ...

    async def compute_diff(self) -> SnapshotDiff:
        """Compute diff between previous and current file versions.

        Fetches current file, parses it, and compares against
        the previously stored data.

        Returns:
            SnapshotDiff with changes.

        Example:
            >>> # After initial fetch, fetch again and compute diff
            >>> # diff = await adapter.compute_diff()
            >>> # print(diff.summary)
        """
        content = await self._fetch_file()
        diff = SnapshotDiff()

        # Build current data map
        self._current_data = {}
        async for row in self._parse_file(content):
            key = self._get_key_from_row(row)
            self._current_data[key] = row

        # Compute diff
        current_keys = set(self._current_data.keys())
        previous_keys = set(self._previous_data.keys())

        # New items
        for key in current_keys - previous_keys:
            diff.add_new(key, self._current_data[key])

        # Removed items
        for key in previous_keys - current_keys:
            diff.add_removed(key, self._previous_data[key])

        # Check for modifications in common keys
        for key in current_keys & previous_keys:
            if self._current_data[key] != self._previous_data[key]:
                diff.add_modified(
                    key,
                    self._previous_data[key],
                    self._current_data[key],
                )
            else:
                diff.increment_unchanged()

        return diff

    async def fetch_diff_only(self) -> AsyncIterator[RecordCandidate]:
        """Fetch and yield only new/modified records.

        More efficient than full fetch when most records are unchanged.

        Yields:
            RecordCandidate for new and modified records only.
        """
        diff = await self.compute_diff()

        # Yield new records
        for key, data in diff.added.items():
            index = len(self._previous_data) + list(diff.added.keys()).index(key)
            yield self._row_to_candidate(data, index)

        # Yield modified records
        for key, (_, new_data) in diff.modified.items():
            index = list(self._current_data.keys()).index(key)
            yield self._row_to_candidate(new_data, index)

        # Update previous data for next diff
        self._previous_data = self._current_data.copy()

    def commit_snapshot(self) -> None:
        """Commit current data as the baseline for next diff.

        Call after successfully processing to update baseline.
        """
        self._previous_data = self._current_data.copy()

    def reset_baseline(self) -> None:
        """Reset diff baseline (treat next fetch as initial).

        Call to start fresh comparison.
        """
        self._previous_data.clear()
        self._current_data.clear()
