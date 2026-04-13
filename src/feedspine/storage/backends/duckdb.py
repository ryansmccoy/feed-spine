"""DuckDB storage backend - refactored with shared components.

This is the refactored DuckDB storage that uses shared converters,
query builders, and validators. Reduced from ~816 lines to ~400 lines.

DuckDB provides an embeddable OLAP database optimized for analytical queries.
This backend is ideal for:
- Analytical queries on collected data
- JSON content field queries
- Parquet export for data warehouse integration
- Time-series analysis with window functions
- Embedded usage (no server required)

Example:
    >>> from feedspine.storage.backends import DuckDBStorage
    >>> storage = DuckDBStorage("feedspine.duckdb")
    >>> await storage.initialize()

Note:
    Requires the `duckdb` optional dependency:
    ``pip install feedspine[duckdb]``
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from spine.core.logging import get_logger

try:
    import duckdb
except ImportError as e:
    raise ImportError("DuckDB is required for DuckDBStorage. Install with: pip install feedspine[duckdb]") from e

from feedspine.models.base import Layer
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting
from feedspine.storage.shared.converters import (
    row_to_record,
    row_to_sighting,
    serialize_datetime,
)
from feedspine.storage.shared.query_builders import DuckDBQueryBuilder
from feedspine.storage.shared.validators import (
    validate_layer,
    validate_record,
    validate_sighting,
)

# Column map for tuple -> Record conversion
logger = get_logger(__name__)

RECORD_COLUMNS = {
    "id": 0,
    "natural_key": 1,
    "layer": 2,
    "content": 3,
    "metadata": 4,
    "published_at": 5,
    "captured_at": 6,
    "updated_at": 7,
    "version": 8,
    "first_seen_at": 9,
    "last_seen_at": 10,
    "seen_count": 11,
}

SIGHTING_COLUMNS = {
    "id": 0,
    "natural_key": 1,
    "record_id": 2,
    "source": 3,
    "seen_at": 4,
    "is_new": 5,
    "raw_data_hash": 6,
    "metadata": 7,
}


class DuckDBStorage:
    """DuckDB storage backend for analytical workloads.

    Uses shared components for query building, type conversion, and validation.
    Provides OLAP-optimized storage with SQL analytics capabilities.

    Args:
        path: Database file path, or ":memory:" for in-memory mode.
        read_only: Open in read-only mode (default False).
    """

    def __init__(self, path: str = ":memory:", *, read_only: bool = False) -> None:
        self._path = path
        self._read_only = read_only
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._initialized = False
        self._query_builder = DuckDBQueryBuilder()

    async def initialize(self) -> None:
        """Initialize storage and create tables."""
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
                version INTEGER NOT NULL DEFAULT 1,
                first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
                last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1
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

        # Create indexes
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_records_natural_key ON records(natural_key)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_records_layer ON records(layer)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sightings_key ON sightings(natural_key)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sightings_source ON sightings(natural_key, source)")

        self._initialized = True

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self._initialized = False

    # --- Record Operations (using shared converters) ---

    async def store(self, record: Record) -> None:
        """Store a record (upsert)."""
        validate_record(record)
        assert self._conn is not None, "Storage not initialized"

        metadata_json = record.metadata.model_dump_json() if record.metadata else "{}"

        self._conn.execute(
            """
            INSERT OR REPLACE INTO records
                (id, natural_key, layer, content, metadata, published_at, captured_at, updated_at, version,
                 first_seen_at, last_seen_at, seen_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.id,
                record.natural_key,
                record.layer.value,
                json.dumps(record.content),
                metadata_json,
                serialize_datetime(record.published_at),
                serialize_datetime(record.captured_at),
                serialize_datetime(record.updated_at),
                record.version,
                serialize_datetime(record.first_seen_at),
                serialize_datetime(record.last_seen_at),
                record.seen_count,
            ],
        )

    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get record by ID."""
        layer = validate_layer(layer)
        assert self._conn is not None, "Storage not initialized"

        if layer:
            result = self._conn.execute(
                "SELECT * FROM records WHERE id = ? AND layer = ?",
                [record_id, layer.value],
            ).fetchone()
        else:
            result = self._conn.execute("SELECT * FROM records WHERE id = ?", [record_id]).fetchone()

        if result:
            return row_to_record(result, RECORD_COLUMNS)
        return None

    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get record by natural key."""
        assert self._conn is not None, "Storage not initialized"

        normalized = natural_key.strip().lower()
        result = self._conn.execute("SELECT * FROM records WHERE LOWER(natural_key) = ?", [normalized]).fetchone()

        if result:
            return row_to_record(result, RECORD_COLUMNS)
        return None

    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if record exists."""
        layer = validate_layer(layer)
        assert self._conn is not None, "Storage not initialized"

        if layer:
            result = self._conn.execute(
                "SELECT 1 FROM records WHERE id = ? AND layer = ?",
                [record_id, layer.value],
            ).fetchone()
        else:
            result = self._conn.execute("SELECT 1 FROM records WHERE id = ?", [record_id]).fetchone()

        return result is not None

    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if natural key exists."""
        assert self._conn is not None, "Storage not initialized"

        normalized = natural_key.strip().lower()
        result = self._conn.execute("SELECT 1 FROM records WHERE LOWER(natural_key) = ?", [normalized]).fetchone()

        return result is not None

    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record."""
        layer = validate_layer(layer)
        assert self._conn is not None, "Storage not initialized"

        if layer:
            result = self._conn.execute(
                "DELETE FROM records WHERE id = ? AND layer = ? RETURNING id",
                [record_id, layer.value],
            ).fetchone()
        else:
            result = self._conn.execute("DELETE FROM records WHERE id = ? RETURNING id", [record_id]).fetchone()

        return result is not None

    async def query(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AsyncIterator[Record]:
        """Query records with filters using shared query builder."""
        layer = validate_layer(layer)
        assert self._conn is not None, "Storage not initialized"

        sql, params = self._query_builder.build_select_query(
            table="records",
            layer=layer.value if layer else None,
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

        results = self._conn.execute(sql, params).fetchall()

        for row in results:
            yield row_to_record(row, RECORD_COLUMNS)

    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records matching filters."""
        layer = validate_layer(layer)
        assert self._conn is not None, "Storage not initialized"

        sql, params = self._query_builder.build_count_query(
            table="records",
            layer=layer.value if layer else None,
            filters=filters,
        )

        result = self._conn.execute(sql, params).fetchone()
        return result[0] if result else 0

    async def count_by_layer(self) -> dict[str, int]:
        """Count records grouped by layer in a single query."""
        assert self._conn is not None, "Storage not initialized"
        results = self._conn.execute("SELECT layer, COUNT(*) FROM records GROUP BY layer").fetchall()
        return {row[0]: row[1] for row in results}

    # --- Sighting Operations (using shared converters) ---

    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting."""
        validate_sighting(sighting)
        assert self._conn is not None, "Storage not initialized"

        # Check if exists first
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
                serialize_datetime(sighting.seen_at),
                sighting.is_new,
                sighting.raw_data_hash,
                json.dumps(sighting.metadata or {}),
            ],
        )
        return True

    async def record_sighting_on_existing(self, natural_key: str) -> Record | None:
        """Update sighting tracking on an existing record."""
        assert self._conn is not None, "Storage not initialized"

        record = await self.get_by_natural_key(natural_key)
        if record is None:
            return None

        updated_record = record.record_sighting()
        await self.store(updated_record)
        return updated_record

    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a natural key."""
        assert self._conn is not None, "Storage not initialized"

        results = self._conn.execute(
            """SELECT id, natural_key, record_id, source, seen_at, is_new, raw_data_hash, metadata
               FROM sightings WHERE natural_key = ?""",
            [natural_key],
        ).fetchall()

        return [row_to_sighting(row, SIGHTING_COLUMNS) for row in results]

    # --- Bulk Operations ---

    async def store_batch(
        self,
        records: list[Record],
        *,
        batch_size: int = 1000,
        on_conflict: str = "skip",
    ) -> int:
        """Store multiple records efficiently."""
        assert self._conn is not None, "Storage not initialized"

        if not records:
            return 0

        stored_count = 0
        sql = self._query_builder.build_upsert_sql(
            table="records",
            columns=[
                "id",
                "natural_key",
                "layer",
                "content",
                "metadata",
                "published_at",
                "captured_at",
                "updated_at",
                "version",
                "first_seen_at",
                "last_seen_at",
                "seen_count",
            ],
            on_conflict=on_conflict,
        )

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            rows = []

            for record in batch:
                rows.append(
                    [
                        record.id,
                        record.natural_key,
                        record.layer.value,
                        json.dumps(record.content),
                        record.metadata.model_dump_json() if record.metadata else "{}",
                        serialize_datetime(record.published_at),
                        serialize_datetime(record.captured_at),
                        serialize_datetime(record.updated_at),
                        record.version,
                        serialize_datetime(record.first_seen_at),
                        serialize_datetime(record.last_seen_at),
                        record.seen_count,
                    ]
                )

            try:
                self._conn.executemany(sql, rows)
                stored_count += len(rows)
            except Exception:
                if on_conflict == "error":
                    raise
                logger.warning(
                    "Failed to store batch of %d records (non-error conflict mode)",
                    len(rows),
                    exc_info=True,
                )

        return stored_count

    async def delete_batch(
        self,
        record_ids: list[str],
        *,
        batch_size: int = 1000,
    ) -> int:
        """Delete multiple records efficiently."""
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
        """Execute raw SQL query for analytics."""
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
        """Export records to Parquet file."""
        layer = validate_layer(layer)
        assert self._conn is not None, "Storage not initialized"

        # Build query
        sql, params = self._query_builder.build_select_query(
            table="records",
            layer=layer.value if layer else None,
            filters=filters,
        )

        # Get count first
        count_sql = sql.replace("SELECT *", "SELECT COUNT(*)")
        count_sql = count_sql.split("ORDER BY")[0]  # Remove ORDER BY
        count_result = self._conn.execute(count_sql, params).fetchone()
        count = count_result[0] if count_result else 0

        if count == 0:
            return 0

        # Export to parquet
        export_sql = self._query_builder.build_parquet_export(sql, str(path))
        self._conn.execute(export_sql, params)

        return count

    async def export_query_to_parquet(self, sql: str, path: str | Path) -> int:
        """Export custom query results to Parquet.

        .. warning::

            ``sql`` is interpolated into the query. Callers **must** ensure
            it comes from trusted, internal code — never from user input.

        Raises:
            ValueError: If ``sql`` contains statement terminators.
        """
        assert self._conn is not None, "Storage not initialized"

        # Reject obvious multi-statement payloads
        if ";" in sql:
            raise ValueError("SQL must be a single SELECT statement")

        count_result = self._conn.execute(  # nosec — sql is internal-only
            f"SELECT COUNT(*) FROM ({sql})"
        ).fetchone()
        count = count_result[0] if count_result else 0

        if count == 0:
            return 0

        export_sql = self._query_builder.build_parquet_export(sql, str(path))
        self._conn.execute(export_sql)  # nosec — delegated to query builder
        return count
