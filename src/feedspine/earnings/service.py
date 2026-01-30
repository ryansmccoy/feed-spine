"""
Earnings Calendar Service - Professional API with full customization.

This is the main entry point for earnings operations. It provides:
- Well-named methods with clear parameters
- Full customization via kwargs
- Consistent return types
- Integration with spine-core pipelines

Follows spine-core conventions:
- fetch_*: Async retrieval from external sources
- get_*: Synchronous/cached retrieval  
- compute_*: Calculations
- store_*: Persistence operations

Example:
    from feedspine.earnings import EarningsCalendarService
    
    service = EarningsCalendarService()
    
    # Fetch with full customization
    result = await service.fetch_calendar(
        target_date=date(2026, 1, 30),
        sources=["sec", "finnhub"],
        include_estimates=True,
        sectors=["Technology"],
    )
    
    # Watch for releases
    async for event in service.watch_releases(
        tickers=["AAPL", "MSFT"],
        poll_interval_seconds=30,
    ):
        print(f"🔔 {event.ticker} released!")
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Awaitable

from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    import pandas as pd


# =============================================================================
# ENUMS
# =============================================================================


class EventStatus(str, Enum):
    """Status of an earnings event."""
    SCHEDULED = "SCHEDULED"
    RELEASED = "RELEASED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"


class ReportTime(str, Enum):
    """When earnings are typically released."""
    BMO = "BMO"  # Before Market Open
    AMC = "AMC"  # After Market Close
    UNKNOWN = "UNKNOWN"


class SurpriseDirection(str, Enum):
    """Direction of earnings surprise."""
    BEAT = "BEAT"
    MISS = "MISS"
    INLINE = "INLINE"


# =============================================================================
# MODELS
# =============================================================================


class EventLinks(BaseModel):
    """Links associated with an earnings event."""
    model_config = ConfigDict(frozen=True)
    
    ir_url: str | None = None
    press_release_url: str | None = None
    sec_filing_url: str | None = None
    webcast_url: str | None = None
    transcript_url: str | None = None


class CalendarEvent(BaseModel):
    """A single earnings calendar event."""
    model_config = ConfigDict(frozen=True)
    
    # Identity
    ticker: str
    company_name: str
    entity_id: str | None = None
    
    # Timing
    report_date: date
    report_time: ReportTime = ReportTime.UNKNOWN
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    
    # Status
    status: EventStatus = EventStatus.SCHEDULED
    
    # Estimates (populated if include_estimates=True)
    eps_estimate: Decimal | None = None
    revenue_estimate: Decimal | None = None
    estimate_source: str | None = None
    num_estimates: int | None = None
    
    # Actuals (populated when status=RELEASED)
    eps_actual: Decimal | None = None
    revenue_actual: Decimal | None = None
    actual_source: str | None = None
    released_at: datetime | None = None
    
    # Links (populated if include_links=True)
    links: EventLinks = Field(default_factory=EventLinks)
    
    # Source tracking
    source: str = ""
    source_priority: int = 0
    
    @property
    def fiscal_period(self) -> str | None:
        """Fiscal period string (e.g., '2026:Q1')."""
        if self.fiscal_year and self.fiscal_quarter:
            return f"{self.fiscal_year}:Q{self.fiscal_quarter}"
        return None
    
    @property
    def eps_surprise(self) -> Decimal | None:
        """EPS surprise as percentage."""
        if self.eps_actual is not None and self.eps_estimate:
            return (self.eps_actual - self.eps_estimate) / abs(self.eps_estimate)
        return None
    
    @property
    def eps_direction(self) -> SurpriseDirection | None:
        """EPS surprise direction."""
        s = self.eps_surprise
        if s is None:
            return None
        if s > Decimal("0.01"):
            return SurpriseDirection.BEAT
        elif s < Decimal("-0.01"):
            return SurpriseDirection.MISS
        return SurpriseDirection.INLINE
    
    @property
    def revenue_surprise(self) -> Decimal | None:
        """Revenue surprise as percentage."""
        if self.revenue_actual is not None and self.revenue_estimate:
            return (self.revenue_actual - self.revenue_estimate) / abs(self.revenue_estimate)
        return None


@dataclass(frozen=True)
class CalendarResult:
    """Result from calendar fetch operations."""
    
    target_date: date
    events: tuple[CalendarEvent, ...]
    sources_queried: tuple[str, ...] = ()
    sources_succeeded: tuple[str, ...] = ()
    sources_failed: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    fetch_duration_ms: float = 0.0
    cached: bool = False
    captured_at: datetime = field(default_factory=datetime.now)
    
    @property
    def event_count(self) -> int:
        return len(self.events)
    
    @property
    def released_count(self) -> int:
        return sum(1 for e in self.events if e.status == EventStatus.RELEASED)
    
    @property
    def scheduled_count(self) -> int:
        return sum(1 for e in self.events if e.status == EventStatus.SCHEDULED)
    
    def filter(
        self,
        *,
        status: EventStatus | None = None,
        tickers: list[str] | None = None,
        sectors: list[str] | None = None,
        min_market_cap: float | None = None,
    ) -> "CalendarResult":
        """Return filtered copy of results."""
        events = list(self.events)
        
        if status:
            events = [e for e in events if e.status == status]
        if tickers:
            ticker_set = {t.upper() for t in tickers}
            events = [e for e in events if e.ticker.upper() in ticker_set]
        
        return CalendarResult(
            target_date=self.target_date,
            events=tuple(events),
            sources_queried=self.sources_queried,
            sources_succeeded=self.sources_succeeded,
            sources_failed=self.sources_failed,
            errors=self.errors,
            fetch_duration_ms=self.fetch_duration_ms,
            cached=self.cached,
            captured_at=self.captured_at,
        )
    
    def to_dataframe(self) -> "pd.DataFrame":
        """Convert to pandas DataFrame."""
        import pandas as pd
        
        data = []
        for e in self.events:
            data.append({
                "ticker": e.ticker,
                "company_name": e.company_name,
                "entity_id": e.entity_id,
                "report_date": e.report_date,
                "report_time": e.report_time.value,
                "fiscal_period": e.fiscal_period,
                "status": e.status.value,
                "eps_estimate": float(e.eps_estimate) if e.eps_estimate else None,
                "eps_actual": float(e.eps_actual) if e.eps_actual else None,
                "eps_surprise": float(e.eps_surprise) if e.eps_surprise else None,
                "eps_direction": e.eps_direction.value if e.eps_direction else None,
                "revenue_estimate": float(e.revenue_estimate) if e.revenue_estimate else None,
                "revenue_actual": float(e.revenue_actual) if e.revenue_actual else None,
                "source": e.source,
            })
        
        return pd.DataFrame(data)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "target_date": self.target_date.isoformat(),
            "event_count": self.event_count,
            "released_count": self.released_count,
            "scheduled_count": self.scheduled_count,
            "sources_queried": list(self.sources_queried),
            "sources_succeeded": list(self.sources_succeeded),
            "sources_failed": list(self.sources_failed),
            "fetch_duration_ms": self.fetch_duration_ms,
            "cached": self.cached,
            "events": [e.model_dump() for e in self.events],
        }


@dataclass(frozen=True)
class SurpriseResult:
    """Result from surprise calculation."""
    
    entity_id: str
    ticker: str
    period: str
    
    # EPS
    eps_estimate: Decimal | None = None
    eps_actual: Decimal | None = None
    eps_surprise: Decimal | None = None
    eps_direction: SurpriseDirection | None = None
    
    # Revenue
    revenue_estimate: Decimal | None = None
    revenue_actual: Decimal | None = None
    revenue_surprise: Decimal | None = None
    revenue_direction: SurpriseDirection | None = None
    
    # Metadata
    estimate_source: str | None = None
    actual_source: str | None = None
    computed_at: datetime = field(default_factory=datetime.now)
    
    @property
    def beat_eps(self) -> bool:
        return self.eps_direction == SurpriseDirection.BEAT
    
    @property
    def miss_eps(self) -> bool:
        return self.eps_direction == SurpriseDirection.MISS
    
    @property
    def beat_revenue(self) -> bool:
        return self.revenue_direction == SurpriseDirection.BEAT


@dataclass(frozen=True)
class StoreResult:
    """Result from storage operations."""
    
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    capture_id: str = ""
    duration_ms: float = 0.0


# =============================================================================
# CONNECTORS (Base classes for real implementations)
# =============================================================================


class BaseConnector:
    """Base class for data source connectors."""
    
    name: str = ""
    priority: int = 0  # Lower = higher authority
    
    async def fetch_calendar(
        self,
        target_date: date,
        *,
        timeout_seconds: float = 30.0,
    ) -> list[CalendarEvent]:
        """Fetch calendar events from this source."""
        raise NotImplementedError
    
    async def check_releases(
        self,
        events: list[CalendarEvent],
    ) -> list[CalendarEvent]:
        """Check for new releases among scheduled events."""
        raise NotImplementedError


# =============================================================================
# SERVICE
# =============================================================================


class EarningsCalendarService:
    """
    Professional API for earnings calendar operations.
    
    Provides:
    - fetch_*: Async retrieval from external sources
    - get_*: Synchronous/cached retrieval
    - compute_*: Calculations (surprise, etc.)
    - store_*: Persistence operations
    - watch_*: Real-time monitoring
    
    All methods support extensive customization via parameters.
    
    Example:
        service = EarningsCalendarService()
        
        # Basic usage
        result = await service.fetch_calendar(date.today())
        
        # Full customization
        result = await service.fetch_calendar(
            target_date=date(2026, 1, 30),
            sources=["sec", "finnhub"],
            include_estimates=True,
            include_links=True,
            sectors=["Technology", "Financial"],
            min_market_cap=1_000_000_000,
            timeout_seconds=60,
        )
    """
    
    def __init__(
        self,
        connectors: list[BaseConnector] | None = None,
        # entity_resolver: EntityResolver | None = None,  # Future: EntitySpine integration
        # storage: StorageBackend | None = None,  # Future: FeedSpine storage
        cache_ttl_minutes: int = 60,
    ):
        """
        Initialize the service.
        
        Args:
            connectors: Data source connectors (default: mock connectors).
            cache_ttl_minutes: Cache TTL in minutes.
        """
        self._connectors = connectors or self._get_default_connectors()
        self._cache: dict[str, tuple[CalendarResult, datetime]] = {}
        self._cache_ttl = timedelta(minutes=cache_ttl_minutes)
    
    def _get_default_connectors(self) -> list[BaseConnector]:
        """Get default connectors (mock for demo)."""
        return [MockSECConnector(), MockFinnhubConnector()]
    
    # =========================================================================
    # CALENDAR RETRIEVAL
    # =========================================================================
    
    async def fetch_calendar(
        self,
        target_date: date,
        *,
        sources: list[str] | None = None,
        include_estimates: bool = True,
        include_links: bool = True,
        entity_ids: list[str] | None = None,
        tickers: list[str] | None = None,
        sectors: list[str] | None = None,
        min_market_cap: float | None = None,
        max_results: int | None = None,
        timeout_seconds: float = 30.0,
        use_cache: bool = True,
    ) -> CalendarResult:
        """
        Fetch earnings calendar from configured sources.
        
        This is the primary method for getting calendar data. It:
        1. Queries all requested sources in parallel
        2. Deduplicates by ticker using source priority
        3. Optionally enriches with estimates and links
        4. Applies filters
        
        Args:
            target_date: The calendar date to fetch.
            sources: Source names to query (default: all configured).
            include_estimates: Include consensus estimate data.
            include_links: Include IR/PR/SEC filing links.
            entity_ids: Filter to specific EntitySpine IDs.
            tickers: Filter to specific ticker symbols.
            sectors: Filter to specific sectors.
            min_market_cap: Minimum market cap filter (USD).
            max_results: Maximum events to return.
            timeout_seconds: Request timeout per source.
            use_cache: Use cached results if fresh.
            
        Returns:
            CalendarResult containing events and metadata.
            
        Example:
            # Fetch all tech earnings for a date
            result = await service.fetch_calendar(
                date(2026, 1, 30),
                sectors=["Technology"],
                include_estimates=True,
            )
            
            print(f"Found {result.event_count} events")
            for event in result.events:
                if event.status == EventStatus.RELEASED:
                    print(f"{event.ticker}: {event.eps_direction}")
        """
        start_time = datetime.now()
        
        # Check cache
        cache_key = f"{target_date}:{sources}:{tickers}"
        if use_cache and cache_key in self._cache:
            cached, cached_at = self._cache[cache_key]
            if datetime.now() - cached_at < self._cache_ttl:
                return CalendarResult(
                    target_date=cached.target_date,
                    events=cached.events,
                    sources_queried=cached.sources_queried,
                    sources_succeeded=cached.sources_succeeded,
                    sources_failed=cached.sources_failed,
                    fetch_duration_ms=0.0,
                    cached=True,
                    captured_at=cached.captured_at,
                )
        
        # Determine which connectors to use
        connectors = self._connectors
        if sources:
            source_set = {s.lower() for s in sources}
            connectors = [c for c in connectors if c.name.lower() in source_set]
        
        # Fetch from all sources in parallel
        sources_queried = [c.name for c in connectors]
        sources_succeeded = []
        sources_failed = []
        errors = []
        all_events: list[CalendarEvent] = []
        
        async def fetch_one(connector: BaseConnector) -> list[CalendarEvent]:
            try:
                events = await asyncio.wait_for(
                    connector.fetch_calendar(target_date, timeout_seconds=timeout_seconds),
                    timeout=timeout_seconds,
                )
                sources_succeeded.append(connector.name)
                return events
            except Exception as e:
                sources_failed.append(connector.name)
                errors.append(f"{connector.name}: {e}")
                return []
        
        tasks = [fetch_one(c) for c in connectors]
        results = await asyncio.gather(*tasks)
        
        for events in results:
            all_events.extend(events)
        
        # Deduplicate by ticker (prefer higher priority source)
        seen: dict[str, CalendarEvent] = {}
        for event in sorted(all_events, key=lambda e: e.source_priority):
            if event.ticker not in seen:
                seen[event.ticker] = event
        
        events = list(seen.values())
        
        # Apply filters
        if tickers:
            ticker_set = {t.upper() for t in tickers}
            events = [e for e in events if e.ticker.upper() in ticker_set]
        
        if sectors:
            # Would need sector data from EntitySpine
            pass
        
        if max_results:
            events = events[:max_results]
        
        # Sort by ticker for consistent output
        events.sort(key=lambda e: e.ticker)
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        result = CalendarResult(
            target_date=target_date,
            events=tuple(events),
            sources_queried=tuple(sources_queried),
            sources_succeeded=tuple(sources_succeeded),
            sources_failed=tuple(sources_failed),
            errors=tuple(errors),
            fetch_duration_ms=duration_ms,
            cached=False,
        )
        
        # Cache result
        if use_cache:
            self._cache[cache_key] = (result, datetime.now())
        
        return result
    
    async def fetch_calendar_range(
        self,
        start_date: date,
        end_date: date,
        *,
        batch_size: int = 7,
        **kwargs,
    ) -> AsyncIterator[CalendarResult]:
        """
        Fetch calendar for a date range.
        
        Yields results as each batch completes, allowing streaming processing.
        
        Args:
            start_date: Start of range (inclusive).
            end_date: End of range (inclusive).
            batch_size: Days per batch (default: 7).
            **kwargs: Passed to fetch_calendar.
            
        Yields:
            CalendarResult for each date.
            
        Example:
            async for result in service.fetch_calendar_range(
                date(2026, 1, 1),
                date(2026, 1, 31),
            ):
                print(f"{result.target_date}: {result.event_count} events")
        """
        current = start_date
        while current <= end_date:
            yield await self.fetch_calendar(current, **kwargs)
            current += timedelta(days=1)
    
    def get_calendar_cached(
        self,
        target_date: date,
        *,
        max_age_minutes: int | None = None,
    ) -> CalendarResult | None:
        """
        Get calendar from cache if available and fresh.
        
        Args:
            target_date: Target date.
            max_age_minutes: Maximum cache age (default: service TTL).
            
        Returns:
            Cached result or None if stale/missing.
        """
        cache_key = f"{target_date}:None:None"
        if cache_key not in self._cache:
            return None
        
        cached, cached_at = self._cache[cache_key]
        ttl = timedelta(minutes=max_age_minutes) if max_age_minutes else self._cache_ttl
        
        if datetime.now() - cached_at > ttl:
            return None
        
        return cached
    
    # =========================================================================
    # RELEASE MONITORING
    # =========================================================================
    
    async def watch_releases(
        self,
        target_date: date | None = None,
        *,
        poll_interval_seconds: float = 60.0,
        on_release: Callable[[CalendarEvent], Awaitable[None]] | None = None,
        tickers: list[str] | None = None,
        stop_after: timedelta | None = None,
    ) -> AsyncIterator[CalendarEvent]:
        """
        Watch for earnings releases in real-time.
        
        Polls sources at the specified interval and yields newly released events.
        
        Args:
            target_date: Date to watch (default: today).
            poll_interval_seconds: Polling interval.
            on_release: Optional callback for each release.
            tickers: Filter to specific tickers.
            stop_after: Stop watching after this duration.
            
        Yields:
            CalendarEvent for each newly detected release.
            
        Example:
            async for event in service.watch_releases(
                tickers=["AAPL", "MSFT"],
                poll_interval_seconds=30,
            ):
                print(f"🔔 {event.ticker} released! EPS: ${event.eps_actual}")
        """
        target_date = target_date or date.today()
        seen_released: set[str] = set()
        start_time = datetime.now()
        
        while True:
            # Check stop condition
            if stop_after and datetime.now() - start_time > stop_after:
                break
            
            # Fetch current calendar
            result = await self.fetch_calendar(
                target_date,
                tickers=tickers,
                use_cache=False,
            )
            
            # Find new releases
            for event in result.events:
                if event.status == EventStatus.RELEASED and event.ticker not in seen_released:
                    seen_released.add(event.ticker)
                    
                    if on_release:
                        await on_release(event)
                    
                    yield event
            
            # Wait before next poll
            await asyncio.sleep(poll_interval_seconds)
    
    # =========================================================================
    # COMPARISON OPERATIONS
    # =========================================================================
    
    async def compute_surprise(
        self,
        entity_id: str,
        period: str,
        *,
        estimate_source: str | None = None,
        actual_source: str | None = None,
    ) -> SurpriseResult:
        """
        Compute earnings surprise for an entity.
        
        Args:
            entity_id: EntitySpine entity ID.
            period: Fiscal period (e.g., "2026:Q1").
            estimate_source: Preferred estimate source.
            actual_source: Preferred actual source.
            
        Returns:
            SurpriseResult with beat/miss analysis.
        """
        # In real implementation, this would query FeedSpine observations
        # For now, return mock result
        return SurpriseResult(
            entity_id=entity_id,
            ticker="AAPL",  # Would resolve from EntitySpine
            period=period,
            eps_estimate=Decimal("2.35"),
            eps_actual=Decimal("2.50"),
            eps_surprise=Decimal("0.064"),
            eps_direction=SurpriseDirection.BEAT,
        )
    
    async def compute_surprise_batch(
        self,
        entity_ids: list[str],
        period: str,
        *,
        concurrency: int = 10,
        **kwargs,
    ) -> AsyncIterator[SurpriseResult]:
        """
        Compute surprises for multiple entities.
        
        Args:
            entity_ids: List of entity IDs.
            period: Fiscal period.
            concurrency: Max concurrent computations.
            **kwargs: Passed to compute_surprise.
            
        Yields:
            SurpriseResult for each entity.
        """
        sem = asyncio.Semaphore(concurrency)
        
        async def compute_one(entity_id: str) -> SurpriseResult:
            async with sem:
                return await self.compute_surprise(entity_id, period, **kwargs)
        
        tasks = [compute_one(eid) for eid in entity_ids]
        for coro in asyncio.as_completed(tasks):
            yield await coro
    
    # =========================================================================
    # STORAGE OPERATIONS
    # =========================================================================
    
    async def store_calendar(
        self,
        result: CalendarResult,
        *,
        upsert: bool = True,
        capture_id: str | None = None,
    ) -> StoreResult:
        """
        Persist calendar to storage.
        
        Args:
            result: Calendar result to store.
            upsert: Update existing records.
            capture_id: Tracking ID for provenance.
            
        Returns:
            StoreResult with counts.
        """
        # In real implementation, this would persist to FeedSpine
        return StoreResult(
            records_inserted=len(result.events),
            records_updated=0,
            records_skipped=0,
            capture_id=capture_id or f"calendar:{result.target_date}",
        )


# =============================================================================
# MOCK CONNECTORS (for demo/testing)
# =============================================================================


class MockSECConnector(BaseConnector):
    """Mock SEC EDGAR connector."""
    
    name = "sec"
    priority = 1  # Highest authority
    
    async def fetch_calendar(
        self,
        target_date: date,
        *,
        timeout_seconds: float = 30.0,
    ) -> list[CalendarEvent]:
        await asyncio.sleep(0.1)  # Simulate network
        return [
            CalendarEvent(
                ticker="AAPL",
                company_name="Apple Inc.",
                report_date=target_date,
                report_time=ReportTime.AMC,
                status=EventStatus.SCHEDULED,
                eps_estimate=Decimal("2.35"),
                source="sec",
                source_priority=1,
                links=EventLinks(
                    ir_url="https://investor.apple.com/",
                    sec_filing_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=AAPL",
                ),
            ),
            CalendarEvent(
                ticker="MSFT",
                company_name="Microsoft Corporation",
                report_date=target_date,
                report_time=ReportTime.AMC,
                status=EventStatus.SCHEDULED,
                eps_estimate=Decimal("2.78"),
                source="sec",
                source_priority=1,
                links=EventLinks(ir_url="https://www.microsoft.com/investor/"),
            ),
        ]


class MockFinnhubConnector(BaseConnector):
    """Mock Finnhub connector."""
    
    name = "finnhub"
    priority = 2
    
    async def fetch_calendar(
        self,
        target_date: date,
        *,
        timeout_seconds: float = 30.0,
    ) -> list[CalendarEvent]:
        await asyncio.sleep(0.1)
        return [
            CalendarEvent(
                ticker="META",
                company_name="Meta Platforms, Inc.",
                report_date=target_date,
                report_time=ReportTime.AMC,
                status=EventStatus.RELEASED,
                eps_estimate=Decimal("5.25"),
                eps_actual=Decimal("5.58"),
                released_at=datetime.now(),
                source="finnhub",
                source_priority=2,
                links=EventLinks(
                    ir_url="https://investor.fb.com/",
                    press_release_url="https://investor.fb.com/press-releases/",
                ),
            ),
            CalendarEvent(
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                report_date=target_date,
                report_time=ReportTime.AMC,
                status=EventStatus.RELEASED,
                eps_estimate=Decimal("4.12"),
                eps_actual=Decimal("4.65"),
                released_at=datetime.now(),
                source="finnhub",
                source_priority=2,
                links=EventLinks(ir_url="https://investor.nvidia.com/"),
            ),
            CalendarEvent(
                ticker="AAPL",  # Duplicate - will be deduplicated
                company_name="Apple Inc.",
                report_date=target_date,
                report_time=ReportTime.AMC,
                status=EventStatus.SCHEDULED,
                eps_estimate=Decimal("2.40"),  # Different estimate
                source="finnhub",
                source_priority=2,
            ),
        ]


# =============================================================================
# CONVENIENCE FUNCTIONS (top-level API)
# =============================================================================


_default_service: EarningsCalendarService | None = None


def get_service() -> EarningsCalendarService:
    """Get or create default service instance."""
    global _default_service
    if _default_service is None:
        _default_service = EarningsCalendarService()
    return _default_service


async def fetch_calendar(target_date: date, **kwargs) -> CalendarResult:
    """
    Fetch earnings calendar (convenience function).
    
    See EarningsCalendarService.fetch_calendar for full documentation.
    """
    return await get_service().fetch_calendar(target_date, **kwargs)


async def watch_releases(**kwargs) -> AsyncIterator[CalendarEvent]:
    """
    Watch for earnings releases (convenience function).
    
    See EarningsCalendarService.watch_releases for full documentation.
    """
    async for event in get_service().watch_releases(**kwargs):
        yield event


# =============================================================================
# DEMO
# =============================================================================


async def demo():
    """Demonstrate the service API."""
    print("=" * 70)
    print("  📊 EARNINGS CALENDAR SERVICE DEMO")
    print("=" * 70)
    
    service = EarningsCalendarService()
    
    # 1. Basic fetch
    print("\n1️⃣  BASIC FETCH")
    print("-" * 40)
    result = await service.fetch_calendar(date.today())
    print(f"   Events: {result.event_count}")
    print(f"   Released: {result.released_count}")
    print(f"   Scheduled: {result.scheduled_count}")
    print(f"   Sources: {result.sources_queried}")
    print(f"   Duration: {result.fetch_duration_ms:.1f}ms")
    
    # 2. With filters
    print("\n2️⃣  WITH FILTERS")
    print("-" * 40)
    result = await service.fetch_calendar(
        date.today(),
        tickers=["AAPL", "META"],
        include_estimates=True,
    )
    for event in result.events:
        status = "✅" if event.status == EventStatus.RELEASED else "🕐"
        print(f"   {status} {event.ticker}: EPS est ${event.eps_estimate}")
    
    # 3. Released only
    print("\n3️⃣  RELEASED ONLY")
    print("-" * 40)
    released = result.filter(status=EventStatus.RELEASED)
    for event in released.events:
        direction = event.eps_direction.value if event.eps_direction else "N/A"
        surprise = f"{float(event.eps_surprise)*100:+.1f}%" if event.eps_surprise else "N/A"
        print(f"   {event.ticker}: {direction} ({surprise})")
    
    # 4. DataFrame export
    print("\n4️⃣  DATAFRAME EXPORT")
    print("-" * 40)
    try:
        df = result.to_dataframe()
        print(df[["ticker", "status", "eps_estimate", "eps_actual"]].to_string(index=False))
    except ImportError:
        print("   (pandas not installed)")
    
    # 5. Cached access
    print("\n5️⃣  CACHED ACCESS")
    print("-" * 40)
    cached = service.get_calendar_cached(date.today())
    print(f"   Cached: {cached is not None}")
    if cached:
        print(f"   Events: {cached.event_count}")
    
    print("\n" + "=" * 70)
    print("  ✅ DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
