"""Initial schema - records, sightings, feed_runs, record_versions, meta.

Revision ID: 0001
Revises: None
Create Date: 2025-01-01 00:00:00.000000

This migration creates the canonical FeedSpine schema that matches
the raw SQL backends (sqlite.py, postgres.py, duckdb.py).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- records ---
    op.create_table(
        "records",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("natural_key", sa.Text(), nullable=False),
        sa.Column("layer", sa.Text(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("natural_key"),
    )
    op.create_index("idx_records_layer", "records", ["layer"])
    op.create_index("idx_records_published", "records", ["published_at"])
    op.create_index("idx_records_captured", "records", ["captured_at"])

    # --- sightings ---
    op.create_table(
        "sightings",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("natural_key", sa.Text(), nullable=False),
        sa.Column("record_id", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_new", sa.Boolean(), nullable=False),
        sa.Column("raw_data_hash", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sightings_key", "sightings", ["natural_key"])
    op.create_index("idx_sightings_source", "sightings", ["source"])
    op.create_index("idx_sightings_seen", "sightings", ["seen_at"])

    # --- feed_runs ---
    op.create_table(
        "feed_runs",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("feed_name", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("records_fetched", sa.Integer(), server_default="0"),
        sa.Column("records_new", sa.Integer(), server_default="0"),
        sa.Column("records_updated", sa.Integer(), server_default="0"),
        sa.Column("records_unchanged", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("idx_feed_runs_feed", "feed_runs", ["feed_name"])

    # --- record_versions ---
    op.create_table(
        "record_versions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("record_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("parent_version", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_key", "version", name="uq_record_version"),
    )
    op.create_index("idx_versions_key", "record_versions", ["record_key"])

    # --- _feedspine_meta ---
    op.create_table(
        "_feedspine_meta",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    # Stamp schema version
    op.execute("INSERT INTO _feedspine_meta (key, value) VALUES ('schema_version', '1')")


def downgrade() -> None:
    op.drop_table("_feedspine_meta")
    op.drop_table("record_versions")
    op.drop_table("feed_runs")
    op.drop_table("sightings")
    op.drop_table("records")
