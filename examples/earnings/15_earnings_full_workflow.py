#!/usr/bin/env python3
"""
Full Earnings Workflow Demo
===========================

End-to-end demonstration of the complete earnings feature:

1. LOAD: Fetch earnings calendar from multiple sources
2. RESOLVE: Match tickers to entities (EntitySpine)
3. ENRICH: Load estimates from various sources
4. STORE: Save observations to FeedSpine
5. WATCH: Monitor for releases in real-time
6. COMPARE: Calculate beat/miss when results arrive
7. ALERT: Notify via preferred channel
8. EXPORT: Generate reports and dashboards

This demo shows how ALL the pieces fit together.

Run with:
    python 15_earnings_full_workflow.py
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, AsyncIterator, Callable
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# DOMAIN MODELS
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


class CalendarEvent(BaseModel):
    """An earnings calendar event."""
    model_config = ConfigDict(frozen=True)
    
    ticker: str
    company_name: str
    report_date: str
    report_time: ReportTime = ReportTime.UNKNOWN
    status: EventStatus = EventStatus.SCHEDULED
    entity_id: Optional[str] = None  # Link to EntitySpine
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
    
    def with_actuals(self, eps: float, revenue_mm: Optional[float] = None) -> "CalendarEvent":
        """Return new event with actuals filled in."""
        return CalendarEvent(
            **{
                **self.model_dump(),
                "status": EventStatus.RELEASED,
                "eps_actual": eps,
                "revenue_actual_mm": revenue_mm or self.revenue_actual_mm,
            }
        )


class Observation(BaseModel):
    """A FeedSpine observation record."""
    model_config = ConfigDict(frozen=True)
    
    observation_id: str
    entity_id: str
    metric: str
    value: float
    period: str
    source: str
    observed_at: str
    as_of: Optional[str] = None


class AlertConfig(BaseModel):
    """Configuration for earnings alerts."""
    tickers: Optional[list[str]] = None
    min_surprise: float = 0.0
    directions: list[SurpriseDirection] = [SurpriseDirection.BEAT, SurpriseDirection.MISS]


# =============================================================================
# SIMULATED SERVICES
# =============================================================================


class CalendarService:
    """Fetches earnings calendar from multiple sources."""
    
    async def get_calendar(self, date: str) -> list[CalendarEvent]:
        """Get calendar for a date."""
        print(f"    📅 Fetching calendar for {date}...")
        await asyncio.sleep(0.3)  # Simulate API call
        
        return [
            CalendarEvent(
                ticker="AAPL", company_name="Apple Inc.", report_date=date,
                report_time=ReportTime.AMC, status=EventStatus.SCHEDULED,
                eps_estimate=2.35, revenue_estimate_mm=124500,
                ir_url="https://investor.apple.com/"
            ),
            CalendarEvent(
                ticker="META", company_name="Meta Platforms, Inc.", report_date=date,
                report_time=ReportTime.AMC, status=EventStatus.SCHEDULED,
                eps_estimate=5.25, revenue_estimate_mm=40100,
                ir_url="https://investor.fb.com/"
            ),
            CalendarEvent(
                ticker="MSFT", company_name="Microsoft Corporation", report_date=date,
                report_time=ReportTime.AMC, status=EventStatus.SCHEDULED,
                eps_estimate=2.78, revenue_estimate_mm=62800,
                ir_url="https://www.microsoft.com/investor/"
            ),
        ]


class EntityResolver:
    """Resolves tickers to EntitySpine entities."""
    
    _entity_map = {
        "AAPL": "01HXYZ-APPLE",
        "META": "01HXYZ-META",
        "MSFT": "01HXYZ-MSFT",
    }
    
    async def resolve(self, ticker: str) -> Optional[str]:
        """Resolve ticker to entity ID."""
        await asyncio.sleep(0.1)
        return self._entity_map.get(ticker.upper())
    
    async def resolve_batch(self, tickers: list[str]) -> dict[str, str]:
        """Resolve multiple tickers."""
        print(f"    🔗 Resolving {len(tickers)} tickers to entities...")
        await asyncio.sleep(0.2)
        return {t: self._entity_map.get(t.upper(), f"UNKNOWN-{t}") for t in tickers}


class EstimateService:
    """Fetches consensus estimates from data providers."""
    
    async def get_estimates(self, tickers: list[str], period: str) -> dict[str, dict]:
        """Get estimates for tickers."""
        print(f"    📊 Fetching estimates for {len(tickers)} tickers...")
        await asyncio.sleep(0.3)
        
        return {
            "AAPL": {"eps": 2.35, "revenue_mm": 124500, "source": "FactSet"},
            "META": {"eps": 5.25, "revenue_mm": 40100, "source": "Bloomberg"},
            "MSFT": {"eps": 2.78, "revenue_mm": 62800, "source": "FactSet"},
        }


class ObservationStore:
    """FeedSpine observation storage."""
    
    def __init__(self):
        self.observations: list[Observation] = []
    
    async def store(self, obs: Observation) -> None:
        """Store an observation."""
        self.observations.append(obs)
    
    async def store_batch(self, observations: list[Observation]) -> int:
        """Store multiple observations."""
        self.observations.extend(observations)
        return len(observations)
    
    async def get_latest(self, entity_id: str, metric: str) -> Optional[Observation]:
        """Get latest observation for entity/metric."""
        matches = [o for o in self.observations if o.entity_id == entity_id and o.metric == metric]
        return matches[-1] if matches else None


class ReleaseMonitor:
    """Monitors for earnings releases in real-time."""
    
    async def watch(self, events: list[CalendarEvent]) -> AsyncIterator[CalendarEvent]:
        """Watch for releases. Yields updated events when releases detected."""
        print("    👀 Monitoring for releases...")
        
        # Simulate releases arriving
        simulated_releases = [
            ("META", 5.58, 41200, 3),  # ticker, eps, rev, delay_seconds
            ("MSFT", 2.95, 64500, 5),
        ]
        
        for ticker, eps, rev, delay in simulated_releases:
            await asyncio.sleep(delay)
            event = next((e for e in events if e.ticker == ticker), None)
            if event:
                yield event.with_actuals(eps, rev)


class AlertService:
    """Sends alerts when earnings are released."""
    
    def __init__(self, config: AlertConfig):
        self.config = config
        self.handlers: list[Callable] = []
    
    def on_release(self, handler: Callable) -> None:
        """Register a release handler."""
        self.handlers.append(handler)
    
    async def process(self, event: CalendarEvent) -> None:
        """Process a release event."""
        # Check filters
        if self.config.tickers and event.ticker not in self.config.tickers:
            return
        
        surprise = event.eps_surprise
        if surprise and abs(surprise) < self.config.min_surprise:
            return
        
        direction = event.surprise_direction
        if direction and direction not in self.config.directions:
            return
        
        # Call handlers
        for handler in self.handlers:
            await handler(event) if asyncio.iscoroutinefunction(handler) else handler(event)


class ReportGenerator:
    """Generates earnings reports and exports."""
    
    async def generate_summary(self, events: list[CalendarEvent]) -> str:
        """Generate summary report."""
        lines = ["EARNINGS SUMMARY", "=" * 60, ""]
        
        released = [e for e in events if e.status == EventStatus.RELEASED]
        scheduled = [e for e in events if e.status == EventStatus.SCHEDULED]
        
        lines.append(f"📊 Released: {len(released)} | Scheduled: {len(scheduled)}")
        lines.append("")
        
        beats = [e for e in released if e.surprise_direction == SurpriseDirection.BEAT]
        misses = [e for e in released if e.surprise_direction == SurpriseDirection.MISS]
        
        lines.append(f"✅ Beats: {len(beats)} | ❌ Misses: {len(misses)}")
        lines.append("")
        
        for e in released:
            sym = "✅" if e.surprise_direction == SurpriseDirection.BEAT else "❌" if e.surprise_direction == SurpriseDirection.MISS else "➡️"
            lines.append(f"  {sym} {e.ticker:<6} ${e.eps_actual:.2f} vs ${e.eps_estimate:.2f} ({e.eps_surprise:+.1%})")
        
        return "\n".join(lines)
    
    async def export_csv(self, events: list[CalendarEvent]) -> str:
        """Export to CSV format."""
        lines = ["ticker,company,date,time,status,eps_est,eps_act,surprise"]
        for e in events:
            lines.append(f"{e.ticker},{e.company_name},{e.report_date},{e.report_time.value},{e.status.value},{e.eps_estimate},{e.eps_actual or ''},{e.eps_surprise or ''}")
        return "\n".join(lines)


# =============================================================================
# MAIN WORKFLOW
# =============================================================================


async def full_workflow():
    """Run the complete earnings workflow."""
    
    print("=" * 70)
    print("  🚀 FULL EARNINGS WORKFLOW DEMO")
    print("=" * 70)
    
    # Initialize services
    calendar_svc = CalendarService()
    resolver = EntityResolver()
    estimate_svc = EstimateService()
    store = ObservationStore()
    monitor = ReleaseMonitor()
    reporter = ReportGenerator()
    
    alert_config = AlertConfig(
        tickers=None,  # All tickers
        min_surprise=0.0,  # Any surprise
        directions=[SurpriseDirection.BEAT, SurpriseDirection.MISS]
    )
    alert_svc = AlertService(alert_config)
    
    # Track events for final report
    all_events: list[CalendarEvent] = []
    
    # =========================================================================
    # STEP 1: LOAD CALENDAR
    # =========================================================================
    print("\n📌 STEP 1: LOAD CALENDAR")
    print("-" * 40)
    
    target_date = datetime.now().strftime("%Y-%m-%d")
    events = await calendar_svc.get_calendar(target_date)
    print(f"    ✅ Found {len(events)} events for {target_date}")
    all_events = events.copy()
    
    # =========================================================================
    # STEP 2: RESOLVE ENTITIES
    # =========================================================================
    print("\n📌 STEP 2: RESOLVE ENTITIES")
    print("-" * 40)
    
    tickers = [e.ticker for e in events]
    entity_map = await resolver.resolve_batch(tickers)
    
    # Update events with entity IDs
    resolved_events = []
    for event in events:
        entity_id = entity_map.get(event.ticker)
        resolved_events.append(CalendarEvent(
            **{**event.model_dump(), "entity_id": entity_id}
        ))
    events = resolved_events
    
    for e in events:
        print(f"    ✅ {e.ticker} → {e.entity_id}")
    
    # =========================================================================
    # STEP 3: ENRICH WITH ESTIMATES
    # =========================================================================
    print("\n📌 STEP 3: ENRICH WITH ESTIMATES")
    print("-" * 40)
    
    estimates = await estimate_svc.get_estimates(tickers, "2026:Q1")
    print(f"    ✅ Loaded estimates from {len(set(e['source'] for e in estimates.values()))} sources")
    
    for ticker, data in estimates.items():
        print(f"    📊 {ticker}: EPS ${data['eps']:.2f} ({data['source']})")
    
    # =========================================================================
    # STEP 4: STORE OBSERVATIONS
    # =========================================================================
    print("\n📌 STEP 4: STORE OBSERVATIONS (FeedSpine)")
    print("-" * 40)
    
    observations = []
    now = datetime.now().isoformat()
    
    for event in events:
        if event.entity_id and event.eps_estimate:
            observations.append(Observation(
                observation_id=f"obs-{event.ticker}-{now}",
                entity_id=event.entity_id,
                metric="eps_estimate",
                value=event.eps_estimate,
                period="2026:Q1",
                source="FactSet",
                observed_at=now,
            ))
    
    count = await store.store_batch(observations)
    print(f"    ✅ Stored {count} observations")
    
    # =========================================================================
    # STEP 5: WATCH FOR RELEASES
    # =========================================================================
    print("\n📌 STEP 5: WATCH FOR RELEASES (Real-time)")
    print("-" * 40)
    
    # Register alert handler
    def on_release(event: CalendarEvent):
        direction = event.surprise_direction
        sym = "✅" if direction == SurpriseDirection.BEAT else "❌" if direction == SurpriseDirection.MISS else "➡️"
        print(f"\n    🔔 ALERT: {event.ticker} {sym} {direction.value}")
        print(f"       EPS: ${event.eps_actual:.2f} vs ${event.eps_estimate:.2f} ({event.eps_surprise:+.1%})")
    
    alert_svc.on_release(on_release)
    
    # Watch for releases (will simulate 2 releases)
    async for released_event in monitor.watch(events):
        # Update our event list
        all_events = [
            released_event if e.ticker == released_event.ticker else e
            for e in all_events
        ]
        
        # Store actual
        if released_event.entity_id:
            actual_obs = Observation(
                observation_id=f"obs-actual-{released_event.ticker}-{now}",
                entity_id=released_event.entity_id,
                metric="eps_actual",
                value=released_event.eps_actual or 0,
                period="2026:Q1",
                source="Company Report",
                observed_at=datetime.now().isoformat(),
            )
            await store.store(actual_obs)
        
        # Process alert
        await alert_svc.process(released_event)
    
    # =========================================================================
    # STEP 6: GENERATE REPORT
    # =========================================================================
    print("\n\n📌 STEP 6: GENERATE REPORT")
    print("-" * 40)
    
    summary = await reporter.generate_summary(all_events)
    print()
    print(summary)
    
    # =========================================================================
    # STEP 7: EXPORT
    # =========================================================================
    print("\n\n📌 STEP 7: EXPORT")
    print("-" * 40)
    
    csv_data = await reporter.export_csv(all_events)
    print("    📄 CSV Export:")
    for line in csv_data.split("\n")[:5]:  # Show first 5 lines
        print(f"    {line}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n")
    print("=" * 70)
    print("  ✅ WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"""
