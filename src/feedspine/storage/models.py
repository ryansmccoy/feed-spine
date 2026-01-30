"""
FeedSpine SQLAlchemy Models and Schema Management.

This module provides:
- SQLAlchemy ORM models for all FeedSpine tables
- Automatic schema creation and migrations
- Index definitions optimized for large datasets
- Partitioning support for time-series data

Usage:
    from feedspine.storage.models import Base, RecordModel, create_all_tables
    
    # Create engine
    engine = create_engine("postgresql://...")
    
    # Create all tables
    create_all_tables(engine)
    
    # Or use with Alembic for migrations
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# =============================================================================
# Base Model
# =============================================================================


class Base(DeclarativeBase):
    """Base class for all FeedSpine models."""
    
    # Use JSONB for PostgreSQL, fallback to JSON for others
    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


# =============================================================================
# Record Model - Core storage for captured data
# =============================================================================


class RecordModel(Base):
    """
    Core record storage.
    
    Indexes optimized for:
    - Lookup by key (primary)
    - Filter by layer + feed_id (common query pattern)
    - Filter by captured_at (time-range queries)
    - JSONB content search (GIN index)
    """
    
    __tablename__ = "records"
    __table_args__ = (
        # Composite indexes for common query patterns
        Index("ix_records_layer_feed", "layer", "feed_id"),
        Index("ix_records_feed_captured", "feed_id", "captured_at"),
        Index("ix_records_captured_at", "captured_at"),
        # GIN index for JSONB content (enables @> containment queries)
        Index("ix_records_content_gin", "content", postgresql_using="gin"),
        # Partial index for active records only
        Index(
            "ix_records_active",
            "feed_id",
            "layer",
            postgresql_where="is_deleted = false",
        ),
        {"schema": "feedspine"},
    )
    
    # Primary key
    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    
    # Core fields
    feed_id: Mapped[str] = mapped_column(String(128), nullable=False)
    layer: Mapped[str] = mapped_column(String(32), nullable=False, default="bronze")
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Timestamps
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Source tracking
    source_url: Mapped[str | None] = mapped_column(Text)
    source_etag: Mapped[str | None] = mapped_column(String(256))


# =============================================================================
# Sighting Model - Track when/where records were seen
# =============================================================================


class SightingModel(Base):
    """
    Record sighting tracking.
    
    Tracks each time a record is seen in a feed run.
    Useful for:
    - Detecting disappearing records
    - Audit trail
    - Feed health monitoring
    """
    
    __tablename__ = "sightings"
    __table_args__ = (
        Index("ix_sightings_record_key", "record_key"),
        Index("ix_sightings_run_id", "run_id"),
        Index("ix_sightings_seen_at", "seen_at"),
        {"schema": "feedspine"},
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_key: Mapped[str] = mapped_column(String(512), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# =============================================================================
# FeedRun Model - Track feed execution history
# =============================================================================


class FeedRunModel(Base):
    """
    Feed run execution tracking.
    
    Records each feed capture run with statistics.
    """
    
    __tablename__ = "feed_runs"
    __table_args__ = (
        Index("ix_feed_runs_feed_started", "feed_id", "started_at"),
        Index("ix_feed_runs_status", "status"),
        {"schema": "feedspine"},
    )
    
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feed_id: Mapped[str] = mapped_column(String(128), nullable=False)
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Status
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    error_message: Mapped[str | None] = mapped_column(Text)
    
    # Statistics
    records_seen: Mapped[int] = mapped_column(Integer, default=0)
    records_new: Mapped[int] = mapped_column(Integer, default=0)
    records_changed: Mapped[int] = mapped_column(Integer, default=0)
    records_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    
    # Metadata
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


# =============================================================================
# RecordVersion Model - Version history for auditing
# =============================================================================


class RecordVersionModel(Base):
    """
    Record version history.
    
    Stores previous versions of records for auditing.
    Consider partitioning by created_at for large datasets.
    """
    
    __tablename__ = "record_versions"
    __table_args__ = (
        Index("ix_versions_record_key", "record_key"),
        Index("ix_versions_created_at", "created_at"),
        # BRIN index for time-ordered data (very efficient for append-only)
        Index(
            "ix_versions_created_brin",
            "created_at",
            postgresql_using="brin",
        ),
        {"schema": "feedspine"},
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_key: Mapped[str] = mapped_column(String(512), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    
    # Change tracking
    change_type: Mapped[str] = mapped_column(String(32), nullable=False, default="update")
    changed_fields: Mapped[list[str] | None] = mapped_column(JSONB)


# =============================================================================
# Metadata Model - Key-value store for configuration
# =============================================================================


class MetadataModel(Base):
    """
    Key-value metadata storage.
    
    Stores schema version, last run times, etc.
    """
    
    __tablename__ = "_feedspine_meta"
    __table_args__ = {"schema": "feedspine"}
    
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# =============================================================================
# Schema Management Functions
# =============================================================================


def create_all_tables(engine: Engine, schema: str = "feedspine") -> None:
    """
    Create all FeedSpine tables.
    
    Args:
        engine: SQLAlchemy engine
        schema: Schema name (default: feedspine)
    """
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # Create schema if not exists
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(engine)


def drop_all_tables(engine: Engine) -> None:
    """Drop all FeedSpine tables (use with caution!)."""
    Base.metadata.drop_all(engine)


# =============================================================================
# Partitioning Support (for large datasets)
# =============================================================================


def create_partitioned_records_table(engine: Engine, partition_by: str = "month") -> None:
    """
    Create partitioned records table for large datasets.
    
    Partitioning by captured_at is ideal for:
    - Time-range queries
    - Data retention (drop old partitions)
    - Parallel query execution
    
    Args:
        engine: SQLAlchemy engine
        partition_by: 'day', 'week', 'month', 'year'
    """
    from sqlalchemy import text
    
    # SQL for creating partitioned table
    partition_sql = """
    CREATE TABLE IF NOT EXISTS feedspine.records_partitioned (
        key VARCHAR(512) NOT NULL,
        feed_id VARCHAR(128) NOT NULL,
        layer VARCHAR(32) NOT NULL DEFAULT 'bronze',
        content JSONB NOT NULL,
        content_hash VARCHAR(64) NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
        deleted_at TIMESTAMPTZ,
        source_url TEXT,
        source_etag VARCHAR(256),
        PRIMARY KEY (key, captured_at)
    ) PARTITION BY RANGE (captured_at);
    
    -- Create indexes on partitioned table
    CREATE INDEX IF NOT EXISTS ix_records_part_feed_layer 
        ON feedspine.records_partitioned (feed_id, layer);
    CREATE INDEX IF NOT EXISTS ix_records_part_content_gin 
        ON feedspine.records_partitioned USING GIN (content);
    """
    
    with engine.connect() as conn:
        conn.execute(text(partition_sql))
        conn.commit()


def create_partition(
    engine: Engine,
    start_date: datetime,
    end_date: datetime,
    partition_name: str | None = None,
) -> None:
    """
    Create a partition for records_partitioned table.
    
    Args:
        engine: SQLAlchemy engine
        start_date: Partition start (inclusive)
        end_date: Partition end (exclusive)
        partition_name: Optional custom name
    """
    from sqlalchemy import text
    
    if partition_name is None:
        partition_name = f"records_{start_date.strftime('%Y%m')}"
    
    sql = f"""
    CREATE TABLE IF NOT EXISTS feedspine.{partition_name}
    PARTITION OF feedspine.records_partitioned
    FOR VALUES FROM ('{start_date.isoformat()}') TO ('{end_date.isoformat()}');
    """
    
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()


# =============================================================================
# TimescaleDB Support
# =============================================================================


def create_timescale_hypertable(engine: Engine, chunk_interval: str = "1 month") -> None:
    """
    Convert records table to TimescaleDB hypertable.
    
    Hypertables provide:
    - Automatic partitioning (chunks)
    - Compression for old data
    - Continuous aggregates
    - Retention policies
    
    Args:
        engine: SQLAlchemy engine connected to TimescaleDB
        chunk_interval: Time interval for chunks (default: 1 month)
    """
    from sqlalchemy import text
    
    sql = f"""
    -- Convert to hypertable (idempotent with if_not_exists)
    SELECT create_hypertable(
        'feedspine.records',
        'captured_at',
        chunk_time_interval => INTERVAL '{chunk_interval}',
        if_not_exists => TRUE,
        migrate_data => TRUE
    );
    
    -- Add compression policy for data older than 7 days
    ALTER TABLE feedspine.records SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'feed_id, layer'
    );
    
    SELECT add_compression_policy(
        'feedspine.records',
        INTERVAL '7 days',
        if_not_exists => TRUE
    );
    
    -- Add retention policy (optional - keeps 1 year of data)
    -- SELECT add_retention_policy('feedspine.records', INTERVAL '1 year');
    """
    
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()


# =============================================================================
# Index Recommendations
# =============================================================================


INDEX_RECOMMENDATIONS = """
Index Recommendations for Large Datasets (10M+ records):

1. JSONB GIN Index (already included):
   - Enables fast @> containment queries
   - Example: content @> '{"company": "Apple"}'
   - Cost: ~20% storage overhead

2. BRIN Index for Time Columns:
   - Much smaller than B-tree (1000x smaller)
   - Perfect for append-only time-series data
   - Example: CREATE INDEX ... USING BRIN (captured_at)

3. Partial Indexes:
   - Index only rows that matter
   - Example: WHERE is_deleted = false
   - Reduces index size significantly

4. Expression Indexes:
   - Index computed values
   - Example: CREATE INDEX ON records ((content->>'ticker'))
   - Speeds up queries filtering by JSONB field

5. Covering Indexes (INCLUDE):
   - Add columns to avoid table lookup
   - Example: CREATE INDEX ... INCLUDE (content_hash)
   - Trades storage for query speed

Query Patterns to Optimize:

1. Filter by feed + layer + date range:
   INDEX (feed_id, layer, captured_at)

2. Search by JSONB field:
   INDEX ((content->>'field_name'))

3. Find latest records per feed:
   INDEX (feed_id, captured_at DESC)

4. Full-text search in JSONB:
   CREATE INDEX ... USING GIN (to_tsvector('english', content::text))
"""
