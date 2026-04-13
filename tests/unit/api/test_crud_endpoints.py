"""Tests for CRUD endpoints — records, sightings, observations.

Covers the write operations (POST/PATCH/PUT/DELETE) added by #1805.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate

fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")
from fastapi.testclient import TestClient  # noqa: E402

# =============================================================================
# Helpers
# =============================================================================


def make_record(key: str = "test-key", layer: Layer = Layer.BRONZE) -> Record:
    candidate = RecordCandidate(
        natural_key=key,
        published_at=datetime.now(UTC),
        content={"title": f"Title for {key}"},
        metadata=Metadata(source="test"),
    )
    record = Record.from_candidate(candidate, record_id=str(uuid4()))
    if layer != Layer.BRONZE:
        record = record.model_copy(update={"layer": layer})
    return record


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.initialize = AsyncMock()
    storage.close = AsyncMock()
    storage.get = AsyncMock(return_value=None)
    storage.get_by_natural_key = AsyncMock(return_value=None)
    storage.store = AsyncMock()
    storage.delete = AsyncMock(return_value=True)
    storage.count = AsyncMock(return_value=0)
    storage.count_by_layer = AsyncMock(return_value={})
    storage.record_sighting = AsyncMock(return_value=True)
    storage.get_sightings = AsyncMock(return_value=[])
    return storage


@pytest.fixture
def test_client(mock_storage: AsyncMock) -> TestClient:
    from feedspine.api.fastapi import create_app

    app = create_app(storage=mock_storage, search=None)
    return TestClient(app)


# =============================================================================
# Records CRUD
# =============================================================================


class TestRecordCreate:
    """POST /api/v1/records"""

    def test_create_record(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Creates a record and returns 201."""
        response = test_client.post(
            "/api/v1/records",
            json={
                "natural_key": "new-item",
                "content": {"title": "Hello"},
                "source": "test-api",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["natural_key"] == "new-item"
        assert data["content"]["title"] == "Hello"
        assert data["layer"] == "bronze"
        mock_storage.store.assert_called_once()

    def test_create_record_gold_layer(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Can create a record at a specific layer."""
        response = test_client.post(
            "/api/v1/records",
            json={
                "natural_key": "gold-item",
                "layer": "gold",
                "content": {"value": 42},
                "source": "enrichment",
            },
        )

        assert response.status_code == 201
        assert response.json()["layer"] == "gold"

    def test_create_record_duplicate_key(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Returns 409 when natural_key already exists."""
        existing = make_record("dup-key")
        mock_storage.get_by_natural_key = AsyncMock(return_value=existing)

        response = test_client.post(
            "/api/v1/records",
            json={"natural_key": "dup-key", "content": {}, "source": "test"},
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


class TestRecordUpdate:
    """PATCH /api/v1/records/{record_id}"""

    def test_update_content(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """PATCH merges content and bumps version."""
        existing = make_record("item-1")
        mock_storage.get = AsyncMock(return_value=existing)

        response = test_client.patch(
            f"/api/v1/records/{existing.id}",
            json={"content": {"new_field": "value"}},
        )

        assert response.status_code == 200
        data = response.json()
        # Original content merged with new field
        assert data["content"]["title"] == "Title for item-1"
        assert data["content"]["new_field"] == "value"
        assert data["version"] == existing.version + 1

    def test_update_layer(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """PATCH can promote to a different layer."""
        existing = make_record("item-2")
        mock_storage.get = AsyncMock(return_value=existing)

        response = test_client.patch(
            f"/api/v1/records/{existing.id}",
            json={"layer": "silver"},
        )

        assert response.status_code == 200
        assert response.json()["layer"] == "silver"

    def test_update_not_found(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """PATCH returns 404 for nonexistent record."""
        response = test_client.patch(
            "/api/v1/records/nonexistent",
            json={"content": {"x": 1}},
        )

        assert response.status_code == 404


class TestRecordDelete:
    """DELETE /api/v1/records/{record_id}"""

    def test_delete_record(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """DELETE removes the record and returns 204."""
        existing = make_record("del-item")
        mock_storage.get = AsyncMock(return_value=existing)

        response = test_client.delete(f"/api/v1/records/{existing.id}")

        assert response.status_code == 204
        mock_storage.delete.assert_called_once_with(existing.id)

    def test_delete_not_found(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """DELETE returns 404 for nonexistent record."""
        response = test_client.delete("/api/v1/records/nonexistent")

        assert response.status_code == 404


# =============================================================================
# Sightings CRUD
# =============================================================================


class TestSightingCreate:
    """POST /api/v1/sightings"""

    def test_create_sighting(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Creates a sighting and returns 201."""
        mock_storage.record_sighting = AsyncMock(return_value=True)

        response = test_client.post(
            "/api/v1/sightings",
            json={"natural_key": "article-1", "source": "rss-feed"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["natural_key"] == "article-1"
        assert data["source"] == "rss-feed"
        assert data["is_new"] is True
        mock_storage.record_sighting.assert_called_once()

    def test_create_sighting_duplicate(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """Duplicate sighting returns is_new=False."""
        mock_storage.record_sighting = AsyncMock(return_value=False)

        response = test_client.post(
            "/api/v1/sightings",
            json={"natural_key": "seen-before", "source": "feed-2"},
        )

        assert response.status_code == 201
        assert response.json()["is_new"] is False


class TestSightingDelete:
    """DELETE /api/v1/sightings/{sighting_id}"""

    def test_delete_sighting(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """DELETE removes sighting and returns 204."""
        mock_storage.delete_sighting = AsyncMock(return_value=True)

        response = test_client.delete("/api/v1/sightings/sight-abc123")

        assert response.status_code == 204
        mock_storage.delete_sighting.assert_called_once_with("sight-abc123")

    def test_delete_sighting_not_found(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """DELETE returns 404 when sighting doesn't exist."""
        mock_storage.delete_sighting = AsyncMock(return_value=False)

        response = test_client.delete("/api/v1/sightings/nonexistent")

        assert response.status_code == 404

    def test_delete_sighting_unsupported(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """DELETE returns 501 when storage doesn't support delete."""
        # Remove the delete_sighting attr so hasattr returns False
        if hasattr(mock_storage, "delete_sighting"):
            del mock_storage.delete_sighting

        response = test_client.delete("/api/v1/sightings/sight-abc")

        assert response.status_code == 501


# =============================================================================
# Observations CRUD
# =============================================================================


def _obs_storage(mock_storage: AsyncMock) -> AsyncMock:
    """Configure mock_storage to support observation ops."""
    mock_storage.store_observation = AsyncMock()
    mock_storage.list_observations = AsyncMock(return_value=[])
    mock_storage.get_observation = AsyncMock(return_value=None)
    mock_storage.count_observations = AsyncMock(return_value=0)
    mock_storage.delete_observation = AsyncMock(return_value=True)
    return mock_storage


class TestObservationUpdate:
    """PUT /api/v1/observations/{observation_id}"""

    def test_update_observation(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """PUT updates observation fields."""
        _obs_storage(mock_storage)
        existing_row = {
            "id": "obs-1",
            "observation_type": "earning",
            "source": "sec-edgar",
            "created_at": datetime.now(UTC),
            "fingerprint": "fp-1",
            "data": {"eps": 1.5},
            "metadata": {},
        }
        mock_storage.get_observation = AsyncMock(return_value=existing_row)

        response = test_client.put(
            "/api/v1/observations/obs-1",
            json={"data": {"eps": 2.0, "revenue": 100}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["eps"] == 2.0
        assert data["data"]["revenue"] == 100
        mock_storage.store_observation.assert_called_once()

    def test_update_observation_not_found(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """PUT returns 404 for nonexistent observation."""
        _obs_storage(mock_storage)

        response = test_client.put(
            "/api/v1/observations/nonexistent",
            json={"data": {"x": 1}},
        )

        assert response.status_code == 404

    def test_update_observation_no_support(self, mock_storage: AsyncMock) -> None:
        """PUT returns 501 when storage doesn't support observations."""
        from feedspine.api.fastapi import create_app

        # Create a storage that explicitly lacks observation methods
        bare = AsyncMock(spec=["initialize", "close", "get", "store", "count", "count_by_layer"])
        bare.initialize = AsyncMock()
        bare.close = AsyncMock()
        bare.count = AsyncMock(return_value=0)
        bare.count_by_layer = AsyncMock(return_value={})
        app = create_app(storage=bare, search=None)
        client = TestClient(app)

        response = client.put(
            "/api/v1/observations/obs-1",
            json={"data": {"x": 1}},
        )

        assert response.status_code == 501


class TestObservationDelete:
    """DELETE /api/v1/observations/{observation_id}"""

    def test_delete_observation(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """DELETE removes observation and returns 204."""
        _obs_storage(mock_storage)
        existing_row = {
            "id": "obs-del",
            "observation_type": "alert",
            "source": "monitor",
            "created_at": datetime.now(UTC),
            "fingerprint": "fp-del",
            "data": {},
            "metadata": {},
        }
        mock_storage.get_observation = AsyncMock(return_value=existing_row)

        response = test_client.delete("/api/v1/observations/obs-del")

        assert response.status_code == 204
        mock_storage.delete_observation.assert_called_once_with("obs-del")

    def test_delete_observation_not_found(self, test_client: TestClient, mock_storage: AsyncMock) -> None:
        """DELETE returns 404 for nonexistent observation."""
        _obs_storage(mock_storage)

        response = test_client.delete("/api/v1/observations/nonexistent")

        assert response.status_code == 404

    def test_delete_observation_unsupported(self, mock_storage: AsyncMock) -> None:
        """DELETE returns 501 when delete_observation not available."""
        from feedspine.api.fastapi import create_app

        # Create a storage that has observation read/write but NO delete
        bare = AsyncMock(
            spec=[
                "initialize",
                "close",
                "get",
                "store",
                "count",
                "count_by_layer",
                "store_observation",
                "list_observations",
                "get_observation",
                "count_observations",
            ]
        )
        bare.initialize = AsyncMock()
        bare.close = AsyncMock()
        bare.count = AsyncMock(return_value=0)
        bare.count_by_layer = AsyncMock(return_value={})
        bare.store_observation = AsyncMock()
        bare.list_observations = AsyncMock(return_value=[])
        bare.get_observation = AsyncMock(
            return_value={
                "id": "obs-1",
                "observation_type": "x",
                "source": "y",
                "created_at": datetime.now(UTC),
                "fingerprint": "f",
                "data": {},
                "metadata": {},
            }
        )
        bare.count_observations = AsyncMock(return_value=0)
        app = create_app(storage=bare, search=None)
        client = TestClient(app)

        response = client.delete("/api/v1/observations/obs-1")

        assert response.status_code == 501
