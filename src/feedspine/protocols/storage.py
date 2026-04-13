"""Storage backend protocols.

Defines ISP-compliant interfaces for record storage backends,
split into focused protocols that can be composed as needed.

Protocols:
    StorageLifecycle: Initialize/close lifecycle management.
    RecordStore: Core CRUD, query, and batch operations for records.
    SightingStore: Sighting tracking operations.
    StorageBackend: Full storage interface (union of all above).

Example:
    >>> from feedspine.protocols.storage import StorageBackend, RecordStore
    >>> hasattr(StorageBackend, "store")
    True
    >>> hasattr(RecordStore, "store")
    True
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from feedspine.models import Layer, Record, Sighting


# =============================================================================
# Lifecycle Protocol
# =============================================================================


@runtime_checkable
class StorageLifecycle(Protocol):
    """Lifecycle management for storage backends.

    All storage implementations must support initialization and cleanup.
    Used by every consumer that manages a storage backend.
    """

    async def initialize(self) -> None:
        """Initialize storage (create tables, indexes, etc.)."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...


# =============================================================================
# Record Store Protocol
# =============================================================================


@runtime_checkable
class RecordStore(Protocol):
    """Core CRUD, query, and batch operations for records.

    Covers all record-related operations: individual and batch CRUD,
    natural key lookups for deduplication, filtering, and counting.

    Used by:
        - Pipeline (store, get_by_natural_key, store_batch)
        - FeedSpineApp (query, count)
        - API routes (get, get_by_natural_key, query, count)
        - FeedCollectionService (store, query via pipeline)
    """

    # --- Record CRUD ---

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

    # --- Batch Operations ---

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
            batch_size: Number of records per batch.
            on_conflict: How to handle existing records:
                - "skip": Skip existing (default)
                - "update": Update existing records
                - "error": Raise on duplicate

        Returns:
            Number of records actually stored (new or updated).
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


# =============================================================================
# Sighting Store Protocol
# =============================================================================


@runtime_checkable
class SightingStore(Protocol):
    """Sighting tracking operations.

    Tracks when and where records are observed. Used primarily by
    the Pipeline for deduplication and observation history.
    """

    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting. Returns True if this was the first sighting."""
        ...

    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a natural key."""
        ...


# =============================================================================
# Full Storage Backend (Union Protocol)
# =============================================================================


@runtime_checkable
class StorageBackend(RecordStore, SightingStore, StorageLifecycle, Protocol):
    """Full storage backend interface.

    Combines RecordStore, SightingStore, and StorageLifecycle into
    one protocol for backends that implement everything. This is the
    type used when full storage capability is needed (e.g., FeedConfig).

    For narrower type-hints, use the component protocols directly:
        - Pipeline needs: RecordStore + SightingStore + StorageLifecycle
        - API read routes need: RecordStore + StorageLifecycle
        - Collection needs: RecordStore + SightingStore + StorageLifecycle
    """

    ...
