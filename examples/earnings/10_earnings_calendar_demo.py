#!/usr/bin/env python3
"""
Earnings Calendar Demo - The Final Product
==========================================

This is what we're building. Run this and it works.

This example demonstrates:
1. Loading today's earnings calendar from multiple sources
2. Enriching with estimates from storage
3. Detecting when companies release (change detection)
4. Generating Bloomberg-style output with links
5. WebSocket-style alerts when new actuals appear

Usage:
    # Basic usage - show today's calendar
    python examples/10_earnings_calendar_demo.py
    
    # Watch mode - monitor for new releases
    python examples/10_earnings_calendar_demo.py --watch
    
    # Specific date
    python examples/10_earnings_calendar_demo.py --date 2026-01-30
    
    # Export to CSV (Bloomberg-style)
    python examples/10_earnings_calendar_demo.py --export earnings.csv

Architecture:
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │ SEC EDGAR   │     │  Finnhub    │     │   Yahoo     │
    │  Adapter    │     │  Adapter    │     │  Adapter    │
    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
           │                   │                   │
           └───────────────────┴───────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │  CalendarService │  (aggregates, dedupes)
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  EntitySpine     │  (resolve entities)
                    │  Event + payload │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  ObsStorage      │  (get estimates)
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────────────────────────────┐
                    │  Output: Table, CSV, WebSocket, Webhook  │
                    └──────────────────────────────────────────┘
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import AsyncIterator

# =============================================================================
# FeedSpine Models (Pydantic - FeedSpine convention)
# =============================================================================

from pydantic import BaseModel, Field


class CalendarEventStatus(str, Enum):
    """Status of an earnings event."""
    TENTATIVE = "tentative"      # Unconfirmed
    SCHEDULED = "scheduled"      # Confirmed date
    REVISED = "revised"          # Date changed
    RELEASED = "released"        # Press release out
    FILED_8K = "filed_8k"        # 8-K submitted
    FILED_10Q = "filed_10q"      # 10-Q/10-K submitted


class ReportTime(str, Enum):
    """When during the day earnings are released."""
    BMO = "bmo"      # Before Market Open
    AMC = "amc"      # After Market Close  
    DMH = "dmh"      # During Market Hours
    UNKNOWN = "unknown"


class EarningsEventLinks(BaseModel):
    """URLs related to an earnings event."""
    press_release_url: str | None = None
    sec_8k_url: str | None = None
    sec_10q_url: str | None = None
    ir_website_url: str | None = None
    conference_call_url: str | None = None
    webcast_url: str | None = None
    presentation_url: str | None = None


class CalendarEvent(BaseModel):
    """
    An earnings calendar event - FeedSpine's view.
    
    This is what we display and track. It wraps EntitySpine's Event
    with FeedSpine-specific fields.
    """
    # Identity
    event_id: str
    entity_id: str
    ticker: str | None = None
    company_name: str | None = None
    
    # Period
    fiscal_year: int
    fiscal_quarter: int
    
    # Timing
    scheduled_date: date
    report_time: ReportTime = ReportTime.UNKNOWN
    
    # Status
    status: CalendarEventStatus = CalendarEventStatus.SCHEDULED
    
    # Financial data (when released)
    eps_estimate: Decimal | None = None
    eps_actual: Decimal | None = None
    revenue_estimate: Decimal | None = None
    revenue_actual: Decimal | None = None
    
    # Computed
    @property
    def eps_surprise_pct(self) -> float | None:
        if self.eps_actual and self.eps_estimate:
            return float((self.eps_actual - self.eps_estimate) / abs(self.eps_estimate))
        return None
    
    @property
    def beat_miss(self) -> str | None:
        if self.eps_surprise_pct is None:
            return None
        return "BEAT" if self.eps_surprise_pct >= 0 else "MISS"
    
    # Timestamps
    released_at: datetime | None = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Source tracking
    source: str = "unknown"  # "sec", "finnhub", "yahoo", etc.
    source_authority: int = 50  # 50-100 scale
    
    # Links
    links: EarningsEventLinks = Field(default_factory=EarningsEventLinks)
    
    # Metadata
    metadata: dict = Field(default_factory=dict)


# =============================================================================
# Calendar Adapters (Pluggable data sources)
# =============================================================================

class CalendarAdapter:
    """
    Base class for calendar data sources.
    
    Each source (SEC, Finnhub, Yahoo) implements this interface.
    """
    
    @property
    def source_name(self) -> str:
        raise NotImplementedError
    
    @property
    def authority_level(self) -> int:
        """Authority level 50-100 for source ranking."""
        raise NotImplementedError
    
    async def get_calendar(
        self,
        target_date: date,
    ) -> list[CalendarEvent]:
        """Get calendar events for a specific date."""
        raise NotImplementedError


class SECEdgarAdapter(CalendarAdapter):
    """
    SEC EDGAR as calendar source.
    
    Monitors 8-K Item 2.02 (Results of Operations) and 10-Q/10-K filings.
    This is the authoritative source but delayed (hours after PR).
    """
    
    source_name = "sec"
    authority_level = 95
    
    async def get_calendar(self, target_date: date) -> list[CalendarEvent]:
        # TODO: Use py-sec-edgar to fetch 8-K/10-Q filings
        # For now, return demo data
        print(f"  📡 SEC: Checking EDGAR for {target_date}...")
        await asyncio.sleep(0.5)  # Simulate API call
        return []


class FinnhubAdapter(CalendarAdapter):
    """
    Finnhub API adapter.
    
    Free tier: 60 calls/minute
    Good for: Testing, real-time calendar data
    """
    
    source_name = "finnhub"
    authority_level = 65
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
    
    async def get_calendar(self, target_date: date) -> list[CalendarEvent]:
        print(f"  📡 Finnhub: Fetching calendar for {target_date}...")
        await asyncio.sleep(0.3)  # Simulate API call
        
        # Demo data (in production, call finnhub.io/api/v1/calendar/earnings)
        if not self.api_key:
            # Return demo data
            return [
                CalendarEvent(
                    event_id=f"fh_aapl_{target_date}",
                    entity_id="aapl",
                    ticker="AAPL",
                    company_name="Apple Inc.",
                    fiscal_year=2026,
                    fiscal_quarter=1,
                    scheduled_date=target_date,
                    report_time=ReportTime.AMC,
                    status=CalendarEventStatus.SCHEDULED,
                    eps_estimate=Decimal("2.35"),
                    source="finnhub",
                    source_authority=65,
                    links=EarningsEventLinks(
                        ir_website_url="https://investor.apple.com",
                    ),
                ),
                CalendarEvent(
                    event_id=f"fh_msft_{target_date}",
                    entity_id="msft",
                    ticker="MSFT",
                    company_name="Microsoft Corporation",
                    fiscal_year=2026,
                    fiscal_quarter=2,
                    scheduled_date=target_date,
                    report_time=ReportTime.AMC,
                    status=CalendarEventStatus.SCHEDULED,
                    eps_estimate=Decimal("2.78"),
                    source="finnhub",
                    source_authority=65,
                    links=EarningsEventLinks(
                        ir_website_url="https://www.microsoft.com/investor",
                    ),
                ),
                CalendarEvent(
                    event_id=f"fh_meta_{target_date}",
                    entity_id="meta",
                    ticker="META",
                    company_name="Meta Platforms, Inc.",
                    fiscal_year=2025,
                    fiscal_quarter=4,
                    scheduled_date=target_date,
                    report_time=ReportTime.AMC,
                    status=CalendarEventStatus.RELEASED,  # Already released!
                    eps_estimate=Decimal("5.25"),
                    eps_actual=Decimal("5.58"),
                    released_at=datetime.combine(target_date, datetime.min.time().replace(hour=16, minute=5)),
                    source="finnhub",
                    source_authority=65,
                    links=EarningsEventLinks(
                        ir_website_url="https://investor.fb.com",
                        press_release_url="https://investor.fb.com/press-releases/...",
                    ),
                ),
            ]
        return []


# =============================================================================
# Calendar Service (Aggregation & Change Detection)
# =============================================================================

class CalendarService:
    """
    Aggregates calendar data from multiple sources.
    
    Handles:
    - Multi-source aggregation with deduplication
    - Authority-based source ranking
    - Change detection (what's new since last check)
    """
    
    def __init__(self, adapters: list[CalendarAdapter] | None = None):
        self.adapters = adapters or []
        self._last_seen: dict[str, CalendarEvent] = {}
    
    def add_adapter(self, adapter: CalendarAdapter) -> None:
        self.adapters.append(adapter)
    
    async def get_calendar(self, target_date: date) -> list[CalendarEvent]:
        """
        Get calendar for a date from all sources.
        
        Deduplicates by entity_id, keeping highest-authority source.
        """
        all_events: dict[str, CalendarEvent] = {}
        
        # Gather from all adapters
        for adapter in self.adapters:
            try:
                events = await adapter.get_calendar(target_date)
                for event in events:
                    key = f"{event.entity_id}:{event.fiscal_year}:Q{event.fiscal_quarter}"
                    
                    # Keep highest authority
                    if key not in all_events or event.source_authority > all_events[key].source_authority:
                        all_events[key] = event
            except Exception as e:
                print(f"  ⚠️ {adapter.source_name} failed: {e}")
        
        return list(all_events.values())
    
    async def detect_changes(
        self,
        target_date: date,
    ) -> tuple[list[CalendarEvent], list[CalendarEvent]]:
        """
        Detect what's changed since last check.
        
        Returns:
            (new_releases, status_changes)
        """
        current = await self.get_calendar(target_date)
        
        new_releases = []
        status_changes = []
        
        for event in current:
            key = f"{event.entity_id}:{event.fiscal_year}:Q{event.fiscal_quarter}"
            
            if key in self._last_seen:
                old = self._last_seen[key]
                
                # Check for status transition to RELEASED
                if old.status != CalendarEventStatus.RELEASED and event.status == CalendarEventStatus.RELEASED:
                    new_releases.append(event)
                
                # Check for any status change
                elif old.status != event.status:
                    status_changes.append(event)
            
            self._last_seen[key] = event
        
        return new_releases, status_changes
    
    async def watch(
        self,
        target_date: date,
        poll_interval: int = 60,
    ) -> AsyncIterator[tuple[str, CalendarEvent]]:
        """
        Watch for changes (generator).
        
        Yields:
            (event_type, event) where event_type is "NEW_RELEASE" or "STATUS_CHANGE"
        """
        print(f"\n👀 Watching for changes (polling every {poll_interval}s)...")
        
        # Initial load
        await self.get_calendar(target_date)
        
        while True:
            await asyncio.sleep(poll_interval)
            
            new_releases, status_changes = await self.detect_changes(target_date)
            
            for event in new_releases:
                yield ("NEW_RELEASE", event)
            
            for event in status_changes:
                yield ("STATUS_CHANGE", event)


# =============================================================================
# Display / Output
# =============================================================================

def format_calendar_table(events: list[CalendarEvent]) -> str:
    """Format events as a text table."""
    
    lines = []
    lines.append("")
    lines.append("┌────────┬────────┬─────────────────────────────┬──────────┬─────────────┬────────────────────────────┐")
    lines.append("│ TIME   │ TICKER │ COMPANY                     │ EPS EST  │ STATUS      │ LINKS                      │")
    lines.append("├────────┼────────┼─────────────────────────────┼──────────┼─────────────┼────────────────────────────┤")
    
    for event in sorted(events, key=lambda e: (e.report_time.value, e.ticker or "")):
        time_str = event.report_time.value.upper()
        ticker = (event.ticker or event.entity_id.upper())[:6]
        company = (event.company_name or "")[:27]
        
        if event.eps_estimate:
            eps_str = f"${event.eps_estimate:.2f}"
        else:
            eps_str = "N/A"
        
        # Status with emoji
        status_map = {
            CalendarEventStatus.SCHEDULED: "🕐 SCHEDULED",
            CalendarEventStatus.RELEASED: "✅ RELEASED ",
            CalendarEventStatus.FILED_8K: "📄 FILED 8-K",
            CalendarEventStatus.FILED_10Q: "📄 FILED 10Q",
            CalendarEventStatus.REVISED: "📝 REVISED  ",
            CalendarEventStatus.TENTATIVE: "❓ TENTATIVE",
        }
        status_str = status_map.get(event.status, str(event.status.value))
        
        # Links
        link_parts = []
        if event.links.ir_website_url:
            link_parts.append("[IR]")
        if event.links.press_release_url:
            link_parts.append("[PR]")
        if event.links.sec_8k_url:
            link_parts.append("[8-K]")
        if event.links.conference_call_url:
            link_parts.append("[Call]")
        links_str = " ".join(link_parts) if link_parts else ""
        
        lines.append(
            f"│ {time_str:<6} │ {ticker:<6} │ {company:<27} │ {eps_str:<8} │ {status_str} │ {links_str:<26} │"
        )
    
    lines.append("└────────┴────────┴─────────────────────────────┴──────────┴─────────────┴────────────────────────────┘")
    
    return "\n".join(lines)


def format_release_alert(event: CalendarEvent) -> str:
    """Format a release alert message."""
    
    ticker = event.ticker or event.entity_id.upper()
    
    if event.eps_actual and event.eps_estimate:
        surprise = event.eps_surprise_pct
        direction = event.beat_miss
        return (
            f"🔔 {ticker} just released! "
            f"EPS: ${event.eps_actual:.2f} ({surprise:+.1%} {direction})\n"
            f"   vs estimate: ${event.eps_estimate:.2f}"
        )
    else:
        return f"🔔 {ticker} just released! (no estimate available)"


def export_to_csv(events: list[CalendarEvent], path: str) -> None:
    """Export to CSV (Bloomberg EVTS style)."""
    import csv
    
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "DATE", "TIME", "TICKER", "COMPANY", "SECTOR",
            "EPS_EST", "EPS_ACT", "EPS_SURP%", 
            "STATUS", "SOURCE",
            "PR_URL", "8K_URL", "IR_URL", "CALL_URL",
        ])
        
        for e in events:
            writer.writerow([
                e.scheduled_date.isoformat(),
                e.report_time.value.upper(),
                e.ticker or e.entity_id.upper(),
                e.company_name or "",
                e.metadata.get("sector", ""),
                f"{e.eps_estimate:.2f}" if e.eps_estimate else "",
                f"{e.eps_actual:.2f}" if e.eps_actual else "",
                f"{e.eps_surprise_pct:.1%}" if e.eps_surprise_pct else "",
                e.status.value,
                e.source,
                e.links.press_release_url or "",
                e.links.sec_8k_url or "",
                e.links.ir_website_url or "",
                e.links.conference_call_url or "",
            ])
    
    print(f"📊 Exported {len(events)} events to {path}")


# =============================================================================
# Main Demo
# =============================================================================

async def run_demo(
    target_date: date,
    watch_mode: bool = False,
    export_path: str | None = None,
) -> None:
    """Run the earnings calendar demo."""
    
    print("=" * 70)
    print("  📅 EARNINGS CALENDAR DEMO")
    print("=" * 70)
    print(f"\nTarget date: {target_date}")
    print("\nLoading calendar from multiple sources...")
    
    # Create service with adapters
    service = CalendarService()
    service.add_adapter(SECEdgarAdapter())
    service.add_adapter(FinnhubAdapter())  # Demo mode (no API key)
    
    # Fetch calendar
    events = await service.get_calendar(target_date)
    
    print(f"\n✅ Found {len(events)} companies reporting")
    
    # Display table
    print(format_calendar_table(events))
    
    # Show any already-released
    released = [e for e in events if e.status == CalendarEventStatus.RELEASED]
    if released:
        print("\n📢 Already released today:")
        for e in released:
            print(f"   {format_release_alert(e)}")
    
    # Export if requested
    if export_path:
        export_to_csv(events, export_path)
    
    # Watch mode
    if watch_mode:
        async for event_type, event in service.watch(target_date, poll_interval=30):
            if event_type == "NEW_RELEASE":
                print(f"\n{format_release_alert(event)}")
                if event.links.press_release_url:
                    print(f"   Press release: {event.links.press_release_url}")


def main():
    parser = argparse.ArgumentParser(description="Earnings Calendar Demo")
    parser.add_argument(
        "--date", "-d",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="Target date (YYYY-MM-DD), default: today",
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Watch mode - monitor for new releases",
    )
    parser.add_argument(
        "--export", "-e",
        type=str,
        help="Export to CSV file path",
    )
    
    args = parser.parse_args()
    
    asyncio.run(run_demo(
        target_date=args.date,
        watch_mode=args.watch,
        export_path=args.export,
    ))


if __name__ == "__main__":
    main()
