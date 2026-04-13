"""Feed operation mixins for RepositoryStorageBackend.

Provides feed run, feed config, sighting, observation, and stats operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from feedspine.models.sighting import Sighting
from feedspine.storage.shared.validators import validate_sighting


class SightingOperationsMixin:
    """Mixin providing sighting operations."""

    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting. Returns True if this was the first sighting."""
        validate_sighting(sighting)
        with self._repo() as repo:
            repo.store_sighting(sighting)
        return sighting.is_new

    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get all sightings for a natural key."""
        with self._repo() as repo:
            return repo.get_sightings(natural_key)


class FeedRunOperationsMixin:
    """Mixin providing feed run operations."""

    async def start_feed_run(
        self,
        run_id: str,
        feed_name: str,
        started_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Start a feed run."""
        with self._repo() as repo:
            repo.start_feed_run(run_id, feed_name, started_at, metadata)

    async def complete_feed_run(
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
        """Complete a feed run."""
        with self._repo() as repo:
            repo.complete_feed_run(
                run_id,
                status=status,
                records_fetched=records_fetched,
                records_new=records_new,
                records_updated=records_updated,
                records_unchanged=records_unchanged,
                error_message=error_message,
            )

    async def get_feed_runs(
        self,
        feed_name: str | None = None,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recent feed runs."""
        with self._repo() as repo:
            return repo.get_feed_runs(feed_name, limit=limit)


class FeedConfigOperationsMixin:
    """Mixin providing feed configuration operations."""

    async def store_feed_config(self, config: dict[str, Any]) -> None:
        """Store/upsert a feed configuration."""
        with self._repo() as repo:
            repo.store_feed_config(config)

    async def get_feed_config(self, feed_id: str) -> dict[str, Any] | None:
        """Get a feed configuration by ID."""
        with self._repo() as repo:
            return repo.get_feed_config(feed_id)

    async def list_feed_configs(
        self,
        *,
        enabled: bool | None = None,
        adapter_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List feed configurations with optional filtering."""
        with self._repo() as repo:
            return repo.list_feed_configs(
                enabled=enabled,
                adapter_type=adapter_type,
                limit=limit,
                offset=offset,
            )

    async def update_feed_config(
        self,
        feed_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """Update a feed configuration. Returns True if found."""
        with self._repo() as repo:
            return repo.update_feed_config(feed_id, updates)

    async def delete_feed_config(self, feed_id: str) -> bool:
        """Delete a feed configuration."""
        with self._repo() as repo:
            return repo.delete_feed_config(feed_id)


class ObservationOperationsMixin:
    """Mixin providing observation operations."""

    async def store_observation(self, obs: dict[str, Any]) -> None:
        """Store an observation (upsert on fingerprint)."""
        with self._repo() as repo:
            repo.store_observation(obs)

    async def get_observation(self, obs_id: str) -> dict[str, Any] | None:
        """Get an observation by ID."""
        with self._repo() as repo:
            return repo.get_observation(obs_id)

    async def list_observations(
        self,
        *,
        observation_type: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List observations with optional filtering."""
        with self._repo() as repo:
            return repo.list_observations(
                observation_type=observation_type,
                source=source,
                since=since,
                limit=limit,
                offset=offset,
            )

    async def count_observations(
        self,
        *,
        observation_type: str | None = None,
        source: str | None = None,
    ) -> int:
        """Count observations."""
        with self._repo() as repo:
            return repo.count_observations(
                observation_type=observation_type,
                source=source,
            )


class StatsOperationsMixin:
    """Mixin providing statistics operations."""

    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        with self._repo() as repo:
            stats = repo.get_stats()
            stats["backend"] = self._backend
            stats["connection_string"] = self.connection_string
            return stats


__all__ = [
    "FeedConfigOperationsMixin",
    "FeedRunOperationsMixin",
    "ObservationOperationsMixin",
    "SightingOperationsMixin",
    "StatsOperationsMixin",
]
