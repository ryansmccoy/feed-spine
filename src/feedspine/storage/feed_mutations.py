"""Write and mutation operations for FeedRepository.

Provides :class:`FeedMutationMixin` containing all write/mutation
database operations for records, sightings, feed runs, feed configs,
observations, and schema management.

Must be composed with :class:`~feedspine.storage.repository.BaseRepository`
which supplies ``execute``, ``insert``, ``insert_many``, ``commit``,
``ph``, and ``dialect``.

Tags:
    repository, mutations, writes, storage
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from feedspine.models.record import Record
from feedspine.models.sighting import Sighting
from feedspine.storage.schemas import POSTGRES_SCHEMA, SQLITE_SCHEMA
from feedspine.storage.shared.converters import (
    json_serial,
    record_to_row,
    serialize_datetime,
    sighting_to_row,
)


class FeedMutationMixin:
    """Mixin providing all write/mutation operations for FeedRepository.

    Must be used with a class that inherits from
    :class:`~feedspine.storage.repository.BaseRepository`.
    """

    # -- Schema Management -------------------------------------------------

    def ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist.

        Uses the dialect to pick the right DDL (SQLite TEXT vs PostgreSQL JSONB/TIMESTAMPTZ).
        """
        schema = POSTGRES_SCHEMA if self.dialect.name == "postgresql" else SQLITE_SCHEMA
        for statement in schema.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)
        self.commit()

    # -- Record Mutations --------------------------------------------------

    def store_record(self, record: Record) -> None:
        """Upsert a record into the records table.

        On conflict with ``natural_key``, updates content, metadata,
        timestamps, and increments version/seen_count.
        """
        row = record_to_row(record)
        columns = list(row.keys())
        values = tuple(row.values())

        sql = self.dialect.upsert("records", columns, ["natural_key"])
        self.execute(sql, values)

    def store_records(self, records: list[Record]) -> int:
        """Upsert multiple records. Returns count stored."""
        for record in records:
            self.store_record(record)
        return len(records)

    def delete_record(self, record_id: str) -> bool:
        """Delete a record by ID. Returns True if a row was deleted."""
        self.execute(
            f"DELETE FROM records WHERE id = {self.ph(1)}",
            (record_id,),
        )
        return True

    # -- Sighting Mutations ------------------------------------------------

    def store_sighting(self, sighting: Sighting) -> None:
        """Insert a sighting record."""
        row = sighting_to_row(sighting)
        self.insert("sightings", row)

    def store_sightings(self, sightings: list[Sighting]) -> int:
        """Insert multiple sightings. Returns count stored."""
        if not sightings:
            return 0
        rows = [sighting_to_row(s) for s in sightings]
        return self.insert_many("sightings", rows)

    # -- Feed Run Mutations ------------------------------------------------

    def start_feed_run(
        self,
        run_id: str,
        feed_name: str,
        started_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a new feed run record."""
        now = started_at or datetime.now(UTC)
        row = {
            "run_id": run_id,
            "feed_name": feed_name,
            "started_at": serialize_datetime(now),
            "status": "running",
            "records_fetched": 0,
            "records_new": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "metadata": json.dumps(metadata, default=json_serial) if metadata else None,
        }
        self.insert("feed_runs", row)

    def complete_feed_run(
        self,
        run_id: str,
        *,
        status: str = "completed",
        records_fetched: int = 0,
        records_new: int = 0,
        records_updated: int = 0,
        records_unchanged: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Update a feed run with completion data."""
        now = serialize_datetime(datetime.now(UTC))
        sql = (
            f"UPDATE feed_runs SET "
            f"completed_at = {self.ph(1)}, "
            f"status = {self.ph(1)}, "
            f"records_fetched = {self.ph(1)}, "
            f"records_new = {self.ph(1)}, "
            f"records_updated = {self.ph(1)}, "
            f"records_unchanged = {self.ph(1)}, "
            f"error_message = {self.ph(1)} "
            f"WHERE run_id = {self.ph(1)}"
        )
        self.execute(
            sql,
            (
                now,
                status,
                records_fetched,
                records_new,
                records_updated,
                records_unchanged,
                error_message,
                run_id,
            ),
        )

    # -- Metadata Mutations ------------------------------------------------

    def set_meta(self, key: str, value: str) -> None:
        """Set a metadata key-value pair (upsert)."""
        sql = self.dialect.upsert("_feedspine_meta", ["key", "value"], ["key"])
        self.execute(sql, (key, value))

    # -- Feed Config Mutations ---------------------------------------------

    def store_feed_config(self, config: dict[str, Any]) -> None:
        """Upsert a feed configuration."""
        # Serialize nested config dict to JSON if present
        row = dict(config)
        if "config" in row and isinstance(row["config"], dict):
            row["config"] = json.dumps(row["config"], default=json_serial)
        # Keep boolean values as Python booleans - psycopg2 handles conversion
        # SQLite accepts True/False, PostgreSQL needs native bool (not 0/1)

        sql = self.dialect.upsert("feed_configs", list(row.keys()), ["id"])
        self.execute(sql, tuple(row.values()))

    def update_feed_config(self, feed_id: str, updates: dict[str, Any]) -> bool:
        """Update specific fields of a feed config. Returns True if found."""
        existing = self.get_feed_config(feed_id)
        if not existing:
            return False
        existing.update(updates)
        self.store_feed_config(existing)
        return True

    def delete_feed_config(self, feed_id: str) -> bool:
        """Delete a feed config. Returns True if a row was deleted."""
        self.execute(
            f"DELETE FROM feed_configs WHERE id = {self.ph(1)}",
            (feed_id,),
        )
        return True

    # -- Observation Mutations ---------------------------------------------

    def store_observation(self, obs: dict[str, Any]) -> None:
        """Insert or replace an observation (upsert on fingerprint)."""
        row = dict(obs)
        if "data" in row and isinstance(row["data"], dict):
            row["data"] = json.dumps(row["data"], default=json_serial)
        if "metadata" in row and isinstance(row["metadata"], dict):
            row["metadata"] = json.dumps(row["metadata"], default=json_serial)

        sql = self.dialect.upsert("observations", list(row.keys()), ["fingerprint"])
        self.execute(sql, tuple(row.values()))
