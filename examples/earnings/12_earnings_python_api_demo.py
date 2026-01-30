#!/usr/bin/env python3
"""
Earnings Python API Demo
========================

Demonstrates the fluent Python API for earnings calendar:
- One-liners for common operations
- Chainable, pandas-like interface
- Async-first but sync wrappers available
- Direct DataFrame export

Run with:
    python 12_earnings_python_api_demo.py

This demo runs standalone with mock data.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import AsyncIterator, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# DOMAIN MODELS (Pydantic - FeedSpine convention)
# =============================================================================


class ReportTime(str, Enum):
    BMO = "BMO"
    AMC = "AMC"
    UNKNOWN = "UNK"


class EventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    RELEASED = "RELEASED"
    DELAYED = "DELAYED"


class SurpriseDirection(str, Enum):
    BEAT = "BEAT"
    MISS = "MISS"
    INLINE = "INLINE"


class EarningsEvent(BaseModel):
    """A single earnings event."""
    model_config = ConfigDict(frozen=True)
    
    ticker: str
    company_name: str
    report_date: str
    report_time: ReportTime = ReportTime.UNKNOWN
    status: EventStatus = EventStatus.SCHEDULED
    sector: str = "Unknown"
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate_mm: Optional[float] = None
    revenue_actual_mm: Optional[float] = None
    ir_url: Optional[str] = None
    press_release_url: Optional[str] = None
    sec_filing_url: Optional[str] = None
    
    @property
    def eps_surprise(self) -> Optional[float]:
        if self.eps_actual is not None and self.eps_estimate:
            return (self.eps_actual - self.eps_estimate) / abs(self.eps_estimate)
        return None
    
    @property
    def surprise_direction(self) -> Optional[SurpriseDirection]:
        s = self.eps_surprise
        if s is None:
            return None
        if s > 0.01:
            return SurpriseDirection.BEAT
        elif s < -0.01:
            return SurpriseDirection.MISS
        return SurpriseDirection.INLINE


class CheckResult(BaseModel):
    """Result of checking a ticker's earnings."""
    model_config = ConfigDict(frozen=True)
    
    ticker: str
    found: bool
    status: Optional[EventStatus] = None
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    surprise: Optional[float] = None
    direction: Optional[SurpriseDirection] = None
    beat: bool = False
    miss: bool = False
    inline: bool = False
    
    def __str__(self) -> str:
        if not self.found:
            return f"{self.ticker}: No data"
        if self.direction:
            sym = "✅" if self.beat else "❌" if self.miss else "➡️"
            return f"{self.ticker} {sym} {self.direction.value}: {self.surprise:+.1%}"
        return f"{self.ticker}: Scheduled (est: ${self.eps_estimate:.2f})"


class CompareResult(BaseModel):
    """Result of comparing estimates vs actuals."""
    model_config = ConfigDict(frozen=True)
    
    ticker: str
    period: str  # e.g., "2026:Q1"
    eps_estimate: float
    eps_actual: float
    eps_surprise: float
    revenue_estimate_mm: Optional[float] = None
    revenue_actual_mm: Optional[float] = None
    revenue_surprise: Optional[float] = None
    beat: bool = False
    miss: bool = False
    
    def __str__(self) -> str:
        symbol = "✅" if self.beat else "❌" if self.miss else "➡️"
        return f"{self.ticker} {self.period}: {symbol} EPS {self.eps_surprise:+.1%} | Rev {self.revenue_surprise:+.1%}" if self.revenue_surprise else f"{self.ticker} {self.period}: {symbol} EPS {self.eps_surprise:+.1%}"


# =============================================================================
# MOCK DATA
# =============================================================================


