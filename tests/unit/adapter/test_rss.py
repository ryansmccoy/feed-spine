"""Tests for feedspine.adapter.rss - RSS/Atom feed adapter."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from feedspine.adapter.base import FeedAdapter, FeedError
from feedspine.models.record import RecordCandidate

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_rss_xml() -> str:
    """Sample RSS 2.0 feed XML."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <description>A test feed</description>
            <item>
                <title>First Article</title>
                <link>https://example.com/article/1</link>
                <guid>article-001</guid>
                <pubDate>Thu, 01 Jan 2026 12:00:00 GMT</pubDate>
                <description>First article description</description>
            </item>
            <item>
                <title>Second Article</title>
                <link>https://example.com/article/2</link>
                <guid>article-002</guid>
                <pubDate>Fri, 02 Jan 2026 12:00:00 GMT</pubDate>
                <description>Second article description</description>
            </item>
        </channel>
    </rss>"""


@pytest.fixture
def sample_atom_xml() -> str:
    """Sample Atom feed XML."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Atom Feed</title>
        <link href="https://example.com"/>
        <entry>
            <title>Atom Entry 1</title>
            <link href="https://example.com/entry/1"/>
            <id>urn:uuid:entry-001</id>
            <updated>2026-01-01T12:00:00Z</updated>
            <summary>Entry summary</summary>
        </entry>
    </feed>"""


@pytest.fixture
def sample_rss_with_namespace() -> str:
    """RSS feed with namespaces (common in SEC feeds)."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:sec="http://www.sec.gov/">
        <channel>
            <title>SEC Filings</title>
            <item>
                <title>10-K Filing</title>
                <link>https://sec.gov/filing/123</link>
                <guid>filing-123</guid>
                <pubDate>Mon, 15 Jan 2026 09:00:00 EST</pubDate>
                <sec:accessionNumber>0001234567-26-000001</sec:accessionNumber>
                <sec:cik>1234567</sec:cik>
            </item>
        </channel>
    </rss>"""


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestRSSAdapterProtocol:
    """Tests for FeedAdapter protocol compliance."""

    async def test_implements_feed_adapter_protocol(self) -> None:
        """RSSFeedAdapter implements FeedAdapter protocol."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")
        assert isinstance(adapter, FeedAdapter)

    async def test_has_required_name_property(self) -> None:
        """Adapter has name property."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="my-feed")
        assert adapter.name == "my-feed"

    async def test_has_fetch_method(self) -> None:
        """Adapter has async fetch method."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")
        assert hasattr(adapter, "fetch")
        assert callable(adapter.fetch)

    async def test_has_initialize_and_close(self) -> None:
        """Adapter has lifecycle methods."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")
        assert hasattr(adapter, "initialize")
        assert hasattr(adapter, "close")


# =============================================================================
# Creation Tests
# =============================================================================


class TestRSSAdapterCreation:
    """Tests for RSSFeedAdapter instantiation."""

    async def test_create_with_url_and_name(self) -> None:
        """Create adapter with required parameters."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="example-feed",
        )
        assert adapter.url == "https://example.com/feed.xml"
        assert adapter.name == "example-feed"

    async def test_create_with_custom_source_type(self) -> None:
        """Create adapter with custom source type for records."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="test",
            source_type="sec.rss",
        )
        assert adapter.source_type == "sec.rss"

    async def test_default_source_type_is_rss(self) -> None:
        """Default source type is 'rss'."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="test",
        )
        assert adapter.source_type == "rss"

    async def test_create_with_headers(self) -> None:
        """Create adapter with custom HTTP headers."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="test",
            headers={"User-Agent": "MyBot/1.0"},
        )
        assert adapter.headers == {"User-Agent": "MyBot/1.0"}

    async def test_create_with_timeout(self) -> None:
        """Create adapter with custom timeout."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="test",
            timeout=60.0,
        )
        assert adapter.timeout == 60.0


# =============================================================================
# Fetch Tests (with mocked HTTP)
# =============================================================================


