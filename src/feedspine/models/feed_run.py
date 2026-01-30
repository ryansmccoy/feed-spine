"""FeedRun model - tracks feed collection runs.

FeedRuns provide operational visibility into feed collection:
- Track when collections started/completed
- Monitor success/failure rates
- Record item counts (new, duplicates, errors)
- Enable replay and debugging

This mirrors capture-spine's `feed_runs` table for migration compatibility.

Example:
    >>> from feedspine.models.feed_run import FeedRun, FeedRunStatus
    >>> run = FeedRun(
    ...     feed_name="sec-daily",
    ...     status=FeedRunStatus.RUNNING,
    ... )
    >>> run.is_complete
    False
    >>> run.duration_seconds is None
    True
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import Field, field_validator

from feedspine.models.base import FeedSpineModel


class FeedRunStatus(str, Enum):
    """Feed run execution states.

    Example:
        >>> from feedspine.models.feed_run import FeedRunStatus
        >>> FeedRunStatus.SUCCESS.value
        'success'
        >>> FeedRunStatus.RUNNING in list(FeedRunStatus)
        True
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FeedRun(FeedSpineModel):
    """Records a single feed collection run.

    Used for:
    - Operational monitoring (which feeds ran successfully?)
    - Debugging (what went wrong in a failed run?)
    - Metrics (how many records per run?)
    - Replay (re-run failed collections)

    Example:
        >>> from feedspine.models.feed_run import FeedRun, FeedRunStatus
        >>> from datetime import datetime, UTC
        >>> run = FeedRun(
        ...     feed_name="hacker-news",
        ...     status=FeedRunStatus.SUCCESS,
        ...     items_processed=100,
        ...     items_new=80,
        ...     items_duplicate=20,
        ... )
        >>> run.is_complete
        True
        >>> run.success_rate
        1.0
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique run identifier",
    )
    feed_name: str = Field(..., description="Name of the feed being collected")
    status: FeedRunStatus = Field(
        default=FeedRunStatus.PENDING,
        description="Current run status",
    )

    # Timestamps
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the run started",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When the run finished (success or failure)",
    )

    # Item counts
    items_processed: int = Field(
        default=0,
        ge=0,
        description="Total items processed in this run",
    )
    items_new: int = Field(
        default=0,
        ge=0,
        description="New items captured (not seen before)",
    )
    items_duplicate: int = Field(
        default=0,
        ge=0,
        description="Duplicate items skipped",
    )
    items_failed: int = Field(
        default=0,
        ge=0,
        description="Items that failed processing",
    )

    # Error tracking
    errors: list[str] = Field(
        default_factory=list,
        description="Error messages encountered during run",
    )
    error_type: str | None = Field(
        default=None,
        description="Exception class name if run failed",
    )

    # Checkpointing
    checkpoint_position: dict[str, Any] = Field(
        default_factory=dict,
        description="Position marker for resuming interrupted runs",
    )

    # Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional run metadata (URLs fetched, etc.)",
    )

    @field_validator("feed_name")
    @classmethod
    def validate_feed_name(cls, v: str) -> str:
        """Ensure feed name is non-empty and trimmed."""
        v = v.strip()
        if not v:
            raise ValueError("feed_name cannot be empty")
        return v

    @property
    def is_complete(self) -> bool:
        """Check if run has finished (success, failed, or cancelled).

        Example:
            >>> from feedspine.models.feed_run import FeedRun, FeedRunStatus
            >>> FeedRun(feed_name="test", status=FeedRunStatus.RUNNING).is_complete
            False
            >>> FeedRun(feed_name="test", status=FeedRunStatus.SUCCESS).is_complete
            True
        """
        return self.status in (
            FeedRunStatus.SUCCESS,
            FeedRunStatus.FAILED,
            FeedRunStatus.CANCELLED,
        )

    @property
    def is_success(self) -> bool:
        """Check if run completed successfully."""
        return self.status == FeedRunStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        """Check if run failed."""
        return self.status == FeedRunStatus.FAILED

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds.

        Returns:
            Duration in seconds, or None if not completed.

        Example:
            >>> from feedspine.models.feed_run import FeedRun, FeedRunStatus
            >>> from datetime import datetime, timedelta, UTC
            >>> start = datetime.now(UTC)
            >>> run = FeedRun(
            ...     feed_name="test",
            ...     status=FeedRunStatus.SUCCESS,
            ...     started_at=start,
            ...     completed_at=start + timedelta(seconds=5),
            ... )
            >>> run.duration_seconds
            5.0
        """
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate (items without errors).

        Returns:
            Float from 0.0 to 1.0.

        Example:
            >>> from feedspine.models.feed_run import FeedRun
            >>> run = FeedRun(feed_name="test", items_processed=100, items_failed=10)
            >>> run.success_rate
            0.9
        """
        if self.items_processed == 0:
            return 1.0
        return (self.items_processed - self.items_failed) / self.items_processed

    @property
    def dedup_rate(self) -> float:
        """Calculate deduplication rate.

        Returns:
            Float from 0.0 to 1.0 (1.0 = all duplicates).

        Example:
            >>> from feedspine.models.feed_run import FeedRun
            >>> run = FeedRun(feed_name="test", items_processed=100, items_duplicate=75)
            >>> run.dedup_rate
            0.75
        """
        if self.items_processed == 0:
            return 0.0
        return self.items_duplicate / self.items_processed

    def start(self) -> FeedRun:
        """Create a new FeedRun marked as running.

        Returns:
            New FeedRun with RUNNING status.

        Example:
            >>> from feedspine.models.feed_run import FeedRun, FeedRunStatus
            >>> run = FeedRun(feed_name="test")
            >>> running = run.start()
            >>> running.status
            <FeedRunStatus.RUNNING: 'running'>
        """
        return self.model_copy(
            update={
                "status": FeedRunStatus.RUNNING,
                "started_at": datetime.now(UTC),
            }
        )

    def complete(
        self,
        items_processed: int = 0,
        items_new: int = 0,
        items_duplicate: int = 0,
        items_failed: int = 0,
    ) -> FeedRun:
        """Mark the run as successfully completed.

        Args:
            items_processed: Total items processed.
            items_new: New items captured.
            items_duplicate: Duplicate items skipped.
            items_failed: Failed items.

        Returns:
            New FeedRun with SUCCESS status.

        Example:
            >>> from feedspine.models.feed_run import FeedRun, FeedRunStatus
            >>> run = FeedRun(feed_name="test").start()
            >>> completed = run.complete(items_processed=50, items_new=30, items_duplicate=20)
            >>> completed.status
            <FeedRunStatus.SUCCESS: 'success'>
            >>> completed.items_new
            30
        """
        return self.model_copy(
            update={
                "status": FeedRunStatus.SUCCESS,
                "completed_at": datetime.now(UTC),
                "items_processed": items_processed,
                "items_new": items_new,
                "items_duplicate": items_duplicate,
                "items_failed": items_failed,
            }
        )

    def fail(self, error: str, error_type: str | None = None) -> FeedRun:
        """Mark the run as failed.

        Args:
            error: Error message describing the failure.
            error_type: Exception class name.

        Returns:
            New FeedRun with FAILED status.

        Example:
            >>> from feedspine.models.feed_run import FeedRun, FeedRunStatus
            >>> run = FeedRun(feed_name="test").start()
            >>> failed = run.fail("Network timeout", "TimeoutError")
            >>> failed.status
            <FeedRunStatus.FAILED: 'failed'>
            >>> failed.error_type
            'TimeoutError'
        """
        errors = self.errors.copy()
        errors.append(error)
        return self.model_copy(
            update={
                "status": FeedRunStatus.FAILED,
                "completed_at": datetime.now(UTC),
                "errors": errors,
                "error_type": error_type,
            }
        )

    def cancel(self, reason: str | None = None) -> FeedRun:
        """Mark the run as cancelled.

        Args:
            reason: Optional reason for cancellation.

        Returns:
            New FeedRun with CANCELLED status.
        """
        errors = self.errors.copy()
        if reason:
            errors.append(f"Cancelled: {reason}")
        return self.model_copy(
            update={
                "status": FeedRunStatus.CANCELLED,
                "completed_at": datetime.now(UTC),
                "errors": errors,
            }
        )

    def update_progress(
        self,
        items_processed: int | None = None,
        items_new: int | None = None,
        items_duplicate: int | None = None,
        items_failed: int | None = None,
        checkpoint_position: dict[str, Any] | None = None,
    ) -> FeedRun:
        """Update run progress counters.

        Args:
            items_processed: New total processed count.
            items_new: New total new count.
            items_duplicate: New total duplicate count.
            items_failed: New total failed count.
            checkpoint_position: New checkpoint position.

        Returns:
            Updated FeedRun.

        Example:
            >>> from feedspine.models.feed_run import FeedRun
            >>> run = FeedRun(feed_name="test").start()
            >>> updated = run.update_progress(items_processed=10, items_new=8)
            >>> updated.items_processed
            10
        """
        updates: dict[str, Any] = {}
        if items_processed is not None:
            updates["items_processed"] = items_processed
        if items_new is not None:
            updates["items_new"] = items_new
        if items_duplicate is not None:
            updates["items_duplicate"] = items_duplicate
        if items_failed is not None:
            updates["items_failed"] = items_failed
        if checkpoint_position is not None:
            updates["checkpoint_position"] = checkpoint_position
        return self.model_copy(update=updates)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.

        Example:
            >>> from feedspine.models.feed_run import FeedRun
            >>> run = FeedRun(feed_name="test")
            >>> d = run.to_dict()
            >>> d["feed_name"]
            'test'
        """
        return {
            "id": self.id,
            "feed_name": self.feed_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "items_processed": self.items_processed,
            "items_new": self.items_new,
            "items_duplicate": self.items_duplicate,
            "items_failed": self.items_failed,
            "errors": self.errors,
            "error_type": self.error_type,
            "checkpoint_position": self.checkpoint_position,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedRun:
        """Create FeedRun from dictionary.

        Args:
            data: Dictionary with FeedRun data.

        Returns:
            New FeedRun instance.

        Example:
            >>> from feedspine.models.feed_run import FeedRun, FeedRunStatus
            >>> data = {"feed_name": "test", "status": "success", "started_at": "2024-01-01T00:00:00+00:00"}
            >>> run = FeedRun.from_dict(data)
            >>> run.feed_name
            'test'
        """
        return cls(
            id=data.get("id", str(uuid4())),
            feed_name=data["feed_name"],
            status=FeedRunStatus(data.get("status", "pending")),
            started_at=datetime.fromisoformat(data["started_at"])
            if isinstance(data.get("started_at"), str)
            else data.get("started_at", datetime.now(UTC)),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None,
            items_processed=data.get("items_processed", 0),
            items_new=data.get("items_new", 0),
            items_duplicate=data.get("items_duplicate", 0),
            items_failed=data.get("items_failed", 0),
            errors=data.get("errors", []),
            error_type=data.get("error_type"),
            checkpoint_position=data.get("checkpoint_position", {}),
            metadata=data.get("metadata", {}),
        )
