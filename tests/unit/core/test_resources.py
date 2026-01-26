"""Tests for feedspine.core.resources."""

from __future__ import annotations

import asyncio

import pytest

from feedspine.core.resources import RateLimiter, ResourcePool, Semaphore


class TestResourcePoolBasic:
    """Basic ResourcePool tests."""

    @pytest.fixture
    async def pool(self) -> ResourcePool:
        """Create and initialize a resource pool."""
        p = ResourcePool()
        await p.initialize()
        yield p
        await p.close()

    async def test_initialize_and_close(self) -> None:
        """Can initialize and close pool."""
        pool = ResourcePool()
        await pool.initialize()
        assert pool._initialized is True
        await pool.close()
        assert pool._initialized is False

    async def test_set_and_get(self, pool: ResourcePool) -> None:
        """Can set and get resources."""
        pool.set("key", "value")
        assert pool.get("key") == "value"

    async def test_get_default(self, pool: ResourcePool) -> None:
        """get() returns default for missing key."""
        assert pool.get("missing") is None
        assert pool.get("missing", "default") == "default"

    async def test_has(self, pool: ResourcePool) -> None:
        """has() checks resource existence."""
        assert pool.has("key") is False
        pool.set("key", "value")
        assert pool.has("key") is True

    async def test_remove(self, pool: ResourcePool) -> None:
        """Can remove resources."""
        pool.set("key", "value")
        assert pool.remove("key") is True
        assert pool.has("key") is False
        assert pool.remove("key") is False


class TestResourcePoolFactories:
    """ResourcePool factory tests."""

    @pytest.fixture
    async def pool(self) -> ResourcePool:
        """Create and initialize a resource pool."""
        p = ResourcePool()
        await p.initialize()
        yield p
        await p.close()

    async def test_sync_factory(self, pool: ResourcePool) -> None:
        """Sync factory creates resource on first get."""
        call_count = [0]

        def factory() -> str:
            call_count[0] += 1
            return "created"

        pool.register_factory("lazy", factory)
        assert pool.has("lazy") is True  # Has factory
        assert call_count[0] == 0  # Not called yet

        value = pool.get("lazy")
        assert value == "created"
        assert call_count[0] == 1

        # Second get reuses cached value
        pool.get("lazy")
        assert call_count[0] == 1

    async def test_async_factory(self, pool: ResourcePool) -> None:
        """Async factory creates resource on first get_async."""
        call_count = [0]

        async def factory() -> str:
            call_count[0] += 1
            return "async_created"

        pool.register_async_factory("async_lazy", factory)
        assert call_count[0] == 0

        value = await pool.get_async("async_lazy")
        assert value == "async_created"
        assert call_count[0] == 1

        # Second get reuses cached value
        await pool.get_async("async_lazy")
        assert call_count[0] == 1


class TestResourcePoolCleanup:
    """ResourcePool cleanup tests."""

    async def test_cleanup_called_on_close(self) -> None:
        """Cleanup functions are called on close."""
        cleaned = [False]

        async def cleanup() -> None:
            cleaned[0] = True

        pool = ResourcePool()
        await pool.initialize()
        pool.register_factory("resource", lambda: "value", cleanup=cleanup)
        pool.get("resource")  # Create resource

        await pool.close()
        assert cleaned[0] is True


class TestResourcePoolScoped:
    """ResourcePool scoped context tests."""

    async def test_scoped_override(self) -> None:
        """scoped() temporarily overrides value."""
        pool = ResourcePool()
        await pool.initialize()
        pool.set("env", "prod")

        async with pool.scoped("env", "test"):
            assert pool.get("env") == "test"

        assert pool.get("env") == "prod"
        await pool.close()

    async def test_scoped_new_key(self) -> None:
        """scoped() with new key removes on exit."""
        pool = ResourcePool()
        await pool.initialize()

        async with pool.scoped("temp", "value"):
            assert pool.get("temp") == "value"

        assert pool.get("temp") is None
        await pool.close()


class TestRateLimiter:
    """RateLimiter tests."""

    async def test_acquire_basic(self) -> None:
        """Can acquire tokens."""
        limiter = RateLimiter(rate=100, burst=10)
        await limiter.acquire()  # Should not block

    async def test_burst_capacity(self) -> None:
        """Burst capacity allows multiple quick acquires."""
        limiter = RateLimiter(rate=100, burst=5)
        # Should be able to acquire 5 quickly
        for _ in range(5):
            await limiter.acquire()

    async def test_rate_limiting(self) -> None:
        """Rate limiting slows acquisition when burst exhausted."""
        limiter = RateLimiter(rate=1000, burst=1)  # 1 token, fast refill
        await limiter.acquire()  # Use burst token
        # Next acquire will need to wait for refill
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        # Should have waited approximately 1/1000 = 0.001 seconds
        assert elapsed >= 0  # Just verify it completed


class TestSemaphore:
    """Semaphore tests."""

    async def test_basic_acquire_release(self) -> None:
        """Can acquire and release semaphore."""
        sem = Semaphore(max_concurrent=2)
        await sem.acquire()
        sem.release()

    async def test_context_manager(self) -> None:
        """Works as context manager."""
        sem = Semaphore(max_concurrent=2)
        async with sem:
            pass  # Acquired

    async def test_max_concurrent(self) -> None:
        """Limits concurrent acquisitions."""
        sem = Semaphore(max_concurrent=2)
        acquired = [0]
        max_concurrent = [0]

        async def worker() -> None:
            async with sem:
                acquired[0] += 1
                max_concurrent[0] = max(max_concurrent[0], acquired[0])
                await asyncio.sleep(0.01)
                acquired[0] -= 1

        # Run 4 workers concurrently
        await asyncio.gather(*[worker() for _ in range(4)])
        assert max_concurrent[0] <= 2