def _mock_events() -> list[EarningsEvent]:
    """Generate mock earnings events."""
    return [
        EarningsEvent(
            ticker="AAPL", company_name="Apple Inc.", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.SCHEDULED, sector="Technology",
            eps_estimate=2.35, revenue_estimate_mm=124500, ir_url="https://investor.apple.com/"
        ),
        EarningsEvent(
            ticker="META", company_name="Meta Platforms, Inc.", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.RELEASED, sector="Technology",
            eps_estimate=5.25, eps_actual=5.58, revenue_estimate_mm=40100, revenue_actual_mm=41200,
            ir_url="https://investor.fb.com/", press_release_url="https://investor.fb.com/press-releases/"
        ),
        EarningsEvent(
            ticker="MSFT", company_name="Microsoft Corporation", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.SCHEDULED, sector="Technology",
            eps_estimate=2.78, revenue_estimate_mm=62800, ir_url="https://www.microsoft.com/investor/"
        ),
        EarningsEvent(
            ticker="NVDA", company_name="NVIDIA Corporation", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.RELEASED, sector="Technology",
            eps_estimate=4.12, eps_actual=4.65, revenue_estimate_mm=28500, revenue_actual_mm=30800,
            ir_url="https://investor.nvidia.com/"
        ),
        EarningsEvent(
            ticker="JPM", company_name="JPMorgan Chase", report_date="2026-01-30",
            report_time=ReportTime.BMO, status=EventStatus.RELEASED, sector="Financial",
            eps_estimate=4.50, eps_actual=4.42, revenue_estimate_mm=42000, revenue_actual_mm=41500,
            ir_url="https://www.jpmorganchase.com/ir/"
        ),
    ]


# =============================================================================
# FLUENT API - CalendarQuery
# =============================================================================


