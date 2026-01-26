"""Task models for executor communication.

Tasks represent units of work submitted to executors. The task system
supports retries, timeouts, priorities, and result tracking.

Example:
    >>> from feedspine.models.task import Task, TaskStatus, TaskResult
    >>> task = Task(name="fetch_url", payload={"url": "https://example.com"})
    >>> task.name
    'fetch_url'
    >>> task.max_retries
    3
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import Field

from feedspine.models.base import FeedSpineModel

T = TypeVar("T")


class TaskStatus(str, Enum):
    """Task execution states.

    Example:
        >>> from feedspine.models.task import TaskStatus
        >>> TaskStatus.PENDING.value
        'pending'
        >>> TaskStatus.SUCCESS in list(TaskStatus)
        True
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class Task(FeedSpineModel, Generic[T]):
    """A unit of work to be executed.

    Example:
        >>> from feedspine.models.task import Task
        >>> t = Task(name="process", payload={"id": 1}, priority=10)
        >>> t.priority
        10
        >>> t.retry_count
        0
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Task name/type")
    payload: T = Field(..., description="Task-specific data")
    priority: int = Field(default=0, description="Higher = more urgent")
    max_retries: int = Field(default=3, ge=0)
    retry_count: int = Field(default=0, ge=0)
    retry_delay_seconds: float = Field(default=1.0, ge=0)
    timeout_seconds: float | None = Field(default=300, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResult(FeedSpineModel, Generic[T]):
    """Result of task execution.

    Example:
        >>> from feedspine.models.task import TaskResult, TaskStatus
        >>> result = TaskResult(
        ...     task_id="task-1",
        ...     status=TaskStatus.SUCCESS,
        ...     result={"processed": True},
        ... )
        >>> result.is_success
        True
        >>> result.is_failure
        False
    """

    task_id: str = Field(..., description="ID of the executed task")
    status: TaskStatus = Field(..., description="Final status")
    result: T | None = Field(default=None, description="Success result")
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: str | None = Field(default=None, description="Exception class name")
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    duration_ms: float | None = Field(default=None, ge=0)
    retries_used: int = Field(default=0, ge=0)

    @property
    def is_success(self) -> bool:
        """Check if task succeeded."""
        return self.status == TaskStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        """Check if task failed."""
        return self.status == TaskStatus.FAILED
