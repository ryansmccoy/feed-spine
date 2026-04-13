"""Vendored spine-core port protocols used by feedspine.

Contains the minimal protocol definitions for ``ScheduleStore``,
``EventRuleStore``, ``WatermarkStore``, and the ``WorkItemCreate``
dataclass so that feedspine works without spine-core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Store protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class ScheduleStore(Protocol):
    """Minimal protocol for a schedule persistence backend."""

    def create(self, schedule: dict[str, Any]) -> str: ...
    def get_due(self, now: str) -> list[dict[str, Any]]: ...
    def advance_next_run(self, schedule_id: str, next_run_at: str) -> None: ...
    def get_by_id(self, schedule_id: str) -> dict[str, Any] | None: ...


@runtime_checkable
class EventRuleStore(Protocol):
    """Minimal protocol for an event-rule persistence backend."""

    def create(self, rule: dict[str, Any]) -> str: ...
    def match(self, event: dict[str, Any]) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# WorkItemCreate dataclass
# ---------------------------------------------------------------------------


@dataclass
class WorkItemCreate:
    """Minimal representation of a work-item creation request."""

    workflow: str = ""
    step: str = ""
    params: str = ""
    priority: int = 100
    execution_mode: str = "FIRE_AND_FORGET"
    batch_id: str | None = None
    parent_id: str | None = None
    source: str | None = None
    tags: str = ""
    max_attempts: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# WatermarkStore — in-memory fallback
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Watermark:
    """High-water mark for a single (domain, source, partition_key) cursor."""

    domain: str
    source: str
    partition_key: str
    high_water: str
    low_water: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: Any = None  # datetime | None


class WatermarkStore:
    """In-memory watermark tracker (lightweight standalone fallback).

    When spine-core is installed callers should prefer
    ``spine.domain.watermarks.WatermarkStore`` which persists to SQLite.
    """

    def __init__(self) -> None:
        self._marks: dict[tuple[str, str, str], Watermark] = {}

    def upsert(
        self,
        domain: str,
        source: str,
        partition_key: str,
        high_water: str,
        *,
        low_water: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Watermark:
        key = (domain, source, partition_key)
        wm = Watermark(
            domain=domain,
            source=source,
            partition_key=partition_key,
            high_water=high_water,
            low_water=low_water,
            metadata=metadata or {},
        )
        self._marks[key] = wm
        return wm

    def get(self, domain: str, source: str, partition_key: str) -> Watermark | None:
        return self._marks.get((domain, source, partition_key))

    def advance(
        self,
        domain: str,
        source: str,
        partition_key: str,
        high_water: str,
        *,
        low_water: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Watermark:
        """Alias for upsert — advances the high-water mark."""
        return self.upsert(
            domain=domain,
            source=source,
            partition_key=partition_key,
            high_water=high_water,
            low_water=low_water,
            metadata=metadata,
        )

    def list_all(self, domain: str | None = None) -> list[Watermark]:
        if domain is None:
            return list(self._marks.values())
        return [w for w in self._marks.values() if w.domain == domain]
