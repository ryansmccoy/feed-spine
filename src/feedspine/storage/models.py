"""
FeedSpine SQLAlchemy Models and Schema Management.

This module provides:
- SQLAlchemy ORM models aligned with the raw SQL backends (sqlite, postgres, duckdb)
- Automatic schema creation and migrations via Alembic
- Index definitions optimized for large datasets

The canonical schema is defined by the raw SQL backends (sqlite.py, postgres.py).
These ORM models mirror that schema for use with SQLAlchemy-based storage and
Alembic migrations.

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
    DateTime,
    Index,
    Integer,
    Text,
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

    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


# =============================================================================
# Record Model - Core storage for captured data
# =============================================================================


class RecordModel(Base):
    """
    Core record storage.

    Aligned with the raw SQL schema in sqlite.py / postgres.py.

    Columns:
        id: Unique record identifier (TEXT PK)
        natural_key: Business-domain deduplication key (UNIQUE)
        layer: Medallion layer (bronze/silver/gold)
        content: JSON payload
        metadata: Optional JSON metadata
        published_at: When the source published the record
        captured_at: When feedspine captured the record
        updated_at: Last update timestamp
        version: Monotonically increasing version (auto-incremented on upsert)
        first_seen_at: Timestamp of first observation
        last_seen_at: Timestamp of most recent observation
        seen_count: Number of times this record has been observed
    """

    __tablename__ = "records"
    __table_args__ = (
        Index("idx_records_layer", "layer"),
        Index("idx_records_published", "published_at"),
        Index("idx_records_captured", "captured_at"),
        # GIN index for JSONB content (PostgreSQL only)
        Index("ix_records_content_gin", "content", postgresql_using="gin"),
    )

    # Primary key
    id: Mapped[str] = mapped_column(Text, primary_key=True)

    # Business key for deduplication
    natural_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Medallion layer
    layer: Mapped[str] = mapped_column(Text, nullable=False)

    # Payload
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    # Timestamps
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Sighting tracking (maintained by upsert logic)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


# =============================================================================
# Sighting Model - Track when/where records were seen
# =============================================================================


class SightingModel(Base):
    """
    Record sighting tracking.

    Each row records a single observation of a natural_key from a source.
    """

    __tablename__ = "sightings"
    __table_args__ = (
        Index("idx_sightings_key", "natural_key"),
        Index("idx_sightings_source", "source"),
        Index("idx_sightings_seen", "seen_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    natural_key: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_data_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    sighting_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )


# =============================================================================
# FeedRun Model - Track feed execution history
# =============================================================================


class FeedRunModel(Base):
    """Feed run execution tracking with statistics."""

    __tablename__ = "feed_runs"
    __table_args__ = (Index("idx_feed_runs_feed", "feed_name"),)

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    feed_name: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_new: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )


# =============================================================================
# RecordVersion Model - Version history for auditing
# =============================================================================


class RecordVersionModel(Base):
    """Record version history for auditing and rollback."""

    __tablename__ = "record_versions"
    __table_args__ = (Index("idx_versions_key", "record_key"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    record_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )


# =============================================================================
# Metadata Model - Key-value store for configuration
# =============================================================================


class MetadataModel(Base):
    """Key-value metadata storage (schema version, etc.)."""

    __tablename__ = "_feedspine_meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


# =============================================================================
# Schema Management Functions
# =============================================================================


def create_all_tables(engine: Engine) -> None:
    """Create all FeedSpine tables.

    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.create_all(engine)


def drop_all_tables(engine: Engine) -> None:
    """Drop all FeedSpine tables (use with caution!)."""
    Base.metadata.drop_all(engine)
