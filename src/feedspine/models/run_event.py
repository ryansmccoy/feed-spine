"""Run event model for structured event logging.

RunEvents provide a complete audit trail of pipeline execution,
enabling debugging, monitoring, and analytics.

Example:
    >>> from feedspine.models.run_event import RunEvent, RunEventType
    >>> from datetime import datetime, UTC
    >>> event = RunEvent(
    ...     run_id="run-123",
    ...     event_type=RunEventType.RUN_STARTED,
    ...     feed_name="sec-filings",
    ...     message="Starting collection run",
    ... )
    >>> event.event_type == RunEventType.RUN_STARTED
    True
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field

from feedspine.models.base import FeedSpineModel
from feedspine.types import FeedName


class RunEventType(Enum):
    """Types of events that can occur during a pipeline run.

    Event Lifecycle:
        RUN_STARTED → (FETCH_STARTED → FETCH_COMPLETED)* → RUN_COMPLETED

    Error Events:
        FETCH_ERROR, RUN_ERROR can occur at any point

    Record Events:
        RECORD_CREATED, RECORD_UPDATED, RECORD_DUPLICATE during fetch
    """

    # Run lifecycle events
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_ERROR = "run_error"

    # Fetch lifecycle events
    FETCH_STARTED = "fetch_started"
    FETCH_COMPLETED = "fetch_completed"
    FETCH_ERROR = "fetch_error"
    FETCH_NOT_MODIFIED = "fetch_not_modified"  # HTTP 304

    # Record events
    RECORD_CREATED = "record_created"
    RECORD_UPDATED = "record_updated"
    RECORD_DUPLICATE = "record_duplicate"

    # Checkpoint events
    CHECKPOINT_SAVED = "checkpoint_saved"
    CHECKPOINT_RESUMED = "checkpoint_resumed"


class RunEvent(FeedSpineModel):
    """A single event in a pipeline run.

    Attributes:
        run_id: Unique identifier for the pipeline run.
        event_type: The type of event.
        feed_name: Name of the feed this event relates to.
        message: Human-readable event description.
        timestamp: When the event occurred.
        event_id: Unique identifier for this event.
        data: Optional structured data specific to event type.

    Example:
        >>> from feedspine.models.run_event import RunEvent, RunEventType
        >>> event = RunEvent(
        ...     run_id="run-001",
        ...     event_type=RunEventType.RECORD_CREATED,
        ...     feed_name="sec-filings",
        ...     message="Created record acc-001",
        ...     data={"natural_key": "acc-001", "record_id": "uuid-123"},
        ... )
        >>> event.is_error
        False
        >>> event.is_record_event
        True
    """

    run_id: str = Field(..., description="Unique identifier for the pipeline run")
    event_type: RunEventType = Field(..., description="The type of event")
    feed_name: FeedName = Field(..., description="Name of the feed")
    message: str = Field(..., description="Human-readable event description")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the event occurred",
    )
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this event",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data specific to event type",
    )

    @property
    def is_error(self) -> bool:
        """Check if this is an error event."""
        return self.event_type in {
            RunEventType.RUN_ERROR,
            RunEventType.FETCH_ERROR,
        }

    @property
    def is_record_event(self) -> bool:
        """Check if this event relates to a record."""
        return self.event_type in {
            RunEventType.RECORD_CREATED,
            RunEventType.RECORD_UPDATED,
            RunEventType.RECORD_DUPLICATE,
        }

    @property
    def is_lifecycle_event(self) -> bool:
        """Check if this is a run or fetch lifecycle event."""
        return self.event_type in {
            RunEventType.RUN_STARTED,
            RunEventType.RUN_COMPLETED,
            RunEventType.FETCH_STARTED,
            RunEventType.FETCH_COMPLETED,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage/logging."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunEvent:
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    # Factory methods for common events
    @classmethod
    def run_started(
        cls,
        run_id: str,
        feed_name: str,
        *,
        feeds: list[str] | None = None,
    ) -> RunEvent:
        """Create a RUN_STARTED event."""
        data = {}
        if feeds:
            data["feeds"] = feeds
        return cls(
            run_id=run_id,
            event_type=RunEventType.RUN_STARTED,
            feed_name=feed_name,
            message=f"Started run for feed '{feed_name}'",
            data=data,
        )

    @classmethod
    def run_completed(
        cls,
        run_id: str,
        feed_name: str,
        *,
        processed: int = 0,
        new: int = 0,
        updated: int = 0,
        duplicates: int = 0,
        errors: int = 0,
        duration_ms: float = 0.0,
    ) -> RunEvent:
        """Create a RUN_COMPLETED event with stats."""
        return cls(
            run_id=run_id,
            event_type=RunEventType.RUN_COMPLETED,
            feed_name=feed_name,
            message=f"Completed run: {processed} processed, {new} new, {updated} updated, {errors} errors",
            data={
                "processed": processed,
                "new": new,
                "updated": updated,
                "duplicates": duplicates,
                "errors": errors,
                "duration_ms": duration_ms,
            },
        )

    @classmethod
    def run_error(
        cls,
        run_id: str,
        feed_name: str,
        error: str,
        *,
        error_type: str | None = None,
    ) -> RunEvent:
        """Create a RUN_ERROR event."""
        data = {"error": error}
        if error_type:
            data["error_type"] = error_type
        return cls(
            run_id=run_id,
            event_type=RunEventType.RUN_ERROR,
            feed_name=feed_name,
            message=f"Run failed: {error}",
            data=data,
        )

    @classmethod
    def record_created(
        cls,
        run_id: str,
        feed_name: str,
        natural_key: str,
        record_id: str,
    ) -> RunEvent:
        """Create a RECORD_CREATED event."""
        return cls(
            run_id=run_id,
            event_type=RunEventType.RECORD_CREATED,
            feed_name=feed_name,
            message=f"Created record: {natural_key}",
            data={"natural_key": natural_key, "record_id": record_id},
        )

    @classmethod
    def record_updated(
        cls,
        run_id: str,
        feed_name: str,
        natural_key: str,
        record_id: str,
        *,
        previous_hash: str | None = None,
        new_hash: str | None = None,
        version: int | None = None,
    ) -> RunEvent:
        """Create a RECORD_UPDATED event."""
        data = {"natural_key": natural_key, "record_id": record_id}
        if previous_hash:
            data["previous_hash"] = previous_hash
        if new_hash:
            data["new_hash"] = new_hash
        if version is not None:
            data["version"] = version
        return cls(
            run_id=run_id,
            event_type=RunEventType.RECORD_UPDATED,
            feed_name=feed_name,
            message=f"Updated record: {natural_key} (v{version})",
            data=data,
        )

    @classmethod
    def record_duplicate(
        cls,
        run_id: str,
        feed_name: str,
        natural_key: str,
        record_id: str,
    ) -> RunEvent:
        """Create a RECORD_DUPLICATE event."""
        return cls(
            run_id=run_id,
            event_type=RunEventType.RECORD_DUPLICATE,
            feed_name=feed_name,
            message=f"Duplicate: {natural_key}",
            data={"natural_key": natural_key, "record_id": record_id},
        )

    @classmethod
    def fetch_not_modified(
        cls,
        run_id: str,
        feed_name: str,
        *,
        url: str | None = None,
    ) -> RunEvent:
        """Create a FETCH_NOT_MODIFIED event (HTTP 304)."""
        data = {}
        if url:
            data["url"] = url
        return cls(
            run_id=run_id,
            event_type=RunEventType.FETCH_NOT_MODIFIED,
            feed_name=feed_name,
            message=f"Feed not modified (304): {feed_name}",
            data=data,
        )
