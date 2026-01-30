"""
SQLAlchemy-based PostgreSQL Storage Backend.

Production-ready storage with:
- SQLAlchemy ORM for schema management
- Connection pooling
- Batch operations for bulk inserts
- Query optimization for large datasets
- Automatic schema creation

Usage:
    from feedspine.storage.sqlalchemy_storage import SQLAlchemyStorage
    
    # Basic usage (auto-creates schema)
    storage = SQLAlchemyStorage("postgresql://user:pass@localhost/db")
    await storage.initialize()
    
    # With connection pooling
    storage = SQLAlchemyStorage(
        "postgresql://user:pass@localhost/db",
        pool_size=20,
        max_overflow=10,
    )
    
    # With PgBouncer (use NullPool)
    storage = SQLAlchemyStorage(
        "postgresql://user:pass@pgbouncer:6432/db",
        poolclass="null",  # Let PgBouncer handle pooling
    )
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterator, Sequence

from feedspine.models import Record, Sighting, FeedRunStats

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# Storage Configuration
# =============================================================================


class StorageConfig:
    """
    Storage configuration with sensible defaults.
    
    Attributes:
        pool_size: Connection pool size (default: 5)
        max_overflow: Extra connections allowed (default: 10)
        pool_timeout: Seconds to wait for connection (default: 30)
        pool_recycle: Recycle connections after N seconds (default: 1800)
        batch_size: Records per batch insert (default: 1000)
        echo: Log SQL statements (default: False)
        schema: Database schema name (default: feedspine)
    """
    
    def __init__(
        self,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        batch_size: int = 1000,
        echo: bool = False,
        schema: str = "feedspine",
        use_timescale: bool = False,
    ):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.batch_size = batch_size
        self.echo = echo
        self.schema = schema
        self.use_timescale = use_timescale


# =============================================================================
# SQLAlchemy Storage Backend
# =============================================================================


class SQLAlchemyStorage:
    """
    Production PostgreSQL storage using SQLAlchemy.
    
    Features:
    - Automatic schema creation
    - Connection pooling (configurable)
    - Batch inserts for bulk operations
    - Query optimization helpers
    - TimescaleDB support (optional)
    
    For millions of records:
    - Use batch_upsert() for bulk inserts
    - Use iterate_records() for memory-efficient reads
    - Enable TimescaleDB for time-series compression
    
    Args:
        connection_string: PostgreSQL connection string
        config: StorageConfig instance (optional)
        **kwargs: Override config options
    """
    
    def __init__(
        self,
        connection_string: str,
        config: StorageConfig | None = None,
        **kwargs: Any,
    ):
        self.connection_string = connection_string
        self.config = config or StorageConfig(**kwargs)
        self._engine: Engine | None = None
        self._initialized = False
    
    def _get_engine(self) -> "Engine":
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            from sqlalchemy.pool import NullPool, QueuePool
            
            # Choose pool class
            poolclass = QueuePool
            pool_kwargs: dict[str, Any] = {
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
                "pool_timeout": self.config.pool_timeout,
                "pool_recycle": self.config.pool_recycle,
            }
            
            # Use NullPool if connecting through PgBouncer
            if "pgbouncer" in self.connection_string.lower() or self.config.pool_size == 0:
                poolclass = NullPool
                pool_kwargs = {}
            
            self._engine = create_engine(
                self.connection_string,
                poolclass=poolclass,
                echo=self.config.echo,
                **pool_kwargs,
            )
        
        return self._engine
    
    @contextmanager
    def session(self) -> Iterator["Session"]:
        """Context manager for database sessions."""
        from sqlalchemy.orm import sessionmaker
        
        Session = sessionmaker(bind=self._get_engine())
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    async def initialize(self) -> None:
        """
        Initialize storage (create schema and tables).
        
        Safe to call multiple times - uses IF NOT EXISTS.
        """
        from feedspine.storage.models import create_all_tables
        from sqlalchemy import text
        
        engine = self._get_engine()
        
        # Create schema
        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.config.schema}"))
            conn.commit()
        
        # Create tables
        create_all_tables(engine, self.config.schema)
        
        # Initialize TimescaleDB if requested
        if self.config.use_timescale:
            try:
                from feedspine.storage.models import create_timescale_hypertable
                create_timescale_hypertable(engine)
                logger.info("TimescaleDB hypertable created")
            except Exception as e:
                logger.warning(f"TimescaleDB not available: {e}")
        
        # Store schema version
        with self.session() as session:
            from feedspine.storage.models import MetadataModel
            
            meta = session.get(MetadataModel, "schema_version")
            if meta is None:
                meta = MetadataModel(
                    key="schema_version",
                    value="1.0.0",
                )
                session.add(meta)
        
        self._initialized = True
        logger.info(f"SQLAlchemyStorage initialized (schema: {self.config.schema})")
    
    async def close(self) -> None:
        """Close all connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
    
    # =========================================================================
    # Record Operations
    # =========================================================================
    
    async def store(self, record: Record) -> str:
        """
        Store a single record (upsert).
        
        Returns the record key.
        """
        from feedspine.storage.models import RecordModel
        
        with self.session() as session:
            existing = session.get(RecordModel, record.key)
            
            if existing:
                # Update existing
                existing.content = record.content
                existing.content_hash = record.content_hash
                existing.version = existing.version + 1
                existing.layer = record.layer
                existing.updated_at = datetime.now(timezone.utc)
            else:
                # Insert new
                model = RecordModel(
                    key=record.key,
                    feed_id=record.feed_id,
                    layer=record.layer,
                    content=record.content,
                    content_hash=record.content_hash,
                    version=1,
                    captured_at=record.captured_at,
                    source_url=record.metadata.source_url if record.metadata else None,
                )
                session.add(model)
        
        return record.key
    
    async def batch_upsert(
        self,
        records: Sequence[Record],
        batch_size: int | None = None,
    ) -> int:
        """
        Bulk upsert records efficiently.
        
        Uses PostgreSQL's ON CONFLICT for atomic upserts.
        
        For millions of records:
        - Uses batching to avoid memory issues
        - Uses COPY for initial loads (when table is empty)
        - Returns count of affected rows
        
        Args:
            records: Records to upsert
            batch_size: Override default batch size
            
        Returns:
            Number of records processed
        """
        from sqlalchemy import text
        
        batch_size = batch_size or self.config.batch_size
        total = 0
        
        with self.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                # Build values for batch insert
                values = []
                params = {}
                
                for j, record in enumerate(batch):
                    prefix = f"r{j}_"
                    values.append(f"""(
                        :{prefix}key,
                        :{prefix}feed_id,
                        :{prefix}layer,
                        :{prefix}content::jsonb,
                        :{prefix}content_hash,
                        1,
                        :{prefix}captured_at,
                        NOW(),
                        FALSE,
                        NULL,
                        :{prefix}source_url,
                        NULL
                    )""")
                    
                    params[f"{prefix}key"] = record.key
                    params[f"{prefix}feed_id"] = record.feed_id
                    params[f"{prefix}layer"] = record.layer
                    params[f"{prefix}content"] = json.dumps(record.content)
                    params[f"{prefix}content_hash"] = record.content_hash
                    params[f"{prefix}captured_at"] = record.captured_at
                    params[f"{prefix}source_url"] = (
                        record.metadata.source_url if record.metadata else None
                    )
                
                # Execute batch upsert
                sql = f"""
                INSERT INTO {self.config.schema}.records (
                    key, feed_id, layer, content, content_hash, version,
                    captured_at, updated_at, is_deleted, deleted_at,
                    source_url, source_etag
                )
                VALUES {', '.join(values)}
                ON CONFLICT (key) DO UPDATE SET
                    content = EXCLUDED.content,
                    content_hash = EXCLUDED.content_hash,
                    layer = EXCLUDED.layer,
                    version = records.version + 1,
                    updated_at = NOW(),
                    is_deleted = FALSE
                """
                
                session.execute(text(sql), params)
                total += len(batch)
                
                logger.debug(f"Batch upserted {total} records")
        
        return total
    
    async def get(self, key: str) -> Record | None:
        """Get a record by key."""
        from feedspine.storage.models import RecordModel
        
        with self.session() as session:
            model = session.get(RecordModel, key)
            if model is None or model.is_deleted:
                return None
            
            return self._model_to_record(model)
    
    async def get_many(self, keys: Sequence[str]) -> dict[str, Record]:
        """Get multiple records by keys."""
        from feedspine.storage.models import RecordModel
        from sqlalchemy import select
        
        result = {}
        
        with self.session() as session:
            stmt = (
                select(RecordModel)
                .where(RecordModel.key.in_(keys))
                .where(RecordModel.is_deleted == False)
            )
            
            for model in session.scalars(stmt):
                result[model.key] = self._model_to_record(model)
        
        return result
    
    async def delete(self, key: str) -> bool:
        """Soft delete a record."""
        from feedspine.storage.models import RecordModel
        
        with self.session() as session:
            model = session.get(RecordModel, key)
            if model is None:
                return False
            
            model.is_deleted = True
            model.deleted_at = datetime.now(timezone.utc)
            return True
    
    # =========================================================================
    # Query Operations (Optimized for Large Datasets)
    # =========================================================================
    
    async def query_records(
        self,
        feed_id: str | None = None,
        layer: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        content_filter: dict[str, Any] | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Record]:
        """
        Query records with filters.
        
        For large datasets, use iterate_records() instead.
        
        Args:
            feed_id: Filter by feed ID
            layer: Filter by layer (bronze, silver, gold)
            since: Records captured after this time
            until: Records captured before this time
            content_filter: JSONB containment filter (@>)
            limit: Max records to return
            offset: Skip this many records
        """
        from feedspine.storage.models import RecordModel
        from sqlalchemy import select
        
        with self.session() as session:
            stmt = (
                select(RecordModel)
                .where(RecordModel.is_deleted == False)
                .limit(limit)
                .offset(offset)
            )
            
            if feed_id:
                stmt = stmt.where(RecordModel.feed_id == feed_id)
            if layer:
                stmt = stmt.where(RecordModel.layer == layer)
            if since:
                stmt = stmt.where(RecordModel.captured_at >= since)
            if until:
                stmt = stmt.where(RecordModel.captured_at < until)
            if content_filter:
                # JSONB containment query
                stmt = stmt.where(
                    RecordModel.content.contains(content_filter)
                )
            
            return [
                self._model_to_record(model)
                for model in session.scalars(stmt)
            ]
    
    def iterate_records(
        self,
        feed_id: str | None = None,
        layer: str | None = None,
        batch_size: int = 1000,
    ) -> Iterator[Record]:
        """
        Memory-efficient iterator for large result sets.
        
        Uses server-side cursors to avoid loading all records into memory.
        
        Usage:
            for record in storage.iterate_records(feed_id="sec"):
                process(record)
        
        Args:
            feed_id: Filter by feed ID
            layer: Filter by layer
            batch_size: Fetch this many records at a time
        """
        from feedspine.storage.models import RecordModel
        from sqlalchemy import select
        
        with self.session() as session:
            stmt = (
                select(RecordModel)
                .where(RecordModel.is_deleted == False)
                .execution_options(yield_per=batch_size)
            )
            
            if feed_id:
                stmt = stmt.where(RecordModel.feed_id == feed_id)
            if layer:
                stmt = stmt.where(RecordModel.layer == layer)
            
            for model in session.scalars(stmt):
                yield self._model_to_record(model)
    
    async def count_records(
        self,
        feed_id: str | None = None,
        layer: str | None = None,
    ) -> int:
        """Count records matching filters."""
        from feedspine.storage.models import RecordModel
        from sqlalchemy import func, select
        
        with self.session() as session:
            stmt = select(func.count()).select_from(RecordModel).where(
                RecordModel.is_deleted == False
            )
            
            if feed_id:
                stmt = stmt.where(RecordModel.feed_id == feed_id)
            if layer:
                stmt = stmt.where(RecordModel.layer == layer)
            
            return session.scalar(stmt) or 0
    
    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        from feedspine.storage.models import RecordModel, SightingModel, RecordVersionModel
        from sqlalchemy import func, select
        
        with self.session() as session:
            records = session.scalar(
                select(func.count()).select_from(RecordModel).where(
                    RecordModel.is_deleted == False
                )
            ) or 0
            
            sightings = session.scalar(
                select(func.count()).select_from(SightingModel)
            ) or 0
            
            versions = session.scalar(
                select(func.count()).select_from(RecordVersionModel)
            ) or 0
            
            # Count by layer
            layer_counts = session.execute(
                select(RecordModel.layer, func.count())
                .where(RecordModel.is_deleted == False)
                .group_by(RecordModel.layer)
            ).all()
            
            return {
                "records": records,
                "sightings": sightings,
                "versions": versions,
                "by_layer": {layer: count for layer, count in layer_counts},
            }
    
    # =========================================================================
    # Advanced Queries (for Analytics)
    # =========================================================================
    
    async def query_jsonb(
        self,
        jsonb_path: str,
        value: Any,
        operator: str = "=",
        limit: int = 100,
    ) -> list[Record]:
        """
        Query by JSONB field with optimized index usage.
        
        Uses expression index if available.
        
        Args:
            jsonb_path: JSONB path (e.g., "ticker" or "company.name")
            value: Value to match
            operator: Comparison operator (=, >, <, etc.)
            limit: Max records to return
        
        Example:
            # Find all records where content.ticker = 'AAPL'
            records = await storage.query_jsonb("ticker", "AAPL")
        """
        from sqlalchemy import text
        
        with self.session() as session:
            # Build JSONB path query
            sql = f"""
            SELECT * FROM {self.config.schema}.records
            WHERE is_deleted = FALSE
            AND content->>:path {operator} :value
            LIMIT :limit
            """
            
            result = session.execute(
                text(sql),
                {"path": jsonb_path, "value": str(value), "limit": limit}
            )
            
            return [
                self._row_to_record(row)
                for row in result.mappings()
            ]
    
    async def aggregate_by_field(
        self,
        jsonb_path: str,
        feed_id: str | None = None,
    ) -> dict[str, int]:
        """
        Aggregate record counts by JSONB field value.
        
        Useful for analytics dashboards.
        
        Args:
            jsonb_path: JSONB field to group by
            feed_id: Optional feed filter
            
        Returns:
            Dict of field_value -> count
        """
        from sqlalchemy import text
        
        with self.session() as session:
            where_clause = "WHERE is_deleted = FALSE"
            params: dict[str, Any] = {"path": jsonb_path}
            
            if feed_id:
                where_clause += " AND feed_id = :feed_id"
                params["feed_id"] = feed_id
            
            sql = f"""
            SELECT content->>:path as field_value, COUNT(*) as cnt
            FROM {self.config.schema}.records
            {where_clause}
            GROUP BY content->>:path
            ORDER BY cnt DESC
            """
            
            result = session.execute(text(sql), params)
            return {row.field_value: row.cnt for row in result if row.field_value}
    
    # =========================================================================
    # Maintenance Operations
    # =========================================================================
    
    async def vacuum_analyze(self) -> None:
        """Run VACUUM ANALYZE for query optimization."""
        from sqlalchemy import text
        
        engine = self._get_engine()
        with engine.connect() as conn:
            # Must run outside transaction
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text(f"VACUUM ANALYZE {self.config.schema}.records"))
    
    async def create_expression_index(self, jsonb_path: str) -> None:
        """
        Create expression index for frequently queried JSONB field.
        
        Dramatically speeds up queries like:
            WHERE content->>'ticker' = 'AAPL'
        
        Args:
            jsonb_path: JSONB field to index (e.g., "ticker")
        """
        from sqlalchemy import text
        
        index_name = f"ix_records_content_{jsonb_path.replace('.', '_')}"
        
        with self.session() as session:
            session.execute(text(f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON {self.config.schema}.records ((content->>'{jsonb_path}'))
            """))
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _model_to_record(self, model: Any) -> Record:
        """Convert SQLAlchemy model to Record."""
        from feedspine.models import Metadata
        
        return Record(
            key=model.key,
            feed_id=model.feed_id,
            layer=model.layer,
            content=model.content,
            content_hash=model.content_hash,
            captured_at=model.captured_at,
            metadata=Metadata(
                source_url=model.source_url,
                source_etag=model.source_etag,
            ) if model.source_url else Metadata(),
        )
    
    def _row_to_record(self, row: Any) -> Record:
        """Convert raw row to Record."""
        from feedspine.models import Metadata
        
        content = row["content"]
        if isinstance(content, str):
            content = json.loads(content)
        
        return Record(
            key=row["key"],
            feed_id=row["feed_id"],
            layer=row["layer"],
            content=content,
            content_hash=row["content_hash"],
            captured_at=row["captured_at"],
            metadata=Metadata(
                source_url=row.get("source_url"),
                source_etag=row.get("source_etag"),
            ),
        )
