"""Synchronous executor implementation.

Provides a simple executor that runs tasks directly in the current
process, supporting both sync and async callables.

Example:
    >>> from feedspine.executor.sync import SyncExecutor
    >>> executor = SyncExecutor()
    >>> # SyncExecutor implements Executor protocol
    >>> hasattr(executor, 'submit')
    True
    >>> hasattr(executor, 'submit_many')
    True
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from feedspine.models.task import Task, TaskResult, TaskStatus

T = TypeVar("T")
R = TypeVar("R")


class SyncExecutor:
    """Simple synchronous executor.

    Runs tasks directly without any queueing or distribution.
    Supports both sync and async callables.

    Best for: Testing, development, simple pipelines.

    Example:
        >>> import asyncio
        >>> from feedspine.executor.sync import SyncExecutor
        >>> from feedspine.models.task import Task
        >>> executor = SyncExecutor()
        >>> task = Task(name="double", payload=5)
        >>> result = asyncio.run(executor.submit(task, lambda x: x * 2))
        >>> result.result
        10
        >>> result.status.value
        'success'
    """

    def __init__(self, name: str = "sync") -> None:
        """Initialize the executor.

        Args:
            name: Executor name for logging.
        """
        self.name = name
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize executor (no-op for sync).

        Example:
            >>> import asyncio
            >>> from feedspine.executor.sync import SyncExecutor
            >>> e = SyncExecutor()
            >>> asyncio.run(e.initialize())
            >>> e._initialized
            True
        """
        self._initialized = True

    async def close(self) -> None:
        """Shutdown executor (no-op for sync)."""
        self._initialized = False

    async def submit(
        self,
        task: Task[T],
        func: Callable[[T], R] | Callable[[T], Awaitable[R]],
    ) -> TaskResult[R]:
        """Submit a task for execution.

        Runs the task immediately and returns the result.
        Supports retries on failure.

        Args:
            task: Task to execute.
            func: Function to call with task.payload.

        Returns:
            TaskResult with status, result/error, and timing info.

        Example:
            >>> import asyncio
            >>> from feedspine.executor.sync import SyncExecutor
            >>> from feedspine.models.task import Task
            >>> e = SyncExecutor()
            >>> t = Task(name="greet", payload="world")
            >>> r = asyncio.run(e.submit(t, lambda x: f"hello {x}"))
            >>> r.result
            'hello world'
        """
        started_at = datetime.now(UTC)
        last_error: str | None = None
        last_error_type: str | None = None
        retries = 0

        while retries <= task.max_retries:
            try:
                # Run the function
                if inspect.iscoroutinefunction(func):
                    result = await func(task.payload)
                else:
                    result = func(task.payload)

                completed_at = datetime.now(UTC)
                duration_ms = (completed_at - started_at).total_seconds() * 1000

                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.SUCCESS,
                    result=result,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    retries_used=retries,
                )

            except Exception as e:
                last_error = str(e)
                last_error_type = type(e).__name__
                retries += 1

                if retries <= task.max_retries:
                    # Wait before retry
                    delay = task.retry_delay_seconds * (2 ** (retries - 1))  # Exponential backoff
                    await asyncio.sleep(delay)

        # All retries exhausted
        completed_at = datetime.now(UTC)
        duration_ms = (completed_at - started_at).total_seconds() * 1000

        return TaskResult(
            task_id=task.id,
            status=TaskStatus.FAILED,
            error=last_error,
            error_type=last_error_type,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            retries_used=retries - 1,
        )

    async def submit_many(
        self,
        tasks: list[Task[T]],
        func: Callable[[T], R] | Callable[[T], Awaitable[R]],
        max_concurrent: int = 10,
    ) -> list[TaskResult[R]]:
        """Submit multiple tasks with bounded concurrency.

        Uses asyncio.Semaphore to limit concurrent executions.

        Args:
            tasks: Tasks to execute.
            func: Function to call for each task.
            max_concurrent: Maximum concurrent tasks.

        Returns:
            List of TaskResults in same order as input tasks.

        Example:
            >>> import asyncio
            >>> from feedspine.executor.sync import SyncExecutor
            >>> from feedspine.models.task import Task
            >>> e = SyncExecutor()
            >>> tasks = [Task(name="sq", payload=i) for i in [1, 2, 3]]
            >>> results = asyncio.run(e.submit_many(tasks, lambda x: x**2))
            >>> [r.result for r in results]
            [1, 4, 9]
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_submit(task: Task[T]) -> TaskResult[R]:
            async with semaphore:
                return await self.submit(task, func)

        # Run all tasks concurrently (bounded)
        return await asyncio.gather(*[bounded_submit(t) for t in tasks])

    # --- Utility Methods ---

    async def map(
        self,
        func: Callable[[T], R] | Callable[[T], Awaitable[R]],
        items: list[T],
        max_concurrent: int = 10,
    ) -> list[R]:
        """Map a function over items, returning results only.

        Convenience method that wraps items in tasks.

        Args:
            func: Function to apply.
            items: Input items.
            max_concurrent: Concurrency limit.

        Returns:
            List of results (raises if any failed).

        Example:
            >>> import asyncio
            >>> from feedspine.executor.sync import SyncExecutor
            >>> e = SyncExecutor()
            >>> asyncio.run(e.map(lambda x: x + 1, [1, 2, 3]))
            [2, 3, 4]
        """
        tasks = [Task(name="map", payload=item, max_retries=0) for item in items]
        results = await self.submit_many(tasks, func, max_concurrent)

        # Check for failures
        for result in results:
            if result.status == TaskStatus.FAILED:
                raise RuntimeError(f"Task failed: {result.error}")

        return [r.result for r in results]