class TestRSSAdapterFetch:
    """Tests for fetching and parsing RSS feeds."""

    async def test_fetch_parses_rss_items(self, sample_rss_xml: str) -> None:
        """Fetch returns RecordCandidates from RSS items."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="test",
        )

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            candidates = [c async for c in adapter.fetch()]

        assert len(candidates) == 2
        assert all(isinstance(c, RecordCandidate) for c in candidates)

    async def test_fetch_extracts_title(self, sample_rss_xml: str) -> None:
        """Fetch extracts title from RSS items."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].content.get("title") == "First Article"
        assert candidates[1].content.get("title") == "Second Article"

    async def test_fetch_extracts_url(self, sample_rss_xml: str) -> None:
        """Fetch extracts URL from RSS items."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].content.get("url") == "https://example.com/article/1"

    async def test_fetch_uses_guid_as_natural_key(self, sample_rss_xml: str) -> None:
        """Fetch uses guid as natural key for deduplication."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].natural_key == "article-001"
        assert candidates[1].natural_key == "article-002"

    async def test_fetch_parses_pubdate(self, sample_rss_xml: str) -> None:
        """Fetch parses pubDate into published_at."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].published_at is not None
        assert candidates[0].published_at.year == 2026
        assert candidates[0].published_at.month == 1
        assert candidates[0].published_at.day == 1

    async def test_fetch_sets_metadata_source(self, sample_rss_xml: str) -> None:
        """Fetch sets metadata source to adapter name."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="my-feed")

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].metadata.source == "my-feed"

    async def test_fetch_sets_metadata_record_type(self, sample_rss_xml: str) -> None:
        """Fetch sets metadata record_type in extra dict."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="test",
            source_type="sec.rss",
        )

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].metadata.extra.get("record_type") == "sec.rss"


# =============================================================================
# Atom Feed Tests
# =============================================================================


class TestRSSAdapterAtom:
    """Tests for Atom feed parsing."""

    async def test_fetch_parses_atom_entries(self, sample_atom_xml: str) -> None:
        """Fetch handles Atom feeds correctly."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with patch.object(adapter, "_fetch_xml", return_value=sample_atom_xml):
            candidates = [c async for c in adapter.fetch()]

        assert len(candidates) == 1
        assert candidates[0].content.get("title") == "Atom Entry 1"

    async def test_atom_uses_id_as_natural_key(self, sample_atom_xml: str) -> None:
        """Atom feed uses <id> as natural key."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with patch.object(adapter, "_fetch_xml", return_value=sample_atom_xml):
            candidates = [c async for c in adapter.fetch()]

        assert candidates[0].natural_key == "urn:uuid:entry-001"


# =============================================================================
# Namespace Handling Tests
# =============================================================================


class TestRSSAdapterNamespaces:
    """Tests for RSS feeds with namespaces."""

    async def test_extracts_namespaced_elements(self, sample_rss_with_namespace: str) -> None:
        """Fetch extracts elements with namespaces."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="sec-feed",
            namespace_map={"sec": "http://www.sec.gov/"},
        )

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_with_namespace):
            candidates = [c async for c in adapter.fetch()]

        # Namespaced elements should be accessible in content
        assert len(candidates) == 1


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestRSSAdapterErrors:
    """Tests for error handling."""

    async def test_network_error_raises_feed_error(self) -> None:
        """Network errors are wrapped in FeedError."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with (
            patch.object(
                adapter,
                "_fetch_xml",
                side_effect=ConnectionError("Failed to connect"),
            ),
            pytest.raises(FeedError) as exc_info,
        ):
            _ = [c async for c in adapter.fetch()]

        assert exc_info.value.source == "test"
        assert exc_info.value.cause is not None

    async def test_invalid_xml_raises_feed_error(self) -> None:
        """Invalid XML raises FeedError."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with (
            patch.object(adapter, "_fetch_xml", return_value="<not valid xml"),
            pytest.raises(FeedError) as exc_info,
        ):
            _ = [c async for c in adapter.fetch()]

        assert "parse" in str(exc_info.value).lower() or exc_info.value.cause is not None

    async def test_empty_feed_returns_no_candidates(self) -> None:
        """Empty feed returns empty iterator, not error."""
        from feedspine.adapter.rss import RSSFeedAdapter

        empty_feed = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Empty Feed</title>
            </channel>
        </rss>"""

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with patch.object(adapter, "_fetch_xml", return_value=empty_feed):
            candidates = [c async for c in adapter.fetch()]

        assert candidates == []


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestRSSAdapterLifecycle:
    """Tests for adapter lifecycle management."""

    async def test_initialize_is_idempotent(self) -> None:
        """Multiple initialize calls are safe."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")
        await adapter.initialize()
        await adapter.initialize()  # Should not raise

    async def test_close_is_idempotent(self) -> None:
        """Multiple close calls are safe."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")
        await adapter.initialize()
        await adapter.close()
        await adapter.close()  # Should not raise

    async def test_context_manager_support(self) -> None:
        """Adapter works as async context manager."""
        from feedspine.adapter.rss import RSSFeedAdapter

        async with RSSFeedAdapter(url="https://example.com/feed.xml", name="test") as adapter:
            assert adapter.name == "test"


# =============================================================================
# Metadata Tracking Tests
# =============================================================================


class TestRSSAdapterMetadata:
    """Tests for adapter metadata tracking."""

    async def test_tracks_last_fetch_time(self, sample_rss_xml: str) -> None:
        """Adapter tracks when last fetch occurred."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")
        assert adapter.last_fetch_at is None

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            _ = [c async for c in adapter.fetch()]

        assert adapter.last_fetch_at is not None

    async def test_tracks_last_fetch_count(self, sample_rss_xml: str) -> None:
        """Adapter tracks number of items from last fetch."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            _ = [c async for c in adapter.fetch()]

        assert adapter.last_fetch_count == 2

    async def test_info_returns_adapter_info(self) -> None:
        """info() returns adapter metadata."""
        from feedspine.adapter.rss import RSSFeedAdapter

        adapter = RSSFeedAdapter(
            url="https://example.com/feed.xml",
            name="test-feed",
            source_type="custom.rss",
        )
        info = adapter.info

        assert info["name"] == "test-feed"
        assert info["url"] == "https://example.com/feed.xml"
        assert info["source_type"] == "custom.rss"


# =============================================================================
# Pipeline Integration Test
# =============================================================================


class TestRSSAdapterPipelineIntegration:
    """Tests for integration with Pipeline."""

    async def test_works_with_pipeline(self, sample_rss_xml: str) -> None:
        """RSSFeedAdapter works with Pipeline.run()."""
        from feedspine.adapter.rss import RSSFeedAdapter
        from feedspine.pipeline import Pipeline
        from feedspine.storage.memory import MemoryStorage

        storage = MemoryStorage()
        await storage.initialize()

        adapter = RSSFeedAdapter(url="https://example.com/feed.xml", name="test")
        pipeline = Pipeline(storage=storage)

        with patch.object(adapter, "_fetch_xml", return_value=sample_rss_xml):
            stats = await pipeline.run(adapter)

        assert stats.processed == 2
        assert stats.new == 2
        assert await storage.count() == 2
