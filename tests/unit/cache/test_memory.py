"""Tests for MemoryCache implementation.

Tests cover:
- Basic get/set/delete operations
- TTL expiration
- Pattern-based clearing
- Lifecycle (initialize/close)
- Protocol compliance
"""

from datetime import timedelta

from feedspine.cache.memory import CacheEntry, MemoryCache

# =============================================================================
# CacheEntry Tests
# =============================================================================


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_create_without_expiry(self):
        """Entry without expiry is never expired."""
        entry = CacheEntry(value="test")

        assert entry.value == "test"
        assert entry.expires_at is None
        assert entry.is_expired is False

    def test_create_with_future_expiry(self):
        """Entry with future expiry is not expired."""
        from datetime import UTC, datetime, timedelta

        future = datetime.now(UTC) + timedelta(hours=1)
        entry = CacheEntry(value="data", expires_at=future)

        assert entry.is_expired is False

    def test_create_with_past_expiry(self):
        """Entry with past expiry is expired."""
        from datetime import UTC, datetime, timedelta

        past = datetime.now(UTC) - timedelta(hours=1)
        entry = CacheEntry(value="old", expires_at=past)

        assert entry.is_expired is True

    def test_created_at_auto_set(self):
        """created_at is automatically set to now."""
        from datetime import UTC, datetime

        before = datetime.now(UTC)
        entry = CacheEntry(value="x")
        after = datetime.now(UTC)

        assert before <= entry.created_at <= after


# =============================================================================
# MemoryCache Basic Operations
# =============================================================================


class TestMemoryCacheBasicOps:
    """Tests for basic get/set/delete operations."""

    async def test_set_and_get(self):
        """Can store and retrieve a value."""
        cache = MemoryCache()

        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    async def test_get_nonexistent_returns_none(self):
        """Getting missing key returns None."""
        cache = MemoryCache()

        result = await cache.get("missing")

        assert result is None

    async def test_set_overwrites_existing(self):
        """Setting existing key overwrites value."""
        cache = MemoryCache()

        await cache.set("key", "old")
        await cache.set("key", "new")
        result = await cache.get("key")

        assert result == "new"

    async def test_delete_existing(self):
        """Deleting existing key returns True."""
        cache = MemoryCache()

        await cache.set("key", "value")
        result = await cache.delete("key")

        assert result is True
        assert await cache.get("key") is None

    async def test_delete_nonexistent(self):
        """Deleting missing key returns False."""
        cache = MemoryCache()

        result = await cache.delete("missing")

        assert result is False

    async def test_exists_for_existing_key(self):
        """exists returns True for existing key."""
        cache = MemoryCache()

        await cache.set("key", "value")

        assert await cache.exists("key") is True

    async def test_exists_for_missing_key(self):
        """exists returns False for missing key."""
        cache = MemoryCache()

        assert await cache.exists("missing") is False

    async def test_store_various_types(self):
        """Can store various Python types."""
        cache = MemoryCache()

        await cache.set("string", "hello")
        await cache.set("int", 42)
        await cache.set("float", 3.14)
        await cache.set("list", [1, 2, 3])
        await cache.set("dict", {"a": 1})
        await cache.set("none", None)

        assert await cache.get("string") == "hello"
        assert await cache.get("int") == 42
        assert await cache.get("float") == 3.14
        assert await cache.get("list") == [1, 2, 3]
        assert await cache.get("dict") == {"a": 1}
        assert await cache.get("none") is None


# =============================================================================
# TTL Tests
# =============================================================================


class TestMemoryCacheTTL:
    """Tests for TTL (time-to-live) functionality."""

    async def test_set_with_timedelta_ttl(self):
        """Can set TTL using timedelta."""
        cache = MemoryCache()

        await cache.set("key", "value", ttl=timedelta(hours=1))

        # Not expired yet
        result = await cache.get("key")
        assert result == "value"

    async def test_set_with_int_ttl(self):
        """Can set TTL using integer seconds."""
        cache = MemoryCache()

        await cache.set("key", "value", ttl=3600)

        result = await cache.get("key")
        assert result == "value"

    async def test_expired_entry_returns_none(self):
        """Expired entries return None on get."""
        cache = MemoryCache()

        # Set with negative TTL (already expired)
        await cache.set("key", "value", ttl=timedelta(seconds=-1))

        result = await cache.get("key")
        assert result is None

    async def test_expired_entry_removed_on_get(self):
        """Expired entries are removed when accessed."""
        cache = MemoryCache()

        await cache.set("key", "value", ttl=timedelta(seconds=-1))

        await cache.get("key")  # This should remove it

        assert "key" not in cache._data


# =============================================================================
# Pattern Clearing Tests
# =============================================================================


class TestMemoryCachePatternClear:
    """Tests for pattern-based cache clearing."""

    async def test_clear_all(self):
        """clear with no pattern clears everything."""
        cache = MemoryCache()

        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)

        count = await cache.clear()

        assert count == 3
        assert await cache.get("a") is None
        assert await cache.get("b") is None
        assert await cache.get("c") is None

    async def test_clear_with_pattern(self):
        """clear with pattern only clears matching keys."""
        cache = MemoryCache()

        await cache.set("user:1", "alice")
        await cache.set("user:2", "bob")
        await cache.set("post:1", "hello")

        count = await cache.clear("user:*")

        assert count == 2
        assert await cache.get("user:1") is None
        assert await cache.get("user:2") is None
        assert await cache.get("post:1") == "hello"

    async def test_clear_empty_cache(self):
        """Clearing empty cache returns 0."""
        cache = MemoryCache()

        count = await cache.clear()

        assert count == 0


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestMemoryCacheLifecycle:
    """Tests for initialize/close lifecycle."""

    async def test_initialize_sets_flag(self):
        """initialize sets _initialized flag."""
        cache = MemoryCache()

        assert cache._initialized is False

        await cache.initialize()

        assert cache._initialized is True

    async def test_initialize_idempotent(self):
        """Multiple initializations are safe."""
        cache = MemoryCache()

        await cache.initialize()
        await cache.initialize()

        assert cache._initialized is True

    async def test_close_clears_data(self):
        """close clears cached data."""
        cache = MemoryCache()
        await cache.initialize()

        await cache.set("key", "value")
        await cache.close()

        assert len(cache._data) == 0
        assert cache._initialized is False

    async def test_close_idempotent(self):
        """Multiple closes are safe."""
        cache = MemoryCache()
        await cache.initialize()

        await cache.close()
        await cache.close()

        assert cache._initialized is False


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestMemoryCacheProtocol:
    """Tests for CacheBackend protocol compliance."""

    def test_has_required_methods(self):
        """MemoryCache has all required CacheBackend methods."""
        cache = MemoryCache()

        assert hasattr(cache, "initialize")
        assert hasattr(cache, "close")
        assert hasattr(cache, "get")
        assert hasattr(cache, "set")
        assert hasattr(cache, "delete")
        assert hasattr(cache, "exists")
        assert hasattr(cache, "clear")

    def test_methods_are_async(self):
        """All I/O methods are async."""
        import inspect

        cache = MemoryCache()

        assert inspect.iscoroutinefunction(cache.initialize)
        assert inspect.iscoroutinefunction(cache.close)
        assert inspect.iscoroutinefunction(cache.get)
        assert inspect.iscoroutinefunction(cache.set)
        assert inspect.iscoroutinefunction(cache.delete)
        assert inspect.iscoroutinefunction(cache.exists)
        assert inspect.iscoroutinefunction(cache.clear)
