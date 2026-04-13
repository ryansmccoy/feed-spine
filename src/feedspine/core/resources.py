"""Resource pool for shared resources.

Centralized pool for managing shared resources like HTTP clients,
database connections, and rate limiters.  Resources are created
on-demand via registered factories and cleaned up on ``close()``.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any


class ResourcePool:
    """Centralized resource pool for shared resources.

    Manages lifecycle of shared resources like HTTP clients, database
    connections, semaphores, and configuration.
    """

    def __init__(self) -> None:
        """Initialize an empty resource pool."""
        self._resources: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._async_factories: dict[str, Callable[[], Coroutine[Any, Any, Any]]] = {}
        self._cleanup_funcs: dict[str, Callable[[], Coroutine[Any, Any, None]]] = {}
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the resource pool."""
        self._initialized = True

    async def close(self) -> None:
        """Close all resources and run cleanup functions."""
        # Run cleanup functions in reverse registration order
        for name in reversed(list(self._cleanup_funcs.keys())):
            with contextlib.suppress(Exception):
                await self._cleanup_funcs[name]()
        self._resources.clear()
        self._initialized = False

    def set(self, name: str, value: Any) -> None:
        """Set a resource value directly."""
        self._resources[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Get a resource value, invoking its factory if registered."""
        if name in self._resources:
            return self._resources[name]

        # Try sync factory
        if name in self._factories:
            value = self._factories[name]()
            self._resources[name] = value
            return value

        return default

    async def get_async(self, name: str, default: Any = None) -> Any:
        """Get a resource value, potentially creating it asynchronously.

        Args:
            name: Resource identifier.
            default: Default value if resource not found.

        Returns:
            The resource value, or default if not found.
        """
        async with self._lock:
            if name in self._resources:
                return self._resources[name]

            # Try async factory first
            if name in self._async_factories:
                value = await self._async_factories[name]()
                self._resources[name] = value
                return value

            # Try sync factory
            if name in self._factories:
                value = self._factories[name]()
                self._resources[name] = value
                return value

            return default

    def register_factory(
        self,
        name: str,
        factory: Callable[[], Any],
        cleanup: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """Register a factory for lazy resource creation."""
        self._factories[name] = factory
        if cleanup:
            self._cleanup_funcs[name] = cleanup

    def register_async_factory(
        self,
        name: str,
        factory: Callable[[], Coroutine[Any, Any, Any]],
        cleanup: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """Register an async factory for lazy resource creation."""
        self._async_factories[name] = factory
        if cleanup:
            self._cleanup_funcs[name] = cleanup

    def has(self, name: str) -> bool:
        """Check if a resource exists or has a factory.

        Args:
            name: Resource identifier.

        Returns:
            True if resource exists or can be created.

        Example:
            >>> from feedspine.core.resources import ResourcePool
            >>> pool = ResourcePool()
            >>> pool.has("missing")
            False
            >>> pool.set("exists", 1)
            >>> pool.has("exists")
            True
        """
        return name in self._resources or name in self._factories or name in self._async_factories

    def remove(self, name: str) -> bool:
        """Remove a resource from the pool.

        Args:
            name: Resource identifier.

        Returns:
            True if resource was removed.

        Example:
            >>> from feedspine.core.resources import ResourcePool
            >>> pool = ResourcePool()
            >>> pool.set("value", 1)
            >>> pool.remove("value")
            True
            >>> pool.remove("value")
            False
        """
        removed = name in self._resources
        self._resources.pop(name, None)
        return removed

    @asynccontextmanager
    async def scoped(self, name: str, value: Any) -> AsyncIterator[Any]:
        """Context manager for scoped resource override.

        Temporarily sets a resource value, restoring the original on exit.

        Args:
            name: Resource identifier.
            value: Temporary value.

        Yields:
            The temporary value.

        Example:
            >>> import asyncio
            >>> from feedspine.core.resources import ResourcePool
            >>> async def example():
            ...     pool = ResourcePool()
            ...     pool.set("env", "prod")
            ...     async with pool.scoped("env", "test"):
            ...         assert pool.get("env") == "test"
            ...     assert pool.get("env") == "prod"
            >>> asyncio.run(example())
        """
        original = self._resources.get(name)
        had_original = name in self._resources
        self._resources[name] = value
        try:
            yield value
        finally:
            if had_original:
                self._resources[name] = original
            else:
                self._resources.pop(name, None)


class RateLimiter:
    """Simple async rate limiter using token bucket algorithm.

    Example:
        >>> import asyncio
        >>> from feedspine.core.resources import RateLimiter
        >>> async def example():
        ...     limiter = RateLimiter(rate=10, burst=10)  # 10 req/sec
        ...     await limiter.acquire()  # Wait for token
        ...     return True
        >>> asyncio.run(example())
        True
    """

    def __init__(self, rate: float, burst: int = 1) -> None:
        """Initialize rate limiter.

        Args:
            rate: Tokens per second to add.
            burst: Maximum tokens (burst capacity).
        """
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_update = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire.
        """
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_update
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_update = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return

            # Wait for enough tokens
            wait_time = (tokens - self._tokens) / self._rate
            await asyncio.sleep(wait_time)
            self._tokens = 0


class Semaphore:
    """Named semaphore wrapper for resource pool.

    Example:
        >>> import asyncio
        >>> from feedspine.core.resources import Semaphore
        >>> async def example():
        ...     sem = Semaphore(max_concurrent=2)
        ...     async with sem:
        ...         return "acquired"
        >>> asyncio.run(example())
        'acquired'
    """

    def __init__(self, max_concurrent: int) -> None:
        """Initialize semaphore.

        Args:
            max_concurrent: Maximum concurrent acquisitions.
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def __aenter__(self) -> None:
        """Acquire the semaphore."""
        await self._semaphore.acquire()

    async def __aexit__(self, *args: object) -> None:
        """Release the semaphore."""
        self._semaphore.release()

    async def acquire(self) -> None:
        """Acquire the semaphore."""
        await self._semaphore.acquire()

    def release(self) -> None:
        """Release the semaphore."""
        self._semaphore.release()
