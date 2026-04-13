"""In-memory storage backend for testing and development."""

from __future__ import annotations

from feedspine.storage.shared.mixins import (
    FetchContextMixin,
    RecordStorageMixin,
    RunLogMixin,
)


class MemoryStorage(RecordStorageMixin, FetchContextMixin, RunLogMixin):
    """In-memory storage using dictionaries.

    Implements StorageBackend, FetchContextStore, and RunLogStore
    via mixins. Data is lost when the process exits.
    """

    def __init__(self, max_events: int = 10000) -> None:
        # Initialize all mixins
        RecordStorageMixin.__init__(self)
        FetchContextMixin.__init__(self)
        RunLogMixin.__init__(self, max_events=max_events)
        self._initialized = False

    async def initialize(self) -> None:
        """No-op for memory storage."""
        self._initialized = True

    async def close(self) -> None:
        """Clear all data."""
        self._clear_records()
        self._clear_fetch_contexts()
        self._clear_events()
        self._initialized = False
