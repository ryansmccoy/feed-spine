"""Tests for feedspine.models.task."""

from __future__ import annotations

from feedspine.models.task import Task, TaskResult, TaskStatus


class TestTaskCreation:
    """Tests for Task creation."""

    def test_create_minimal(self) -> None:
        """Can create with required fields."""
        task = Task(name="test-task", payload={"data": "value"})
        assert task.name == "test-task"
        assert task.payload == {"data": "value"}
        assert task.id is not None  # Auto-generated

    def test_create_with_options(self) -> None:
        """Can specify options."""
        task = Task(
            name="test-task",
            payload={"data": "value"},
            priority=10,
            max_retries=5,
            timeout_seconds=60.0,
        )
        assert task.priority == 10
        assert task.max_retries == 5
        assert task.timeout_seconds == 60.0

    def test_defaults(self) -> None:
        """Default values are correct."""
        task = Task(name="test", payload={})
        assert task.priority == 0
        assert task.max_retries == 3
        assert task.retry_count == 0
        assert task.retry_delay_seconds == 1.0
        assert task.timeout_seconds == 300


class TestTaskResult:
    """Tests for TaskResult."""

    def test_create_success(self) -> None:
        """Can create successful result."""
        result = TaskResult(
            task_id="task-123",
            status=TaskStatus.SUCCESS,
            result={"output": "done"},
        )
        assert result.is_success
        assert not result.is_failure
        assert result.result == {"output": "done"}

    def test_create_failure(self) -> None:
        """Can create failed result."""
        result = TaskResult(
            task_id="task-123",
            status=TaskStatus.FAILED,
            error="Something went wrong",
            error_type="ValueError",
        )
        assert result.is_failure
        assert not result.is_success
        assert result.error == "Something went wrong"

    def test_duration_calculation(self) -> None:
        """Duration can be set."""
        result = TaskResult(
            task_id="task-123",
            status=TaskStatus.SUCCESS,
            duration_ms=150.5,
        )
        assert result.duration_ms == 150.5


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_all_statuses(self) -> None:
        """All expected statuses exist."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.RETRYING.value == "retrying"
