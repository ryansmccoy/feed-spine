"""Vendored event types — standalone replacements for spine.events.

When spine-core is installed these are unused; feedspine falls back to
these lightweight stubs so the package can run independently.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class Event:
    """Immutable event payload for cross-component communication."""

    event_type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str | None = None

    def matches(self, pattern: str) -> bool:
        """Check if event_type matches *pattern* (supports trailing ``*``)."""
        if pattern.endswith("*"):
            return self.event_type.startswith(pattern[:-1])
        return self.event_type == pattern


@runtime_checkable
class EventBus(Protocol):
    """Protocol for publish/subscribe event bus."""

    async def publish(self, event: Event) -> None: ...
    async def subscribe(self, event_type: str, handler: Any) -> str: ...
    async def unsubscribe(self, subscription_id: str) -> None: ...
    async def close(self) -> None: ...


@runtime_checkable
class EventStore(Protocol):
    """Protocol: append-only event log."""

    def append(self, event: dict[str, Any]) -> str: ...
    def get_since(self, cursor: int) -> list[dict[str, Any]]: ...
