"""SQLite storage backend - zero-config persistent storage.

SQLite is perfect for:
- Single-user applications
- Local development
- Small-to-medium datasets
- Embedded applications
- Zero configuration

Example:
    >>> from feedspine.storage.sqlite import SQLiteStorage
    >>> 
    >>> # Just pass a path - schema auto-creates!
    >>> storage = SQLiteStorage("my_feeds.db")
    >>> await storage.initialize()
    >>> 
    >>> # Or use in-memory for testing
    >>> storage = SQLiteStorage(":memory:")
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import contextmanager
from datetime import UTC, datetime, date
from pathlib import Path
from typing import Any

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting


def _json_serial(obj):
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class SQLiteStorage:
    """SQLite storage backend with auto-schema creation.
    
    Just provide a file path - tables and indexes are created automatically
    on first use. No manual migration needed.
    
    Args:
        path: Database file path, or ":memory:" for in-memory.
        timeout: Lock timeout in seconds (default 30).
        
    Example:
        >>> import asyncio
        >>> storage = SQLiteStorage("feeds.db")
        >>> await storage.initialize()  # Auto-creates tables
        >>> await storage.store(record)
    """
    
    # Schema version for migrations
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
        """Initialize storage and auto-create schema.
        
        Creates all tables, indexes, and triggers automatically.
        Safe to call multiple times (idempotent).
        """
        self._conn = sqlite3.connect(
            self._path,
            timeout=self._timeout,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrent access
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        
        # Create schema
        self._create_schema()
        self._initialized = True
    
    def _create_schema(self) -> None:
        """Create tables and indexes."""
        with self._cursor() as cursor:
            # Records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    natural_key TEXT NOT NULL UNIQUE,
                    layer TEXT NOT NULL,
                    content TEXT NOT NULL,  -- JSON
                    metadata TEXT,  -- JSON
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
                    metadata TEXT,  -- JSON
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
                    metadata TEXT  -- JSON
                )
            """)
            
            # Versioned records table (for version control feature)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS record_versions (
                    id TEXT PRIMARY KEY,
                    record_key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL,  -- JSON
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    change_reason TEXT,
                    parent_version INTEGER,
                    metadata TEXT,  -- JSON
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
            
            # Store schema version
            cursor.execute("""
                INSERT OR REPLACE INTO _feedspine_meta (key, value) VALUES ('schema_version', ?)
            """, (str(self.SCHEMA_VERSION),))
            
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
        if self._conn:
            self._conn.close()
            self._conn = None
        self._initialized = False
    
    # --- Record Operations ---
    
    async def store(self, record: Record) -> None:
        """Store a record (upsert)."""
        now = datetime.now(UTC).isoformat()
        with self._cursor() as cursor:
            cursor.execute("""
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
            """, (
                record.id,
                record.natural_key,
                record.layer.value,
                json.dumps(record.content, default=_json_serial),
                json.dumps(record.metadata.model_dump(), default=_json_serial) if record.metadata else None,
                record.published_at.isoformat(),
                record.captured_at.isoformat(),
                now,
                1,
                now,
                now,
                1,
            ))
    
    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get record by ID."""
        with self._cursor() as cursor:
            if layer:
                cursor.execute(
                    "SELECT * FROM records WHERE id = ? AND layer = ?",
                    (record_id, layer.value)
                )
            else:
                cursor.execute("SELECT * FROM records WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get record by natural key."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM records WHERE natural_key = ?", (natural_key,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if record exists."""
        with self._cursor() as cursor:
            if layer:
                cursor.execute(
                    "SELECT 1 FROM records WHERE id = ? AND layer = ?",
                    (record_id, layer.value)
                )
            else:
                cursor.execute("SELECT 1 FROM records WHERE id = ?", (record_id,))
            return cursor.fetchone() is not None
    
    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if natural key exists."""
        with self._cursor() as cursor:
            cursor.execute("SELECT 1 FROM records WHERE natural_key = ?", (natural_key,))
            return cursor.fetchone() is not None
    
    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record."""
        with self._cursor() as cursor:
            if layer:
                cursor.execute(
                    "DELETE FROM records WHERE id = ? AND layer = ?",
                    (record_id, layer.value)
                )
            else:
                cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
            return cursor.rowcount > 0
    
    async def query(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AsyncIterator[Record]:
        """Query records."""
        sql = "SELECT * FROM records WHERE 1=1"
        params: list[Any] = []
        
        if layer:
            sql += " AND layer = ?"
            params.append(layer.value)
        
        if filters:
            for key, value in filters.items():
                if key.startswith("content."):
                    # JSON field query
                    json_path = key.replace("content.", "")
                    sql += f" AND json_extract(content, '$.{json_path}') = ?"
                    params.append(value)
                else:
                    sql += f" AND {key} = ?"
                    params.append(value)
        
        sql += f" ORDER BY {order_by or 'captured_at DESC'}"
        sql += f" LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self._cursor() as cursor:
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                record = self._row_to_record(row)
                if record:
                    yield record
    
    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records."""
        sql = "SELECT COUNT(*) FROM records WHERE 1=1"
        params: list[Any] = []
        
        if layer:
            sql += " AND layer = ?"
            params.append(layer.value)
        
        if filters:
            for key, value in filters.items():
                sql += f" AND {key} = ?"
                params.append(value)
        
        with self._cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()[0]
    
    # --- Sighting Operations ---
    
    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting."""
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO sightings (id, natural_key, record_id, source, seen_at, is_new, raw_data_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sighting.id,
                sighting.natural_key,
                sighting.record_id,
                sighting.source,
                sighting.seen_at.isoformat(),
                1 if sighting.is_new else 0,
                sighting.raw_data_hash,
                json.dumps(sighting.metadata) if sighting.metadata else None,
            ))
            return sighting.is_new
    
    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a key."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM sightings WHERE natural_key = ? ORDER BY seen_at",
                (natural_key,)
            )
            return [self._row_to_sighting(row) for row in cursor.fetchall()]
    
    # --- Bulk Operations ---
    
    async def store_batch(
        self,
        records: list[Record],
        *,
        batch_size: int = 1000,
        on_conflict: str = "skip",
    ) -> int:
        """Store multiple records efficiently."""
        stored = 0
        now = datetime.now(UTC).isoformat()
        
        with self._cursor() as cursor:
            for record in records:
                try:
                    if on_conflict == "skip":
                        cursor.execute("""
                            INSERT OR IGNORE INTO records (
                                id, natural_key, layer, content, metadata,
                                published_at, captured_at, updated_at, version,
                                first_seen_at, last_seen_at, seen_count
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            record.id,
                            record.natural_key,
                            record.layer.value,
                            json.dumps(record.content, default=_json_serial),
                            json.dumps(record.metadata.model_dump(), default=_json_serial) if record.metadata else None,
                            record.published_at.isoformat(),
                            record.captured_at.isoformat(),
                            now,
                            1,
                            now,
                            now,
                            1,
                        ))
                    else:
                        await self.store(record)
                    
                    if cursor.rowcount > 0:
                        stored += 1
                except Exception:
                    continue
        
        return stored
    
    # --- Version Control Operations ---
    
    async def save_version(self, record_key: str, version: int, content: Any, **kwargs) -> None:
        """Save a versioned record."""
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO record_versions (
                    id, record_key, version, content, content_hash,
                    created_at, source, change_type, change_reason, parent_version, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
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
            ))
    
    async def get_latest_version(self, record_key: str) -> dict | None:
        """Get latest version of a record."""
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT * FROM record_versions 
                WHERE record_key = ? 
                ORDER BY version DESC LIMIT 1
            """, (record_key,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    async def get_all_versions(self, record_key: str) -> list[dict]:
        """Get all versions of a record."""
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT * FROM record_versions 
                WHERE record_key = ? 
                ORDER BY version ASC
            """, (record_key,))
            return [dict(row) for row in cursor.fetchall()]
    
    # --- Helper Methods ---
    
    def _row_to_record(self, row: sqlite3.Row) -> Record | None:
        """Convert a database row to Record."""
        if not row:
            return None
        return Record(
            id=row["id"],
            natural_key=row["natural_key"],
            layer=Layer(row["layer"]),
            content=json.loads(row["content"]),
            metadata=Metadata(**json.loads(row["metadata"])) if row["metadata"] else None,
            published_at=datetime.fromisoformat(row["published_at"]),
            captured_at=datetime.fromisoformat(row["captured_at"]),
        )
    
    def _row_to_sighting(self, row: sqlite3.Row) -> Sighting:
        """Convert a database row to Sighting."""
        return Sighting(
            id=row["id"],
            natural_key=row["natural_key"],
            record_id=row["record_id"],
            source=row["source"],
            seen_at=datetime.fromisoformat(row["seen_at"]),
            is_new=bool(row["is_new"]),
            raw_data_hash=row["raw_data_hash"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )
    
    # --- Convenience Methods ---
    
    async def vacuum(self) -> None:
        """Optimize database (run after bulk deletes)."""
        if self._conn:
            self._conn.execute("VACUUM")
    
    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
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
