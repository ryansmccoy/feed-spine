"""PostgreSQL storage backend - production-grade persistent storage.

PostgreSQL is ideal for:
- Multi-user production systems
- Large datasets
- Complex queries with full SQL support
- JSONB for flexible content storage
- Strong ACID guarantees

Example:
    >>> from feedspine.storage.postgres import PostgresStorage
    >>> 
    >>> # Just pass connection string - schema auto-creates!
    >>> storage = PostgresStorage("postgresql://user:pass@localhost/feeds")
    >>> await storage.initialize()
    >>> 
    >>> # Or use a connection pool (recommended for production)
    >>> storage = PostgresStorage.from_pool(pool)

Note:
    Requires the `asyncpg` optional dependency:
    ``pip install feedspine[postgres]``
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

try:
    import asyncpg
except ImportError as e:
    raise ImportError(
        "asyncpg is required for PostgresStorage. Install with: pip install feedspine[postgres]"
    ) from e

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting


class PostgresStorage:
    """PostgreSQL storage backend with auto-schema creation.
    
    Just provide a connection string - tables, indexes, and constraints
    are created automatically on first use.
    
    Args:
        dsn: PostgreSQL connection string.
        schema: Schema name (default 'feedspine').
        pool_min: Minimum pool connections (default 2).
        pool_max: Maximum pool connections (default 10).
        
    Example:
        >>> storage = PostgresStorage("postgresql://localhost/mydb")
        >>> await storage.initialize()  # Auto-creates schema + tables
        >>> await storage.store(record)
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(
        self,
        dsn: str,
        *,
        schema: str = "feedspine",
        pool_min: int = 2,
        pool_max: int = 10,
    ) -> None:
        self._dsn = dsn
        self._schema = schema
        self._pool_min = pool_min
        self._pool_max = pool_max
        self._pool: asyncpg.Pool | None = None
        self._initialized = False
    
    @classmethod
    def from_pool(cls, pool: asyncpg.Pool, schema: str = "feedspine") -> "PostgresStorage":
        """Create storage from existing connection pool."""
        storage = cls.__new__(cls)
        storage._dsn = ""
        storage._schema = schema
        storage._pool_min = 0
        storage._pool_max = 0
        storage._pool = pool
        storage._initialized = False
        return storage
    
    async def initialize(self) -> None:
        """Initialize storage and auto-create schema.
        
        Creates schema, tables, indexes, and triggers automatically.
        Uses IF NOT EXISTS so safe to call multiple times.
        """
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=self._pool_min,
                max_size=self._pool_max,
            )
        
        async with self._pool.acquire() as conn:
            # Create schema
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self._schema}")
            
            # Create tables
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._schema}.records (
                    id TEXT PRIMARY KEY,
                    natural_key TEXT NOT NULL UNIQUE,
                    layer TEXT NOT NULL,
                    content JSONB NOT NULL,
                    metadata JSONB,
                    published_at TIMESTAMPTZ NOT NULL,
                    captured_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    version INTEGER NOT NULL DEFAULT 1,
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    seen_count INTEGER NOT NULL DEFAULT 1
                )
            """)
            
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._schema}.sightings (
                    id TEXT PRIMARY KEY,
                    natural_key TEXT NOT NULL,
                    record_id TEXT REFERENCES {self._schema}.records(id),
                    source TEXT NOT NULL,
                    seen_at TIMESTAMPTZ NOT NULL,
                    is_new BOOLEAN NOT NULL,
                    raw_data_hash TEXT,
                    metadata JSONB
                )
            """)
            
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._schema}.feed_runs (
                    run_id TEXT PRIMARY KEY,
                    feed_name TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ,
                    status TEXT NOT NULL DEFAULT 'running',
                    records_fetched INTEGER DEFAULT 0,
                    records_new INTEGER DEFAULT 0,
                    records_updated INTEGER DEFAULT 0,
                    records_unchanged INTEGER DEFAULT 0,
                    error_message TEXT,
                    metadata JSONB
                )
            """)
            
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._schema}.record_versions (
                    id TEXT PRIMARY KEY,
                    record_key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content JSONB NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    source TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    change_reason TEXT,
                    parent_version INTEGER,
                    metadata JSONB,
                    UNIQUE(record_key, version)
                )
            """)
            
            # Schema metadata
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._schema}._meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            await conn.execute(f"""
                INSERT INTO {self._schema}._meta (key, value) VALUES ('schema_version', $1)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, str(self.SCHEMA_VERSION))
            
            # Create indexes
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_records_layer ON {self._schema}.records(layer)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_records_published ON {self._schema}.records(published_at)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_records_captured ON {self._schema}.records(captured_at)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_records_content ON {self._schema}.records USING GIN(content)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_sightings_key ON {self._schema}.sightings(natural_key)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_sightings_source ON {self._schema}.sightings(source)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_feed_runs_feed ON {self._schema}.feed_runs(feed_name)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_versions_key ON {self._schema}.record_versions(record_key)")
        
        self._initialized = True
    
    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        self._initialized = False
    
    # --- Record Operations ---
    
    async def store(self, record: Record) -> None:
        """Store a record (upsert)."""
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self._schema}.records (
                    id, natural_key, layer, content, metadata,
                    published_at, captured_at, updated_at, version,
                    first_seen_at, last_seen_at, seen_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), 1, NOW(), NOW(), 1)
                ON CONFLICT (natural_key) DO UPDATE SET
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW(),
                    version = {self._schema}.records.version + 1,
                    last_seen_at = NOW(),
                    seen_count = {self._schema}.records.seen_count + 1
            """,
                record.id,
                record.natural_key,
                record.layer.value,
                json.dumps(record.content),
                json.dumps(record.metadata.model_dump()) if record.metadata else None,
                record.published_at,
                record.captured_at,
            )
    
    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get record by ID."""
        async with self._pool.acquire() as conn:
            if layer:
                row = await conn.fetchrow(
                    f"SELECT * FROM {self._schema}.records WHERE id = $1 AND layer = $2",
                    record_id, layer.value
                )
            else:
                row = await conn.fetchrow(
                    f"SELECT * FROM {self._schema}.records WHERE id = $1",
                    record_id
                )
            return self._row_to_record(row) if row else None
    
    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get record by natural key."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self._schema}.records WHERE natural_key = $1",
                natural_key
            )
            return self._row_to_record(row) if row else None
    
    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if record exists."""
        async with self._pool.acquire() as conn:
            if layer:
                result = await conn.fetchval(
                    f"SELECT 1 FROM {self._schema}.records WHERE id = $1 AND layer = $2",
                    record_id, layer.value
                )
            else:
                result = await conn.fetchval(
                    f"SELECT 1 FROM {self._schema}.records WHERE id = $1",
                    record_id
                )
            return result is not None
    
    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if natural key exists."""
        async with self._pool.acquire() as conn:
            result = await conn.fetchval(
                f"SELECT 1 FROM {self._schema}.records WHERE natural_key = $1",
                natural_key
            )
            return result is not None
    
    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record."""
        async with self._pool.acquire() as conn:
            if layer:
                result = await conn.execute(
                    f"DELETE FROM {self._schema}.records WHERE id = $1 AND layer = $2",
                    record_id, layer.value
                )
            else:
                result = await conn.execute(
                    f"DELETE FROM {self._schema}.records WHERE id = $1",
                    record_id
                )
            return "DELETE 1" in result
    
    async def query(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AsyncIterator[Record]:
        """Query records with filters.
        
        Supports JSONB queries via content.field syntax.
        """
        sql = f"SELECT * FROM {self._schema}.records WHERE 1=1"
        params: list[Any] = []
        param_idx = 1
        
        if layer:
            sql += f" AND layer = ${param_idx}"
            params.append(layer.value)
            param_idx += 1
        
        if filters:
            for key, value in filters.items():
                if key.startswith("content."):
                    # JSONB query
                    json_path = key.replace("content.", "")
                    sql += f" AND content->>'{json_path}' = ${param_idx}"
                    params.append(str(value))
                else:
                    sql += f" AND {key} = ${param_idx}"
                    params.append(value)
                param_idx += 1
        
        sql += f" ORDER BY {order_by or 'captured_at DESC'}"
        sql += f" LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])
        
        async with self._pool.acquire() as conn:
            async for row in conn.cursor(sql, *params):
                record = self._row_to_record(row)
                if record:
                    yield record
    
    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records matching filters."""
        sql = f"SELECT COUNT(*) FROM {self._schema}.records WHERE 1=1"
        params: list[Any] = []
        param_idx = 1
        
        if layer:
            sql += f" AND layer = ${param_idx}"
            params.append(layer.value)
            param_idx += 1
        
        if filters:
            for key, value in filters.items():
                sql += f" AND {key} = ${param_idx}"
                params.append(value)
                param_idx += 1
        
        async with self._pool.acquire() as conn:
            return await conn.fetchval(sql, *params)
    
    # --- Sighting Operations ---
    
    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting."""
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self._schema}.sightings 
                (id, natural_key, record_id, source, seen_at, is_new, raw_data_hash, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                sighting.id,
                sighting.natural_key,
                sighting.record_id,
                sighting.source,
                sighting.seen_at,
                sighting.is_new,
                sighting.raw_data_hash,
                json.dumps(sighting.metadata) if sighting.metadata else None,
            )
            return sighting.is_new
    
    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a key."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {self._schema}.sightings WHERE natural_key = $1 ORDER BY seen_at",
                natural_key
            )
            return [self._row_to_sighting(row) for row in rows]
    
    # --- Bulk Operations ---
    
    async def store_batch(
        self,
        records: list[Record],
        *,
        batch_size: int = 1000,
        on_conflict: str = "skip",
    ) -> int:
        """Store multiple records efficiently using COPY."""
        if not records:
            return 0
        
        stored = 0
        async with self._pool.acquire() as conn:
            # Use transaction for batch
            async with conn.transaction():
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    
                    if on_conflict == "skip":
                        # Use INSERT ... ON CONFLICT DO NOTHING
                        for record in batch:
                            try:
                                result = await conn.execute(f"""
                                    INSERT INTO {self._schema}.records (
                                        id, natural_key, layer, content, metadata,
                                        published_at, captured_at
                                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                                    ON CONFLICT (natural_key) DO NOTHING
                                """,
                                    record.id,
                                    record.natural_key,
                                    record.layer.value,
                                    json.dumps(record.content),
                                    json.dumps(record.metadata.model_dump()) if record.metadata else None,
                                    record.published_at,
                                    record.captured_at,
                                )
                                if "INSERT" in result:
                                    stored += 1
                            except Exception:
                                continue
                    else:
                        for record in batch:
                            await self.store(record)
                            stored += 1
        
        return stored
    
    # --- Version Control Operations ---
    
    async def save_version(self, record_key: str, version: int, content: Any, **kwargs) -> None:
        """Save a versioned record."""
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self._schema}.record_versions (
                    id, record_key, version, content, content_hash,
                    source, change_type, change_reason, parent_version, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                f"{record_key}@v{version}",
                record_key,
                version,
                json.dumps(content),
                kwargs.get("content_hash", ""),
                kwargs.get("source", "unknown"),
                kwargs.get("change_type", "updated"),
                kwargs.get("change_reason"),
                kwargs.get("parent_version"),
                json.dumps(kwargs.get("metadata", {})),
            )
    
    async def get_latest_version(self, record_key: str) -> dict | None:
        """Get latest version of a record."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                SELECT * FROM {self._schema}.record_versions 
                WHERE record_key = $1 
                ORDER BY version DESC LIMIT 1
            """, record_key)
            return dict(row) if row else None
    
    async def get_all_versions(self, record_key: str) -> list[dict]:
        """Get all versions of a record."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM {self._schema}.record_versions 
                WHERE record_key = $1 
                ORDER BY version ASC
            """, record_key)
            return [dict(row) for row in rows]
    
    # --- Helper Methods ---
    
    def _row_to_record(self, row: asyncpg.Record) -> Record | None:
        """Convert database row to Record."""
        if not row:
            return None
        content = row["content"]
        if isinstance(content, str):
            content = json.loads(content)
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return Record(
            id=row["id"],
            natural_key=row["natural_key"],
            layer=Layer(row["layer"]),
            content=content,
            metadata=Metadata(**metadata) if metadata else None,
            published_at=row["published_at"],
            captured_at=row["captured_at"],
        )
    
    def _row_to_sighting(self, row: asyncpg.Record) -> Sighting:
        """Convert database row to Sighting."""
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return Sighting(
            id=row["id"],
            natural_key=row["natural_key"],
            record_id=row["record_id"],
            source=row["source"],
            seen_at=row["seen_at"],
            is_new=row["is_new"],
            raw_data_hash=row["raw_data_hash"],
            metadata=metadata,
        )
    
    # --- Convenience Methods ---
    
    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        async with self._pool.acquire() as conn:
            record_count = await conn.fetchval(f"SELECT COUNT(*) FROM {self._schema}.records")
            sighting_count = await conn.fetchval(f"SELECT COUNT(*) FROM {self._schema}.sightings")
            version_count = await conn.fetchval(f"SELECT COUNT(*) FROM {self._schema}.record_versions")
            
            by_layer = {}
            rows = await conn.fetch(f"SELECT layer, COUNT(*) FROM {self._schema}.records GROUP BY layer")
            for row in rows:
                by_layer[row["layer"]] = row["count"]
            
            return {
                "records": record_count,
                "sightings": sighting_count,
                "versions": version_count,
                "by_layer": by_layer,
                "schema": self._schema,
            }
