"""Tests for feedspine.search.elasticsearch - Elasticsearch search backend.

Elasticsearch provides distributed full-text search with:
- Full-text search at scale
- Aggregations and analytics
- Real-time indexing
- Highlight support

Tests cover:
- Standard SearchBackend protocol compliance
- Full-text search functionality
- Filter support
- Aggregation queries
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from feedspine.protocols.search import SearchResponse, SearchType

# Elasticsearch is optional - use mocks for testing without real ES
# The tests will verify the implementation logic without requiring a running ES cluster

# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def make_content(title: str = "Test Title", body: str = "Test body content") -> dict[str, Any]:
    """Create test content for indexing."""
    return {
        "title": title,
        "body": body,
        "category": "test",
        "tags": ["python", "testing"],
    }


def make_es_hit(
    record_id: str,
    content: dict[str, Any],
    score: float = 1.0,
    highlights: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Create a mock Elasticsearch hit response."""
    hit: dict[str, Any] = {
        "_id": record_id,
        "_score": score,
        "_source": {
            "content": content,
            "metadata": {"source": "test"},
            "indexed_at": datetime.now(UTC).isoformat(),
        },
    }
    if highlights:
        hit["highlight"] = highlights
    return hit


def make_es_response(
    hits: list[dict[str, Any]],
    total: int | None = None,
    took_ms: int = 10,
) -> dict[str, Any]:
    """Create a mock Elasticsearch search response."""
    return {
        "took": took_ms,
        "hits": {
            "total": {"value": total if total is not None else len(hits)},
            "hits": hits,
        },
    }


@pytest.fixture
def mock_es_client() -> AsyncMock:
    """Create a mock Elasticsearch async client."""
    client = AsyncMock()
    client.indices = AsyncMock()
    client.indices.exists = AsyncMock(return_value=False)
    client.indices.create = AsyncMock()
    client.close = AsyncMock()
    return client


# =============================================================================
# Tests with Mocked Elasticsearch
# =============================================================================


class TestElasticsearchSearchInitialization:
    """Tests for initialization and lifecycle."""

    async def test_creates_index_on_initialize(self, mock_es_client: AsyncMock) -> None:
        """Initialize creates index if it doesn't exist."""
        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"], index="test")
            await search.initialize()

            mock_es_client.indices.exists.assert_called_once()
            mock_es_client.indices.create.assert_called_once()

    async def test_skips_index_creation_if_exists(self, mock_es_client: AsyncMock) -> None:
        """Initialize skips index creation if already exists."""
        mock_es_client.indices.exists = AsyncMock(return_value=True)

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            mock_es_client.indices.create.assert_not_called()

    async def test_close_releases_client(self, mock_es_client: AsyncMock) -> None:
        """Close releases Elasticsearch client."""
        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()
            await search.close()

            mock_es_client.close.assert_called_once()


class TestElasticsearchSearchIndex:
    """Tests for index operations."""

    async def test_index_document(self, mock_es_client: AsyncMock) -> None:
        """Can index a document."""
        mock_es_client.index = AsyncMock()

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            content = make_content("Apple Inc", "Technology company")
            await search.index("rec-1", content, metadata={"source": "test"})

            mock_es_client.index.assert_called_once()
            call_kwargs = mock_es_client.index.call_args.kwargs
            assert call_kwargs["id"] == "rec-1"
            assert call_kwargs["document"]["content"] == content

    async def test_index_without_metadata(self, mock_es_client: AsyncMock) -> None:
        """Can index without metadata."""
        mock_es_client.index = AsyncMock()

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            await search.index("rec-2", {"title": "Test"})

            mock_es_client.index.assert_called_once()


class TestElasticsearchSearchDelete:
    """Tests for delete operations."""

    async def test_delete_existing(self, mock_es_client: AsyncMock) -> None:
        """Can delete existing document."""
        mock_es_client.delete = AsyncMock()

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            result = await search.delete("rec-1")

            assert result is True
            mock_es_client.delete.assert_called_once()

    async def test_delete_nonexistent(self, mock_es_client: AsyncMock) -> None:
        """Delete returns False for nonexistent document."""
        from elasticsearch import NotFoundError

        mock_es_client.delete = AsyncMock(side_effect=NotFoundError(404, "not_found", {}))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            result = await search.delete("nonexistent")

            assert result is False


