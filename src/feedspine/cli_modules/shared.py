"""Shared utilities for CLI modules."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from rich.console import Console

console = Console()


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async function from sync CLI context."""
    return asyncio.run(coro)


def async_command(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Any]:
    """Decorator to run an async function as a sync Typer command."""
    import functools

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(func(*args, **kwargs))

    return wrapper


def get_storage(
    connection: str | None = None,
    storage_type: str | None = None,
) -> Any:
    """Create storage backend from CLI args or environment."""
    from feedspine.storage.factory import create_storage

    return create_storage(
        connection_string=connection,
        storage_type=storage_type,
    )
