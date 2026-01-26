"""Tests for SyncExecutor implementation.

Tests cover:
- Basic task execution
- Sync and async callable support
- Retry logic with exponential backoff
- Error handling
- Multiple task execution
- Lifecycle (initialize/close)
- Protocol compliance
"""

import asyncio

from feedspine.executor.sync import SyncExecutor
from feedspine.models.task import Task, TaskStatus

# =============================================================================
# Basic Execution Tests
# =============================================================================


class TestSyncExecutorBasicExecution:
    """Tests for basic task execution."""

    async def test_execute_sync_function(self):
        """Can execute a synchronous function."""
        executor = SyncExecutor()

        task = Task(name="double", payload=5)
        result = await executor.submit(task, lambda x: x * 2)

        assert result.result == 10
        assert result.status == TaskStatus.SUCCESS

    async def test_execute_async_function(self):
        """Can execute an async function."""
        executor = SyncExecutor()

        async def async_double(x):
            await asyncio.sleep(0.001)
            return x * 2

        task = Task(name="async_double", payload=7)
        result = await executor.submit(task, async_double)

        assert result.result == 14
        assert result.status == TaskStatus.SUCCESS

    async def test_execute_returns_task_id(self):
        """Result contains original task ID."""
        executor = SyncExecutor()

        task = Task(name="test", payload="x")
        result = await executor.submit(task, lambda x: x)

        assert result.task_id == task.id

    async def test_execute_records_timing(self):
        """Result contains timing information."""
        executor = SyncExecutor()

        task = Task(name="test", payload=1)
        result = await executor.submit(task, lambda x: x)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_ms >= 0

    async def test_execute_with_complex_payload(self):
        """Can handle complex payloads."""
        executor = SyncExecutor()

        payload = {"name": "test", "values": [1, 2, 3]}
        task = Task(name="process", payload=payload)
        result = await executor.submit(task, lambda x: len(x["values"]))

        assert result.result == 3


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestSyncExecutorErrorHandling:
    """Tests for error handling."""

    async def test_failed_task_returns_error(self):
        """Failed tasks return FAILED status with error info."""
        executor = SyncExecutor()

        def failing_func(x):
            raise ValueError("Test error")

        task = Task(name="fail", payload=1, max_retries=0)
        result = await executor.submit(task, failing_func)

        assert result.status == TaskStatus.FAILED
        assert result.error == "Test error"
        assert result.error_type == "ValueError"
        assert result.result is None

    async def test_failed_async_task(self):
        """Async failures are captured."""
        executor = SyncExecutor()

        async def async_fail(x):
            raise RuntimeError("Async error")

        task = Task(name="async_fail", payload=1, max_retries=0)
        result = await executor.submit(task, async_fail)

        assert result.status == TaskStatus.FAILED
        assert "Async error" in result.error
        assert result.error_type == "RuntimeError"


# =============================================================================
# Retry Tests
# =============================================================================


class TestSyncExecutorRetry:
    """Tests for retry logic."""

    async def test_retry_on_failure(self):
        """Tasks retry on failure up to max_retries."""
        executor = SyncExecutor()

        call_count = 0

        def sometimes_fail(x):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        task = Task(name="retry", payload=1, max_retries=3, retry_delay_seconds=0.001)
        result = await executor.submit(task, sometimes_fail)

        assert result.status == TaskStatus.SUCCESS
        assert result.result == "success"
        assert result.retries_used == 2  # Failed twice, succeeded on third

    async def test_exhaust_retries(self):
        """Task fails after exhausting all retries."""
        executor = SyncExecutor()

        call_count = 0

        def always_fail(x):
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        task = Task(name="exhaust", payload=1, max_retries=2, retry_delay_seconds=0.001)
        result = await executor.submit(task, always_fail)

        assert result.status == TaskStatus.FAILED
        assert result.retries_used == 2
        assert call_count == 3  # Initial + 2 retries

    async def test_no_retry_when_max_zero(self):
        """No retries when max_retries=0."""
        executor = SyncExecutor()

        call_count = 0

        def fail_once(x):
            nonlocal call_count
            call_count += 1
            raise ValueError("Fail")

        task = Task(name="no_retry", payload=1, max_retries=0)
        result = await executor.submit(task, fail_once)

        assert result.status == TaskStatus.FAILED
        assert call_count == 1


# =============================================================================
# Multiple Task Execution Tests
# =============================================================================


class TestSyncExecutorSubmitMany:
    """Tests for submit_many functionality."""

    async def test_submit_many_all_succeed(self):
        """Can execute multiple tasks."""
        executor = SyncExecutor()

        tasks = [
            Task(name="t1", payload=1),
            Task(name="t2", payload=2),
            Task(name="t3", payload=3),
        ]

        results = await executor.submit_many(tasks, lambda x: x * 10)

        assert len(results) == 3
        assert all(r.status == TaskStatus.SUCCESS for r in results)
        assert [r.result for r in results] == [10, 20, 30]

    async def test_submit_many_partial_failure(self):
        """Partial failures don't affect other tasks."""
        executor = SyncExecutor()

        def process(x):
            if x == 2:
                raise ValueError("Skip 2")
            return x * 10

        tasks = [
            Task(name="t1", payload=1, max_retries=0),
            Task(name="t2", payload=2, max_retries=0),
            Task(name="t3", payload=3, max_retries=0),
        ]

        results = await executor.submit_many(tasks, process)

        assert results[0].status == TaskStatus.SUCCESS
        assert results[1].status == TaskStatus.FAILED
        assert results[2].status == TaskStatus.SUCCESS

    async def test_submit_many_empty_list(self):
        """Empty task list returns empty results."""
        executor = SyncExecutor()

        results = await executor.submit_many([], lambda x: x)

        assert results == []


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestSyncExecutorLifecycle:
    """Tests for initialize/close lifecycle."""

    async def test_initialize_sets_flag(self):
        """initialize sets _initialized flag."""
        executor = SyncExecutor()

        assert executor._initialized is False

        await executor.initialize()

        assert executor._initialized is True

    async def test_close_clears_flag(self):
        """close clears _initialized flag."""
        executor = SyncExecutor()
        await executor.initialize()

        await executor.close()

        assert executor._initialized is False

    async def test_works_without_initialize(self):
        """Executor works without explicit initialize."""
        executor = SyncExecutor()

        task = Task(name="test", payload=5)
        result = await executor.submit(task, lambda x: x + 1)

        assert result.result == 6

    async def test_executor_name(self):
        """Executor has configurable name."""
        executor = SyncExecutor(name="my-executor")

        assert executor.name == "my-executor"


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestSyncExecutorProtocol:
    """Tests for Executor protocol compliance."""

    def test_has_required_methods(self):
        """SyncExecutor has all required Executor methods."""
        executor = SyncExecutor()

        assert hasattr(executor, "initialize")
        assert hasattr(executor, "close")
        assert hasattr(executor, "submit")
        assert hasattr(executor, "submit_many")

    def test_methods_are_async(self):
        """All I/O methods are async."""
        import inspect

        executor = SyncExecutor()

        assert inspect.iscoroutinefunction(executor.initialize)
        assert inspect.iscoroutinefunction(executor.close)
        assert inspect.iscoroutinefunction(executor.submit)
        assert inspect.iscoroutinefunction(executor.submit_many)
