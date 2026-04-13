"""Tests for feedspine.ops.stats — statistics operations.

Covers fetch_storage_summary, fetch_layer_distribution,
check_storage_health, and _get_layer_counts.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from feedspine.ops import OperationContext

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def storage() -> AsyncMock:
    """Minimal mock storage with count and count_by_layer."""
    s = AsyncMock()
    s.count = AsyncMock(return_value=42)
    s.count_by_layer = AsyncMock(return_value={"bronze": 30, "silver": 10, "gold": 2})
    return s


@pytest.fixture
def ctx(storage: AsyncMock) -> OperationContext:
    return OperationContext(storage=storage)


# ── fetch_storage_summary ───────────────────────────────────────


class TestFetchStorageSummary:
    """Tests for fetch_storage_summary."""

    async def test_basic_summary(self, ctx: OperationContext) -> None:
        from feedspine.ops.stats import fetch_storage_summary

        del ctx.storage.get_storage_summary
        result = await fetch_storage_summary(ctx)
        assert result.success
        data = result.data
        assert data["records"]["total"] == 42
        assert data["records"]["by_layer"]["bronze"] == 30

    async def test_uses_rich_summary_if_available(self, ctx: OperationContext) -> None:
        from feedspine.ops.stats import fetch_storage_summary

        ctx.storage.get_storage_summary = AsyncMock(return_value={"custom": True})
        result = await fetch_storage_summary(ctx)
        assert result.success
        assert result.data == {"custom": True}


# ── fetch_layer_distribution ────────────────────────────────────


class TestFetchLayerDistribution:
    async def test_returns_layer_counts(self, ctx: OperationContext) -> None:
        from feedspine.ops.stats import fetch_layer_distribution

        result = await fetch_layer_distribution(ctx)
        assert result.success
        assert result.data["total"] == 42
        assert result.data["by_layer"]["silver"] == 10


# ── check_storage_health ────────────────────────────────────────


class TestCheckStorageHealth:
    async def test_success(self, ctx: OperationContext) -> None:
        from feedspine.ops.stats import check_storage_health

        result = await check_storage_health(ctx)
        assert result.success
        assert result.data["record_count"] == 42
        assert "backend" in result.data


# ── _get_layer_counts ───────────────────────────────────────────


class TestGetLayerCounts:
    async def test_uses_count_by_layer_when_available(self) -> None:
        from feedspine.ops.stats import _get_layer_counts

        s = AsyncMock()
        s.count_by_layer = AsyncMock(return_value={"bronze": 5})
        result = await _get_layer_counts(s)
        assert result == {"bronze": 5}
        s.count_by_layer.assert_awaited_once()

    async def test_falls_back_to_per_layer(self) -> None:
        from feedspine.ops.stats import _get_layer_counts

        s = AsyncMock(spec=[])  # no count_by_layer
        s.count = AsyncMock(side_effect=[10, 3, 0])
        result = await _get_layer_counts(s)
        # Only non-zero layers
        assert "bronze" in result
        assert "silver" in result
        assert "gold" not in result


# ── fetch_feed_runs ─────────────────────────────────────────────


class TestFetchFeedRuns:
    async def test_not_available(self, ctx: OperationContext) -> None:
        """Graceful failure when storage has no get_feed_runs."""
        from feedspine.ops.stats import fetch_feed_runs

        del ctx.storage.get_feed_runs
        result = await fetch_feed_runs(ctx)
        assert not result.success
        assert "not available" in result.error


# ── fetch_collection_stats ──────────────────────────────────────


class TestFetchCollectionStats:
    async def test_not_available(self, ctx: OperationContext) -> None:
        from feedspine.ops.stats import fetch_collection_stats

        del ctx.storage.get_collection_stats
        result = await fetch_collection_stats(ctx)
        assert not result.success
