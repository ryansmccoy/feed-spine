"""Checkpoint support for resumable long-running collections.

This module provides checkpoint/resume functionality for FeedSpine
collections. When processing large feeds, checkpoints save progress
so collections can resume from where they left off after interruption.

Example:
    >>> import asyncio
    >>> from feedspine.core.checkpoint import Checkpoint, MemoryCheckpointStore
    >>>
    >>> async def example():
    ...     store = MemoryCheckpointStore()
    ...     checkpoint = Checkpoint(
    ...         collection_id="sec-daily-2024",
    ...         feed_name="sec-daily",
    ...         position={"page": 5, "offset": 1000},
    ...         records_processed=1000,
    ...     )
    ...     await store.save(checkpoint)
    ...     loaded = await store.load("sec-daily-2024")
    ...     return loaded.records_processed if loaded else 0
    >>> asyncio.run(example())
    1000
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    """A checkpoint for resumable collection progress.

    Attributes:
        collection_id: Unique identifier for this collection run.
        feed_name: Name of the feed being collected.
        position: Feed-specific position marker (e.g., page number, cursor).
        records_processed: Total records processed so far.
        records_new: Number of new records captured.
        records_duplicate: Number of duplicate records skipped.
        records_failed: Number of failed records.
        started_at: When collection started.
        updated_at: When checkpoint was last updated.
        metadata: Additional checkpoint data.
        is_complete: Whether collection finished successfully.

    Example:
        >>> from feedspine.core.checkpoint import Checkpoint
        >>> from datetime import datetime, timezone
        >>> cp = Checkpoint(
        ...     collection_id="run-001",
        ...     feed_name="my-feed",
        ...     position={"cursor": "abc123"},
        ...     records_processed=500,
        ... )
        >>> cp.is_complete
        False
    """

    collection_id: str
    feed_name: str
    position: dict[str, Any] = field(default_factory=dict)
    records_processed: int = 0
    records_new: int = 0
    records_duplicate: int = 0
    records_failed: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    is_complete: bool = False

    def update(
        self,
        position: dict[str, Any] | None = None,
        records_processed: int | None = None,
        records_new: int | None = None,
        records_duplicate: int | None = None,
        records_failed: int | None = None,
    ) -> Checkpoint:
        """Create an updated checkpoint with new values.

        Args:
            position: New position marker.
            records_processed: New total processed count.
            records_new: New count of new records.
            records_duplicate: New count of duplicate records.
            records_failed: New count of failed records.

        Returns:
            A new Checkpoint with updated values.

        Example:
            >>> from feedspine.core.checkpoint import Checkpoint
            >>> cp = Checkpoint(collection_id="run-001", feed_name="feed")
            >>> cp2 = cp.update(records_processed=100)
            >>> cp2.records_processed
            100
        """
        return Checkpoint(
            collection_id=self.collection_id,
            feed_name=self.feed_name,
            position=position if position is not None else self.position,
            records_processed=records_processed
            if records_processed is not None
            else self.records_processed,
            records_new=records_new if records_new is not None else self.records_new,
            records_duplicate=records_duplicate
            if records_duplicate is not None
            else self.records_duplicate,
            records_failed=records_failed if records_failed is not None else self.records_failed,
            started_at=self.started_at,
            updated_at=datetime.now(UTC),
            metadata=self.metadata,
            is_complete=self.is_complete,
        )

    def mark_complete(self) -> Checkpoint:
        """Mark the checkpoint as complete.

        Returns:
            A new Checkpoint marked as complete.

        Example:
            >>> from feedspine.core.checkpoint import Checkpoint
            >>> cp = Checkpoint(collection_id="run-001", feed_name="feed")
            >>> cp.is_complete
            False
            >>> cp2 = cp.mark_complete()
            >>> cp2.is_complete
            True
        """
        return Checkpoint(
            collection_id=self.collection_id,
            feed_name=self.feed_name,
            position=self.position,
            records_processed=self.records_processed,
            records_new=self.records_new,
            records_duplicate=self.records_duplicate,
            records_failed=self.records_failed,
            started_at=self.started_at,
            updated_at=datetime.now(UTC),
            metadata=self.metadata,
            is_complete=True,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert checkpoint to dictionary for serialization.

        Returns:
            Dictionary representation of the checkpoint.

        Example:
            >>> from feedspine.core.checkpoint import Checkpoint
            >>> cp = Checkpoint(collection_id="run-001", feed_name="feed")
            >>> d = cp.to_dict()
            >>> d["collection_id"]
            'run-001'
        """
        return {
            "collection_id": self.collection_id,
            "feed_name": self.feed_name,
            "position": self.position,
            "records_processed": self.records_processed,
            "records_new": self.records_new,
            "records_duplicate": self.records_duplicate,
            "records_failed": self.records_failed,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "is_complete": self.is_complete,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        """Create checkpoint from dictionary.

        Args:
            data: Dictionary with checkpoint data.

        Returns:
            A new Checkpoint instance.

        Example:
            >>> from feedspine.core.checkpoint import Checkpoint
            >>> from datetime import datetime, timezone
            >>> data = {
            ...     "collection_id": "run-001",
            ...     "feed_name": "feed",
            ...     "position": {},
            ...     "records_processed": 0,
            ...     "records_new": 0,
            ...     "records_duplicate": 0,
            ...     "records_failed": 0,
            ...     "started_at": "2024-01-01T00:00:00+00:00",
            ...     "updated_at": "2024-01-01T00:00:00+00:00",
            ...     "metadata": {},
            ...     "is_complete": False,
            ... }
            >>> cp = Checkpoint.from_dict(data)
            >>> cp.collection_id
            'run-001'
        """
        return cls(
            collection_id=data["collection_id"],
            feed_name=data["feed_name"],
            position=data.get("position", {}),
            records_processed=data.get("records_processed", 0),
            records_new=data.get("records_new", 0),
            records_duplicate=data.get("records_duplicate", 0),
            records_failed=data.get("records_failed", 0),
            started_at=datetime.fromisoformat(data["started_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
            is_complete=data.get("is_complete", False),
        )


class CheckpointStore(ABC):
    """Abstract base class for checkpoint storage backends.

    Implement this to provide persistent checkpoint storage.
    """

    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint.

        Args:
            checkpoint: The checkpoint to save.
        """
        ...

    @abstractmethod
    async def load(self, collection_id: str) -> Checkpoint | None:
        """Load a checkpoint by collection ID.

        Args:
            collection_id: The collection identifier.

        Returns:
            The checkpoint if found, None otherwise.
        """
        ...

    @abstractmethod
    async def delete(self, collection_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            collection_id: The collection identifier.

        Returns:
            True if checkpoint was deleted.
        """
        ...

    @abstractmethod
    async def list_incomplete(self, feed_name: str | None = None) -> list[Checkpoint]:
        """List incomplete checkpoints.

        Args:
            feed_name: Optional filter by feed name.

        Returns:
            List of incomplete checkpoints.
        """
        ...


class MemoryCheckpointStore(CheckpointStore):
    """In-memory checkpoint store for testing.

    Example:
        >>> import asyncio
        >>> from feedspine.core.checkpoint import Checkpoint, MemoryCheckpointStore
        >>> async def example():
        ...     store = MemoryCheckpointStore()
        ...     cp = Checkpoint(collection_id="test", feed_name="feed")
        ...     await store.save(cp)
        ...     loaded = await store.load("test")
        ...     return loaded is not None
        >>> asyncio.run(example())
        True
    """

    def __init__(self) -> None:
        """Initialize empty checkpoint store."""
        self._checkpoints: dict[str, Checkpoint] = {}

    async def save(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to memory."""
        self._checkpoints[checkpoint.collection_id] = checkpoint

    async def load(self, collection_id: str) -> Checkpoint | None:
        """Load checkpoint from memory."""
        return self._checkpoints.get(collection_id)

    async def delete(self, collection_id: str) -> bool:
        """Delete checkpoint from memory."""
        if collection_id in self._checkpoints:
            del self._checkpoints[collection_id]
            return True
        return False

    async def list_incomplete(self, feed_name: str | None = None) -> list[Checkpoint]:
        """List incomplete checkpoints."""
        result = []
        for cp in self._checkpoints.values():
            if cp.is_complete:
                continue
            if feed_name is None or cp.feed_name == feed_name:
                result.append(cp)
        return result


class FileCheckpointStore(CheckpointStore):
    """File-based checkpoint store using JSON files.

    Stores checkpoints as JSON files in a directory.

    Example:
        >>> import asyncio
        >>> import tempfile
        >>> from pathlib import Path
        >>> from feedspine.core.checkpoint import Checkpoint, FileCheckpointStore
        >>> async def example():
        ...     with tempfile.TemporaryDirectory() as tmpdir:
        ...         store = FileCheckpointStore(Path(tmpdir))
        ...         cp = Checkpoint(collection_id="test", feed_name="feed")
        ...         await store.save(cp)
        ...         loaded = await store.load("test")
        ...         return loaded is not None
        >>> asyncio.run(example())
        True
    """

    def __init__(self, directory: Path) -> None:
        """Initialize file checkpoint store.

        Args:
            directory: Directory to store checkpoint files.
        """
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)

    def _checkpoint_path(self, collection_id: str) -> Path:
        """Get path for a checkpoint file."""
        # Sanitize collection_id for filename
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in collection_id)
        return self._directory / f"{safe_id}.json"

    async def save(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to JSON file."""
        path = self._checkpoint_path(checkpoint.collection_id)
        path.write_text(json.dumps(checkpoint.to_dict(), indent=2))

    async def load(self, collection_id: str) -> Checkpoint | None:
        """Load checkpoint from JSON file."""
        path = self._checkpoint_path(collection_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Checkpoint.from_dict(data)

    async def delete(self, collection_id: str) -> bool:
        """Delete checkpoint file."""
        path = self._checkpoint_path(collection_id)
        if path.exists():
            path.unlink()
            return True
        return False

    async def list_incomplete(self, feed_name: str | None = None) -> list[Checkpoint]:
        """List incomplete checkpoints from files."""
        result = []
        for path in self._directory.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                cp = Checkpoint.from_dict(data)
                if cp.is_complete:
                    continue
                if feed_name is None or cp.feed_name == feed_name:
                    result.append(cp)
            except (json.JSONDecodeError, KeyError):
                continue  # Skip invalid files
        return result


class CheckpointManager:
    """Manager for checkpoint operations during collection.

    Provides a high-level API for checkpoint management, including
    automatic saving at intervals.

    Example:
        >>> import asyncio
        >>> from feedspine.core.checkpoint import (
        ...     Checkpoint, MemoryCheckpointStore, CheckpointManager
        ... )
        >>> async def example():
        ...     store = MemoryCheckpointStore()
        ...     manager = CheckpointManager(store, save_interval=100)
        ...     cp = manager.start("run-001", "my-feed")
        ...     cp = manager.update(records_processed=50, records_new=50)
        ...     await manager.save()
        ...     return cp.records_processed
        >>> asyncio.run(example())
        50
    """

    def __init__(
        self,
        store: CheckpointStore,
        save_interval: int = 100,
    ) -> None:
        """Initialize checkpoint manager.

        Args:
            store: Checkpoint storage backend.
            save_interval: Save checkpoint every N records.
        """
        self._store = store
        self._save_interval = save_interval
        self._current: Checkpoint | None = None
        self._last_save_count = 0

    def start(
        self,
        collection_id: str,
        feed_name: str,
        position: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Start a new checkpoint.

        Args:
            collection_id: Unique identifier for this collection.
            feed_name: Name of the feed.
            position: Initial position marker.

        Returns:
            The new checkpoint.

        Example:
            >>> from feedspine.core.checkpoint import (
            ...     MemoryCheckpointStore, CheckpointManager
            ... )
            >>> store = MemoryCheckpointStore()
            >>> manager = CheckpointManager(store)
            >>> cp = manager.start("run-001", "feed")
            >>> cp.collection_id
            'run-001'
        """
        self._current = Checkpoint(
            collection_id=collection_id,
            feed_name=feed_name,
            position=position or {},
        )
        self._last_save_count = 0
        return self._current

    async def resume(self, collection_id: str) -> Checkpoint | None:
        """Resume from an existing checkpoint.

        Args:
            collection_id: The collection identifier to resume.

        Returns:
            The loaded checkpoint if found, None otherwise.

        Example:
            >>> import asyncio
            >>> from feedspine.core.checkpoint import (
            ...     Checkpoint, MemoryCheckpointStore, CheckpointManager
            ... )
            >>> async def example():
            ...     store = MemoryCheckpointStore()
            ...     cp = Checkpoint(collection_id="run-001", feed_name="feed")
            ...     await store.save(cp)
            ...     manager = CheckpointManager(store)
            ...     loaded = await manager.resume("run-001")
            ...     return loaded is not None
            >>> asyncio.run(example())
            True
        """
        self._current = await self._store.load(collection_id)
        if self._current:
            self._last_save_count = self._current.records_processed
        return self._current

    def update(
        self,
        position: dict[str, Any] | None = None,
        records_processed: int | None = None,
        records_new: int | None = None,
        records_duplicate: int | None = None,
        records_failed: int | None = None,
    ) -> Checkpoint:
        """Update the current checkpoint.

        Args:
            position: New position marker.
            records_processed: New total processed count.
            records_new: New count of new records.
            records_duplicate: New count of duplicate records.
            records_failed: New count of failed records.

        Returns:
            The updated checkpoint.

        Raises:
            RuntimeError: If no checkpoint is active.

        Example:
            >>> from feedspine.core.checkpoint import (
            ...     MemoryCheckpointStore, CheckpointManager
            ... )
            >>> store = MemoryCheckpointStore()
            >>> manager = CheckpointManager(store)
            >>> _ = manager.start("run-001", "feed")
            >>> cp = manager.update(records_processed=100)
            >>> cp.records_processed
            100
        """
        if self._current is None:
            raise RuntimeError("No active checkpoint. Call start() or resume() first.")

        self._current = self._current.update(
            position=position,
            records_processed=records_processed,
            records_new=records_new,
            records_duplicate=records_duplicate,
            records_failed=records_failed,
        )
        return self._current

    async def save(self) -> None:
        """Save the current checkpoint.

        Example:
            >>> import asyncio
            >>> from feedspine.core.checkpoint import (
            ...     MemoryCheckpointStore, CheckpointManager
            ... )
            >>> async def example():
            ...     store = MemoryCheckpointStore()
            ...     manager = CheckpointManager(store)
            ...     _ = manager.start("run-001", "feed")
            ...     await manager.save()
            ...     return await store.load("run-001") is not None
            >>> asyncio.run(example())
            True
        """
        if self._current is not None:
            await self._store.save(self._current)
            self._last_save_count = self._current.records_processed

    async def maybe_save(self) -> bool:
        """Save checkpoint if save interval reached.

        Returns:
            True if checkpoint was saved.

        Example:
            >>> import asyncio
            >>> from feedspine.core.checkpoint import (
            ...     MemoryCheckpointStore, CheckpointManager
            ... )
            >>> async def example():
            ...     store = MemoryCheckpointStore()
            ...     manager = CheckpointManager(store, save_interval=10)
            ...     _ = manager.start("run-001", "feed")
            ...     _ = manager.update(records_processed=5)
            ...     saved1 = await manager.maybe_save()  # Not enough
            ...     _ = manager.update(records_processed=15)
            ...     saved2 = await manager.maybe_save()  # Interval reached
            ...     return (saved1, saved2)
            >>> asyncio.run(example())
            (False, True)
        """
        if self._current is None:
            return False

        records_since_save = self._current.records_processed - self._last_save_count
        if records_since_save >= self._save_interval:
            await self.save()
            return True
        return False

    async def complete(self) -> Checkpoint:
        """Mark collection as complete and save.

        Returns:
            The completed checkpoint.

        Raises:
            RuntimeError: If no checkpoint is active.

        Example:
            >>> import asyncio
            >>> from feedspine.core.checkpoint import (
            ...     MemoryCheckpointStore, CheckpointManager
            ... )
            >>> async def example():
            ...     store = MemoryCheckpointStore()
            ...     manager = CheckpointManager(store)
            ...     _ = manager.start("run-001", "feed")
            ...     cp = await manager.complete()
            ...     return cp.is_complete
            >>> asyncio.run(example())
            True
        """
        if self._current is None:
            raise RuntimeError("No active checkpoint. Call start() or resume() first.")

        self._current = self._current.mark_complete()
        await self.save()
        return self._current

    @property
    def current(self) -> Checkpoint | None:
        """Get the current checkpoint."""
        return self._current

    @property
    def position(self) -> dict[str, Any]:
        """Get the current position marker."""
        if self._current is None:
            return {}
        return self._current.position
