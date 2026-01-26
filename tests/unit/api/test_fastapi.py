"""Tests for feedspine.api.fastapi - FastAPI integration.

FastAPI provides a modern REST API for FeedSpine with:
- Type-safe endpoints with Pydantic
- Automatic OpenAPI documentation
- Background task support for collection
- WebSocket support for streaming

Tests cover:
- App factory and lifecycle
- CRUD endpoints for records
- Search endpoints
- Collection trigger endpoint
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate

# FastAPI is optional - check if available
fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")
from fastapi.testclient import TestClient  # noqa: E402

# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def make_candidate(key: str = "test-key") -> RecordCandidate:
    """Create a test candidate with default values."""
    return RecordCandidate(
        natural_key=key,
        published_at=datetime.now(UTC),
        content={"title": f"Title for {key}"},
        metadata=Metadata(source="test"),
    )


def make_record(key: str = "test-key", layer: Layer = Layer.BRONZE) -> Record:
    """Create a test record with default values."""
    candidate = make_candidate(key)
    record = Record.from_candidate(candidate, record_id=str(uuid4()))
    if layer != Layer.BRONZE:
        record = record.model_copy(update={"layer": layer})
    return record


@pytest.fixture
def mock_storage() -> AsyncMock:
    """Create a mock storage backend."""
    storage = AsyncMock()
    storage.initialize = AsyncMock()
    storage.close = AsyncMock()
    storage.get = AsyncMock(return_value=None)
    storage.get_by_natural_key = AsyncMock(return_value=None)
    storage.count = AsyncMock(return_value=0)
    return storage


@pytest.fixture
def mock_search() -> AsyncMock:
    """Create a mock search backend."""
    from feedspine.protocols.search import SearchResponse

    search = AsyncMock()
    search.initialize = AsyncMock()
    search.close = AsyncMock()
    search.search = AsyncMock(return_value=SearchResponse())
    return search


@pytest.fixture
def test_client(mock_storage: AsyncMock, mock_search: AsyncMock) -> TestClient:
    """Create test client with mocked backends."""
    from feedspine.api.fastapi import create_app

    app = create_app(storage=mock_storage, search=mock_search)
    return TestClient(app)


# =============================================================================
# App Factory Tests
# =============================================================================


class TestAppFactory:
    """Tests for app factory function."""

    def test_creates_app(self, mock_storage: AsyncMock, mock_search: AsyncMock) -> None:
        """create_app returns a FastAPI application."""
        from feedspine.api.fastapi import create_app

        app = create_app(storage=mock_storage, search=mock_search)

        assert app is not None
        assert hasattr(app, "routes")

    def test_app_has_title(self, mock_storage: AsyncMock, mock_search: AsyncMock) -> None:
        """App has proper title."""
        from feedspine.api.fastapi import create_app

        app = create_app(storage=mock_storage, search=mock_search)

        assert app.title == "FeedSpine API"

    def test_custom_title(self, mock_storage: AsyncMock, mock_search: AsyncMock) -> None:
        """Can customize app title."""
        from feedspine.api.fastapi import create_app

        app = create_app(
            storage=mock_storage,
            search=mock_search,
            title="Custom API",
        )

        assert app.title == "Custom API"


# =============================================================================
# Health and Info Endpoints
# =============================================================================


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, test_client: TestClient) -> None:
        """Health check endpoint returns ok."""
        response = test_client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_returns_api_info(self, test_client: TestClient) -> None:
        """Root endpoint returns API info."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


# =============================================================================
# Records Endpoints
# =============================================================================


class TestRecordsEndpoints:
    """Tests for record CRUD endpoints."""

    def test_get_records_empty(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Get records returns empty list when no records."""

        async def empty_query(*args: Any, **kwargs: Any):
            return
            yield  # Empty async generator

        mock_storage.query = MagicMock(return_value=empty_query())

        response = test_client.get("/api/v1/records")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_records_with_layer_filter(
        self, test_client: TestClient, mock_storage: AsyncMock
    ) -> None:
        """Get records respects layer filter."""

        async def empty_query(*args: Any, **kwargs: Any):
            return
            yield

        mock_storage.query = MagicMock(return_value=empty_query())

        response = test_client.get("/api/v1/records?layer=gold")

        assert response.status_code == 200
        # Verify query was called with layer filter
        mock_storage.query.assert_called_once()

    def test_get_record_by_id(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Can get record by ID."""
        record = make_record("test-record", Layer.GOLD)
        mock_storage.get = AsyncMock(return_value=record)

        response = test_client.get(f"/api/v1/records/{record.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == record.id
        assert data["natural_key"] == record.natural_key

    def test_get_record_not_found(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Returns 404 for nonexistent record."""
        mock_storage.get = AsyncMock(return_value=None)

        response = test_client.get("/api/v1/records/nonexistent")

        assert response.status_code == 404

    def test_get_record_by_natural_key(
        self, test_client: TestClient, mock_storage: AsyncMock
    ) -> None:
        """Can get record by natural key."""
        record = make_record("unique-key")
        mock_storage.get_by_natural_key = AsyncMock(return_value=record)

        response = test_client.get("/api/v1/records/by-key/unique-key")

        assert response.status_code == 200
        data = response.json()
        assert data["natural_key"] == "unique-key"


# =============================================================================
# Search Endpoints
# =============================================================================


class TestSearchEndpoints:
    """Tests for search endpoints."""

    def test_search_basic(self, test_client: TestClient, mock_search: AsyncMock) -> None:
        """Can perform basic search."""
        from feedspine.protocols.search import SearchResponse, SearchResult

        mock_search.search = AsyncMock(
            return_value=SearchResponse(
                results=[SearchResult(record_id="rec-1", score=0.9)],
                total_count=1,
                query_time_ms=10,
            )
        )

        response = test_client.get("/api/v1/search?q=test")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["results"]) == 1

    def test_search_requires_query(self, test_client: TestClient) -> None:
        """Search requires query parameter."""
        response = test_client.get("/api/v1/search")

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    def test_search_with_limit(self, test_client: TestClient, mock_search: AsyncMock) -> None:
        """Search respects limit parameter."""
        from feedspine.protocols.search import SearchResponse

        mock_search.search = AsyncMock(return_value=SearchResponse())

        response = test_client.get("/api/v1/search?q=test&limit=5")

        assert response.status_code == 200
        mock_search.search.assert_called_once()
        _, kwargs = mock_search.search.call_args
        assert kwargs.get("limit") == 5


# =============================================================================
# Statistics Endpoints
# =============================================================================


class TestStatsEndpoints:
    """Tests for statistics endpoints."""

    def test_get_stats(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Can get storage statistics."""
        mock_storage.count = AsyncMock(return_value=100)

        response = test_client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_records" in data


# =============================================================================
# Collection Endpoints
# =============================================================================


class TestCollectionEndpoints:
    """Tests for collection trigger endpoints."""

    def test_trigger_collection(self, test_client: TestClient) -> None:
        """Can trigger collection (starts background task)."""
        response = test_client.post("/api/v1/collect")

        assert response.status_code == 202
        assert response.json()["status"] == "collection_started"


# =============================================================================
# API Documentation
# =============================================================================


class TestAPIDocumentation:
    """Tests for API documentation."""

    def test_openapi_available(self, test_client: TestClient) -> None:
        """OpenAPI schema is available."""
        response = test_client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_available(self, test_client: TestClient) -> None:
        """Swagger docs are available."""
        response = test_client.get("/docs")

        assert response.status_code == 200
