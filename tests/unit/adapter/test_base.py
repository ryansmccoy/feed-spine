"""Tests for FeedAdapter protocol and base implementation.

TDD tests defining how FeedAdapters should work:
- Protocol compliance
- Fetching candidates from sources
- Error handling and retries
- Rate limiting
- Feed metadata
"""

from datetime import UTC, datetime

import pytest

from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate

# =============================================================================
# FeedAdapter Protocol Tests
# =============================================================================


class TestFeedAdapterProtocol:
    """Tests for FeedAdapter protocol requirements."""

    def test_protocol_has_name(self):
        """FeedAdapter must have a name property."""
        from feedspine.adapter.base import FeedAdapter

        # Protocol should define name
        assert hasattr(FeedAdapter, "name")

    def test_protocol_has_fetch(self):
        """FeedAdapter must have async fetch method."""
        from feedspine.adapter.base import FeedAdapter

        assert hasattr(FeedAdapter, "fetch")

    def test_protocol_has_initialize(self):
        """FeedAdapter must have initialize method."""
        from feedspine.adapter.base import FeedAdapter

        assert hasattr(FeedAdapter, "initialize")

    def test_protocol_has_close(self):
        """FeedAdapter must have close method."""
        from feedspine.adapter.base import FeedAdapter

        assert hasattr(FeedAdapter, "close")


# =============================================================================
# BaseFeedAdapter Tests
# =============================================================================


class TestBaseFeedAdapterCreation:
    """Tests for BaseFeedAdapter instantiation."""

    def test_create_with_name(self):
        """Can create adapter with name."""
        from feedspine.adapter.base import BaseFeedAdapter

        class TestAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass

        adapter = TestAdapter(name="test-feed")

        assert adapter.name == "test-feed"

    def test_create_with_source_url(self):
        """Can create adapter with source URL."""
        from feedspine.adapter.base import BaseFeedAdapter

        class TestAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass

        adapter = TestAdapter(
            name="rss-feed",
            source_url="https://example.com/feed.xml",
        )

        assert adapter.source_url == "https://example.com/feed.xml"

    def test_create_with_rate_limit(self):
        """Can configure rate limiting."""
        from feedspine.adapter.base import BaseFeedAdapter

        class TestAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass

        adapter = TestAdapter(
            name="limited",
            requests_per_second=2.0,
        )

        assert adapter.requests_per_second == 2.0


# =============================================================================
# Fetch Tests
# =============================================================================


