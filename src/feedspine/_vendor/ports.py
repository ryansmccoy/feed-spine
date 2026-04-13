"""Vendored spine-core port protocols used by feedspine.

Contains the minimal protocol definitions for ``ScheduleStore``,
``EventRuleStore``, and the ``WorkItemCreate`` dataclass so that
feedspine's ``registration`` module works without spine-core.
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
