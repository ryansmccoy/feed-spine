"""Vendored execution types — standalone replacements for spine.runtime/ports.

These stubs replicate the subset of spine-core's execution, dispatch,
and backoff contracts that feedspine references at runtime.  When
spine-core is installed, callers should prefer the canonical types.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


# ── Dispatch & backoff (spine.ports.*) ─────────────────────────────


@dataclass(frozen=True)
class DispatchConfig:
    """Dispatch configuration for a work item."""

    type: str
    target: str | None = None
    timeout: int = 300
    soft_timeout: float | None = None
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    resource_limits: dict[str, float] = field(default_factory=dict)
    required_capabilities: dict[str, Any] = field(default_factory=dict)
    preferred_worker_id: str | None = None
    task_queue: str | None = None

    def to_json(self) -> str:
        """Serialize to JSON string for DB storage."""
        from dataclasses import asdict

        return json.dumps({k: v for k, v in asdict(self).items() if v})

    @classmethod
    def from_json(cls, raw: str | dict[str, Any] | None) -> DispatchConfig | None:
        """Deserialize from JSON string or dict."""
        if raw is None:
            return None
        data = json.loads(raw) if isinstance(raw, str) else raw
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class BackoffPolicy:
    """Configurable backoff strategy for work-item retries."""

    strategy: str = "exponential"
    base_seconds: float = 10.0
    max_seconds: float = 3600.0
    jitter: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """Return the delay in seconds for *attempt* (1-based)."""
        if self.strategy == "fixed":
            return min(self.base_seconds, self.max_seconds)
        if self.strategy == "linear":
            return min(self.base_seconds * attempt, self.max_seconds)
        # exponential
        return min(self.base_seconds * (2 ** (attempt - 1)), self.max_seconds)

    def to_dict(self) -> dict[str, str | float | bool]:
        """Serialize to a dict for JSON storage."""
        from dataclasses import asdict

        return asdict(self)  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, data: dict[str, str | float | bool]) -> BackoffPolicy:
        """Deserialize from a dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})  # type: ignore[arg-type]


@dataclass
class DispatchResult:
    """Outcome of an executor dispatch."""

    success: bool
    status_code: int | None = None
    error: str | None = None
    response_body: str | None = None
    duration_ms: int | None = None
    updated_work_item_params: dict | str | None = None


# ── Execution lifecycle (spine.runtime.lifecycle) ──────────────────


class ExecutionState(StrEnum):
    """Formal execution lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def is_terminal(self) -> bool:
        return self in (self.COMPLETED, self.FAILED, self.CANCELLED, self.TIMED_OUT)

    @property
    def is_success(self) -> bool:
        return self == self.COMPLETED

    @property
    def is_failure(self) -> bool:
        return self in (self.FAILED, self.TIMED_OUT)


class ExecutionErrorCategory(StrEnum):
    """Normalised error categories for structured retry decisions."""

    HANDLER_ERROR = "handler_error"
    TIMEOUT = "timeout"
    OOM = "oom"
    CRASH = "crash"
    INFRASTRUCTURE = "infrastructure"
    DEPENDENCY = "dependency"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExecutionHandle:
    """Opaque reference to a submitted execution."""

    execution_id: str
    runtime_name: str
    external_ref: str
    request_name: str
    submitted_at: datetime

    @classmethod
    def create(
        cls,
        *,
        runtime_name: str,
        external_ref: str,
        request_name: str,
        submitted_at: datetime | None = None,
        execution_id: str | None = None,
    ) -> ExecutionHandle:
        return cls(
            execution_id=execution_id or str(uuid.uuid4()),
            runtime_name=runtime_name,
            external_ref=external_ref,
            request_name=request_name,
            submitted_at=submitted_at or datetime.now(UTC),
        )


@dataclass(frozen=True)
class ExecutionStatus:
    """Point-in-time status report for an execution."""

    handle: ExecutionHandle
    state: ExecutionState
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    error_category: ExecutionErrorCategory | None = None
    exit_code: int | None = None
    is_oom: bool = False
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
