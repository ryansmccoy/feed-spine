"""Storage backend protocol.

Defines the interface for record storage backends.

Example:
    >>> from feedspine.protocols.storage import StorageBackend
    >>> # StorageBackend is a Protocol - implementations include MemoryStorage
    >>> hasattr(StorageBackend, "store")
    True
    >>> hasattr(StorageBackend, "get_by_natural_key")
    True
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from feedspine.models import Layer, Record, Sighting


@runtime_checkable
class StorageBackend(Protocol):
    """Storage backend protocol.

    All storage implementations must implement this interface.
    Supports: SQLite, PostgreSQL, DuckDB, Redis, MongoDB, filesystem, etc.

    See Also:
        feedspine.storage.memory.MemoryStorage: In-memory implementation
    """

    # --- Record Operations ---

    async def store(self, record: Record) -> None:
        """Store a record at its specified layer."""
        ...

    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get record by ID, optionally from specific layer."""
        ...

    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get record by natural key."""
        ...

    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if record exists."""
        ...

    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if natural key exists."""
        ...

    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record. Returns True if existed."""
        ...

    # --- Query Operations ---

    async def query(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AsyncIterator[Record]:
        """Query records with filters."""
        ...

    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records matching filters."""
        ...

    # --- Sighting Operations ---

    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting. Returns True if this was the first sighting."""
        ...

    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a natural key."""
        ...

    # --- Bulk Operations ---

    async def store_batch(
        self,
        records: list[Record],
        *,
        batch_size: int = 1000,
        on_conflict: str = "skip",
    ) -> int:
        """Store multiple records efficiently.

        Args:
            records: List of records to store.
            batch_size: Number of records per batch (for chunked processing).
            on_conflict: How to handle existing records:
                - "skip": Skip existing (default)
                - "update": Update existing records
                - "error": Raise on duplicate

        Returns:
            Number of records actually stored (new or updated).

        Note:
            Implementations should use database-specific bulk operations
            (e.g., COPY for PostgreSQL, bulk insert for DuckDB).
        """
        ...

    async def delete_batch(
        self,
        record_ids: list[str],
        *,
        batch_size: int = 1000,
    ) -> int:
        """Delete multiple records efficiently.

        Returns:
            Number of records deleted.
        """
        ...

    # --- Lifecycle ---

    async def initialize(self) -> None:
        """Initialize storage (create tables, indexes, etc.)."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
