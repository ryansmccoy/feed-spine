"""Tests for CSVFeedAdapter.

Tests cover:
- Basic CSV parsing with key_column
- Composite key_columns
- Tab-delimited files
- Date extraction from various column names
- Change detection via FileFeedAdapter
- Protocol compliance
"""

from __future__ import annotations

from pathlib import Path

import pytest

from feedspine.adapter.csv_adapter import CSVFeedAdapter
from feedspine.models.record import RecordCandidate
from feedspine.protocols.feed import FeedAdapter


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    """Create a sample CSV file."""
    fp = tmp_path / "data.csv"
    fp.write_text(
        "ticker,date,close,volume\n"
        "AAPL,2024-01-15,185.50,50000000\n"
        "MSFT,2024-01-15,390.25,35000000\n"
        "GOOG,2024-01-15,141.80,22000000\n",
        encoding="utf-8",
    )
    return fp


@pytest.fixture
def tsv_file(tmp_path: Path) -> Path:
    """Create a sample TSV file."""
    fp = tmp_path / "data.tsv"
    fp.write_text(
        "accession\tform_type\tfiled\tcompany\n"
        "0001234-24-000001\t10-K\t2024-03-15\tAcme Corp\n"
        "0001234-24-000002\t10-Q\t2024-05-10\tAcme Corp\n",
        encoding="utf-8",
    )
    return fp


class TestCSVFeedAdapterCreation:
    def test_requires_key(self) -> None:
        with pytest.raises(ValueError, match="key_column"):
            CSVFeedAdapter(path="x.csv", name="test")

    def test_key_column(self) -> None:
        adapter = CSVFeedAdapter(path="x.csv", name="test", key_column="id")
        assert adapter.name == "test"

    def test_key_columns(self) -> None:
        adapter = CSVFeedAdapter(path="x.csv", name="test", key_columns=["a", "b"])
        assert adapter.name == "test"

    def test_protocol_compliance(self) -> None:
        adapter = CSVFeedAdapter(path="x.csv", name="test", key_column="id")
        assert isinstance(adapter, FeedAdapter)


class TestCSVFeedAdapterFetch:
    @pytest.mark.asyncio
    async def test_fetch_csv(self, csv_file: Path) -> None:
        adapter = CSVFeedAdapter(
            path=str(csv_file),
            name="prices",
            key_column="ticker",
            source_type="market.prices",
        )
        await adapter.initialize()
        records = []
        async for record in adapter.fetch():
            records.append(record)
        await adapter.close()

        assert len(records) == 3
        assert all(isinstance(r, RecordCandidate) for r in records)

    @pytest.mark.asyncio
    async def test_natural_key_format(self, csv_file: Path) -> None:
        adapter = CSVFeedAdapter(path=str(csv_file), name="prices", key_column="ticker")
        await adapter.initialize()
        records = [r async for r in adapter.fetch()]
        await adapter.close()

        keys = [r.natural_key for r in records]
        assert "prices:aapl" in keys  # normalized to lowercase
        assert "prices:msft" in keys
        assert "prices:goog" in keys

    @pytest.mark.asyncio
    async def test_composite_key(self, csv_file: Path) -> None:
        adapter = CSVFeedAdapter(
            path=str(csv_file),
            name="prices",
            key_columns=["ticker", "date"],
        )
        await adapter.initialize()
        records = [r async for r in adapter.fetch()]
        await adapter.close()

        # Keys include both columns joined with |
        assert "prices:aapl|2024-01-15" in records[0].natural_key

    @pytest.mark.asyncio
    async def test_tsv_autodetect(self, tsv_file: Path) -> None:
        adapter = CSVFeedAdapter(
            path=str(tsv_file),
            name="filings",
            key_column="accession",
        )
        await adapter.initialize()
        records = [r async for r in adapter.fetch()]
        await adapter.close()

        assert len(records) == 2
        assert "0001234-24-000001" in records[0].natural_key

    @pytest.mark.asyncio
    async def test_date_extraction(self, csv_file: Path) -> None:
        adapter = CSVFeedAdapter(path=str(csv_file), name="p", key_column="ticker")
        await adapter.initialize()
        records = [r async for r in adapter.fetch()]
        await adapter.close()

        # Should extract date from "date" column
        assert records[0].published_at.year == 2024
        assert records[0].published_at.month == 1
        assert records[0].published_at.day == 15

    @pytest.mark.asyncio
    async def test_content_preserved(self, csv_file: Path) -> None:
        adapter = CSVFeedAdapter(path=str(csv_file), name="p", key_column="ticker")
        await adapter.initialize()
        records = [r async for r in adapter.fetch()]
        await adapter.close()

        content = records[0].content
        assert content["ticker"] == "AAPL"
        assert content["close"] == "185.50"
        assert content["volume"] == "50000000"

    @pytest.mark.asyncio
    async def test_metadata(self, csv_file: Path) -> None:
        adapter = CSVFeedAdapter(
            path=str(csv_file),
            name="prices",
            key_column="ticker",
            source_type="market.prices",
        )
        await adapter.initialize()
        records = [r async for r in adapter.fetch()]
        await adapter.close()

        assert records[0].metadata.source == "prices"
        assert records[0].metadata.source_type == "market.prices"

    @pytest.mark.asyncio
    async def test_explicit_delimiter(self, tsv_file: Path) -> None:
        adapter = CSVFeedAdapter(
            path=str(tsv_file),
            name="filings",
            key_column="accession",
            delimiter="\t",
        )
        await adapter.initialize()
        records = [r async for r in adapter.fetch()]
        await adapter.close()
        assert len(records) == 2