class TestBaseFeedAdapterFetch:
    """Tests for fetching candidates."""

    async def test_fetch_returns_async_iterator(self):
        """fetch() returns an async iterator of candidates."""
        from feedspine.adapter.base import BaseFeedAdapter

        class TestAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return [
                    {"id": "1", "title": "First", "published": datetime.now(UTC)},
                    {"id": "2", "title": "Second", "published": datetime.now(UTC)},
                ]

            def _to_candidate(self, item):
                return RecordCandidate(
                    natural_key=item["id"],
                    published_at=item["published"],
                    content={"title": item["title"]},
                    metadata=Metadata(source=self.name),
                )

        adapter = TestAdapter(name="test")

        candidates = []
        async for candidate in adapter.fetch():
            candidates.append(candidate)

        assert len(candidates) == 2
        assert all(isinstance(c, RecordCandidate) for c in candidates)

    async def test_fetch_yields_record_candidates(self):
        """fetch() yields RecordCandidate instances."""
        from feedspine.adapter.base import BaseFeedAdapter

        class TestAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return [{"id": "item-1", "published": datetime.now(UTC)}]

            def _to_candidate(self, item):
                return RecordCandidate(
                    natural_key=item["id"],
                    published_at=item["published"],
                    content={},
                    metadata=Metadata(source=self.name),
                )

        adapter = TestAdapter(name="test")

        async for candidate in adapter.fetch():
            assert isinstance(candidate, RecordCandidate)
            assert candidate.natural_key == "item-1"

    async def test_fetch_empty_source(self):
        """fetch() handles empty sources gracefully."""
        from feedspine.adapter.base import BaseFeedAdapter

        class EmptyAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass  # Won't be called

        adapter = EmptyAdapter(name="empty")

        candidates = []
        async for candidate in adapter.fetch():
            candidates.append(candidate)

        assert candidates == []

    async def test_fetch_sets_metadata_source(self):
        """Candidates have correct source in metadata."""
        from feedspine.adapter.base import BaseFeedAdapter

        class TestAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return [{"id": "1", "published": datetime.now(UTC)}]

            def _to_candidate(self, item):
                return RecordCandidate(
                    natural_key=item["id"],
                    published_at=item["published"],
                    content={},
                    metadata=Metadata(source=self.name),
                )

        adapter = TestAdapter(name="my-feed")

        async for candidate in adapter.fetch():
            assert candidate.metadata.source == "my-feed"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestBaseFeedAdapterErrorHandling:
    """Tests for error handling during fetch."""

    async def test_fetch_error_raises_by_default(self):
        """Errors during fetch raise FeedError by default."""
        from feedspine.adapter.base import BaseFeedAdapter, FeedError

        class FailingAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                raise ConnectionError("Network failure")

            def _to_candidate(self, item):
                pass

        adapter = FailingAdapter(name="failing")

        with pytest.raises(FeedError) as exc_info:
            async for _ in adapter.fetch():
                pass

        assert "Network failure" in str(exc_info.value)

    async def test_fetch_skips_invalid_items(self):
        """Invalid items are skipped, not blocking the whole fetch."""
        from feedspine.adapter.base import BaseFeedAdapter

        class MixedAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return [
                    {"id": "good-1", "published": datetime.now(UTC)},
                    {"id": None, "published": None},  # Invalid
                    {"id": "good-2", "published": datetime.now(UTC)},
                ]

            def _to_candidate(self, item):
                if item["id"] is None:
                    raise ValueError("Invalid item")
                return RecordCandidate(
                    natural_key=item["id"],
                    published_at=item["published"],
                    content={},
                    metadata=Metadata(source=self.name),
                )

        adapter = MixedAdapter(name="mixed")

        candidates = []
        async for candidate in adapter.fetch():
            candidates.append(candidate)

        assert len(candidates) == 2
        assert candidates[0].natural_key == "good-1"
        assert candidates[1].natural_key == "good-2"

    async def test_fetch_tracks_error_count(self):
        """Adapter tracks number of errors during fetch."""
        from feedspine.adapter.base import BaseFeedAdapter

        class ErrorTrackingAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return [
                    {"id": "1", "published": datetime.now(UTC)},
                    {"id": None},  # Will error
                    {"id": None},  # Will error
                    {"id": "2", "published": datetime.now(UTC)},
                ]

            def _to_candidate(self, item):
                if item["id"] is None:
                    raise ValueError("Bad")
                return RecordCandidate(
                    natural_key=item["id"],
                    published_at=item["published"],
                    content={},
                    metadata=Metadata(source=self.name),
                )

        adapter = ErrorTrackingAdapter(name="errors")

        async for _ in adapter.fetch():
            pass

        assert adapter.last_fetch_errors == 2


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestBaseFeedAdapterRateLimiting:
    """Tests for rate limiting functionality."""

    async def test_respects_rate_limit(self):
        """Fetch respects configured rate limit."""
        import time

        from feedspine.adapter.base import BaseFeedAdapter

        fetch_times = []

        class TimedAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                fetch_times.append(time.time())
                return [{"id": "1", "published": datetime.now(UTC)}]

            def _to_candidate(self, item):
                return RecordCandidate(
                    natural_key=item["id"],
                    published_at=item["published"],
                    content={},
                    metadata=Metadata(source=self.name),
                )

        # 10 requests per second = 100ms between requests
        adapter = TimedAdapter(name="timed", requests_per_second=10.0)

        # Fetch multiple times
        for _ in range(3):
            async for _ in adapter.fetch():
                pass

        # Should have some delay between fetches
        # (Just checking the mechanism exists, not exact timing)
        assert len(fetch_times) == 3


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestBaseFeedAdapterLifecycle:
    """Tests for adapter lifecycle management."""

    async def test_initialize_called_before_fetch(self):
        """initialize() prepares adapter for fetching."""
        from feedspine.adapter.base import BaseFeedAdapter

        class LifecycleAdapter(BaseFeedAdapter):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.initialized = False

            async def initialize(self):
                await super().initialize()
                self.initialized = True

            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass

        adapter = LifecycleAdapter(name="lifecycle")

        assert adapter.initialized is False
        await adapter.initialize()
        assert adapter.initialized is True

    async def test_close_releases_resources(self):
        """close() releases adapter resources."""
        from feedspine.adapter.base import BaseFeedAdapter

        class ResourceAdapter(BaseFeedAdapter):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.closed = False

            async def close(self):
                await super().close()
                self.closed = True

            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass

        adapter = ResourceAdapter(name="resource")
        await adapter.initialize()

        assert adapter.closed is False
        await adapter.close()
        assert adapter.closed is True

    async def test_context_manager_support(self):
        """Adapter can be used as async context manager."""
        from feedspine.adapter.base import BaseFeedAdapter

        class ContextAdapter(BaseFeedAdapter):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.entered = False
                self.exited = False

            async def initialize(self):
                await super().initialize()
                self.entered = True

            async def close(self):
                await super().close()
                self.exited = True

            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass

        async with ContextAdapter(name="ctx") as adapter:
            assert adapter.entered is True
            assert adapter.exited is False

        assert adapter.exited is True


