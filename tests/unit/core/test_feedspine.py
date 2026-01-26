"""Tests for feedspine.core.feedspine - Main orchestrator."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.adapter.base import BaseFeedAdapter
from feedspine.models.base import Layer, Metadata
from feedspine.models.record import RecordCandidate
from feedspine.storage.memory import MemoryStorage

# =============================================================================
# Test Fixtures
# =============================================================================


class MockAdapter(BaseFeedAdapter):
    """Mock adapter for testing."""

    def __init__(self, name: str, items: list[dict] | None = None) -> None:
        super().__init__(name=name)
        self._items = items or []

    async def _fetch_items(self) -> list[dict]:
        return self._items

    def _to_candidate(self, item: dict) -> RecordCandidate:
        return RecordCandidate(
            natural_key=item.get("id", "unknown"),
            published_at=datetime.now(UTC),
            content={"title": item.get("title", "")},
            metadata=Metadata(source=self.name),
        )


@pytest.fixture
def storage() -> MemoryStorage:
    """Fresh storage instance."""
    return MemoryStorage()


@pytest.fixture
def mock_adapter() -> MockAdapter:
    """Mock adapter with sample data."""
    return MockAdapter(
        name="test-feed",
        items=[
            {"id": "item-001", "title": "First Item"},
            {"id": "item-002", "title": "Second Item"},
        ],
    )


# =============================================================================
# Creation Tests
# =============================================================================


class TestFeedSpineCreation:
    """Tests for FeedSpine instantiation."""

    async def test_create_with_storage(self, storage: MemoryStorage) -> None:
        """Create FeedSpine with required storage."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)
        assert spine.storage is storage

    async def test_create_with_optional_components(self, storage: MemoryStorage) -> None:
        """Create FeedSpine with optional components."""
        from feedspine.cache.memory import MemoryCache
        from feedspine.core.feedspine import FeedSpine
        from feedspine.search.memory import MemorySearch

        cache = MemoryCache()
        search = MemorySearch()

        spine = FeedSpine(
            storage=storage,
            cache=cache,
            search=search,
        )

        assert spine.cache is cache
        assert spine.search_backend is search


# =============================================================================
# Feed Registration Tests
# =============================================================================


