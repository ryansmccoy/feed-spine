"""Record operation mixins for RepositoryStorageBackend.

Provides record CRUD, query, and batch operations as mixins.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from feedspine._vendor.logging import get_logger

from feedspine.models.base import Layer
from feedspine.models.record import Record
from feedspine.storage.shared.converters import json_serial, serialize_datetime
from feedspine.storage.shared.validators import (
    sanitize_order_by,
    validate_filters,
    validate_layer,
    validate_limit_offset,
    validate_record,
)

logger = get_logger(__name__)


class RecordOperationsMixin:
    """Mixin providing record CRUD and query operations."""

    async def store(self, record: Record) -> None:
        """Store a record (upsert by natural_key)."""
        validate_record(record)
        with self._repo() as repo:
            repo.store_record(record)

    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get record by ID, optionally from a specific layer."""
        with self._repo() as repo:
            record = repo.get_record(record_id)
            if record and layer and record.layer != layer:
                return None
            return record

    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get record by natural key."""
        with self._repo() as repo:
            return repo.get_record_by_key(natural_key)

    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if record exists."""
        return (await self.get(record_id, layer)) is not None

    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if natural key exists."""
        return (await self.get_by_natural_key(natural_key)) is not None

    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record by ID. Returns True if a row was affected."""
        with self._repo() as repo:
            return repo.delete_record(record_id)

    async def query(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AsyncIterator[Record]:
        """Query records with optional filtering.

        Yields Record instances matching the criteria.
        """
        layer = validate_layer(layer)
        filters = validate_filters(filters)
        order_by = sanitize_order_by(order_by)
        limit, offset = validate_limit_offset(limit, offset)

        with self._repo() as repo:
            records = repo.query_records(
                layer=layer.value if layer else None,
                limit=limit,
                offset=offset,
                order_by=order_by or "captured_at DESC",
            )
            for record in records:
                yield record

    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records matching filters."""
        layer = validate_layer(layer)
        with self._repo() as repo:
            return repo.count_records(layer=layer.value if layer else None)

    async def count_by_layer(self) -> dict[str, int]:
        """Count records grouped by layer in a single query."""
        with self._repo() as repo:
            rows = repo.query("SELECT layer, COUNT(*) AS cnt FROM records GROUP BY layer")
            return {row["layer"]: row["cnt"] for row in rows}


class BatchOperationsMixin:
    """Mixin providing batch record operations."""

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
            batch_size: Not used by the repository path (operations are atomic).
            on_conflict: ``"update"`` or ``"skip"``. Defaults to skip.

        Returns:
            Number of records stored.
        """
        stored = 0
        with self._repo() as repo:
            for record in records:
                try:
                    if on_conflict == "update":
                        repo.store_record(record)
                        stored += 1
                    else:
                        # "skip" — only insert if natural_key doesn't exist
                        existing = repo.get_record_by_key(record.natural_key)
                        if existing is None:
                            repo.store_record(record)
                            stored += 1
                except Exception as e:
                    logger.warning("Failed to store record %s: %s", record.natural_key, e)
                    continue
        return stored

    async def delete_batch(
        self,
        record_ids: list[str],
        *,
        batch_size: int = 1000,
    ) -> int:
        """Delete multiple records."""
        deleted = 0
        with self._repo() as repo:
            for record_id in record_ids:
                try:
                    repo.delete_record(record_id)
                    deleted += 1
                except Exception as e:
                    logger.warning("Failed to delete record %s: %s", record_id, e)
                    continue
        return deleted


class VersionControlMixin:
    """Mixin providing record version control operations."""

    async def save_version(
        self,
        record_key: str,
        version: int,
        content: Any,
        **kwargs: Any,
    ) -> None:
        """Save a versioned record snapshot."""
        now = serialize_datetime(datetime.now(UTC))
        row = {
            "id": f"{record_key}@v{version}",
            "record_key": record_key,
            "version": version,
            "content": json.dumps(content, default=json_serial) if not isinstance(content, str) else content,
            "content_hash": kwargs.get("content_hash", ""),
            "created_at": now,
            "source": kwargs.get("source", "unknown"),
            "change_type": kwargs.get("change_type", "updated"),
            "change_reason": kwargs.get("change_reason"),
            "parent_version": kwargs.get("parent_version"),
            "metadata": json.dumps(kwargs.get("metadata", {})),
        }
        with self._repo() as repo:
            repo.insert("record_versions", row)

    async def get_latest_version(self, record_key: str) -> dict | None:
        """Get latest version of a record."""
        with self._repo() as repo:
            return repo.query_one(
                f"SELECT * FROM record_versions WHERE record_key = {repo.ph(1)} ORDER BY version DESC LIMIT 1",
                (record_key,),
            )

    async def get_all_versions(self, record_key: str) -> list[dict]:
        """Get all versions of a record."""
        with self._repo() as repo:
            return repo.query(
                f"SELECT * FROM record_versions WHERE record_key = {repo.ph(1)} ORDER BY version ASC",
                (record_key,),
            )


__all__ = [
    "BatchOperationsMixin",
    "RecordOperationsMixin",
    "VersionControlMixin",
]
