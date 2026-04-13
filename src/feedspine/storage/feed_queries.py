"""Query and read operations for FeedRepository.

Provides :class:`FeedQueryMixin` containing all read-only database
operations for records, sightings, feed runs, feed configs,
observations, and statistics/health reporting.

Must be composed with :class:`~feedspine.storage.repository.BaseRepository`
which supplies ``query``, ``query_one``, ``ph``, and ``dialect``.

Tags:
    repository, queries, reads, storage
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from feedspine.models.record import Record
from feedspine.models.sighting import Sighting
from feedspine.storage.shared.converters import (
    row_to_record,
    row_to_sighting,
    serialize_datetime,
)


class FeedQueryMixin:
    """Mixin providing all query/read operations for FeedRepository.

    Must be used with a class that inherits from
    :class:`~feedspine.storage.repository.BaseRepository`.
    """

    # -- Record Queries ----------------------------------------------------

    def get_record(self, record_id: str) -> Record | None:
        """Get a record by its primary key ``id``."""
        row = self.query_one(
            f"SELECT * FROM records WHERE id = {self.ph(1)}",
            (record_id,),
        )
        return row_to_record(row) if row else None

    def get_record_by_key(self, natural_key: str) -> Record | None:
        """Get a record by its business key ``natural_key``."""
        row = self.query_one(
            f"SELECT * FROM records WHERE natural_key = {self.ph(1)}",
            (natural_key,),
        )
        return row_to_record(row) if row else None

    def query_records(
        self,
        *,
        layer: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "captured_at DESC",
    ) -> list[Record]:
        """Query records with optional filtering.

        Args:
            layer: Filter by medallion layer (e.g. 'bronze', 'silver')
            since: Records captured after this time
            until: Records captured before this time
            limit: Max rows to return
            offset: Number of rows to skip
            order_by: SQL ORDER BY clause

        Returns:
            List of Record domain models
        """
        conditions: list[str] = []
        params: list[Any] = []

        if layer:
            conditions.append(f"layer = {self.ph(1)}")
            params.append(layer)

        if since:
            conditions.append(f"captured_at >= {self.dialect.placeholder(len(params))}")
            params.append(serialize_datetime(since))

        if until:
            conditions.append(f"captured_at < {self.dialect.placeholder(len(params))}")
            params.append(serialize_datetime(until))

        where = " AND ".join(conditions) if conditions else "1=1"

        # Sanitize order_by to prevent SQL injection
        allowed_columns = {
            "captured_at",
            "published_at",
            "updated_at",
            "natural_key",
            "layer",
            "version",
            "seen_count",
        }
        order_parts = order_by.split()
        col = order_parts[0] if order_parts else "captured_at"
        direction = order_parts[1].upper() if len(order_parts) > 1 else "DESC"
        if col not in allowed_columns:
            col = "captured_at"
        if direction not in ("ASC", "DESC"):
            direction = "DESC"
        safe_order = f"{col} {direction}"

        sql = f"SELECT * FROM records WHERE {where} ORDER BY {safe_order} LIMIT {int(limit)} OFFSET {int(offset)}"

        rows = self.query(sql, tuple(params))
        return [r for row in rows if (r := row_to_record(row)) is not None]

    def count_records(self, *, layer: str | None = None) -> int:
        """Count records, optionally filtered by layer."""
        if layer:
            row = self.query_one(
                f"SELECT COUNT(*) as cnt FROM records WHERE layer = {self.ph(1)}",
                (layer,),
            )
        else:
            row = self.query_one("SELECT COUNT(*) as cnt FROM records")
        return row["cnt"] if row else 0

    # -- Sighting Queries --------------------------------------------------

    def get_sightings(
        self,
        natural_key: str,
        *,
        limit: int = 100,
    ) -> list[Sighting]:
        """Get sightings for a natural key, newest first."""
        rows = self.query(
            f"SELECT * FROM sightings WHERE natural_key = {self.ph(1)} ORDER BY seen_at DESC LIMIT {int(limit)}",
            (natural_key,),
        )
        return [row_to_sighting(row) for row in rows]

    def count_sightings(self) -> int:
        """Count all sightings."""
        row = self.query_one("SELECT COUNT(*) as cnt FROM sightings")
        return row["cnt"] if row else 0

    # -- Feed Run Queries --------------------------------------------------

    def get_feed_runs(
        self,
        feed_name: str | None = None,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recent feed runs, optionally filtered by feed name."""
        if feed_name:
            return self.query(
                f"SELECT * FROM feed_runs WHERE feed_name = {self.ph(1)} ORDER BY started_at DESC LIMIT {int(limit)}",
                (feed_name,),
            )
        return self.query(f"SELECT * FROM feed_runs ORDER BY started_at DESC LIMIT {int(limit)}")

    # -- Metadata Queries --------------------------------------------------

    def get_meta(self, key: str) -> str | None:
        """Get a metadata value by key."""
        row = self.query_one(
            f"SELECT value FROM _feedspine_meta WHERE key = {self.ph(1)}",
            (key,),
        )
        return row["value"] if row else None

    # -- Statistics --------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        record_count = self.count_records()
        sighting_count = self.count_sightings()

        layer_counts: dict[str, int] = {
            row["layer"]: row["cnt"] for row in self.query("SELECT layer, COUNT(*) AS cnt FROM records GROUP BY layer")
        }

        return {
            "total_records": record_count,
            "total_sightings": sighting_count,
            "records_by_layer": layer_counts,
            "schema_version": self.get_meta("schema_version"),
        }

    def get_collection_stats(self, days: int = 30) -> dict[str, Any]:
        """Get aggregated collection statistics.

        Returns:
            Dictionary with total_runs, successful_runs, failed_runs,
            total_records_collected, total_errors, avg_records_per_run,
            feeds_active, runs_per_day.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        cutoff_str = serialize_datetime(cutoff)

        # Get all runs in the time window
        runs = self.query(
            f"SELECT * FROM feed_runs WHERE started_at >= {self.ph(1)}",
            (cutoff_str,),
        )

        if not runs:
            return {
                "days": days,
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "total_records_collected": 0,
                "total_errors": 0,
                "avg_records_per_run": 0.0,
                "feeds_active": 0,
                "runs_per_day": 0.0,
            }

        total_runs = len(runs)
        successful = sum(1 for r in runs if r.get("status") == "completed")
        failed = sum(1 for r in runs if r.get("status") in ("failed", "error"))
        total_records = sum(r.get("records_new", 0) or 0 for r in runs)
        total_errors = sum(r.get("records_errors", 0) or 0 for r in runs)
        feeds_active = len(set(r.get("feed_name") for r in runs if r.get("feed_name")))

        return {
            "days": days,
            "total_runs": total_runs,
            "successful_runs": successful,
            "failed_runs": failed,
            "total_records_collected": total_records,
            "total_errors": total_errors,
            "avg_records_per_run": total_records / total_runs if total_runs > 0 else 0.0,
            "feeds_active": feeds_active,
            "runs_per_day": total_runs / days if days > 0 else 0.0,
        }

    def get_feed_collection_stats(
        self,
        feed_name: str | None = None,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get per-feed collection statistics.

        Returns list of dicts with: feed_name, total_runs, successful_runs,
        total_records, avg_records_per_run, last_run_at, success_rate.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        cutoff_str = serialize_datetime(cutoff)

        if feed_name:
            runs = self.query(
                f"SELECT * FROM feed_runs WHERE feed_name = {self.ph(1)} AND started_at >= {self.ph(1)}",
                (feed_name, cutoff_str),
            )
            feed_runs = {feed_name: runs}
        else:
            runs = self.query(
                f"SELECT * FROM feed_runs WHERE started_at >= {self.ph(1)}",
                (cutoff_str,),
            )
            # Group by feed_name
            feed_runs: dict[str, list[dict[str, Any]]] = {}
            for r in runs:
                fname = r.get("feed_name", "unknown")
                if fname not in feed_runs:
                    feed_runs[fname] = []
                feed_runs[fname].append(r)

        result = []
        for fname, fruns in feed_runs.items():
            if not fruns:
                continue
            total = len(fruns)
            successful = sum(1 for r in fruns if r.get("status") == "completed")
            total_records = sum(r.get("records_new", 0) or 0 for r in fruns)
            last_run = max((r.get("started_at") for r in fruns if r.get("started_at")), default=None)

            result.append(
                {
                    "feed_name": fname,
                    "total_runs": total,
                    "successful_runs": successful,
                    "total_records": total_records,
                    "avg_records_per_run": total_records / total if total > 0 else 0.0,
                    "last_run_at": last_run,
                    "success_rate": successful / total if total > 0 else 0.0,
                }
            )

        # Sort by total_records descending
        return sorted(result, key=lambda x: x["total_records"], reverse=True)

    def get_storage_summary(self) -> dict[str, Any]:
        """Get comprehensive storage summary.

        Combines record stats, sighting stats, observation counts,
        and collection stats into a unified summary.
        """
        stats = self.get_stats()
        collection_stats = self.get_collection_stats(days=30)
        observation_count = self.count_observations()
        feed_config_count = len(self.list_feed_configs())

        return {
            "records": {
                "total": stats["total_records"],
                "by_layer": stats["records_by_layer"],
            },
            "sightings": {
                "total": stats["total_sightings"],
            },
            "observations": {
                "total": observation_count,
            },
            "feed_configs": {
                "total": feed_config_count,
            },
            "collection": collection_stats,
            "schema_version": stats.get("schema_version"),
        }

    # -- Feed Health -------------------------------------------------------

    def get_unique_feed_names(self) -> list[str]:
        """Get unique feed names from feed_runs table."""
        rows = self.query("SELECT DISTINCT feed_name FROM feed_runs ORDER BY feed_name")
        return [row["feed_name"] for row in rows]

    def get_feed_health(
        self,
        feed_name: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Calculate health metrics for a feed over N days.

        Returns:
            Dictionary with: feed_name, status, total_runs, success_rate,
            last_success_at, consecutive_failures, avg_records_per_run
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        cutoff_str = serialize_datetime(cutoff)

        # Get runs for this feed in the time window
        runs = self.query(
            f"SELECT * FROM feed_runs WHERE feed_name = {self.ph(1)} "
            f"AND started_at >= {self.ph(1)} ORDER BY started_at DESC",
            (feed_name, cutoff_str),
        )

        if not runs:
            return {
                "feed_name": feed_name,
                "status": "unknown",
                "total_runs": 0,
                "success_rate": 0.0,
                "last_success_at": None,
                "consecutive_failures": 0,
                "avg_records_per_run": 0.0,
            }

        total = len(runs)
        successful = sum(1 for r in runs if r.get("status") == "completed")
        success_rate = successful / total if total > 0 else 0.0

        # Find last success
        last_success = None
        for run in runs:
            if run.get("status") == "completed":
                last_success = run.get("started_at")
                break

        # Count consecutive failures from most recent
        consecutive_failures = 0
        for run in runs:  # Already ordered DESC
            if run.get("status") != "completed":
                consecutive_failures += 1
            else:
                break

        # Average records per run
        total_records = sum(r.get("records_new", 0) or 0 for r in runs)
        avg_records = total_records / total if total > 0 else 0.0

        # Determine RAG status
        if success_rate >= 0.8 and consecutive_failures < 3:
            status = "healthy"  # 🟢 Green
        elif success_rate >= 0.5 or consecutive_failures < 5:
            status = "degraded"  # 🟡 Amber
        else:
            status = "failing"  # 🔴 Red

        return {
            "feed_name": feed_name,
            "status": status,
            "total_runs": total,
            "success_rate": success_rate,
            "last_success_at": last_success,
            "consecutive_failures": consecutive_failures,
            "avg_records_per_run": avg_records,
        }

    def get_all_feed_health(self, days: int = 7) -> list[dict[str, Any]]:
        """Get health metrics for all feeds.

        Returns:
            List of health dictionaries for each feed, sorted by success_rate.
        """
        feed_names = self.get_unique_feed_names()
        health_list = []
        for feed_name in feed_names:
            health = self.get_feed_health(feed_name, days)
            health_list.append(health)

        # Sort by success rate (worst first)
        return sorted(health_list, key=lambda h: h["success_rate"])

    def get_failing_feeds(
        self,
        consecutive_failures_threshold: int = 3,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get feeds that are failing beyond threshold.

        Returns:
            List of health dictionaries for failing feeds.
        """
        all_health = self.get_all_feed_health(days)
        return [
            h
            for h in all_health
            if h["consecutive_failures"] >= consecutive_failures_threshold or h["status"] == "failing"
        ]

    # -- Feed Config Queries -----------------------------------------------

    def get_feed_config(self, feed_id: str) -> dict[str, Any] | None:
        """Get a feed config by ID."""
        row = self.query_one(
            f"SELECT * FROM feed_configs WHERE id = {self.ph(1)}",
            (feed_id,),
        )
        return self._deserialize_feed_config(row) if row else None

    def list_feed_configs(
        self,
        *,
        enabled: bool | None = None,
        adapter_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List feed configs with optional filtering."""
        conditions: list[str] = []
        params: list[Any] = []

        if enabled is not None:
            conditions.append(f"enabled = {self.dialect.placeholder(len(params))}")
            params.append(1 if enabled else 0)

        if adapter_type is not None:
            conditions.append(f"adapter_type = {self.dialect.placeholder(len(params))}")
            params.append(adapter_type)

        where = " AND ".join(conditions) if conditions else "1=1"
        limit_ph = self.dialect.placeholder(len(params))
        params.append(limit)
        offset_ph = self.dialect.placeholder(len(params))
        params.append(offset)
        rows = self.query(
            f"SELECT * FROM feed_configs WHERE {where} ORDER BY name LIMIT {limit_ph} OFFSET {offset_ph}",
            tuple(params),
        )
        return [self._deserialize_feed_config(r) for r in rows]

    def _deserialize_feed_config(self, row: dict[str, Any]) -> dict[str, Any]:
        """Deserialize a feed config row (parse JSON config, bool enabled)."""
        result = dict(row)
        if isinstance(result.get("config"), str):
            try:
                result["config"] = json.loads(result["config"])
            except (json.JSONDecodeError, TypeError):
                result["config"] = {}
        if "enabled" in result:
            result["enabled"] = bool(result["enabled"])
        return result

    # -- Observation Queries -----------------------------------------------

    def get_observation(self, obs_id: str) -> dict[str, Any] | None:
        """Get an observation by ID."""
        row = self.query_one(
            f"SELECT * FROM observations WHERE id = {self.ph(1)}",
            (obs_id,),
        )
        return self._deserialize_observation(row) if row else None

    def list_observations(
        self,
        *,
        observation_type: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List observations with optional filtering."""
        conditions: list[str] = []
        params: list[Any] = []

        if observation_type:
            conditions.append(f"observation_type = {self.dialect.placeholder(len(params))}")
            params.append(observation_type)

        if source:
            conditions.append(f"source = {self.dialect.placeholder(len(params))}")
            params.append(source)

        if since:
            conditions.append(f"created_at >= {self.dialect.placeholder(len(params))}")
            params.append(serialize_datetime(since))

        where = " AND ".join(conditions) if conditions else "1=1"

        rows = self.query(
            f"SELECT * FROM observations WHERE {where} "
            f"ORDER BY created_at DESC LIMIT {int(limit)} OFFSET {int(offset)}",
            tuple(params),
        )
        return [self._deserialize_observation(r) for r in rows]

    def count_observations(
        self,
        *,
        observation_type: str | None = None,
        source: str | None = None,
    ) -> int:
        """Count observations, optionally filtered."""
        conditions: list[str] = []
        params: list[Any] = []

        if observation_type:
            conditions.append(f"observation_type = {self.dialect.placeholder(len(params))}")
            params.append(observation_type)

        if source:
            conditions.append(f"source = {self.dialect.placeholder(len(params))}")
            params.append(source)

        where = " AND ".join(conditions) if conditions else "1=1"
        row = self.query_one(
            f"SELECT COUNT(*) as cnt FROM observations WHERE {where}",
            tuple(params),
        )
        return row["cnt"] if row else 0

    def _deserialize_observation(self, row: dict[str, Any]) -> dict[str, Any]:
        """Deserialize an observation row (parse JSON data/metadata)."""
        result = dict(row)
        for field in ("data", "metadata"):
            if isinstance(result.get(field), str):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    result[field] = {}
        return result