class CalendarQuery:
    """
    Fluent query builder for earnings calendar.
    
    Usage:
        events = await (
            calendar
            .date("2026-01-30")
            .sector("Technology")
            .with_estimates()
            .execute()
        )
    """
    
    def __init__(self):
        self._date: Optional[str] = None
        self._sector: Optional[str] = None
        self._tickers: Optional[list[str]] = None
        self._status: Optional[EventStatus] = None
        self._include_estimates: bool = False
        self._include_links: bool = False
    
    def date(self, date: str) -> "CalendarQuery":
        """Filter by date (YYYY-MM-DD)."""
        self._date = date
        return self
    
    def today(self) -> "CalendarQuery":
        """Filter to today's events."""
        self._date = datetime.now().strftime("%Y-%m-%d")
        return self
    
    def tomorrow(self) -> "CalendarQuery":
        """Filter to tomorrow's events."""
        self._date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return self
    
    def sector(self, sector: str) -> "CalendarQuery":
        """Filter by sector."""
        self._sector = sector
        return self
    
    def tickers(self, *tickers: str) -> "CalendarQuery":
        """Filter to specific tickers."""
        self._tickers = list(tickers)
        return self
    
    def status(self, status: EventStatus) -> "CalendarQuery":
        """Filter by status."""
        self._status = status
        return self
    
    def released(self) -> "CalendarQuery":
        """Only released events."""
        self._status = EventStatus.RELEASED
        return self
    
    def scheduled(self) -> "CalendarQuery":
        """Only scheduled events."""
        self._status = EventStatus.SCHEDULED
        return self
    
    def with_estimates(self) -> "CalendarQuery":
        """Include estimate data."""
        self._include_estimates = True
        return self
    
    def with_links(self) -> "CalendarQuery":
        """Include IR/PR links."""
        self._include_links = True
        return self
    
    async def execute(self) -> list[EarningsEvent]:
        """Execute the query and return results."""
        # Start with all mock events
        events = _mock_events()
        
        # Apply filters
        if self._sector:
            events = [e for e in events if e.sector == self._sector]
        if self._tickers:
            events = [e for e in events if e.ticker in self._tickers]
        if self._status:
            events = [e for e in events if e.status == self._status]
        
        return events
    
    async def to_dataframe(self):
        """Execute and return as pandas DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_dataframe(). Install with: pip install pandas")
        
        events = await self.execute()
        data = []
        for e in events:
            row = {
                "ticker": e.ticker,
                "company": e.company_name,
                "date": e.report_date,
                "time": e.report_time.value,
                "status": e.status.value,
                "sector": e.sector,
            }
            if self._include_estimates or True:  # Always include for demo
                row["eps_estimate"] = e.eps_estimate
                row["eps_actual"] = e.eps_actual
                row["eps_surprise"] = e.eps_surprise
            if self._include_links:
                row["ir_url"] = e.ir_url
                row["pr_url"] = e.press_release_url
            data.append(row)
        
        return pd.DataFrame(data)
    
    def __await__(self):
        """Allow direct await on query."""
        return self.execute().__await__()


# =============================================================================
# MAIN API CLASS - EarningsCalendar
# =============================================================================


class EarningsCalendar:
    """
    Main entry point for earnings calendar API.
    
    Usage:
        calendar = EarningsCalendar()
        
        # Quick check
        result = await calendar.check("AAPL")
        print(result)  # AAPL ✅ BEAT: +6.3%
        
        # Fluent query
        df = await calendar.date("2026-01-30").sector("Technology").to_dataframe()
    """
    
    def check(self, ticker: str) -> "CheckTask":
        """
        Quick check if a ticker beat or missed.
        
        Returns awaitable CheckResult.
        """
        return CheckTask(ticker)
    
    def date(self, date: str) -> CalendarQuery:
        """Start a query for a specific date."""
        return CalendarQuery().date(date)
    
    def today(self) -> CalendarQuery:
        """Start a query for today."""
        return CalendarQuery().today()
    
    def tomorrow(self) -> CalendarQuery:
        """Start a query for tomorrow."""
        return CalendarQuery().tomorrow()
    
    def sector(self, sector: str) -> CalendarQuery:
        """Start a query filtered by sector."""
        return CalendarQuery().sector(sector)
    
    def tickers(self, *tickers: str) -> CalendarQuery:
        """Start a query for specific tickers."""
        return CalendarQuery().tickers(*tickers)
    
    async def all_released_today(self) -> list[EarningsEvent]:
        """Get all released earnings today."""
        return await self.today().released().execute()


class CheckTask:
    """Awaitable task for checking a ticker."""
    
    def __init__(self, ticker: str):
        self.ticker = ticker
    
    async def _execute(self) -> CheckResult:
        events = _mock_events()
        event = next((e for e in events if e.ticker.upper() == self.ticker.upper()), None)
        
        if event is None:
            return CheckResult(ticker=self.ticker, found=False)
        
        return CheckResult(
            ticker=event.ticker,
            found=True,
            status=event.status,
            eps_estimate=event.eps_estimate,
            eps_actual=event.eps_actual,
            surprise=event.eps_surprise,
            direction=event.surprise_direction,
            beat=event.surprise_direction == SurpriseDirection.BEAT,
            miss=event.surprise_direction == SurpriseDirection.MISS,
            inline=event.surprise_direction == SurpriseDirection.INLINE,
        )
    
    def __await__(self):
        return self._execute().__await__()


# =============================================================================
# COMPARE API
# =============================================================================


class CompareAPI:
    """
    Compare estimates vs actuals.
    
    Usage:
        result = await compare("AAPL", "2026:Q1")
        
        async for result in compare.all(period="2026:Q1"):
            if result.beat:
                print(f"✅ {result.ticker}")
    """
    
    async def __call__(self, ticker: str, period: str = "2026:Q1") -> CompareResult:
        """Compare a single ticker."""
        events = _mock_events()
        event = next((e for e in events if e.ticker.upper() == ticker.upper() and e.status == EventStatus.RELEASED), None)
        
        if event is None:
            raise ValueError(f"No released earnings found for {ticker}")
        
        eps_surprise = event.eps_surprise or 0.0
        rev_surprise = None
        if event.revenue_actual_mm and event.revenue_estimate_mm:
            rev_surprise = (event.revenue_actual_mm - event.revenue_estimate_mm) / event.revenue_estimate_mm
        
        return CompareResult(
            ticker=event.ticker,
            period=period,
            eps_estimate=event.eps_estimate or 0.0,
            eps_actual=event.eps_actual or 0.0,
            eps_surprise=eps_surprise,
            revenue_estimate_mm=event.revenue_estimate_mm,
            revenue_actual_mm=event.revenue_actual_mm,
            revenue_surprise=rev_surprise,
            beat=eps_surprise > 0.01,
            miss=eps_surprise < -0.01,
        )
    
    async def all(self, period: str = "2026:Q1") -> AsyncIterator[CompareResult]:
        """Compare all released earnings for a period."""
        events = _mock_events()
        for event in events:
            if event.status == EventStatus.RELEASED:
                yield await self(event.ticker, period)


# Global instances for convenience
calendar = EarningsCalendar()
compare = CompareAPI()


# =============================================================================
# DEMO
# =============================================================================


async def demo():
    """Run the Python API demo."""
    print("=" * 70)
    print("  📊 EARNINGS PYTHON API DEMO")
    print("=" * 70)
    
    # 1. Quick check - one liner
    print("\n1️⃣  QUICK CHECK (one-liner)")
    print("-" * 40)
    result = await calendar.check("META")
    print(f"   >>> result = await calendar.check('META')")
    print(f"   {result}")
    
    result = await calendar.check("AAPL")
    print(f"\n   >>> result = await calendar.check('AAPL')")
    print(f"   {result}")
    
    # 2. Fluent query
    print("\n\n2️⃣  FLUENT QUERY")
    print("-" * 40)
    print("   >>> events = await calendar.today().sector('Technology').execute()")
    events = await calendar.today().sector("Technology").execute()
    for e in events:
        status_sym = "✅" if e.status == EventStatus.RELEASED else "🕐"
        print(f"   {status_sym} {e.ticker:<6} {e.company_name}")
    
    # 3. Only released
    print("\n\n3️⃣  FILTER: RELEASED ONLY")
    print("-" * 40)
    print("   >>> released = await calendar.today().released().execute()")
    released = await calendar.today().released().execute()
    for e in released:
        print(f"   ✅ {e.ticker:<6} EPS: ${e.eps_actual:.2f} vs ${e.eps_estimate:.2f}")
    
    # 4. DataFrame export
    print("\n\n4️⃣  DATAFRAME EXPORT")
    print("-" * 40)
    print("   >>> df = await calendar.today().with_estimates().to_dataframe()")
    try:
        df = await calendar.today().with_estimates().to_dataframe()
        print(df.to_string(index=False))
    except ImportError:
        print("   (pandas not installed - skipping DataFrame demo)")
    
    # 5. Compare API
    print("\n\n5️⃣  COMPARE ESTIMATES VS ACTUALS")
    print("-" * 40)
    print("   >>> result = await compare('NVDA', '2026:Q1')")
    try:
        result = await compare("NVDA", "2026:Q1")
        print(f"   {result}")
    except ValueError as e:
        print(f"   Error: {e}")
    
    # 6. Batch compare
    print("\n\n6️⃣  BATCH COMPARE (async iteration)")
    print("-" * 40)
    print("   >>> async for result in compare.all(period='2026:Q1'):")
    print("   ...     if result.beat: print(result)")
    async for result in compare.all(period="2026:Q1"):
        if result.beat:
            print(f"   {result}")
    
    # 7. Beat/miss flags
    print("\n\n7️⃣  BEAT/MISS FLAGS")
    print("-" * 40)
    print("   >>> result = await calendar.check('JPM')")
    result = await calendar.check("JPM")
    print(f"   result.beat  = {result.beat}")
    print(f"   result.miss  = {result.miss}")
    print(f"   result.inline = {result.inline}")
    
    # Summary
    print("\n")
    print("=" * 70)
    print("  ✅ DEMO COMPLETE")
    print("=" * 70)
    print("""
Key API Patterns:
    
    # Quick check
    result = await calendar.check("AAPL")
    
    # Fluent query  
    events = await calendar.today().sector("Tech").execute()
    
    # DataFrame export
    df = await calendar.today().to_dataframe()
    
    # Compare
    result = await compare("AAPL", "2026:Q1")
    
    # Batch iterate
    async for r in compare.all():
        print(r)
""")


if __name__ == "__main__":
    asyncio.run(demo())
