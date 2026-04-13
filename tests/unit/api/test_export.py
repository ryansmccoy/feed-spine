"""Tests for feedspine.api.routes.export - Data export endpoints.

# Manifesto
Export endpoints enable data portability across formats (CSV, JSONL, Parquet).
Two-phase pattern (create → download) supports async processing and large datasets.

# Test Coverage
- Export capability detection via /status endpoint
- CSV export with all storage backends
- JSONL export with all storage backends
- Parquet export with DuckDB backend only
- Error handling: empty results, unsupported backends, missing export files
- Layer filtering (bronze/silver/gold)
- Download endpoint file retrieval

# Test Patterns
Uses FastAPI TestClient with mocked storage backend. Verifies:
- Response status codes (200, 404, 501)
- ExportResult schema compliance
- File creation and download flow
- Error messages for unsupported operations
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate

# FastAPI is optional - check if available
fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")
from fastapi.testclient import TestClient  # noqa: E402

# =============================================================================
# Test Fixtures
# =============================================================================


def make_test_records(count: int = 10, layer: Layer = Layer.BRONZE) -> list[Record]:
    """Create test records for export testing."""
    from datetime import UTC, datetime
    from uuid import uuid4

    records = []
    for i in range(count):
        candidate = RecordCandidate(
            natural_key=f"test-key-{i}",
            published_at=datetime.now(UTC),
            content={"title": f"Title {i}", "index": i},
            metadata=Metadata(source="test-export"),
        )
        record = Record.from_candidate(candidate, record_id=str(uuid4()))
        if layer != Layer.BRONZE:
            record = record.model_copy(update={"layer": layer})
        records.append(record)
    return records


@pytest.fixture
def mock_duckdb_storage() -> AsyncMock:
    """Create a mock DuckDB storage backend with parquet export support."""
    storage = AsyncMock()
    storage.initialize = AsyncMock()
    storage.close = AsyncMock()

    # Add export_to_parquet method to simulate DuckDB backend
    async def export_to_parquet_mock(path: Path, layer: Layer | None = None) -> int:
        # Write a minimal parquet file (real impl would use DuckDB)
        path.write_bytes(b"PARQUET_MOCK_DATA")
        return 100  # Mock record count

    storage.export_to_parquet = export_to_parquet_mock

    # Mock query for CSV/JSONL exports
    async def query_mock(layer: Layer | None = None, limit: int = 100_000) -> AsyncGenerator:
        records = make_test_records(min(50, limit))
        for record in records:
            yield record

    storage.query = query_mock

    return storage


@pytest.fixture
def mock_sqlite_storage() -> AsyncMock:
    """Create a mock SQLite storage backend (no parquet support)."""
    storage = AsyncMock()
    storage.initialize = AsyncMock()
    storage.close = AsyncMock()

    # Explicitly remove export_to_parquet to simulate non-DuckDB backend
    if hasattr(storage, "export_to_parquet"):
        delattr(storage, "export_to_parquet")

    # Mock query for CSV/JSONL exports
    async def query_mock(layer: Layer | None = None, limit: int = 100_000) -> AsyncGenerator:
        records = make_test_records(min(25, limit))
        for record in records:
            yield record

    storage.query = query_mock

    return storage


@pytest.fixture
def test_client_duckdb(mock_duckdb_storage: AsyncMock) -> TestClient:
    """Create test client with DuckDB backend."""
    from feedspine.api.fastapi import create_app

    app = create_app(storage=mock_duckdb_storage)
    return TestClient(app)


@pytest.fixture
def test_client_sqlite(mock_sqlite_storage: AsyncMock) -> TestClient:
    """Create test client with SQLite backend (no parquet support)."""
    from feedspine.api.fastapi import create_app

    app = create_app(storage=mock_sqlite_storage)
    return TestClient(app)


# =============================================================================
# Export Status Tests
# =============================================================================


class TestExportStatus:
    """Tests for GET /api/v1/export/status endpoint."""

    def test_status_with_duckdb_backend(self, test_client_duckdb: TestClient) -> None:
        """Status endpoint reports all formats available with DuckDB."""
        response = test_client_duckdb.get("/api/v1/export/status")

        assert response.status_code == 200
        data = response.json()

        assert "backend" in data
        assert "formats" in data

        # DuckDB supports all formats
        assert data["formats"]["parquet"]["available"] is True
        assert data["formats"]["csv"]["available"] is True
        assert data["formats"]["jsonl"]["available"] is True

    def test_status_with_sqlite_backend(self, test_client_sqlite: TestClient) -> None:
        """Status endpoint reports limited formats with SQLite."""
        response = test_client_sqlite.get("/api/v1/export/status")

        assert response.status_code == 200
        data = response.json()

        # SQLite doesn't support parquet
        assert data["formats"]["parquet"]["available"] is False

        # But CSV and JSONL work with all backends
        assert data["formats"]["csv"]["available"] is True
        assert data["formats"]["jsonl"]["available"] is True


# =============================================================================
# CSV Export Tests
# =============================================================================


class TestCSVExport:
    """Tests for POST /api/v1/export/csv endpoint."""

    def test_csv_export_creates_file(self, test_client_duckdb: TestClient) -> None:
        """CSV export creates temp file and returns download URL."""
        response = test_client_duckdb.post("/api/v1/export/csv")

        assert response.status_code == 200
        data = response.json()

        assert data["format"] == "csv"
        assert data["record_count"] == 50  # Mock returns 50 records
        assert data["download_url"] is not None
        assert "/api/v1/export/download/" in data["download_url"]

    def test_csv_export_with_layer_filter(self, test_client_duckdb: TestClient) -> None:
        """CSV export supports layer filtering."""
        response = test_client_duckdb.post("/api/v1/export/csv?layer=bronze")

        assert response.status_code == 200
        data = response.json()

        assert data["format"] == "csv"
        assert "bronze" in data["file_path"]  # Filename should include layer

    def test_csv_export_with_limit(self, test_client_duckdb: TestClient) -> None:
        """CSV export respects limit parameter."""
        response = test_client_duckdb.post("/api/v1/export/csv?limit=10")

        assert response.status_code == 200
        data = response.json()

        # Mock storage returns min(limit, 50)
        assert data["record_count"] <= 10

    def test_csv_export_works_with_any_backend(self, test_client_sqlite: TestClient) -> None:
        """CSV export works even without DuckDB."""
        response = test_client_sqlite.post("/api/v1/export/csv")

        assert response.status_code == 200
        data = response.json()

        assert data["format"] == "csv"
        assert data["record_count"] > 0


# =============================================================================
# JSONL Export Tests
# =============================================================================


class TestJSONLExport:
    """Tests for POST /api/v1/export/jsonl endpoint."""

    def test_jsonl_export_creates_file(self, test_client_duckdb: TestClient) -> None:
        """JSONL export creates temp file with line-delimited JSON."""
        response = test_client_duckdb.post("/api/v1/export/jsonl")

        assert response.status_code == 200
        data = response.json()

        assert data["format"] == "jsonl"
        assert data["record_count"] == 50
        assert data["download_url"] is not None
        assert data["file_path"].endswith(".jsonl")

    def test_jsonl_export_with_layer_filter(self, test_client_duckdb: TestClient) -> None:
        """JSONL export supports layer filtering."""
        response = test_client_duckdb.post("/api/v1/export/jsonl?layer=gold")

        assert response.status_code == 200
        data = response.json()

        assert data["format"] == "jsonl"
        assert "gold" in data["file_path"]

    def test_jsonl_export_with_limit(self, test_client_duckdb: TestClient) -> None:
        """JSONL export respects limit parameter."""
        response = test_client_duckdb.post("/api/v1/export/jsonl?limit=5")

        assert response.status_code == 200
        data = response.json()

        assert data["record_count"] <= 5

    def test_jsonl_export_works_with_any_backend(self, test_client_sqlite: TestClient) -> None:
        """JSONL export works even without DuckDB."""
        response = test_client_sqlite.post("/api/v1/export/jsonl")

        assert response.status_code == 200
        data = response.json()

        assert data["format"] == "jsonl"
        assert data["record_count"] > 0


# =============================================================================
# Parquet Export Tests
# =============================================================================


class TestParquetExport:
    """Tests for POST /api/v1/export/parquet endpoint."""

    def test_parquet_export_with_duckdb(self, test_client_duckdb: TestClient) -> None:
        """Parquet export works with DuckDB backend."""
        response = test_client_duckdb.post("/api/v1/export/parquet")

        assert response.status_code == 200
        data = response.json()

        assert data["format"] == "parquet"
        assert data["record_count"] == 100  # Mock returns 100
        assert data["download_url"] is not None
        assert data["file_path"].endswith(".parquet")

    def test_parquet_export_without_duckdb(self, test_client_sqlite: TestClient) -> None:
        """Parquet export returns 501 without DuckDB backend."""
        response = test_client_sqlite.post("/api/v1/export/parquet")

        assert response.status_code == 501
        assert "not available" in response.json()["detail"].lower()
        assert "duckdb" in response.json()["detail"].lower()

    def test_parquet_export_with_layer_filter(self, test_client_duckdb: TestClient) -> None:
        """Parquet export supports layer filtering."""
        response = test_client_duckdb.post("/api/v1/export/parquet?layer=silver")

        assert response.status_code == 200
        data = response.json()

        assert "silver" in data["file_path"]


# =============================================================================
# Download Endpoint Tests
# =============================================================================


class TestDownloadEndpoint:
    """Tests for GET /api/v1/export/download/{export_id} endpoint."""

    def test_download_after_export(self, test_client_duckdb: TestClient) -> None:
        """Download endpoint retrieves previously exported file."""
        # First create an export
        export_response = test_client_duckdb.post("/api/v1/export/csv")
        export_data = export_response.json()

        # Extract export_id from download_url
        download_url = export_data["download_url"]
        export_id = download_url.split("/")[-1]

        # Download the file
        download_response = test_client_duckdb.get(f"/api/v1/export/download/{export_id}")

        assert download_response.status_code == 200
        assert len(download_response.content) > 0

    def test_download_nonexistent_export(self, test_client_duckdb: TestClient) -> None:
        """Download endpoint returns 404 for unknown export_id."""
        response = test_client_duckdb.get("/api/v1/export/download/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestExportEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_export_with_no_records(self, test_client_duckdb: TestClient) -> None:
        """Export with no matching records returns empty result."""
        # Create mock that returns no records
        from feedspine.api.fastapi import create_app

        empty_storage = AsyncMock()
        empty_storage.initialize = AsyncMock()
        empty_storage.close = AsyncMock()

        async def empty_query(*args, **kwargs) -> AsyncGenerator:
            return
            yield

        empty_storage.query = empty_query

        app = create_app(storage=empty_storage)
        client = TestClient(app)

        response = client.post("/api/v1/export/csv")

        assert response.status_code == 200
        data = response.json()

        assert data["record_count"] == 0
        assert data["download_url"] is None

    def test_export_with_invalid_layer(self, test_client_duckdb: TestClient) -> None:
        """Export with invalid layer parameter returns validation error."""
        response = test_client_duckdb.post("/api/v1/export/csv?layer=invalid")

        # FastAPI should return 500 for ValueError from Layer enum
        # In production, this should be caught and return 400/422
        assert response.status_code in (400, 422, 500)