Steps completed:
    1. ✅ Loaded calendar ({len(events)} events)
    2. ✅ Resolved entities ({len(entity_map)} tickers)
    3. ✅ Enriched with estimates ({len(estimates)} tickers)
    4. ✅ Stored observations ({len(store.observations)} records)
    5. ✅ Monitored releases (2 detected)
    6. ✅ Generated summary report
    7. ✅ Exported to CSV

This workflow demonstrates:
    • Multi-source calendar aggregation
    • EntitySpine integration for entity resolution
    • FeedSpine observation storage
    • Real-time release monitoring
    • Automatic beat/miss calculation
    • Alert notifications
    • Report generation and export
""")


# =============================================================================
# ALTERNATE: SIMPLE ONE-LINER API
# =============================================================================


async def simple_api_demo():
    """Show the simple one-liner API that wraps all this complexity."""
    
    print("\n" + "=" * 70)
    print("  💡 SIMPLE API (What Users See)")
    print("=" * 70)
    print("""
All that complexity above is wrapped in a simple API:

    from feedspine.earnings import calendar, compare, watch
    
    # One-liner: Today's calendar
    events = await calendar.today()
    
    # One-liner: Did Apple beat?
    result = await calendar.check("AAPL")
    print(result)  # AAPL ✅ BEAT: +6.3%
    
    # One-liner: Compare estimate vs actual
    comparison = await compare("META", "2026:Q1")
    print(comparison)  # META: ✅ EPS +6.3% | Rev +2.7%
    
    # One-liner: Watch for releases
    async for release in watch(today=True):
        print(f"🔔 {release.ticker} just reported!")

The full workflow runs behind the scenes, but users get:
    • Simple, discoverable API
    • Sensible defaults
    • Type hints and autocomplete
    • Async-first with sync wrappers

Interface design principle:
    "Make the simple things simple, and the complex things possible."
""")


# =============================================================================
# MAIN
# =============================================================================


if __name__ == "__main__":
    asyncio.run(full_workflow())
    asyncio.run(simple_api_demo())
