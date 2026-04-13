"""Tests for feedspine.cli_modules.capture_cmds - Capture-spine CLI commands."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from feedspine.cli_modules.capture_cmds import capture_app
from feedspine.integration.capture_spine import BatchIngestResult, IngestResult

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def cli_runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client():
    """Mock CaptureSpineClient in the integration module (where it's imported from)."""
    with patch("feedspine.integration.CaptureSpineClient") as mock_cls:
        client = AsyncMock()
        # Ensure async context manager returns the same mock
        client.__aenter__.return_value = client
        mock_cls.return_value = client
        yield client


@pytest.fixture
def mock_storage():
    """Mock storage backend."""
    with patch("feedspine.cli_modules.capture_cmds.get_storage") as mock_fn:
        storage = AsyncMock()
        # query needs to return an async iterator directly, not a coroutine
        storage.query = MagicMock()
        mock_fn.return_value = storage
        yield storage


# =============================================================================
# Health Command Tests
# =============================================================================


class TestHealthCommand:
    """Tests for 'feedspine capture health' command."""

    def test_health_success(self, cli_runner, mock_client):
        """Should display healthy status when API is available."""
        mock_client.health_check.return_value = True

        result = cli_runner.invoke(capture_app, ["health"])

        assert result.exit_code == 0
        assert "healthy" in result.stdout.lower() or "✅" in result.stdout
        mock_client.health_check.assert_called_once()

    def test_health_failure(self, cli_runner, mock_client):
        """Should display unhealthy status when API is down."""
        mock_client.health_check.return_value = False

        result = cli_runner.invoke(capture_app, ["health"])

        assert result.exit_code == 1
        assert "unreachable" in result.stdout.lower() or "❌" in result.stdout
        mock_client.health_check.assert_called_once()

    def test_health_connection_error(self, cli_runner, mock_client):
        """Should handle connection errors gracefully."""
        mock_client.health_check.side_effect = Exception("Connection refused")

        result = cli_runner.invoke(capture_app, ["health"])

        # Connection errors result in exit code 1
        assert result.exit_code == 1
        assert "error" in result.stdout.lower() or "❌" in result.stdout

    def test_health_custom_url(self, cli_runner, mock_client):
        """Should use custom URL when provided."""
        mock_client.health_check.return_value = True

        result = cli_runner.invoke(capture_app, ["health", "--url", "http://custom:9000"])

        assert result.exit_code == 0


# =============================================================================
# Status Command Tests
# =============================================================================


class TestStatusCommand:
    """Tests for 'feedspine capture status' command."""

    def test_status_healthy(self, cli_runner, mock_client):
        """Should display connection status."""
        mock_client.health_check.return_value = True

        result = cli_runner.invoke(capture_app, ["status"])

        assert result.exit_code == 0
        assert "http://localhost:8200" in result.stdout.lower()

    def test_status_custom_url(self, cli_runner, mock_client):
        """Should display custom URL status."""
        mock_client.health_check.return_value = True

        result = cli_runner.invoke(capture_app, ["status", "--url", "http://prod:8200"])

        assert result.exit_code == 0
        assert "prod:8200" in result.stdout.lower()


# =============================================================================
# Ingest Command Tests
# =============================================================================


class TestIngestCommand:
    """Tests for 'feedspine capture ingest' command."""

    def test_ingest_success(self, cli_runner, mock_client):
        """Should ingest single observation successfully."""
        mock_client.ingest.return_value = IngestResult(
            status="accepted",
            record_id="rec-123",
            sighting_id="sighting-456",
            is_new=True,
            task_id="task-789",
            error=None,
        )

        result = cli_runner.invoke(
            capture_app,
            [
                "ingest",
                "--type",
                "test",
                "--source",
                "test_source",
                "--id",
                "test-1",
                "--title",
                "Test Title",
                "--body",
                "Test body content",
                "--fingerprint",
                "test:1",
            ],
        )

        assert result.exit_code == 0
        assert "accepted" in result.stdout.lower() or "✅" in result.stdout
        mock_client.ingest.assert_called_once()

    def test_ingest_duplicate(self, cli_runner, mock_client):
        """Should handle duplicate observations."""
        mock_client.ingest.return_value = IngestResult(
            status="duplicate",
            record_id="rec-123",
            sighting_id=None,
            is_new=False,
            task_id=None,
            error=None,
        )

        result = cli_runner.invoke(
            capture_app,
            [
                "ingest",
                "--type",
                "test",
                "--source",
                "test_source",
                "--id",
                "test-1",
                "--title",
                "Test",
                "--body",
                "Test",
                "--fingerprint",
                "test:1",
            ],
        )

        assert result.exit_code == 0
        assert "duplicate" in result.stdout.lower() or "⚠" in result.stdout

    def test_ingest_failure(self, cli_runner, mock_client):
        """Should handle ingest failures."""
        mock_client.ingest.return_value = IngestResult(
            status="failed",
            record_id=None,
            sighting_id=None,
            is_new=False,
            task_id=None,
            error="Validation error",
        )

        result = cli_runner.invoke(
            capture_app,
            [
                "ingest",
                "--type",
                "test",
                "--source",
                "test",
                "--id",
                "1",
                "--title",
                "Test",
                "--body",
                "Test",
                "--fingerprint",
                "test:1",
            ],
        )

        assert result.exit_code == 1
        assert "error" in result.stdout.lower() or "❌" in result.stdout

    def test_ingest_missing_httpx(self, cli_runner):
        """Should fail gracefully when httpx is not installed."""
        with patch("feedspine.cli_modules.capture_cmds.is_capture_client_available", return_value=False):
            result = cli_runner.invoke(
                capture_app,
                [
                    "ingest",
                    "--type",
                    "test",
                    "--source",
                    "test",
                    "--id",
                    "1",
                    "--title",
                    "Test",
                    "--body",
                    "Test",
                    "--fingerprint",
                    "test:1",
                ],
            )

            assert result.exit_code == 1
            assert "httpx" in result.stdout.lower() or "capture" in result.stdout.lower()


# =============================================================================
# Batch Command Tests
# =============================================================================


class TestBatchCommand:
    """Tests for 'feedspine capture batch' command."""

    def test_batch_success(self, cli_runner, mock_client, mock_storage):
        """Should batch ingest records successfully."""

        # Mock storage query
        async def mock_query(*args, **kwargs):
            from datetime import datetime

            from feedspine.models import Layer, Record
            from feedspine.models.base import Metadata

            records = [
                Record(
                    id=f"rec-{i}",
                    natural_key=f"key-{i}",
                    layer=Layer.BRONZE,
                    published_at=datetime.now(UTC),
                    captured_at=datetime.now(UTC),
                    metadata=Metadata(source="test-feed"),
                    content={"title": f"Title {i}", "body": f"Body {i}"},
                )
                for i in range(3)
            ]
            for record in records:
                yield record

        mock_storage.query.return_value = mock_query()

        # Mock batch ingest
        mock_client.ingest_batch.return_value = BatchIngestResult(
            total=3, accepted=3, duplicates=0, failed=0, results=[]
        )

        result = cli_runner.invoke(capture_app, ["batch", "--limit", "3"])

        assert result.exit_code == 0
        assert "3" in result.stdout
        mock_client.ingest_batch.assert_called_once()

    def test_batch_dry_run(self, cli_runner, mock_client, mock_storage):
        """Should preview batch without sending when --dry-run is used."""

        # Mock storage query
        async def mock_query(*args, **kwargs):
            from datetime import datetime

            from feedspine.models import Layer, Record
            from feedspine.models.base import Metadata

            records = [
                Record(
                    id="rec-1",
                    natural_key="key-1",
                    layer=Layer.BRONZE,
                    published_at=datetime.now(UTC),
                    captured_at=datetime.now(UTC),
                    metadata=Metadata(source="test-feed"),
                    content={"title": "Title", "body": "Body"},
                )
            ]
            for record in records:
                yield record

        mock_storage.query.return_value = mock_query()

        result = cli_runner.invoke(capture_app, ["batch", "--dry-run", "--limit", "1"])

        assert result.exit_code == 0
        assert "dry run" in result.stdout.lower() or "preview" in result.stdout.lower()
        mock_client.ingest_batch.assert_not_called()

    def test_batch_with_feed_filter(self, cli_runner, mock_client, mock_storage):
        """Should filter by feed name."""

        # Mock storage query
        async def mock_query(*args, **kwargs):
            from datetime import datetime

            from feedspine.models import Layer, Record
            from feedspine.models.base import Metadata

            records = [
                Record(
                    id="rec-1",
                    natural_key="key-1",
                    layer=Layer.BRONZE,
                    published_at=datetime.now(UTC),
                    captured_at=datetime.now(UTC),
                    metadata=Metadata(source="sec-rss"),
                    content={"title": "Title", "body": "Body"},
                )
            ]
            for record in records:
                yield record

        mock_storage.query.return_value = mock_query()
        mock_client.ingest_batch.return_value = BatchIngestResult(
            total=1, accepted=1, duplicates=0, failed=0, results=[]
        )

        result = cli_runner.invoke(capture_app, ["batch", "--feed", "sec-rss", "--limit", "10"])

        assert result.exit_code == 0

    def test_batch_missing_httpx(self, cli_runner):
        """Should fail gracefully when httpx is not installed."""
        with patch("feedspine.cli_modules.capture_cmds.is_capture_client_available", return_value=False):
            result = cli_runner.invoke(capture_app, ["batch", "--limit", "10"])

            assert result.exit_code == 1
            assert "httpx" in result.stdout.lower() or "capture" in result.stdout.lower()

    def test_batch_with_errors(self, cli_runner, mock_client, mock_storage):
        """Should report errors from batch ingestion."""

        # Mock storage query
        async def mock_query(*args, **kwargs):
            from datetime import datetime

            from feedspine.models import Layer, Record
            from feedspine.models.base import Metadata

            records = [
                Record(
                    id=f"rec-{i}",
                    natural_key=f"key-{i}",
                    layer=Layer.BRONZE,
                    published_at=datetime.now(UTC),
                    captured_at=datetime.now(UTC),
                    metadata=Metadata(source="test-feed"),
                    content={"title": f"Title {i}", "body": f"Body {i}"},
                )
                for i in range(5)
            ]
            for record in records:
                yield record

        mock_storage.query.return_value = mock_query()

        # Mock batch ingest with errors
        mock_client.ingest_batch.return_value = BatchIngestResult(
            total=5,
            accepted=3,
            duplicates=1,
            failed=1,
            results=[],
        )

        result = cli_runner.invoke(capture_app, ["batch", "--limit", "5"])

        assert result.exit_code == 0
        assert "failed" in result.stdout.lower() or "error" in result.stdout.lower()
