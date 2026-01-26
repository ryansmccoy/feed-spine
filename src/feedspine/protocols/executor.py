"""Executor protocol.

Defines the interface for task executors (sync, async, threaded, distributed).

Example:
    >>> from feedspine.protocols.executor import Executor
    >>> # Executor is a Protocol - check interface
    >>> hasattr(Executor, "submit")
    True
    >>> hasattr(Executor, "submit_many")
    True
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from feedspine.models.task import Task, TaskResult

T = TypeVar("T")
R = TypeVar("R")


@runtime_checkable
class Executor(Protocol):
    """Executor protocol for running tasks.

    Implementations: Sync, AsyncIO, Threaded, Celery, Prefect, etc.
    """

    async def submit(
        self,
        task: Task[T],
        func: Callable[[T], R] | Callable[[T], Awaitable[R]],
    ) -> TaskResult[R]:
        """Submit a task for execution."""
        ...

    async def submit_many(
        self,
        tasks: list[Task[T]],
        func: Callable[[T], R] | Callable[[T], Awaitable[R]],
        max_concurrent: int = 10,
    ) -> list[TaskResult[R]]:
        """Submit multiple tasks."""
        ...

    async def initialize(self) -> None:
        """Initialize executor."""
        ...

    async def close(self) -> None:
        """Shutdown executor."""
        ...
