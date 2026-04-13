"""Tests for feedspine.integration.capture_spine - Capture-spine client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from feedspine.integration.capture_spine import (
    CaptureSpineClient,
    IngestResult,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_ingest_kwargs() -> dict:
    """Sample kwargs for CaptureSpineClient.ingest()."""
    return {
        "content_type": "sec_filing",
        "source_type": "sec_edgar",
        "source_id": "0000320193-25-000106",
        "content": {
            "title": "AAPL 10-K Annual Report",
            "body": "Full filing text here...",
            "format": "html",
        },
        "fingerprint": "sec:0000320193:10-K:2025-11-01",
        "source_metadata": {"cik": "0000320193"},
        "metadata": {"form_type": "10-K"},
    }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient."""
    with patch("feedspine.integration.capture_spine.httpx") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.AsyncClient.return_value = mock_client
        yield mock_client


# =============================================================================
# IngestResult Tests
# =============================================================================


class TestIngestResult:
    """Tests for IngestResult dataclass."""

    def test_from_response_accepted(self) -> None:
        """Should parse accepted response."""
        data = {
            "status": "accepted",
            "record_id": "uuid-123",
            "sighting_id": "sighting-456",
            "is_new": True,
            "processing": {"task_id": "celery-789"},
        }
        result = IngestResult.from_response(data)

        assert result.status == "accepted"
        assert result.record_id == "uuid-123"
        assert result.sighting_id == "sighting-456"
        assert result.is_new is True
        assert result.task_id == "celery-789"

    def test_from_response_duplicate(self) -> None:
        """Should parse duplicate response."""
        data = {
            "status": "duplicate",
            "record_id": "existing-uuid",
            "is_new": False,
            "deduplication": {"matched_record": "existing-uuid"},
        }
        result = IngestResult.from_response(data)

        assert result.status == "duplicate"
        assert result.is_new is False

    def test_failure_factory(self) -> None:
        """Should create failure result."""
        result = IngestResult.failure("Connection refused")

        assert result.status == "failed"
        assert result.error == "Connection refused"
        assert result.record_id is None


# =============================================================================
# CaptureSpineClient Tests
# =============================================================================


class TestCaptureSpineClient:
    """Tests for CaptureSpineClient."""

    def test_init_default_values(self) -> None:
        """Should initialize with default values."""
        client = CaptureSpineClient()

        assert client.base_url == "http://localhost:8000"
        assert client.api_key is None
        assert client.timeout == 30.0

    def test_init_custom_values(self) -> None:
        """Should accept custom configuration."""
        client = CaptureSpineClient(
            base_url="http://api.example.com",
            api_key="secret-key",
            timeout=60.0,
        )

        assert client.base_url == "http://api.example.com"
        assert client.api_key == "secret-key"
        assert client.timeout == 60.0

    def test_init_strips_trailing_slash(self) -> None:
        """Should strip trailing slash from base_url."""
        client = CaptureSpineClient(base_url="http://localhost:8000/")

        assert client.base_url == "http://localhost:8000"


