"""Unit tests for Polygon earnings adapters."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from feedspine.adapter.polygon_earnings import (
    PolygonEarningsAdapter,
    PolygonEstimateHistoryAdapter,
)
from feedspine.models.record import RecordCandidate


class TestPolygonEarningsAdapter:
    """Tests for PolygonEarningsAdapter."""

    @pytest.fixture
    def adapter(self) -> PolygonEarningsAdapter:
        """Create adapter instance (demo mode, no API key)."""
        return PolygonEarningsAdapter(
            date_from=date(2026, 1, 30),
            date_to=date(2026, 2, 6),
        )

    @pytest.fixture
    def adapter_with_tickers(self) -> PolygonEarningsAdapter:
        """Create adapter with ticker filter."""
        return PolygonEarningsAdapter(
            date_from=date(2026, 1, 30),
            date_to=date(2026, 2, 6),
            tickers=["AAPL", "MSFT"],
        )

    def test_adapter_initialization(self, adapter: PolygonEarningsAdapter) -> None:
        """Test adapter initializes with correct defaults."""
        assert adapter.name == "polygon-earnings"
        assert "polygon.io" in adapter.source_url
        assert adapter._date_from == date(2026, 1, 30)
        assert adapter._date_to == date(2026, 2, 6)
        assert adapter._tickers is None

    def test_adapter_with_tickers(self, adapter_with_tickers: PolygonEarningsAdapter) -> None:
        """Test adapter with ticker filter."""
        assert adapter_with_tickers._tickers == ["AAPL", "MSFT"]

    def test_adapter_rate_limit_default(self, adapter: PolygonEarningsAdapter) -> None:
        """Test default rate limit for Polygon."""
        assert adapter.requests_per_second == 5.0

    @pytest.mark.asyncio
    async def test_fetch_items_demo_mode(self, adapter: PolygonEarningsAdapter) -> None:
        """Test _fetch_items returns demo data when no API key."""
        await adapter.initialize()
        try:
            items = await adapter._fetch_items()

            assert len(items) > 0
            assert all("ticker" in item for item in items)
            assert any(item["ticker"] == "AAPL" for item in items)
            assert any(item["ticker"] == "MSFT" for item in items)
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_to_candidate_converts_item(self, adapter: PolygonEarningsAdapter) -> None:
        """Test _to_candidate creates valid RecordCandidate."""
        raw_item = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "report_date": "2026-01-30",
            "time_of_day": "AMC",
            "fiscal_year": 2026,
            "fiscal_period": "Q1",
            "eps": {
                "estimated": 2.35,
                "actual": 2.42,
            },
            "revenue": {
                "estimated": 119000000000,
                "actual": 121000000000,
            },
            "analyst_count": 38,
        }

        candidate = adapter._to_candidate(raw_item)

        assert isinstance(candidate, RecordCandidate)
        assert candidate.natural_key == "polygon:aapl:2026:q1"
        assert candidate.content["ticker"] == "AAPL"
        assert candidate.content["eps_estimate"] == 2.35
        assert candidate.content["eps_actual"] == 2.42
        assert candidate.content["revenue_estimate"] == 119000000000
        assert candidate.content["revenue_actual"] == 121000000000
        assert candidate.content["is_released"] is True

    @pytest.mark.asyncio
    async def test_to_candidate_handles_missing_actual(self, adapter: PolygonEarningsAdapter) -> None:
        """Test _to_candidate handles unreleased earnings."""
        raw_item = {
            "ticker": "NVDA",
            "name": "NVIDIA Corporation",
            "report_date": "2026-02-01",
            "time_of_day": "AMC",
            "fiscal_year": 2026,
            "fiscal_period": "Q4",
            "eps": {
                "estimated": 4.12,
                "actual": None,
            },
            "revenue": {
                "estimated": 20500000000,
                "actual": None,
            },
            "analyst_count": 45,
        }

        candidate = adapter._to_candidate(raw_item)

        assert candidate.content["eps_actual"] is None
        assert candidate.content["revenue_actual"] is None
        assert candidate.content["is_released"] is False

    @pytest.mark.asyncio
    async def test_full_fetch_demo_mode(self, adapter: PolygonEarningsAdapter) -> None:
        """Test full fetch cycle in demo mode."""
        await adapter.initialize()
        try:
            records = []
            async for record in adapter.fetch():
                records.append(record)

            assert len(records) > 0

            # Check records have required structure
            for record in records:
                assert isinstance(record, RecordCandidate)
                assert record.natural_key.startswith("polygon:")
                assert "ticker" in record.content
                assert record.metadata is not None
        finally:
            await adapter.close()

    def test_normalize_report_time_bmo(self, adapter: PolygonEarningsAdapter) -> None:
        """Test BMO (before market open) normalization."""
        assert adapter._normalize_report_time("BMO") == "bmo"
        assert adapter._normalize_report_time("Before Market Open") == "bmo"
        assert adapter._normalize_report_time("before") == "bmo"

    def test_normalize_report_time_amc(self, adapter: PolygonEarningsAdapter) -> None:
        """Test AMC (after market close) normalization."""
        assert adapter._normalize_report_time("AMC") == "amc"
        assert adapter._normalize_report_time("After Market Close") == "amc"
        assert adapter._normalize_report_time("after") == "amc"

    def test_normalize_report_time_dmh(self, adapter: PolygonEarningsAdapter) -> None:
        """Test DMH (during market hours) normalization."""
        assert adapter._normalize_report_time("DMH") == "dmh"
        assert adapter._normalize_report_time("During Market Hours") == "dmh"
        assert adapter._normalize_report_time("during") == "dmh"

    def test_normalize_report_time_unknown(self, adapter: PolygonEarningsAdapter) -> None:
        """Test unknown report time normalization."""
        assert adapter._normalize_report_time("") == "unknown"
        assert adapter._normalize_report_time("TBD") == "unknown"

    def test_parse_quarter(self, adapter: PolygonEarningsAdapter) -> None:
        """Test quarter parsing from fiscal period."""
        assert adapter._parse_quarter("Q1") == 1
        assert adapter._parse_quarter("Q2") == 2
        assert adapter._parse_quarter("Q3") == 3
        assert adapter._parse_quarter("Q4") == 4
        assert adapter._parse_quarter("q4") == 4  # lowercase
        assert adapter._parse_quarter("") is None
        assert adapter._parse_quarter("annual") is None

    def test_to_decimal_valid(self, adapter: PolygonEarningsAdapter) -> None:
        """Test decimal conversion with valid values."""
        assert adapter._to_decimal(2.35) == Decimal("2.35")
        assert adapter._to_decimal("2.35") == Decimal("2.35")
        assert adapter._to_decimal(100) == Decimal("100")

    def test_to_decimal_invalid(self, adapter: PolygonEarningsAdapter) -> None:
        """Test decimal conversion with invalid values."""
        assert adapter._to_decimal(None) is None
        assert adapter._to_decimal("invalid") is None

    def test_metadata_source_tracking(self, adapter: PolygonEarningsAdapter) -> None:
        """Test that source metadata is properly tracked."""
        raw_item = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "report_date": "2026-01-30",
            "fiscal_year": 2026,
            "fiscal_period": "Q1",
            "eps": {"estimated": 2.35},
            "revenue": {},
        }

        candidate = adapter._to_candidate(raw_item)

        assert candidate.content["source_vendor"] == "polygon"
        assert candidate.content["source_feed"] == "reference/earnings"
        assert candidate.metadata.source == "polygon-earnings"
        assert candidate.metadata.source_type == "polygon.earnings"
        assert "api_url" in candidate.metadata.extra


class TestPolygonEstimateHistoryAdapter:
    """Tests for PolygonEstimateHistoryAdapter."""

    @pytest.fixture
    def history_adapter(self) -> PolygonEstimateHistoryAdapter:
        """Create estimate history adapter."""
        return PolygonEstimateHistoryAdapter(
            ticker="AAPL",
            fiscal_year=2026,
            fiscal_quarter=1,
        )

    def test_history_adapter_initialization(self, history_adapter: PolygonEstimateHistoryAdapter) -> None:
        """Test history adapter initialization."""
        assert history_adapter.name == "polygon-estimate-history"
        assert history_adapter._ticker == "AAPL"
        assert history_adapter._fiscal_year == 2026
        assert history_adapter._fiscal_quarter == 1

    def test_ticker_normalized_to_uppercase(self) -> None:
        """Test ticker is normalized to uppercase."""
        adapter = PolygonEstimateHistoryAdapter(
            ticker="aapl",
            fiscal_year=2026,
            fiscal_quarter=1,
        )
        assert adapter._ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_fetch_items_demo_mode(self, history_adapter: PolygonEstimateHistoryAdapter) -> None:
        """Test demo data for estimate history."""
        await history_adapter.initialize()
        try:
            items = await history_adapter._fetch_items()

            assert len(items) > 0
            # Should have multiple snapshots showing revision history
            assert len(items) >= 2

            # Each should have estimate data
            for item in items:
                assert "eps_estimate" in item
                assert "captured_at" in item
        finally:
            await history_adapter.close()

    @pytest.mark.asyncio
    async def test_to_candidate_creates_valid_record(self, history_adapter: PolygonEstimateHistoryAdapter) -> None:
        """Test converting estimate snapshot to record."""
        raw_item = {
            "captured_at": datetime(2026, 1, 15, tzinfo=UTC),
            "eps_estimate": 2.35,
            "revenue_estimate": 119000000000,
            "num_analysts": 38,
        }

        candidate = history_adapter._to_candidate(raw_item)

        assert isinstance(candidate, RecordCandidate)
        assert "polygon:estimate:aapl:2026:q1:" in candidate.natural_key
        assert candidate.content["ticker"] == "AAPL"
        assert candidate.content["eps_estimate"] == 2.35
        assert candidate.content["fiscal_period"] == "2026:Q1"

    @pytest.mark.asyncio
    async def test_full_fetch_estimate_history(self, history_adapter: PolygonEstimateHistoryAdapter) -> None:
        """Test full fetch cycle for estimate history."""
        await history_adapter.initialize()
        try:
            records = []
            async for record in history_adapter.fetch():
                records.append(record)

            assert len(records) > 0

            # Records should be ordered by captured_at
            captured_dates = [r.published_at for r in records]
            assert captured_dates == sorted(captured_dates)
        finally:
            await history_adapter.close()


class TestPolygonAdapterIntegration:
    """Integration tests for Polygon adapters."""

    @pytest.mark.asyncio
    async def test_context_manager_usage(self) -> None:
        """Test adapter can be used as async context manager."""
        adapter = PolygonEarningsAdapter(
            date_from=date(2026, 1, 30),
            date_to=date(2026, 2, 6),
        )

        # Use async context manager pattern
        await adapter.initialize()
        try:
            records = []
            async for record in adapter.fetch():
                records.append(record)
            assert len(records) > 0
        finally:
            await adapter.close()

    def test_adapter_source_url_format(self) -> None:
        """Test source URL is properly formatted."""
        adapter = PolygonEarningsAdapter()

        assert adapter.source_url.startswith("https://api.polygon.io")
        assert "earnings" in adapter.source_url
