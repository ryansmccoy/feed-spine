"""Tests for MCP server tool logic.

Validates the ops-layer functions that back the MCP tools,
and tests the tool functions directly when spine-mcp is installed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from feedspine.ops import OperationContext, OperationResult
from feedspine.storage import MemoryStorage

# =============================================================================
# Helpers
# =============================================================================


@pytest.fixture
def opctx():
    """OperationContext with MemoryStorage backend."""
    return OperationContext(storage=MemoryStorage())


# =============================================================================
# Timeline (ops layer backing timeline_query tool)
# =============================================================================


class TestTimelineOps:
    @pytest.mark.asyncio
    async def test_fetch_timeline_returns_result(self, opctx):
        from feedspine.ops.feed import fetch_timeline

        result = await fetch_timeline(opctx)
        assert isinstance(result, OperationResult)
        assert result.success
        assert hasattr(result.data, "items")

    @pytest.mark.asyncio
    async def test_fetch_timeline_with_layer_filter(self, opctx):
        from feedspine.ops.feed import fetch_timeline

        result = await fetch_timeline(opctx, layer="bronze")
        assert result.success

    @pytest.mark.asyncio
    async def test_fetch_timeline_with_limit(self, opctx):
        from feedspine.ops.feed import fetch_timeline

        result = await fetch_timeline(opctx, limit=5, offset=0)
        assert result.success
        assert hasattr(result.data, "items")


# =============================================================================
# Storage stats (ops layer backing storage_stats tool)
# =============================================================================


class TestStorageStatsOps:
    @pytest.mark.asyncio
    async def test_fetch_storage_summary(self, opctx):
        from feedspine.ops.stats import fetch_storage_summary

        result = await fetch_storage_summary(opctx)
        assert result.success
        assert "records" in result.data
        assert result.data["records"]["total"] == 0

    @pytest.mark.asyncio
    async def test_fetch_layer_distribution(self, opctx):
        from feedspine.ops.stats import fetch_layer_distribution

        result = await fetch_layer_distribution(opctx)
        assert result.success
        assert "total" in result.data
        assert "by_layer" in result.data


# =============================================================================
# Feed health (ops layer backing feed_health tool)
# =============================================================================


class TestFeedHealthOps:
    @pytest.mark.asyncio
    async def test_all_feeds_health_returns_error_for_memory(self, opctx):
        from feedspine.ops.health import fetch_all_feed_health

        result = await fetch_all_feed_health(opctx)
        # MemoryStorage doesn't support health metrics
        assert not result.success
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_single_feed_health_returns_error_for_memory(self, opctx):
        from feedspine.ops.health import fetch_feed_health

        result = await fetch_feed_health(opctx, "rss-test")
        assert not result.success


# =============================================================================
# Fetch records (ops layer backing fetch_records_tool)
# =============================================================================


class TestFetchRecordsOps:
    @pytest.mark.asyncio
    async def test_fetch_records_empty_storage(self, opctx):
        from feedspine.ops.query import fetch_records

        result = await fetch_records(opctx)
        assert result.success
        assert result.data == []

    @pytest.mark.asyncio
    async def test_fetch_records_with_layer(self, opctx):
        from feedspine.ops.query import fetch_records

        result = await fetch_records(opctx, layer="bronze", limit=5)
        assert result.success

    @pytest.mark.asyncio
    async def test_fetch_records_with_pagination(self, opctx):
        from feedspine.ops.query import fetch_records

        result = await fetch_records(opctx, limit=10, offset=5)
        assert result.success
        assert result.metadata["offset"] == 5


# =============================================================================
# Record history (ops layer backing record_history tool)
# =============================================================================


class TestRecordHistoryOps:
    @pytest.mark.asyncio
    async def test_record_history_returns_error_for_memory(self, opctx):
        from feedspine.ops.query import fetch_record_history

        result = await fetch_record_history(opctx, natural_key="test-key")
        # MemoryStorage doesn't have session_factory
        assert not result.success
        assert "SQLAlchemy" in result.error


# =============================================================================
# Export (ops layer backing export_data tool)
# =============================================================================


class TestExportOps:
    @pytest.mark.asyncio
    async def test_export_json_empty(self, opctx, tmp_path):
        from feedspine.ops.export import export_to_json

        out = tmp_path / "test.json"
        result = await export_to_json(opctx, output_path=out)
        assert result.success
        assert result.data["count"] == 0
        assert out.exists()

    @pytest.mark.asyncio
    async def test_export_csv_empty(self, opctx, tmp_path):
        from feedspine.ops.export import export_to_csv

        out = tmp_path / "test.csv"
        result = await export_to_csv(opctx, output_path=out)
        assert result.success
        assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_export_parquet_requires_duckdb(self, opctx, tmp_path):
        from feedspine.ops.export import export_to_parquet

        out = tmp_path / "test.parquet"
        result = await export_to_parquet(opctx, output_path=out)
        assert not result.success
        assert "not available" in result.error.lower()


# =============================================================================
# MCP tool direct tests (only when spine-mcp is installed)
# =============================================================================

try:
    import spine_mcp  # noqa: F401

    _HAS_SPINE_MCP = True
except ImportError:
    _HAS_SPINE_MCP = False


@pytest.mark.skipif(not _HAS_SPINE_MCP, reason="spine-mcp not installed")
class TestMCPToolsDirect:
    """Direct invocation tests for MCP tool functions."""

    def _ctx(self):
        from feedspine.ops import OperationContext
        from feedspine.storage import MemoryStorage

        opctx = OperationContext(storage=MemoryStorage(), caller="mcp-test")
        mock = MagicMock()
        mock.request_context.lifespan_context = {"opctx": opctx}
        return mock

    def _parse(self, result: str) -> dict:
        return json.loads(result)

    @pytest.mark.asyncio
    async def test_health_check(self):
        from feedspine.transports.mcp.server import health_check

        result = self._parse(await health_check(self._ctx()))
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_timeline_query(self):
        from feedspine.transports.mcp.server import timeline_query

        result = self._parse(await timeline_query(self._ctx()))
        assert "items" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_storage_stats(self):
        from feedspine.transports.mcp.server import storage_stats

        result = self._parse(await storage_stats(self._ctx()))
        assert "total_records" in result

    @pytest.mark.asyncio
    async def test_export_data_json(self, tmp_path):
        from feedspine.transports.mcp.server import export_data

        out = tmp_path / "export.json"
        result = self._parse(await export_data(self._ctx(), format="json", output_path=str(out)))
        assert "count" in result

    @pytest.mark.asyncio
    async def test_export_data_bad_format(self):
        from feedspine.transports.mcp.server import export_data

        result = self._parse(await export_data(self._ctx(), format="xml"))
        assert "error" in result
