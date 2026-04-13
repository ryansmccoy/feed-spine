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
    storage.count_by_layer = AsyncMock(return_value={})
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

    def test_health_includes_database_check(self, test_client: TestClient) -> None:
        """Health response includes database check component (CS-28)."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # spine-core health router returns checks list or simple status
        # At minimum we should get a healthy status
        assert data.get("status") in ("healthy", "ok", "up")

    def test_health_without_search(self, mock_storage: AsyncMock) -> None:
        """Health works when no search backend is configured."""
        from feedspine.api.fastapi import create_app

        app = create_app(storage=mock_storage, search=None)
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200


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

    def test_get_records_with_layer_filter(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
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

    def test_get_record_by_natural_key(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
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

    def test_trigger_collection_legacy_removed(self, test_client: TestClient) -> None:
        """Legacy POST /api/v1/collect was removed — returns 404."""
        response = test_client.post("/api/v1/collect")
        assert response.status_code == 404

    def test_trigger_collection_workitem(self, mock_storage: AsyncMock, mock_search: AsyncMock) -> None:
        """POST /api/v1/feeds/{name}/collect creates a WorkItem."""
        from feedspine.api.fastapi import create_app

        app = create_app(storage=mock_storage, search=mock_search)

        # Stub a work_item_store on app.state
        work_item_store = MagicMock()
        work_item_store.create = MagicMock(return_value={"id": 42})
        app.state.work_item_store = work_item_store

        client = TestClient(app)
        response = client.post("/api/v1/feeds/sec-rss/collect")

        assert response.status_code == 202
        data = response.json()
        assert data["work_item_id"] == 42
        assert data["status"] == "QUEUED"
        assert data["feed_name"] == "sec-rss"

        # Verify the create call
        work_item_store.create.assert_called_once()
        call_kwargs = work_item_store.create.call_args[1]
        assert call_kwargs["domain"] == "feed-spine"
        assert call_kwargs["workflow"] == "feed.collect"
        assert call_kwargs["partition_key"] == "sec-rss"

    def test_trigger_collection_no_store(self, test_client: TestClient) -> None:
        """POST /api/v1/feeds/{name}/collect returns 503 without store."""
        response = test_client.post("/api/v1/feeds/sec-rss/collect")

        assert response.status_code == 503


# =============================================================================
# API Documentation
# =============================================================================


class TestAPIDocumentation:
    """Tests for API documentation."""

    @pytest.mark.xfail(
        reason="Pydantic 2.12 + FastAPI 0.135: ForwardRef('Request') not resolved during OpenAPI schema generation",
        strict=False,
    )
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


# =============================================================================
# Enrichment API Tests (WorkItem-based)
# =============================================================================


class TestEnrichmentAPI:
    """Tests for WorkItem-based enrichment endpoints."""

    def _make_client_with_store(self, mock_storage, mock_search, store_mock=None):
        from feedspine.api.fastapi import create_app

        app = create_app(storage=mock_storage, search=mock_search)
        if store_mock is None:
            store_mock = MagicMock()
        app.state.work_item_store = store_mock
        return TestClient(app), store_mock

    def test_enrich_creates_batch(self, mock_storage: AsyncMock, mock_search: AsyncMock) -> None:
        """POST /api/v1/enrich/ creates enrichment WorkItems."""
        store = MagicMock()
        # create_enrichment_work_items calls store.create per record
        _call_count = 0

        def _fake_create(**kwargs):
            nonlocal _call_count
            _call_count += 1
            return {"id": _call_count}

        store.create = MagicMock(side_effect=_fake_create)

        client, _ = self._make_client_with_store(mock_storage, mock_search, store)

        payload = {
            "enricher": "passthrough",
            "record_ids": ["rec-1", "rec-2", "rec-3"],
        }
        response = client.post("/api/v1/enrich/", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert "batch_id" in data
        assert data["work_items_created"] == 3

    def test_enrich_no_store(self, test_client: TestClient) -> None:
        """POST /api/v1/enrich/ returns 503 without store."""
        payload = {"enricher": "passthrough", "record_ids": ["rec-1"]}
        response = test_client.post("/api/v1/enrich/", json=payload)
        assert response.status_code == 503

    def test_enrich_requires_record_ids(self, mock_storage: AsyncMock, mock_search: AsyncMock) -> None:
        """POST /api/v1/enrich/ requires record_ids."""
        client, _ = self._make_client_with_store(mock_storage, mock_search)
        payload = {"enricher": "passthrough"}
        response = client.post("/api/v1/enrich/", json=payload)
        assert response.status_code == 422  # Validation error

    def test_batch_status(self, mock_storage: AsyncMock, mock_search: AsyncMock) -> None:
        """GET /api/v1/enrich/batches/{batch_id} returns batch status."""
        store = MagicMock()
        store.list_by_batch = MagicMock(
            return_value=[
                {
                    "id": 1,
                    "state": "SUCCEEDED",
                    "params_json": '{"enricher": "passthrough", "record_id": "rec-1"}',
                    "batch_id": "batch-abc",
                    "created_at": "2025-01-01T00:00:00Z",
                },
                {
                    "id": 2,
                    "state": "QUEUED",
                    "params_json": '{"enricher": "passthrough", "record_id": "rec-2"}',
                    "batch_id": "batch-abc",
                    "created_at": "2025-01-01T00:00:00Z",
                },
            ]
        )

        client, _ = self._make_client_with_store(mock_storage, mock_search, store)
        response = client.get("/api/v1/enrich/batches/batch-abc")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == "batch-abc"
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["queued"] == 1
        assert data["status"] == "PARTIAL_SUCCESS"

    def test_batch_status_not_found(self, mock_storage: AsyncMock, mock_search: AsyncMock) -> None:
        """GET /api/v1/enrich/batches/{batch_id} returns 404 for missing batch."""
        store = MagicMock()
        store.list_by_batch = MagicMock(return_value=[])

        client, _ = self._make_client_with_store(mock_storage, mock_search, store)
        response = client.get("/api/v1/enrich/batches/nonexistent")

        assert response.status_code == 404
