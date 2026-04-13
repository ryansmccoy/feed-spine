"""In-memory record storage mixin.

Provides record CRUD operations, querying, and sighting tracking.
Can be mixed into any storage class that needs in-memory record storage.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from feedspine.models.base import Layer
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting


class RecordStorageMixin:
    """Mixin providing in-memory record storage operations.

    Attributes:
        _records: Records indexed by layer and ID.
        _key_index: Natural key to record ID mapping.
        _sightings: Sightings indexed by natural key.
    """

    def __init__(self) -> None:
        self._records: dict[Layer, dict[str, Record]] = defaultdict(dict)
        self._key_index: dict[str, str] = {}
        self._sightings: dict[str, list[Sighting]] = defaultdict(list)

    def _clear_records(self) -> None:
        """Clear all record data."""
        self._records.clear()
        self._key_index.clear()
        self._sightings.clear()

    # --- CRUD Operations ---

    async def store(self, record: Record) -> None:
        """Store a record at its specified layer."""
        self._records[record.layer][record.id] = record
        self._key_index[record.natural_key] = record.id

    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get record by ID, optionally from specific layer."""
        if layer:
            return self._records[layer].get(record_id)
        for layer_records in self._records.values():
            if record_id in layer_records:
                return layer_records[record_id]
        return None

    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get record by natural key."""
        normalized = natural_key.strip().lower()
        record_id = self._key_index.get(normalized)
        if record_id:
            return await self.get(record_id)
        return None

    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if record exists."""
        return await self.get(record_id, layer) is not None

    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if natural key exists."""
        normalized = natural_key.strip().lower()
        return normalized in self._key_index

    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record. Returns True if existed."""
        if layer:
            if record_id in self._records[layer]:
                record = self._records[layer].pop(record_id)
                self._key_index.pop(record.natural_key, None)
                return True
            return False

        for layer_records in self._records.values():
            if record_id in layer_records:
                record = layer_records.pop(record_id)
                self._key_index.pop(record.natural_key, None)
                return True
        return False

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
        records: list[Record] = []

        layers_to_query = [layer] if layer else list(Layer)
        for lyr in layers_to_query:
            records.extend(self._records[lyr].values())

        if filters:
            records = [r for r in records if self._matches_filters(r, filters)]

        if order_by:
            reverse = order_by.startswith("-")
            field = order_by.lstrip("-")
            records.sort(key=lambda r: getattr(r, field, None) or "", reverse=reverse)

        for record in records[offset : offset + limit]:
            yield record

    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records matching filters."""
        count = 0
        async for _ in self.query(layer=layer, filters=filters, limit=1_000_000):
            count += 1
        return count

    async def count_by_layer(self) -> dict[str, int]:
        """Count records grouped by layer."""
        from feedspine.models.base import Layer

        counts: dict[str, int] = {}
        for layer in Layer:
            c = 0
            async for _ in self.query(layer=layer, limit=1_000_000):
                c += 1
            if c > 0:
                counts[layer.value] = c
        return counts

    # --- Sighting Operations ---

    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting. Returns True if first sighting for this key."""
        normalized_key = sighting.natural_key.strip().lower()
        is_first_sighting = normalized_key not in self._sightings
        updated_sighting = sighting.model_copy(update={"is_new": is_first_sighting})
        self._sightings[normalized_key].append(updated_sighting)
        return is_first_sighting

    async def record_sighting_on_existing(self, natural_key: str) -> Record | None:
        """Update sighting tracking on an existing record."""
        normalized = natural_key.strip().lower()
        record = await self.get_by_natural_key(normalized)
        if record is None:
            return None
        updated_record = record.record_sighting()
        await self.store(updated_record)
        return updated_record

    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a natural key."""
        normalized = natural_key.strip().lower()
        return list(self._sightings.get(normalized, []))

    # --- Bulk Operations ---

    async def store_batch(
        self,
        records: list[Record],
        *,
        batch_size: int = 1000,
        on_conflict: str = "skip",
    ) -> int:
        """Store multiple records. Returns count stored."""
        stored_count = 0
        for record in records:
            exists = await self.exists_by_natural_key(record.natural_key)
            if exists:
                if on_conflict == "skip":
                    continue
                elif on_conflict == "error":
                    raise ValueError(f"Record already exists: {record.natural_key}")
                elif on_conflict == "update":
                    old_record_id = self._key_index.get(record.natural_key.strip().lower())
                    if old_record_id:
                        await self.delete(old_record_id)
            await self.store(record)
            stored_count += 1
        return stored_count

    async def delete_batch(self, record_ids: list[str], *, batch_size: int = 1000) -> int:
        """Delete multiple records. Returns count deleted."""
        deleted_count = 0
        for record_id in record_ids:
            if await self.delete(record_id):
                deleted_count += 1
        return deleted_count

    # --- Helpers ---

    @staticmethod
    def _matches_filters(record: Record, filters: dict[str, Any]) -> bool:
        """Check if record matches all filters."""
        for key, value in filters.items():
            if "." in key:
                parts = key.split(".")
                obj: Any = record
                for part in parts:
                    if hasattr(obj, part):
                        obj = getattr(obj, part)
                    elif isinstance(obj, dict):
                        obj = obj.get(part)
                    else:
                        return False
                if obj != value:
                    return False
            elif hasattr(record, key):
                if getattr(record, key) != value:
                    return False
            else:
                return False
        return True
