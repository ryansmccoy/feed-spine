"""Operations layer — pure business logic for FeedSpine.

The ops package provides typed request/response functions that wrap
storage and search backends with consistent patterns:

- All functions accept ``OperationContext`` as first argument
- All functions return ``OperationResult[T]`` (never raise for expected errors)
- All functions are transport-agnostic (no CLI, no API, no Rich imports)
- All functions support ``dry_run`` mode for safe previews

Usage::

    from feedspine.ops import OperationContext, OperationResult
    from feedspine.ops.query import fetch_records, execute_search

    ctx = OperationContext(storage=my_storage)
    result = await fetch_records(ctx, layer="bronze", limit=20, offset=0)
    assert result.success
    print(result.data)

This mirrors spine-core's ops layer pattern but is adapted for
FeedSpine's async storage/search backend architecture.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class OperationContext:
    """Context passed to every operation function.

    Attributes:
        storage: Async storage backend (MemoryStorage, SQLiteStorage, etc.).
        search: Optional async search backend (MemorySearch, ElasticsearchSearch).
        request_id: Unique ID for this operation invocation (auto-generated).
        caller: Origin of the request — ``"api"``, ``"cli"``, ``"sdk"``,
            or ``"scheduler"``.
        dry_run: When ``True``, operations return a preview without side effects.
        metadata: Arbitrary key/value pairs for logging and tracing.
    """

    storage: Any  # StorageBackend (avoid import cycle)
    search: Any | None = None  # SearchBackend
    work_item_store: Any | None = None  # WorkItemStore (spine-core)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    caller: str = "sdk"
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationResult[T]:
    """Envelope returned by every operation function.

    Use factory methods :meth:`ok` and :meth:`fail` instead of the
    constructor directly.

    Attributes:
        success: ``True`` when the operation completed without error.
        data: The typed payload (``None`` on failure).
        error: Error message string (``None`` on success).
        warnings: Non-fatal messages collected during the operation.
        metadata: Additional key/value pairs for debugging or tracing.
    """

    success: bool
    data: T | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: T, **kwargs: Any) -> OperationResult[T]:
        """Create a successful result."""
        return cls(success=True, data=data, **kwargs)

    @classmethod
    def fail(cls, error: str, **kwargs: Any) -> OperationResult[Any]:
        """Create a failed result."""
        return cls(success=False, error=error, **kwargs)


__all__ = [
    "OperationContext",
    "OperationResult",
]
