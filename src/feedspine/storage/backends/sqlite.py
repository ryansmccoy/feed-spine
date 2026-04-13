"""SQLite storage backend - refactored with shared components.

This is the refactored SQLite storage that uses shared converters,
query builders, and validators. Reduced from ~534 lines to ~250 lines.

SQLite is perfect for:
- Single-user applications
- Local development
- Small-to-medium datasets
- Embedded applications
- Zero configuration

Note:
    All async methods delegate to ``asyncio.to_thread()`` so that
    synchronous ``sqlite3`` calls do not block the event loop.

Example:
    >>> from feedspine.storage.backends import SQLiteStorage
    >>> storage = SQLiteStorage("my_feeds.db")
    >>> await storage.initialize()
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spine.core.logging import get_logger

from feedspine.models.base import Layer
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting
from feedspine.storage.shared.converters import (
    json_serial,
    row_to_record,
    row_to_sighting,
    serialize_datetime,
)
from feedspine.storage.shared.query_builders import SQLiteQueryBuilder
from feedspine.storage.shared.validators import (
    sanitize_order_by,
    validate_filters,
    validate_layer,
    validate_limit_offset,
    validate_record,
    validate_sighting,
)

logger = get_logger(__name__)


class SQLiteStorage:
    """SQLite storage backend with auto-schema creation.

    Uses shared components for query building, type conversion, and validation.

    Args:
        path: Database file path, or ":memory:" for in-memory.
        timeout: Lock timeout in seconds (default 30).
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        timeout: float = 30.0,
    ) -> None:
        self._path = str(path)
        self._timeout = timeout
        self._conn: sqlite3.Connection | None = None
        self._initialized = False
        self._query_builder = SQLiteQueryBuilder()

    @contextmanager
    def _cursor(self):
        """Get a cursor with automatic commit/rollback."""
        if not self._conn:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        cursor = self._conn.cursor()
        try:
            yield cursor
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cursor.close()

    async def initialize(self) -> None:
        """Initialize storage and auto-create schema."""

        def _init() -> None:
            self._conn = sqlite3.connect(
                self._path,
                timeout=self._timeout,
                detect_types=sqlite3.PARSE_DECLTYPES,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row

            # Enable WAL mode for better concurrent access
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")

            self._create_schema()
            self._initialized = True

        await asyncio.to_thread(_init)

    def _create_schema(self) -> None:
        """Create tables and indexes."""
        with self._cursor() as cursor:
            # Records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    natural_key TEXT NOT NULL UNIQUE,
                    layer TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    published_at TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1
                )
            """)

            # Sightings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sightings (
                    id TEXT PRIMARY KEY,
                    natural_key TEXT NOT NULL,
                    record_id TEXT,
                    source TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    is_new INTEGER NOT NULL,
                    raw_data_hash TEXT,
                    metadata TEXT,
                    FOREIGN KEY (record_id) REFERENCES records(id)
                )
            """)

            # FeedRun tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feed_runs (
                    run_id TEXT PRIMARY KEY,
                    feed_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'running',
                    records_fetched INTEGER DEFAULT 0,
                    records_new INTEGER DEFAULT 0,
                    records_updated INTEGER DEFAULT 0,
                    records_unchanged INTEGER DEFAULT 0,
                    error_message TEXT,
                    metadata TEXT
                )
            """)

            # Versioned records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS record_versions (
                    id TEXT PRIMARY KEY,
                    record_key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    change_reason TEXT,
                    parent_version INTEGER,
                    metadata TEXT,
                    UNIQUE(record_key, version)
                )
            """)

            # Schema metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS _feedspine_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            cursor.execute(
                """
                INSERT OR REPLACE INTO _feedspine_meta (key, value) VALUES ('schema_version', ?)
            """,
                (str(self.SCHEMA_VERSION),),
            )

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_layer ON records(layer)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_published ON records(published_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_captured ON records(captured_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sightings_key ON sightings(natural_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sightings_source ON sightings(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sightings_seen ON sightings(seen_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feed_runs_feed ON feed_runs(feed_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_versions_key ON record_versions(record_key)")

    async def close(self) -> None:
        """Close database connection."""

        def _close() -> None:
            if self._conn:
                self._conn.close()
                self._conn = None
            self._initialized = False

        await asyncio.to_thread(_close)

    # --- Record Operations (using shared converters) ---

    async def store(self, record: Record) -> None:
        """Store a record (upsert)."""
        validate_record(record)
        now = datetime.now(UTC).isoformat()

        def _store() -> None:
            with self._cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO records (
                        id, natural_key, layer, content, metadata,
                        published_at, captured_at, updated_at, version,
                        first_seen_at, last_seen_at, seen_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(natural_key) DO UPDATE SET
                        content = excluded.content,
                        metadata = excluded.metadata,
                        updated_at = excluded.updated_at,
                        version = records.version + 1,
                        last_seen_at = excluded.last_seen_at,
                        seen_count = records.seen_count + 1
                """,
                    (
                        record.id,
                        record.natural_key,
                        record.layer.value,
                        json.dumps(record.content, default=json_serial),
                        json.dumps(record.metadata.model_dump(), default=json_serial) if record.metadata else None,
                        serialize_datetime(record.published_at),
                        serialize_datetime(record.captured_at),
                        now,
                        1,
                        now,
                        now,
                        1,
                    ),
                )

        await asyncio.to_thread(_store)

    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get record by ID."""
        layer = validate_layer(layer)

        def _get() -> Record | None:
            with self._cursor() as cursor:
                if layer:
                    cursor.execute("SELECT * FROM records WHERE id = ? AND layer = ?", (record_id, layer.value))
                else:
                    cursor.execute("SELECT * FROM records WHERE id = ?", (record_id,))
                row = cursor.fetchone()
                return row_to_record(dict(row)) if row else None

        return await asyncio.to_thread(_get)

    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get record by natural key."""

        def _get() -> Record | None:
            with self._cursor() as cursor:
                cursor.execute("SELECT * FROM records WHERE natural_key = ?", (natural_key,))
                row = cursor.fetchone()
                return row_to_record(dict(row)) if row else None

        return await asyncio.to_thread(_get)

    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if record exists."""
        layer = validate_layer(layer)

        def _exists() -> bool:
            with self._cursor() as cursor:
                if layer:
                    cursor.execute("SELECT 1 FROM records WHERE id = ? AND layer = ?", (record_id, layer.value))
                else:
                    cursor.execute("SELECT 1 FROM records WHERE id = ?", (record_id,))
                return cursor.fetchone() is not None

        return await asyncio.to_thread(_exists)

    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if natural key exists."""

        def _exists() -> bool:
            with self._cursor() as cursor:
                cursor.execute("SELECT 1 FROM records WHERE natural_key = ?", (natural_key,))
                return cursor.fetchone() is not None

        return await asyncio.to_thread(_exists)

    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record."""
        layer = validate_layer(layer)

        def _delete() -> bool:
            with self._cursor() as cursor:
                if layer:
                    cursor.execute("DELETE FROM records WHERE id = ? AND layer = ?", (record_id, layer.value))
                else:
                    cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
                return cursor.rowcount > 0

        return await asyncio.to_thread(_delete)

    async def query(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AsyncIterator[Record]:
        """Query records using shared query builder."""
        layer = validate_layer(layer)
        filters = validate_filters(filters)
        order_by = sanitize_order_by(order_by)
        limit, offset = validate_limit_offset(limit, offset)

        sql, params = self._query_builder.build_select_query(
            table="records",
            layer=layer.value if layer else None,
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

        def _query() -> list[dict]:
            with self._cursor() as cursor:
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]

        rows = await asyncio.to_thread(_query)
        for row in rows:
            record = row_to_record(row)
            if record:
                yield record

    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records."""
        layer = validate_layer(layer)
        filters = validate_filters(filters)

        sql, params = self._query_builder.build_count_query(
            table="records",
            layer=layer.value if layer else None,
            filters=filters,
        )

        def _count() -> int:
            with self._cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()[0]

        return await asyncio.to_thread(_count)

    async def count_by_layer(self) -> dict[str, int]:
        """Count records grouped by layer in a single query."""

        def _count() -> dict[str, int]:
            with self._cursor() as cursor:
                cursor.execute("SELECT layer, COUNT(*) FROM records GROUP BY layer")
                return {row[0]: row[1] for row in cursor.fetchall()}

        return await asyncio.to_thread(_count)

    # --- Sighting Operations (using shared converters) ---

    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting."""
        validate_sighting(sighting)

        def _record() -> bool:
            with self._cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO sightings (id, natural_key, record_id, source, seen_at, is_new, raw_data_hash, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        sighting.id,
                        sighting.natural_key,
                        sighting.record_id,
                        sighting.source,
                        serialize_datetime(sighting.seen_at),
                        1 if sighting.is_new else 0,
                        sighting.raw_data_hash,
                        json.dumps(sighting.metadata) if sighting.metadata else None,
                    ),
                )
                return sighting.is_new

        return await asyncio.to_thread(_record)

    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a key."""

        def _get() -> list[Sighting]:
            with self._cursor() as cursor:
                cursor.execute("SELECT * FROM sightings WHERE natural_key = ? ORDER BY seen_at", (natural_key,))
                return [row_to_sighting(dict(row)) for row in cursor.fetchall()]

        return await asyncio.to_thread(_get)

    # --- Bulk Operations ---

    async def store_batch(
        self,
        records: list[Record],
        *,
        batch_size: int = 1000,
        on_conflict: str = "skip",
    ) -> int:
        """Store multiple records efficiently."""
        now = datetime.now(UTC).isoformat()

        def _store_batch() -> int:
            stored = 0
            with self._cursor() as cursor:
                for record in records:
                    try:
                        if on_conflict == "skip":
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO records (
                                    id, natural_key, layer, content, metadata,
                                    published_at, captured_at, updated_at, version,
                                    first_seen_at, last_seen_at, seen_count
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    record.id,
                                    record.natural_key,
                                    record.layer.value,
                                    json.dumps(record.content, default=json_serial),
                                    json.dumps(record.metadata.model_dump(), default=json_serial)
                                    if record.metadata
                                    else None,
                                    serialize_datetime(record.published_at),
                                    serialize_datetime(record.captured_at),
                                    now,
                                    1,
                                    now,
                                    now,
                                    1,
                                ),
                            )
                            if cursor.rowcount > 0:
                                stored += 1
                        else:
                            # For upsert, we need to use the full store logic
                            cursor.execute(
                                """
                                INSERT INTO records (
                                    id, natural_key, layer, content, metadata,
                                    published_at, captured_at, updated_at, version,
                                    first_seen_at, last_seen_at, seen_count
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(natural_key) DO UPDATE SET
                                    content = excluded.content,
                                    metadata = excluded.metadata,
                                    updated_at = excluded.updated_at,
                                    version = records.version + 1,
                                    last_seen_at = excluded.last_seen_at,
                                    seen_count = records.seen_count + 1
                            """,
                                (
                                    record.id,
                                    record.natural_key,
                                    record.layer.value,
                                    json.dumps(record.content, default=json_serial),
                                    json.dumps(record.metadata.model_dump(), default=json_serial)
                                    if record.metadata
                                    else None,
                                    serialize_datetime(record.published_at),
                                    serialize_datetime(record.captured_at),
                                    now,
                                    1,
                                    now,
                                    now,
                                    1,
                                ),
                            )
                            stored += 1
                    except Exception:
                        logger.warning(
                            "Failed to store record %s in batch",
                            record.natural_key,
                            exc_info=True,
                        )
                        continue
            return stored

        return await asyncio.to_thread(_store_batch)

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

        def _delete_batch() -> int:
            deleted = 0
            with self._cursor() as cursor:
                for i in range(0, len(record_ids), batch_size):
                    batch = record_ids[i : i + batch_size]
                    placeholders = ",".join("?" for _ in batch)
                    cursor.execute(
                        f"DELETE FROM records WHERE id IN ({placeholders})",  # noqa: S608
                        batch,
                    )
                    deleted += cursor.rowcount
            return deleted

        return await asyncio.to_thread(_delete_batch)

    # --- Version Control Operations ---

    async def save_version(self, record_key: str, version: int, content: Any, **kwargs) -> None:
        """Save a versioned record."""

        def _save() -> None:
            with self._cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO record_versions (
                        id, record_key, version, content, content_hash,
                        created_at, source, change_type, change_reason, parent_version, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        f"{record_key}@v{version}",
                        record_key,
                        version,
                        json.dumps(content),
                        kwargs.get("content_hash", ""),
                        datetime.now(UTC).isoformat(),
                        kwargs.get("source", "unknown"),
                        kwargs.get("change_type", "updated"),
                        kwargs.get("change_reason"),
                        kwargs.get("parent_version"),
                        json.dumps(kwargs.get("metadata", {})),
                    ),
                )

        await asyncio.to_thread(_save)

    async def get_latest_version(self, record_key: str) -> dict | None:
        """Get latest version of a record."""

        def _get() -> dict | None:
            with self._cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM record_versions
                    WHERE record_key = ?
                    ORDER BY version DESC LIMIT 1
                """,
                    (record_key,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

        return await asyncio.to_thread(_get)

    async def get_all_versions(self, record_key: str) -> list[dict]:
        """Get all versions of a record."""

        def _get() -> list[dict]:
            with self._cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM record_versions
                    WHERE record_key = ?
                    ORDER BY version ASC
                """,
                    (record_key,),
                )
                return [dict(row) for row in cursor.fetchall()]

        return await asyncio.to_thread(_get)

    # --- Convenience Methods ---

    async def vacuum(self) -> None:
        """Optimize database (run after bulk deletes)."""

        def _vacuum() -> None:
            if self._conn:
                self._conn.execute("VACUUM")

        await asyncio.to_thread(_vacuum)

    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""

        def _stats() -> dict[str, Any]:
            with self._cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM records")
                record_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM sightings")
                sighting_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM record_versions")
                version_count = cursor.fetchone()[0]

                cursor.execute("SELECT layer, COUNT(*) FROM records GROUP BY layer")
                by_layer = {row[0]: row[1] for row in cursor.fetchall()}

                return {
                    "records": record_count,
                    "sightings": sighting_count,
                    "versions": version_count,
                    "by_layer": by_layer,
                    "path": self._path,
                }

        return await asyncio.to_thread(_stats)