class TestCaptureSpineClientIngest:
    """Tests for CaptureSpineClient.ingest() method."""

    @pytest.mark.asyncio
    async def test_ingest_builds_correct_payload(
        self,
        sample_ingest_kwargs: dict,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Should build correct payload for generic ingestion."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "status": "accepted",
            "record_id": "new-record",
            "is_new": True,
        }
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        client = CaptureSpineClient()
        client._client = mock_httpx_client

        result = await client.ingest(**sample_ingest_kwargs)

        # Verify POST was called
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args

        # Check endpoint
        assert call_args[0][0] == "/api/v1/ingest"

        # Check payload structure
        payload = call_args[1]["json"]
        assert payload["content_type"] == "sec_filing"
        assert payload["source"]["type"] == "sec_edgar"
        assert payload["source"]["identifier"] == "0000320193-25-000106"
        assert payload["deduplication"]["unique_id"] == "sec:0000320193:10-K:2025-11-01"
        assert payload["content"]["title"] == "AAPL 10-K Annual Report"
        assert payload["metadata"]["form_type"] == "10-K"

        # Verify result
        assert result.status == "accepted"
        assert result.is_new is True

    @pytest.mark.asyncio
    async def test_ingest_handles_duplicate_response(
        self,
        sample_ingest_kwargs: dict,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Should handle 409 Conflict as duplicate."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.json.return_value = {
            "status": "duplicate",
            "record_id": "existing-record",
            "deduplication": {"matched_record": "existing-record"},
        }
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        client = CaptureSpineClient()
        client._client = mock_httpx_client

        result = await client.ingest(**sample_ingest_kwargs)

        assert result.status == "duplicate"

    @pytest.mark.asyncio
    async def test_ingest_handles_server_error(
        self,
        sample_ingest_kwargs: dict,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Should handle server errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        client = CaptureSpineClient()
        client._client = mock_httpx_client

        result = await client.ingest(**sample_ingest_kwargs)

        assert result.status == "failed"
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_ingest_with_timestamps(
        self,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Should include timestamps when provided."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "accepted", "record_id": "r1"}
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        client = CaptureSpineClient()
        client._client = mock_httpx_client

        await client.ingest(
            content_type="earnings_event",
            source_type="polygon",
            source_id="AAPL:2026-01-30",
            content={"title": "AAPL Q1", "body": "...", "format": "text"},
            fingerprint="earnings:AAPL:2026-01-30",
            timestamps={"created_at": "2026-01-30T16:00:00Z"},
        )

        payload = mock_httpx_client.post.call_args[1]["json"]
        assert "timestamps" in payload
        assert payload["timestamps"]["created_at"] == "2026-01-30T16:00:00Z"


class TestCaptureSpineClientBatch:
    """Tests for batch ingestion."""

    @pytest.mark.asyncio
    async def test_batch_ingest_multiple(
        self,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Should ingest multiple items in batch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "accepted", "record_id": "r1"}
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        client = CaptureSpineClient()
        client._client = mock_httpx_client

        payloads = [
            {
                "content_type": "sec_filing",
                "source_type": "sec_edgar",
                "source_id": "filing-1",
                "content": {"title": "Filing 1", "body": "", "format": "html"},
                "fingerprint": "sec:filing-1",
            },
            {
                "content_type": "earnings_event",
                "source_type": "polygon",
                "source_id": "MSFT:2026",
                "content": {"title": "MSFT Q1", "body": "", "format": "text"},
                "fingerprint": "earnings:MSFT:2026",
            },
        ]

        result = await client.ingest_batch(payloads)

        assert result.total == 2
        assert result.accepted == 2
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_batch_ingest_stops_on_error(
        self,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Should stop on first error when stop_on_error=True."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        client = CaptureSpineClient()
        client._client = mock_httpx_client

        payloads = [
            {
                "content_type": "sec_filing",
                "source_type": "sec_edgar",
                "source_id": "f1",
                "content": {"title": "F1", "body": "", "format": "html"},
                "fingerprint": "sec:f1",
            },
            {
                "content_type": "sec_filing",
                "source_type": "sec_edgar",
                "source_id": "f2",
                "content": {"title": "F2", "body": "", "format": "html"},
                "fingerprint": "sec:f2",
            },
        ]

        result = await client.ingest_batch(payloads, stop_on_error=True)

        assert result.total == 2
        assert result.failed == 1
        assert len(result.results) == 1  # Stopped after first


class TestCaptureSpineClientHealth:
    """Tests for health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_httpx_client: AsyncMock) -> None:
        """Should return True when healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        client = CaptureSpineClient()
        client._client = mock_httpx_client

        result = await client.health_check()

        assert result is True
        mock_httpx_client.get.assert_called_once_with("/health")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_httpx_client: AsyncMock) -> None:
        """Should return False when unhealthy."""
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        client = CaptureSpineClient()
        client._client = mock_httpx_client

        result = await client.health_check()

        assert result is False