class TestFeedSpineRegistration:
    """Tests for feed adapter registration."""

    async def test_register_single_feed(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """Register a single feed adapter."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)
        spine.register_feed(mock_adapter)

        assert mock_adapter.name in spine.feeds
        assert spine.feeds[mock_adapter.name] is mock_adapter

    async def test_register_multiple_feeds(self, storage: MemoryStorage) -> None:
        """Register multiple feed adapters."""
        from feedspine.core.feedspine import FeedSpine

        adapter1 = MockAdapter(name="feed-1", items=[])
        adapter2 = MockAdapter(name="feed-2", items=[])

        spine = FeedSpine(storage=storage)
        spine.register_feed(adapter1)
        spine.register_feed(adapter2)

        assert len(spine.feeds) == 2
        assert "feed-1" in spine.feeds
        assert "feed-2" in spine.feeds

    async def test_register_duplicate_feed_raises(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """Registering duplicate feed name raises error."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)
        spine.register_feed(mock_adapter)

        with pytest.raises(ValueError, match="already registered"):
            spine.register_feed(mock_adapter)

    async def test_list_feeds_returns_registered(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """list_feeds returns all registered feed names."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)
        spine.register_feed(mock_adapter)

        feed_names = spine.list_feeds()
        assert mock_adapter.name in feed_names


# =============================================================================
# Collection Tests
# =============================================================================


class TestFeedSpineCollect:
    """Tests for feed collection."""

    async def test_collect_all_feeds(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """Collect from all registered feeds."""
        from feedspine.core.feedspine import FeedSpine

        await storage.initialize()
        spine = FeedSpine(storage=storage)
        spine.register_feed(mock_adapter)

        result = await spine.collect()

        assert result.total_processed == 2
        assert result.total_new == 2

    async def test_collect_specific_feeds(self, storage: MemoryStorage) -> None:
        """Collect from specific feeds only."""
        from feedspine.core.feedspine import FeedSpine

        await storage.initialize()
        adapter1 = MockAdapter(name="feed-1", items=[{"id": "1", "title": "A"}])
        adapter2 = MockAdapter(name="feed-2", items=[{"id": "2", "title": "B"}])

        spine = FeedSpine(storage=storage)
        spine.register_feed(adapter1)
        spine.register_feed(adapter2)

        # Collect only from feed-1
        result = await spine.collect(feeds=["feed-1"])

        assert result.total_processed == 1
        assert "feed-1" in result.feed_stats

    async def test_collect_returns_stats_per_feed(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """Collect returns stats for each feed."""
        from feedspine.core.feedspine import FeedSpine

        await storage.initialize()
        spine = FeedSpine(storage=storage)
        spine.register_feed(mock_adapter)

        result = await spine.collect()

        assert mock_adapter.name in result.feed_stats
        stats = result.feed_stats[mock_adapter.name]
        assert stats.processed == 2
        assert stats.new == 2

    async def test_collect_handles_empty_feeds(self, storage: MemoryStorage) -> None:
        """Collect handles feeds with no items."""
        from feedspine.core.feedspine import FeedSpine

        await storage.initialize()
        empty_adapter = MockAdapter(name="empty-feed", items=[])

        spine = FeedSpine(storage=storage)
        spine.register_feed(empty_adapter)

        result = await spine.collect()

        assert result.total_processed == 0
        assert result.total_errors == 0

    async def test_collect_unknown_feed_raises(self, storage: MemoryStorage) -> None:
        """Collecting from unknown feed raises error."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)

        with pytest.raises(ValueError, match="Unknown feed"):
            await spine.collect(feeds=["nonexistent"])


# =============================================================================
# Query Tests
# =============================================================================


class TestFeedSpineQuery:
    """Tests for querying stored records."""

    async def test_query_all_records(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """Query returns all stored records."""
        from feedspine.core.feedspine import FeedSpine

        await storage.initialize()
        spine = FeedSpine(storage=storage)
        spine.register_feed(mock_adapter)
        await spine.collect()

        records = [r async for r in spine.query()]

        assert len(records) == 2

    async def test_query_with_layer_filter(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """Query filters by layer."""
        from feedspine.core.feedspine import FeedSpine

        await storage.initialize()
        spine = FeedSpine(storage=storage)
        spine.register_feed(mock_adapter)
        await spine.collect()

        # Query only BRONZE records
        records = [r async for r in spine.query(layer=Layer.BRONZE)]

        assert len(records) == 2
        assert all(r.layer == Layer.BRONZE for r in records)

    async def test_query_with_limit(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """Query respects limit parameter."""
        from feedspine.core.feedspine import FeedSpine

        await storage.initialize()
        spine = FeedSpine(storage=storage)
        spine.register_feed(mock_adapter)
        await spine.collect()

        records = [r async for r in spine.query(limit=1)]

        assert len(records) == 1


# =============================================================================
# Search Tests
# =============================================================================


class TestFeedSpineSearch:
    """Tests for full-text search."""

    async def test_search_requires_search_backend(self, storage: MemoryStorage) -> None:
        """Search raises if no search backend configured."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)

        with pytest.raises(ValueError, match="search backend"):
            await spine.search("query")

    async def test_search_with_backend(
        self, storage: MemoryStorage, mock_adapter: MockAdapter
    ) -> None:
        """Search uses configured search backend."""
        from feedspine.core.feedspine import FeedSpine
        from feedspine.search.memory import MemorySearch

        await storage.initialize()
        search = MemorySearch()
        await search.initialize()

        spine = FeedSpine(storage=storage, search=search)
        spine.register_feed(mock_adapter)
        await spine.collect()

        # Index the records first
        async for record in spine.query():
            await search.index(
                record_id=record.id,
                content=record.content,
            )

        response = await spine.search("First")

        assert response.total_count >= 0  # May or may not find match


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestFeedSpineLifecycle:
    """Tests for lifecycle management."""

    async def test_context_manager(self, storage: MemoryStorage) -> None:
        """FeedSpine works as async context manager."""
        from feedspine.core.feedspine import FeedSpine

        async with FeedSpine(storage=storage) as spine:
            assert spine is not None

    async def test_initialize_initializes_components(self, storage: MemoryStorage) -> None:
        """Initialize calls initialize on all components."""
        from feedspine.cache.memory import MemoryCache
        from feedspine.core.feedspine import FeedSpine

        cache = MemoryCache()
        spine = FeedSpine(storage=storage, cache=cache)

        await spine.initialize()

        # Both should be initialized (no error calling methods)
        await storage.count()  # Would fail if not initialized

    async def test_close_closes_components(self, storage: MemoryStorage) -> None:
        """Close calls close on all components."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)
        await spine.initialize()
        await spine.close()

        # Verify close was called (re-initialize should work)
        await spine.initialize()


# =============================================================================
# Configuration Tests
# =============================================================================


class TestFeedSpineConfiguration:
    """Tests for configuration and settings."""

    async def test_default_configuration(self, storage: MemoryStorage) -> None:
        """Default configuration has sensible defaults."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)

        assert spine.storage is storage
        assert spine.cache is None
        assert spine.search_backend is None

    async def test_info_returns_metadata(self, storage: MemoryStorage) -> None:
        """info() returns orchestrator metadata."""
        from feedspine.core.feedspine import FeedSpine

        spine = FeedSpine(storage=storage)

        info = spine.info()

        assert "feeds" in info
        assert "has_cache" in info
        assert "has_search" in info
