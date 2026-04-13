"""
Polygon.io Earnings Calendar Adapter.

Fetches earnings calendar and estimate data from Polygon.io API.
Follows FeedSpine BaseFeedAdapter pattern.

Example:
    from feedspine.adapter.polygon_earnings import PolygonEarningsAdapter

    adapter = PolygonEarningsAdapter(
        api_key=os.environ["POLYGON_API_KEY"],
        date_from=date.today(),
        date_to=date.today() + timedelta(days=7),
    )

    async for record in adapter.fetch():
        print(record.natural_key, record.content["ticker"])

CLI Usage:
    $ feedspine earnings ingest --source polygon --days 7
"""

from __future__ import annotations

import contextlib
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from feedspine.adapter.base import BaseFeedAdapter, FeedError
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate


class PolygonEarningsAdapter(BaseFeedAdapter):
    """
    Adapter for Polygon.io earnings calendar API.

    Fetches:
    - Earnings calendar events
    - EPS estimates (consensus)
    - Revenue estimates

    API Reference:
    - https://polygon.io/docs/stocks/get_v3_reference_earnings
    - https://polygon.io/docs/stocks/get_v3_reference_dividends

    Example:
        adapter = PolygonEarningsAdapter(
            api_key=os.environ["POLYGON_API_KEY"],
            date_from=date(2026, 1, 30),
            date_to=date(2026, 2, 6),
        )

        async for record in adapter.fetch():
            event = record.content
            print(f"{event['ticker']}: EPS est ${event['eps_estimate']}")
    """

    # Polygon API endpoints
    BASE_URL = "https://api.polygon.io"
    EARNINGS_ENDPOINT = "/v3/reference/earnings"

    def __init__(
        self,
        api_key: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        tickers: list[str] | None = None,
        *,
        name: str = "polygon-earnings",
        requests_per_second: float = 5.0,  # Polygon rate limit
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize the Polygon earnings adapter.

        Args:
            api_key: Polygon.io API key (or set POLYGON_API_KEY env var).
            date_from: Start date for calendar (default: today).
            date_to: End date for calendar (default: today + 7 days).
            tickers: Filter to specific tickers (default: all).
            name: Adapter name.
            requests_per_second: Rate limit.
            timeout_seconds: HTTP request timeout.
        """
        super().__init__(
            name=name,
            source_url=f"{self.BASE_URL}{self.EARNINGS_ENDPOINT}",
            requests_per_second=requests_per_second,
        )

        self._api_key = api_key or os.environ.get("POLYGON_API_KEY", "")
        self._date_from = date_from or date.today()
        self._date_to = date_to or (date.today() + timedelta(days=7))
        self._tickers = tickers
        self._timeout = timeout_seconds

        # HTTP session (lazy init)
        self._session = None

    async def initialize(self) -> None:
        """Initialize HTTP session."""
        await super().initialize()

        # Lazy import to avoid hard dependency
        try:
            import httpx

            self._session = httpx.AsyncClient(timeout=self._timeout)
        except ImportError:
            # Fall back to demo mode if httpx not installed
            self._session = None

    async def close(self) -> None:
        """Clean up HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None
        await super().close()

    async def _fetch_items(self) -> list[dict[str, Any]]:
        """Fetch earnings events from Polygon API."""

        if not self._api_key:
            # Demo mode: return mock data
            return self._get_demo_data()

        if self._session is None:
            raise FeedError(
                "HTTP session not initialized. Call initialize() first.",
                source=self.name,
            )

        params = {
            "apiKey": self._api_key,
            "date.gte": self._date_from.isoformat(),
            "date.lte": self._date_to.isoformat(),
            "limit": 1000,  # Max per page
        }

        if self._tickers:
            params["ticker"] = ",".join(self._tickers)

        all_results: list[dict] = []
        next_url: str | None = f"{self.BASE_URL}{self.EARNINGS_ENDPOINT}"

        while next_url:
            try:
                response = await self._session.get(next_url, params=params)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                all_results.extend(results)

                # Handle pagination
                next_url = data.get("next_url")
                params = {}  # next_url includes params

            except Exception as e:
                raise FeedError(
                    f"Polygon API error: {e}",
                    source=self.name,
                    cause=e,
                ) from e

        return all_results

    def _to_candidate(self, item: dict[str, Any]) -> RecordCandidate:
        """Convert Polygon earnings event to RecordCandidate."""

        ticker = item.get("ticker", "")
        report_date = item.get("report_date", "")
        fiscal_period = item.get("fiscal_period", "")
        fiscal_year = item.get("fiscal_year")

        # Generate natural key: ticker-year-quarter
        natural_key = f"polygon:{ticker}:{fiscal_year}:{fiscal_period}".lower()

        # Parse report date
        published_at = datetime.now(UTC)
        if report_date:
            with contextlib.suppress(ValueError):
                published_at = datetime.strptime(report_date, "%Y-%m-%d").replace(tzinfo=UTC)

        # Extract estimates
        eps_estimate = None
        eps_actual = None
        revenue_estimate = None
        revenue_actual = None

        if "eps" in item:
            eps_data = item["eps"]
            eps_estimate = self._to_decimal(eps_data.get("estimated"))
            eps_actual = self._to_decimal(eps_data.get("actual"))

        if "revenue" in item:
            rev_data = item["revenue"]
            revenue_estimate = self._to_decimal(rev_data.get("estimated"))
            revenue_actual = self._to_decimal(rev_data.get("actual"))

        # Build content
        content = {
            "ticker": ticker,
            "company_name": item.get("name", ""),
            "report_date": report_date,
            "report_time": self._normalize_report_time(item.get("time_of_day", "")),
            "fiscal_year": fiscal_year,
            "fiscal_quarter": self._parse_quarter(fiscal_period),
            "fiscal_period": fiscal_period,
            # Estimates
            "eps_estimate": float(eps_estimate) if eps_estimate else None,
            "eps_actual": float(eps_actual) if eps_actual else None,
            "revenue_estimate": float(revenue_estimate) if revenue_estimate else None,
            "revenue_actual": float(revenue_actual) if revenue_actual else None,
            # Analyst info
            "num_analysts": item.get("analyst_count"),
            # Status
            "is_released": eps_actual is not None,
            # Source metadata
            "source_vendor": "polygon",
            "source_feed": "reference/earnings",
        }

        return RecordCandidate(
            natural_key=natural_key,
            published_at=published_at,
            content=content,
            metadata=Metadata(
                source=self.name,
                source_type="polygon.earnings",
                extra={"api_url": f"{self.BASE_URL}{self.EARNINGS_ENDPOINT}?ticker={ticker}"},
            ),
        )

    def _to_decimal(self, value: Any) -> Decimal | None:
        """Safely convert value to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, Exception):
            return None

    def _normalize_report_time(self, time_str: str) -> str:
        """Normalize report time to BMO/AMC/DMH/UNKNOWN."""
        if not time_str:
            return "unknown"
        time_lower = time_str.lower()
        if "before" in time_lower or "bmo" in time_lower:
            return "bmo"
        elif "after" in time_lower or "amc" in time_lower:
            return "amc"
        elif "during" in time_lower or "dmh" in time_lower:
            return "dmh"
        return "unknown"

    def _parse_quarter(self, fiscal_period: str) -> int | None:
        """Parse quarter from fiscal period string (e.g., 'Q4')."""
        if not fiscal_period:
            return None
        fiscal_period = fiscal_period.upper()
        if fiscal_period.startswith("Q") and len(fiscal_period) >= 2:
            try:
                return int(fiscal_period[1])
            except ValueError:
                pass
        return None

    def _get_demo_data(self) -> list[dict[str, Any]]:
        """Return demo data when no API key is configured."""
        return [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "report_date": self._date_from.isoformat(),
                "time_of_day": "AMC",
                "fiscal_year": 2026,
                "fiscal_period": "Q1",
                "eps": {
                    "estimated": 2.35,
                    "actual": None,
                },
                "revenue": {
                    "estimated": 119000000000,
                    "actual": None,
                },
                "analyst_count": 38,
            },
            {
                "ticker": "MSFT",
                "name": "Microsoft Corporation",
                "report_date": self._date_from.isoformat(),
                "time_of_day": "AMC",
                "fiscal_year": 2026,
                "fiscal_period": "Q2",
                "eps": {
                    "estimated": 2.80,
                    "actual": 2.95,
                },
                "revenue": {
                    "estimated": 65000000000,
                    "actual": 66100000000,
                },
                "analyst_count": 42,
            },
            {
                "ticker": "META",
                "name": "Meta Platforms, Inc.",
                "report_date": (self._date_from + timedelta(days=1)).isoformat(),
                "time_of_day": "AMC",
                "fiscal_year": 2026,
                "fiscal_period": "Q4",
                "eps": {
                    "estimated": 5.25,
                    "actual": 5.58,
                },
                "revenue": {
                    "estimated": 38500000000,
                    "actual": 40100000000,
                },
                "analyst_count": 35,
            },
            {
                "ticker": "NVDA",
                "name": "NVIDIA Corporation",
                "report_date": (self._date_from + timedelta(days=2)).isoformat(),
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
            },
            {
                "ticker": "GOOGL",
                "name": "Alphabet Inc.",
                "report_date": (self._date_from + timedelta(days=3)).isoformat(),
                "time_of_day": "BMO",
                "fiscal_year": 2026,
                "fiscal_period": "Q4",
                "eps": {
                    "estimated": 1.85,
                    "actual": None,
                },
                "revenue": {
                    "estimated": 86000000000,
                    "actual": None,
                },
                "analyst_count": 40,
            },
        ]


class PolygonEstimateHistoryAdapter(BaseFeedAdapter):
    """
    Adapter for fetching historical estimate snapshots from Polygon.

    This is critical for the two-timestamp pattern - we need to know
    what the estimate was BEFORE the actual was announced.

    Example:
        adapter = PolygonEstimateHistoryAdapter(
            api_key=os.environ["POLYGON_API_KEY"],
            ticker="AAPL",
            fiscal_year=2024,
            fiscal_quarter=4,
        )

        async for record in adapter.fetch():
            snapshot = record.content
            print(f"As of {snapshot['captured_at']}: EPS est ${snapshot['eps_estimate']}")
    """

    BASE_URL = "https://api.polygon.io"

    def __init__(
        self,
        ticker: str,
        fiscal_year: int,
        fiscal_quarter: int,
        api_key: str | None = None,
        *,
        name: str = "polygon-estimate-history",
        requests_per_second: float = 5.0,
    ):
        """
        Initialize estimate history adapter.

        Args:
            ticker: Stock ticker symbol.
            fiscal_year: Fiscal year.
            fiscal_quarter: Fiscal quarter (1-4).
            api_key: Polygon API key.
            name: Adapter name.
            requests_per_second: Rate limit.
        """
        super().__init__(
            name=name,
            source_url=self.BASE_URL,
            requests_per_second=requests_per_second,
        )

        self._api_key = api_key or os.environ.get("POLYGON_API_KEY", "")
        self._ticker = ticker.upper()
        self._fiscal_year = fiscal_year
        self._fiscal_quarter = fiscal_quarter
        self._session = None

    async def initialize(self) -> None:
        """Initialize HTTP session."""
        await super().initialize()
        try:
            import httpx

            self._session = httpx.AsyncClient(timeout=30.0)
        except ImportError:
            self._session = None

    async def close(self) -> None:
        """Clean up."""
        if self._session:
            await self._session.aclose()
            self._session = None
        await super().close()

    async def _fetch_items(self) -> list[dict[str, Any]]:
        """Fetch estimate history from Polygon."""

        if not self._api_key:
            # Demo mode
            return self._get_demo_history()

        # Note: Polygon's actual API for estimate history may differ
        # This is a placeholder implementation
        return self._get_demo_history()

    def _to_candidate(self, item: dict[str, Any]) -> RecordCandidate:
        """Convert estimate snapshot to RecordCandidate."""

        captured_at = item.get("captured_at", datetime.now(UTC))
        if isinstance(captured_at, str):
            captured_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))

        natural_key = (
            f"polygon:estimate:{self._ticker}:{self._fiscal_year}:Q{self._fiscal_quarter}:"
            f"{captured_at.strftime('%Y%m%d')}"
        ).lower()

        content = {
            "ticker": self._ticker,
            "fiscal_year": self._fiscal_year,
            "fiscal_quarter": self._fiscal_quarter,
            "fiscal_period": f"{self._fiscal_year}:Q{self._fiscal_quarter}",
            "eps_estimate": item.get("eps_estimate"),
            "revenue_estimate": item.get("revenue_estimate"),
            "num_analysts": item.get("num_analysts"),
            "captured_at": captured_at.isoformat(),
            "source_vendor": "polygon",
            "source_feed": "estimate_history",
        }

        return RecordCandidate(
            natural_key=natural_key,
            published_at=captured_at,
            content=content,
            metadata=Metadata(source=self.name),
        )

    def _get_demo_history(self) -> list[dict[str, Any]]:
        """Demo estimate history showing revisions over time."""
        base_date = datetime(self._fiscal_year, 10, 1, tzinfo=UTC)

        return [
            {
                "captured_at": base_date,
                "eps_estimate": 2.05,
                "revenue_estimate": 115_000_000_000,
                "num_analysts": 35,
            },
            {
                "captured_at": base_date + timedelta(days=15),
                "eps_estimate": 2.08,
                "revenue_estimate": 116_500_000_000,
                "num_analysts": 36,
            },
            {
                "captured_at": base_date + timedelta(days=28),
                "eps_estimate": 2.10,
                "revenue_estimate": 117_000_000_000,
                "num_analysts": 38,
            },
        ]
