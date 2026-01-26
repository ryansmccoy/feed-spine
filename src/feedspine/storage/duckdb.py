"""DuckDB storage backend for analytics.

DuckDB provides an embeddable OLAP database optimized for analytical queries.
This backend is ideal for:
- Analytical queries on collected data
- JSON content field queries
- Parquet export for data warehouse integration
- Time-series analysis with window functions
- Embedded usage (no server required)

Example:
    >>> from feedspine.storage.duckdb import DuckDBStorage
    >>> storage = DuckDBStorage("feedspine.duckdb")
    >>> # Or use in-memory mode for testing
    >>> storage = DuckDBStorage(":memory:")

Note:
    Requires the `duckdb` optional dependency:
    ``pip install feedspine[duckdb]``
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError as e:
    raise ImportError(
        "DuckDB is required for DuckDBStorage. Install with: pip install feedspine[duckdb]"
    ) from e

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting


class DuckDBStorage:
    """DuckDB storage backend for analytical workloads.

    Provides OLAP-optimized storage with SQL analytics capabilities,
    JSON querying, and Parquet export for data warehouse integration.

    Best for: Analytics, time-series, data warehouse export, embedded usage.

    Args:
        path: Database file path, or ":memory:" for in-memory mode.
        read_only: Open in read-only mode (default False).

    Example:
        >>> import asyncio
        >>> from feedspine.storage.duckdb import DuckDBStorage
        >>> storage = DuckDBStorage(":memory:")
        >>> asyncio.run(storage.initialize())
        >>> # Ready for use
        >>> asyncio.run(storage.close())
    """

    def __init__(self, path: str = ":memory:", *, read_only: bool = False) -> None:
        self._path = path
        self._read_only = read_only
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize storage and create tables.

        Creates the records and sightings tables if they don't exist.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> s._initialized
            True
        """
        self._conn = duckdb.connect(self._path, read_only=self._read_only)

        # Create tables
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id VARCHAR PRIMARY KEY,
                natural_key VARCHAR NOT NULL,
                layer VARCHAR NOT NULL,
                content JSON NOT NULL,
                metadata JSON,
                published_at TIMESTAMP WITH TIME ZONE NOT NULL,
                captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                version INTEGER NOT NULL DEFAULT 1
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sightings (
                id VARCHAR PRIMARY KEY,
                natural_key VARCHAR NOT NULL,
                record_id VARCHAR,
                source VARCHAR NOT NULL,
                seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
                is_new BOOLEAN NOT NULL,
                raw_data_hash VARCHAR,
                metadata JSON
            )
        """)

        # Create indexes for common queries
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_natural_key ON records(natural_key)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_records_layer ON records(layer)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sightings_key ON sightings(natural_key)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sightings_source ON sightings(natural_key, source)"
        )

        self._initialized = True

    async def close(self) -> None:
        """Close database connection.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> asyncio.run(s.close())
            >>> s._conn is None
            True
        """
        if self._conn:
            self._conn.close()
            self._conn = None
        self._initialized = False

    # --- Record Operations ---

    async def store(self, record: Record) -> None:
        """Store a record at its specified layer.

        Upserts the record (insert or update if ID exists).

        Args:
            record: The record to store.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> from feedspine.models import Record, Layer, Metadata, RecordCandidate
            >>> from datetime import datetime, UTC
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> candidate = RecordCandidate(
            ...     natural_key="test-key",
            ...     published_at=datetime.now(UTC),
            ...     content={"title": "Test"},
            ...     metadata=Metadata(source="test"),
            ... )
            >>> record = Record.from_candidate(candidate, record_id="r1")
            >>> asyncio.run(s.store(record))
            >>> asyncio.run(s.count())
            1
        """
        assert self._conn is not None, "Storage not initialized"

        # Use Pydantic's JSON serialization to handle datetime fields
        metadata_json = record.metadata.model_dump_json() if record.metadata else "{}"

        self._conn.execute(
            """
            INSERT OR REPLACE INTO records
                (id, natural_key, layer, content, metadata, published_at, captured_at, updated_at, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.id,
                record.natural_key,
                record.layer.value,
                json.dumps(record.content),
                metadata_json,
                record.published_at.isoformat(),
                record.captured_at.isoformat(),
                record.updated_at.isoformat(),
                record.version,
            ],
        )

    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get record by ID, optionally from specific layer.

        Args:
            record_id: The record ID to look up.
            layer: Optional layer filter.

        Returns:
            The record if found, None otherwise.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> result = asyncio.run(s.get("nonexistent"))
            >>> result is None
            True
        """
        assert self._conn is not None, "Storage not initialized"

        if layer:
            result = self._conn.execute(
                "SELECT * FROM records WHERE id = ? AND layer = ?",
                [record_id, layer.value],
            ).fetchone()
        else:
            result = self._conn.execute(
                "SELECT * FROM records WHERE id = ?", [record_id]
            ).fetchone()

        if result:
            return self._row_to_record(result)
        return None

    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get record by natural key.

        Args:
            natural_key: The natural key to look up.

        Returns:
            The record if found, None otherwise.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> result = asyncio.run(s.get_by_natural_key("test"))
            >>> result is None
            True
        """
        assert self._conn is not None, "Storage not initialized"

        normalized = natural_key.strip().lower()
        result = self._conn.execute(
            "SELECT * FROM records WHERE LOWER(natural_key) = ?", [normalized]
        ).fetchone()

        if result:
            return self._row_to_record(result)
        return None

    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if record exists.

        Args:
            record_id: The record ID to check.
            layer: Optional layer filter.

        Returns:
            True if record exists, False otherwise.
        """
        assert self._conn is not None, "Storage not initialized"

        if layer:
            result = self._conn.execute(
                "SELECT 1 FROM records WHERE id = ? AND layer = ?",
                [record_id, layer.value],
            ).fetchone()
        else:
            result = self._conn.execute(
                "SELECT 1 FROM records WHERE id = ?", [record_id]
            ).fetchone()

        return result is not None

    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if natural key exists.

        Args:
            natural_key: The natural key to check.

        Returns:
            True if exists, False otherwise.
        """
        assert self._conn is not None, "Storage not initialized"

        normalized = natural_key.strip().lower()
        result = self._conn.execute(
            "SELECT 1 FROM records WHERE LOWER(natural_key) = ?", [normalized]
        ).fetchone()

        return result is not None

    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record. Returns True if existed.

        Args:
            record_id: The record ID to delete.
            layer: Optional layer filter.

        Returns:
            True if record was deleted, False if not found.
        """
        assert self._conn is not None, "Storage not initialized"

        if layer:
            result = self._conn.execute(
                "DELETE FROM records WHERE id = ? AND layer = ? RETURNING id",
                [record_id, layer.value],
            ).fetchone()
        else:
            result = self._conn.execute(
                "DELETE FROM records WHERE id = ? RETURNING id", [record_id]
            ).fetchone()

        return result is not None

    # --- Query Operations ---

    async def query(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AsyncIterator[Record]:
        """Query records with filters.

        Args:
            layer: Filter by layer.
            filters: Additional filters (key-value pairs).
            order_by: Field to sort by (prefix with - for descending).
            limit: Maximum records to return.
            offset: Number of records to skip.

        Yields:
            Records matching the criteria.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> async def query_all():
            ...     return [r async for r in s.query()]
            >>> records = asyncio.run(query_all())
            >>> len(records)
            0
        """
        assert self._conn is not None, "Storage not initialized"

        query = "SELECT * FROM records WHERE 1=1"
        params: list[Any] = []

        if layer:
            query += " AND layer = ?"
            params.append(layer.value)

        if filters:
            for key, value in filters.items():
                query += f" AND content->>'{key}' = ?"
                params.append(str(value))

        # Ordering
        if order_by:
            if order_by.startswith("-"):
                query += f" ORDER BY {order_by[1:]} DESC"
            else:
                query += f" ORDER BY {order_by} ASC"

        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        results = self._conn.execute(query, params).fetchall()

        for row in results:
            yield self._row_to_record(row)

    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records matching filters.

        Args:
            layer: Filter by layer.
            filters: Additional filters.

        Returns:
            Number of matching records.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> asyncio.run(s.count())
            0
        """
        assert self._conn is not None, "Storage not initialized"

        query = "SELECT COUNT(*) FROM records WHERE 1=1"
        params: list[Any] = []

        if layer:
            query += " AND layer = ?"
            params.append(layer.value)

        if filters:
            for key, value in filters.items():
                query += f" AND content->>'{key}' = ?"
                params.append(str(value))

        result = self._conn.execute(query, params).fetchone()
        return result[0] if result else 0

    # --- Sighting Operations ---

    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting. Returns True if this was the first sighting.

        Args:
            sighting: The sighting to record.

        Returns:
            True if first sighting for this natural_key+source, False if duplicate.
        """
        assert self._conn is not None, "Storage not initialized"

        # Check if exists first (same natural_key + source)
        existing = self._conn.execute(
            "SELECT 1 FROM sightings WHERE natural_key = ? AND source = ?",
            [sighting.natural_key, sighting.source],
        ).fetchone()

        if existing:
            return False

        self._conn.execute(
            """
            INSERT INTO sightings (id, natural_key, record_id, source, seen_at, is_new, raw_data_hash, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                sighting.id,
                sighting.natural_key,
                sighting.record_id,
                sighting.source,
                sighting.seen_at.isoformat(),
                sighting.is_new,
                sighting.raw_data_hash,
                json.dumps(sighting.metadata or {}),
            ],
        )
        return True

    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a natural key.

        Args:
            natural_key: The natural key to look up.

        Returns:
            List of sightings for this key.
        """
        assert self._conn is not None, "Storage not initialized"

        results = self._conn.execute(
            """SELECT id, natural_key, record_id, source, seen_at, is_new, raw_data_hash, metadata
               FROM sightings WHERE natural_key = ?""",
            [natural_key],
        ).fetchall()

        def parse_seen_at(val: Any) -> datetime:
            """Parse seen_at - may be datetime or string."""
            if isinstance(val, datetime):
                return val.replace(tzinfo=UTC) if val.tzinfo is None else val
            return datetime.fromisoformat(val).replace(tzinfo=UTC)

        return [
            Sighting(
                id=row[0],
                natural_key=row[1],
                record_id=row[2],
                source=row[3],
                seen_at=parse_seen_at(row[4]),
                is_new=row[5],
                raw_data_hash=row[6],
                metadata=json.loads(row[7]) if row[7] else {},
            )
            for row in results
        ]

    # --- Bulk Operations ---

    async def store_batch(
        self,
        records: list[Record],
        *,
        batch_size: int = 1000,
        on_conflict: str = "skip",
    ) -> int:
        """Store multiple records efficiently using DuckDB bulk operations.

        Uses INSERT OR IGNORE/REPLACE for efficient bulk loading.
        Optimized for datasets with 100,000+ records.

        Args:
            records: List of records to store.
            batch_size: Number of records per batch (default: 1000).
            on_conflict: How to handle existing records:
                - "skip": Skip existing (default, uses INSERT OR IGNORE)
                - "update": Update existing (uses INSERT OR REPLACE)
                - "error": Raise on duplicate

        Returns:
            Number of records actually stored.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> # Store 10,000 records efficiently
            >>> # count = asyncio.run(s.store_batch(large_record_list))
        """
        assert self._conn is not None, "Storage not initialized"

        if not records:
            return 0

        stored_count = 0

        # Build SQL based on conflict strategy
        if on_conflict == "skip":
            sql = """INSERT OR IGNORE INTO records 
                     (id, natural_key, layer, content, metadata, published_at, captured_at, updated_at, version)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        elif on_conflict == "update":
            sql = """INSERT OR REPLACE INTO records 
                     (id, natural_key, layer, content, metadata, published_at, captured_at, updated_at, version)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        else:  # error
            sql = """INSERT INTO records 
                     (id, natural_key, layer, content, metadata, published_at, captured_at, updated_at, version)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""

        # Process in batches
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            rows = []

            for record in batch:
                rows.append([
                    record.id,
                    record.natural_key,
                    record.layer.value,
                    json.dumps(record.content),
                    record.metadata.model_dump_json(),
                    record.published_at.isoformat(),
                    record.captured_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.version,
                ])

            # Execute batch
            try:
                self._conn.executemany(sql, rows)
                stored_count += len(rows)
            except Exception:
                if on_conflict == "error":
                    raise
                # For skip/update, some may fail - that's expected
                pass

        return stored_count

    async def delete_batch(
        self,
        record_ids: list[str],
        *,
        batch_size: int = 1000,
    ) -> int:
        """Delete multiple records efficiently.

        Args:
            record_ids: List of record IDs to delete.
            batch_size: Number of IDs per batch.

        Returns:
            Number of records deleted.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> asyncio.run(s.delete_batch(["id1", "id2"]))
            0
        """
        assert self._conn is not None, "Storage not initialized"

        if not record_ids:
            return 0

        deleted_count = 0

        for i in range(0, len(record_ids), batch_size):
            batch = record_ids[i : i + batch_size]
            placeholders = ",".join(["?" for _ in batch])
            result = self._conn.execute(
                f"DELETE FROM records WHERE id IN ({placeholders})",
                batch,
            )
            deleted_count += result.rowcount if hasattr(result, "rowcount") else len(batch)

        return deleted_count

    # --- DuckDB-Specific Analytics ---

    async def execute_sql(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Execute raw SQL query for analytics.

        Provides direct SQL access for complex analytical queries.
        Use with caution - no query validation is performed.

        Args:
            sql: SQL query to execute.
            params: Optional query parameters.

        Returns:
            List of dictionaries with query results.

        Example:
            >>> import asyncio
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> results = asyncio.run(s.execute_sql("SELECT COUNT(*) as cnt FROM records"))
            >>> results[0]["cnt"]
            0
        """
        assert self._conn is not None, "Storage not initialized"

        result = self._conn.execute(sql, params) if params else self._conn.execute(sql)

        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]

    async def export_to_parquet(
        self,
        path: str | Path,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Export records to Parquet file.

        Args:
            path: Output file path.
            layer: Filter by layer.
            filters: Additional filters.

        Returns:
            Number of rows exported.

        Example:
            >>> import asyncio
            >>> from pathlib import Path
            >>> from feedspine.storage.duckdb import DuckDBStorage
            >>> s = DuckDBStorage(":memory:")
            >>> asyncio.run(s.initialize())
            >>> # Export returns count (0 for empty)
            >>> # asyncio.run(s.export_to_parquet(Path("/tmp/test.parquet")))
        """
        assert self._conn is not None, "Storage not initialized"

        # Build query
        query = "SELECT * FROM records WHERE 1=1"
        params: list[Any] = []

        if layer:
            query += " AND layer = ?"
            params.append(layer.value)

        if filters:
            for key, value in filters.items():
                query += f" AND content->>'{key}' = ?"
                params.append(str(value))

        # Get count first
        count_result = self._conn.execute(
            query.replace("SELECT *", "SELECT COUNT(*)"), params
        ).fetchone()
        count = count_result[0] if count_result else 0

        if count == 0:
            return 0

        # Export to parquet
        self._conn.execute(f"COPY ({query}) TO '{path}' (FORMAT PARQUET)", params)

        return count

    async def export_query_to_parquet(self, sql: str, path: str | Path) -> int:
        """Export custom query results to Parquet.

        Args:
            sql: SQL query to export.
            path: Output file path.

        Returns:
            Number of rows exported.
        """
        assert self._conn is not None, "Storage not initialized"

        # Get count first
        count_result = self._conn.execute(f"SELECT COUNT(*) FROM ({sql})").fetchone()
        count = count_result[0] if count_result else 0

        if count == 0:
            return 0

        self._conn.execute(f"COPY ({sql}) TO '{path}' (FORMAT PARQUET)")
        return count

    # --- Private Helpers ---

    def _row_to_record(self, row: tuple[Any, ...]) -> Record:
        """Convert database row to Record model."""
        # Columns: id, natural_key, layer, content, metadata, published_at, captured_at, updated_at, version
        content = row[3] if isinstance(row[3], dict) else json.loads(row[3])
        metadata_raw = row[4] if isinstance(row[4], dict) else json.loads(row[4])

        def parse_datetime(val: Any) -> datetime:
            """Parse datetime from string or return as-is."""
            if isinstance(val, str):
                return datetime.fromisoformat(val).replace(tzinfo=UTC)
            if isinstance(val, datetime):
                return val
            # Fallback: convert to string and parse
            return datetime.fromisoformat(str(val)).replace(tzinfo=UTC)

        return Record(
            id=row[0],
            natural_key=row[1],
            layer=Layer(row[2]),
            content=content,
            metadata=Metadata(**metadata_raw) if metadata_raw else Metadata(source="unknown"),
            published_at=parse_datetime(row[5]),
            captured_at=parse_datetime(row[6]),
            updated_at=parse_datetime(row[7]),
            version=row[8] if len(row) > 8 else 1,
        )