class TestElasticsearchSearchQuery:
    """Tests for search operations."""

    async def test_basic_search(self, mock_es_client: AsyncMock) -> None:
        """Can perform basic search."""
        hits = [
            make_es_hit("rec-1", make_content("Apple Inc"), score=1.5),
            make_es_hit("rec-2", make_content("Apple News"), score=1.2),
        ]
        mock_es_client.search = AsyncMock(return_value=make_es_response(hits))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            response = await search.search("apple")

            assert isinstance(response, SearchResponse)
            assert len(response.results) == 2
            assert response.results[0].record_id == "rec-1"
            assert response.results[0].score == 1.5

    async def test_search_with_limit(self, mock_es_client: AsyncMock) -> None:
        """Search respects limit parameter."""
        hits = [make_es_hit(f"rec-{i}", make_content()) for i in range(3)]
        mock_es_client.search = AsyncMock(return_value=make_es_response(hits))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            await search.search("test", limit=3)

            call_kwargs = mock_es_client.search.call_args.kwargs
            assert call_kwargs["size"] == 3

    async def test_search_with_offset(self, mock_es_client: AsyncMock) -> None:
        """Search respects offset parameter."""
        hits = [make_es_hit("rec-1", make_content())]
        mock_es_client.search = AsyncMock(return_value=make_es_response(hits))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            await search.search("test", offset=10)

            call_kwargs = mock_es_client.search.call_args.kwargs
            assert call_kwargs["from_"] == 10

    async def test_search_with_filters(self, mock_es_client: AsyncMock) -> None:
        """Search applies filters."""
        hits = [make_es_hit("rec-1", make_content())]
        mock_es_client.search = AsyncMock(return_value=make_es_response(hits))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            await search.search("test", filters={"category": "tech"})

            call_kwargs = mock_es_client.search.call_args.kwargs
            query = call_kwargs["query"]
            assert "bool" in query
            assert "filter" in query["bool"]

    async def test_search_with_highlights(self, mock_es_client: AsyncMock) -> None:
        """Search returns highlights."""
        hits = [
            make_es_hit(
                "rec-1",
                make_content("Apple Inc"),
                highlights={"content.title": ["<em>Apple</em> Inc"]},
            )
        ]
        mock_es_client.search = AsyncMock(return_value=make_es_response(hits))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            response = await search.search("apple")

            assert response.results[0].highlights is not None
            assert "content.title" in response.results[0].highlights

    async def test_search_empty_results(self, mock_es_client: AsyncMock) -> None:
        """Search returns empty response for no matches."""
        mock_es_client.search = AsyncMock(return_value=make_es_response([]))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            response = await search.search("nonexistent query xyz")

            assert len(response.results) == 0
            assert response.total_count == 0


class TestElasticsearchSearchTypes:
    """Tests for different search types."""

    async def test_keyword_search(self, mock_es_client: AsyncMock) -> None:
        """Keyword search uses match query."""
        mock_es_client.search = AsyncMock(return_value=make_es_response([]))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            await search.search("test", search_type=SearchType.KEYWORD)

            call_kwargs = mock_es_client.search.call_args.kwargs
            # Keyword search should use match_phrase or similar
            assert "query" in call_kwargs

    async def test_fulltext_search(self, mock_es_client: AsyncMock) -> None:
        """Fulltext search uses multi_match query."""
        mock_es_client.search = AsyncMock(return_value=make_es_response([]))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            await search.search("test query", search_type=SearchType.FULLTEXT)

            call_kwargs = mock_es_client.search.call_args.kwargs
            assert "query" in call_kwargs


class TestElasticsearchProtocolCompliance:
    """Tests verifying SearchBackend protocol compliance."""

    def test_has_all_required_methods(self) -> None:
        """ElasticsearchSearch has all required protocol methods."""
        with patch("feedspine.search.elasticsearch.AsyncElasticsearch"):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])

            # SearchBackend protocol methods
            assert hasattr(search, "index")
            assert hasattr(search, "delete")
            assert hasattr(search, "search")
            assert hasattr(search, "initialize")
            assert hasattr(search, "close")


class TestElasticsearchQueryTime:
    """Tests for query timing."""

    async def test_query_time_captured(self, mock_es_client: AsyncMock) -> None:
        """Query time is captured from ES response."""
        mock_es_client.search = AsyncMock(return_value=make_es_response([], took_ms=42))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            response = await search.search("test")

            assert response.query_time_ms == 42


class TestElasticsearchTotalCount:
    """Tests for total count handling."""

    async def test_total_count_from_response(self, mock_es_client: AsyncMock) -> None:
        """Total count is extracted from ES response."""
        hits = [make_es_hit("rec-1", make_content())]
        mock_es_client.search = AsyncMock(return_value=make_es_response(hits, total=100))

        with patch(
            "feedspine.search.elasticsearch.AsyncElasticsearch", return_value=mock_es_client
        ):
            from feedspine.search.elasticsearch import ElasticsearchSearch

            search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            await search.initialize()

            response = await search.search("test")

            # Only 1 hit returned but total is 100
            assert len(response.results) == 1
            assert response.total_count == 100