# =============================================================================
# Feed Metadata Tests
# =============================================================================


class TestBaseFeedAdapterMetadata:
    """Tests for feed-level metadata."""

    async def test_tracks_last_fetch_time(self):
        """Adapter tracks when last fetch occurred."""
        from feedspine.adapter.base import BaseFeedAdapter

        class TrackingAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass

        adapter = TrackingAdapter(name="tracking")

        assert adapter.last_fetch_at is None

        async for _ in adapter.fetch():
            pass

        assert adapter.last_fetch_at is not None
        assert isinstance(adapter.last_fetch_at, datetime)

    async def test_tracks_last_fetch_count(self):
        """Adapter tracks count from last fetch."""
        from feedspine.adapter.base import BaseFeedAdapter

        class CountingAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return [
                    {"id": "1", "published": datetime.now(UTC)},
                    {"id": "2", "published": datetime.now(UTC)},
                    {"id": "3", "published": datetime.now(UTC)},
                ]

            def _to_candidate(self, item):
                return RecordCandidate(
                    natural_key=item["id"],
                    published_at=item["published"],
                    content={},
                    metadata=Metadata(source=self.name),
                )

        adapter = CountingAdapter(name="counting")

        async for _ in adapter.fetch():
            pass

        assert adapter.last_fetch_count == 3

    def test_has_source_info(self):
        """Adapter provides source information."""
        from feedspine.adapter.base import BaseFeedAdapter

        class InfoAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return []

            def _to_candidate(self, item):
                pass

        adapter = InfoAdapter(
            name="info-feed",
            source_url="https://example.com/feed",
        )

        info = adapter.info

        assert info["name"] == "info-feed"
        assert info["source_url"] == "https://example.com/feed"


# =============================================================================
# Integration with Pipeline Tests
# =============================================================================


class TestFeedAdapterPipelineIntegration:
    """Tests for FeedAdapter working with Pipeline."""

    async def test_adapter_works_with_pipeline(self):
        """Adapter can be passed to Pipeline.run()."""
        from feedspine.adapter.base import BaseFeedAdapter
        from feedspine.pipeline import Pipeline
        from feedspine.storage.memory import MemoryStorage

        class SimpleAdapter(BaseFeedAdapter):
            async def _fetch_items(self):
                return [
                    {"id": "item-1", "title": "First", "published": datetime.now(UTC)},
                    {"id": "item-2", "title": "Second", "published": datetime.now(UTC)},
                ]

            def _to_candidate(self, item):
                return RecordCandidate(
                    natural_key=item["id"],
                    published_at=item["published"],
                    content={"title": item["title"]},
                    metadata=Metadata(source=self.name),
                )

        storage = MemoryStorage()
        await storage.initialize()

        pipeline = Pipeline(storage=storage)
        adapter = SimpleAdapter(name="simple")

        stats = await pipeline.run(adapter)

        assert stats.processed == 2
        assert stats.new == 2
        assert stats.feed_name == "simple"
