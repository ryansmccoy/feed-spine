"""Tests for SECEdgarFilingAdapter.

Tests cover:
- CIK normalisation
- Ticker resolution (mocked)
- Filing parsing from mock API response
- Form-type filtering
- Document fetch opt-in
- Protocol compliance
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from feedspine.adapter.sec_edgar import SECEdgarFilingAdapter
from feedspine.models.record import RecordCandidate
from feedspine.protocols.feed import FeedAdapter

# -- Fixtures -----------------------------------------------------------------

MOCK_SUBMISSIONS = {
    "cik": "0000320193",
    "entityType": "operating",
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "filings": {
        "recent": {
            "accessionNumber": [
                "0000320193-24-000001",
                "0000320193-24-000002",
                "0000320193-24-000003",
            ],
            "form": ["10-K", "10-Q", "8-K"],
            "filingDate": ["2024-10-30", "2024-07-30", "2024-06-15"],
            "primaryDocument": [
                "aapl-20241030.htm",
                "aapl-20240730.htm",
                "aapl-20240615.htm",
            ],
            "primaryDocDescription": [
                "10-K Filing",
                "10-Q Filing",
                "8-K Filing",
            ],
        },
        "files": [],
    },
}

MOCK_TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}


def _mock_response(data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = json.dumps(data)
    resp.raise_for_status = MagicMock()
    return resp


# -- Tests --------------------------------------------------------------------


class TestSECEdgarCreation:
    def test_requires_cik_or_ticker(self) -> None:
        with pytest.raises(ValueError, match="cik.*ticker"):
            SECEdgarFilingAdapter(name="test")

    def test_cik_normalised(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik="320193")
        assert adapter._cik == "0000320193"

    def test_int_cik(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik=320193)
        assert adapter._cik == "0000320193"

    def test_ticker_stored(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", ticker="AAPL")
        assert adapter._ticker == "AAPL"

    def test_protocol_compliance(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik="320193")
        assert isinstance(adapter, FeedAdapter)

    def test_name(self) -> None:
        adapter = SECEdgarFilingAdapter(name="edgar-aapl", cik="320193")
        assert adapter.name == "edgar-aapl"


class TestTickerResolution:
    @pytest.mark.asyncio
    async def test_resolve_ticker(self) -> None:
        """Test that ticker is resolved to CIK during fetch."""
        adapter = SECEdgarFilingAdapter(name="test", ticker="AAPL")

        # Mock the ticker lookup and submissions API
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[
                _mock_response(MOCK_TICKERS),  # company_tickers.json
                _mock_response(MOCK_SUBMISSIONS),  # submissions API
            ]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            # Fetch triggers ticker resolution
            records = [r async for r in adapter.fetch()]
            await adapter.close()

        # Should have fetched filings
        assert len(records) > 0

    @pytest.mark.asyncio
    async def test_unknown_ticker_raises(self) -> None:
        """Test that unknown ticker raises FeedError during fetch."""
        from feedspine.adapter.base import FeedError

        adapter = SECEdgarFilingAdapter(name="test", ticker="ZZZZ")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_response(MOCK_TICKERS))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            with pytest.raises(FeedError, match="ZZZZ"):
                # Fetch triggers ticker resolution which should fail
                _ = [r async for r in adapter.fetch()]


class TestFilingParsing:
    @pytest.mark.asyncio
    async def test_fetch_all_filings(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik="320193")
        adapter._cik = "0000320193"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_response(MOCK_SUBMISSIONS))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            records = [r async for r in adapter.fetch()]
            await adapter.close()

        assert len(records) == 3
        assert all(isinstance(r, RecordCandidate) for r in records)

    @pytest.mark.asyncio
    async def test_natural_key_format(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik="320193")
        adapter._cik = "0000320193"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_response(MOCK_SUBMISSIONS))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            records = [r async for r in adapter.fetch()]
            await adapter.close()

        assert records[0].natural_key == "sec:0000320193-24-000001"

    @pytest.mark.asyncio
    async def test_filing_date_parsed(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik="320193")
        adapter._cik = "0000320193"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_response(MOCK_SUBMISSIONS))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            records = [r async for r in adapter.fetch()]
            await adapter.close()

        assert records[0].published_at.year == 2024
        assert records[0].published_at.month == 10
        assert records[0].published_at.day == 30

    @pytest.mark.asyncio
    async def test_content_fields(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik="320193")
        adapter._cik = "0000320193"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_response(MOCK_SUBMISSIONS))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            records = [r async for r in adapter.fetch()]
            await adapter.close()

        c = records[0].content
        assert c["form_type"] == "10-K"
        assert c["accession_number"] == "0000320193-24-000001"
        assert c["company_name"] == "Apple Inc."
        assert c["cik"] == "0000320193"

    @pytest.mark.asyncio
    async def test_metadata(self) -> None:
        adapter = SECEdgarFilingAdapter(name="edgar-aapl", cik="320193")
        adapter._cik = "0000320193"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_response(MOCK_SUBMISSIONS))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            records = [r async for r in adapter.fetch()]
            await adapter.close()

        assert records[0].metadata.source == "edgar-aapl"
        assert records[0].metadata.source_type == "sec.10-k"


class TestFormTypeFilter:
    @pytest.mark.asyncio
    async def test_filter_10k_only(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik="320193", form_types=["10-K"])
        adapter._cik = "0000320193"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_response(MOCK_SUBMISSIONS))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            records = [r async for r in adapter.fetch()]
            await adapter.close()

        assert len(records) == 1
        assert records[0].content["form_type"] == "10-K"

    @pytest.mark.asyncio
    async def test_filter_multiple_forms(self) -> None:
        adapter = SECEdgarFilingAdapter(name="test", cik="320193", form_types=["10-K", "8-K"])
        adapter._cik = "0000320193"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_response(MOCK_SUBMISSIONS))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("feedspine.adapter.sec_edgar.httpx.AsyncClient", return_value=mock_client):
            await adapter.initialize()
            records = [r async for r in adapter.fetch()]
            await adapter.close()

        forms = {r.content["form_type"] for r in records}
        assert forms == {"10-K", "8-K"}
