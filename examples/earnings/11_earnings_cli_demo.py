#!/usr/bin/env python3
"""
Earnings Calendar CLI Demo
===========================

Demonstrates the CLI interface for earnings calendar:
- Simple verb-first commands
- Sensible defaults (today if no date)
- Beautiful terminal output
- Export to CSV/JSON

Run with:
    python 11_earnings_cli_demo.py today
    python 11_earnings_cli_demo.py check AAPL
    python 11_earnings_cli_demo.py watch --today
    python 11_earnings_cli_demo.py export --format csv

This demo runs standalone with mock data.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from io import StringIO
from typing import Optional


# =============================================================================
# DOMAIN MODELS (following FeedSpine Pydantic convention in spirit)
# Using dataclass here for stdlib-only demo, but real impl uses Pydantic
# =============================================================================


class ReportTime(str, Enum):
    """When earnings are released."""
    BMO = "BMO"  # Before Market Open
    AMC = "AMC"  # After Market Close
    UNKNOWN = "UNK"


class EventStatus(str, Enum):
    """Current status of earnings event."""
    SCHEDULED = "SCHEDULED"
    RELEASED = "RELEASED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"


class SurpriseDirection(str, Enum):
    """Beat/miss/inline."""
    BEAT = "BEAT"
    MISS = "MISS"
    INLINE = "INLINE"


@dataclass
class EarningsEvent:
    """A single earnings event."""
    ticker: str
    company_name: str
    report_date: str
    report_time: ReportTime
    status: EventStatus
    # Estimates
    eps_estimate: Optional[float] = None
    revenue_estimate_mm: Optional[float] = None
    # Actuals (when released)
    eps_actual: Optional[float] = None
    revenue_actual_mm: Optional[float] = None
    # Links
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
        surprise = self.eps_surprise
        if surprise is None:
            return None
        if surprise > 0.01:
            return SurpriseDirection.BEAT
        elif surprise < -0.01:
            return SurpriseDirection.MISS
        return SurpriseDirection.INLINE


# =============================================================================
# MOCK DATA SERVICE
# =============================================================================


def get_mock_calendar(date: str) -> list[EarningsEvent]:
    """Generate mock earnings calendar for demo."""
    return [
        EarningsEvent(
            ticker="AAPL",
            company_name="Apple Inc.",
            report_date=date,
            report_time=ReportTime.AMC,
            status=EventStatus.SCHEDULED,
            eps_estimate=2.35,
            revenue_estimate_mm=124500,
            ir_url="https://investor.apple.com/",
        ),
        EarningsEvent(
            ticker="META",
            company_name="Meta Platforms, Inc.",
            report_date=date,
            report_time=ReportTime.AMC,
            status=EventStatus.RELEASED,
            eps_estimate=5.25,
            eps_actual=5.58,
            revenue_estimate_mm=40100,
            revenue_actual_mm=41200,
            ir_url="https://investor.fb.com/",
            press_release_url="https://investor.fb.com/press-releases/",
        ),
        EarningsEvent(
            ticker="MSFT",
            company_name="Microsoft Corporation",
            report_date=date,
            report_time=ReportTime.AMC,
            status=EventStatus.SCHEDULED,
            eps_estimate=2.78,
            revenue_estimate_mm=62800,
            ir_url="https://www.microsoft.com/investor/",
        ),
        EarningsEvent(
            ticker="NVDA",
            company_name="NVIDIA Corporation",
            report_date=date,
            report_time=ReportTime.AMC,
            status=EventStatus.RELEASED,
            eps_estimate=4.12,
            eps_actual=4.65,
            revenue_estimate_mm=28500,
            revenue_actual_mm=30800,
            ir_url="https://investor.nvidia.com/",
            press_release_url="https://investor.nvidia.com/press-releases/",
            sec_filing_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=NVDA",
        ),
        EarningsEvent(
            ticker="AMZN",
            company_name="Amazon.com, Inc.",
            report_date=date,
            report_time=ReportTime.AMC,
            status=EventStatus.SCHEDULED,
            eps_estimate=1.15,
            revenue_estimate_mm=158500,
            ir_url="https://ir.aboutamazon.com/",
        ),
    ]


def get_mock_event(ticker: str) -> Optional[EarningsEvent]:
    """Get most recent event for a ticker."""
    today = datetime.now().strftime("%Y-%m-%d")
    events = get_mock_calendar(today)
    for event in events:
        if event.ticker.upper() == ticker.upper():
            return event
    return None


# =============================================================================
# OUTPUT FORMATTERS
# =============================================================================


def format_table(events: list[EarningsEvent], compact: bool = False) -> str:
    """Format events as a beautiful table."""
    if not events:
        return "No earnings events found."
    
    output = StringIO()
    
    # Status symbols
    status_symbols = {
        EventStatus.SCHEDULED: "🕐",
        EventStatus.RELEASED: "✅",
        EventStatus.DELAYED: "⏸️",
        EventStatus.CANCELLED: "❌",
    }
    
    direction_symbols = {
        SurpriseDirection.BEAT: "📈",
        SurpriseDirection.MISS: "📉",
        SurpriseDirection.INLINE: "➡️",
    }
    
    # Header
    if compact:
        output.write(f"{'TIME':<5} {'TICKER':<6} {'STATUS':<10} {'EPS EST':<8} {'EPS ACT':<8} {'SURPRISE':<10}\n")
        output.write("─" * 55 + "\n")
    else:
        output.write("┌" + "─" * 88 + "┐\n")
        output.write(f"│ {'TIME':<5} {'TICKER':<7} {'COMPANY':<30} {'STATUS':<12} {'EPS EST':<9} {'EPS ACT':<9} {'SURPRISE':<10}│\n")
        output.write("├" + "─" * 88 + "┤\n")
    
    for event in sorted(events, key=lambda e: (e.report_time.value, e.ticker)):
        status_sym = status_symbols.get(event.status, "?")
        status_text = f"{status_sym} {event.status.value}"
        
        eps_est = f"${event.eps_estimate:.2f}" if event.eps_estimate else "-"
        eps_act = f"${event.eps_actual:.2f}" if event.eps_actual else "-"
        
        surprise = ""
        if event.eps_surprise is not None:
            direction = event.surprise_direction
            dir_sym = direction_symbols.get(direction, "")
            surprise = f"{dir_sym} {event.eps_surprise:+.1%}"
        
        if compact:
            output.write(f"{event.report_time.value:<5} {event.ticker:<6} {status_text:<10} {eps_est:<8} {eps_act:<8} {surprise:<10}\n")
        else:
            company = event.company_name[:28] + ".." if len(event.company_name) > 30 else event.company_name
            output.write(f"│ {event.report_time.value:<5} {event.ticker:<7} {company:<30} {status_text:<12} {eps_est:<9} {eps_act:<9} {surprise:<10}│\n")
    
    if not compact:
        output.write("└" + "─" * 88 + "┘\n")
    
    return output.getvalue()


def format_check_result(event: Optional[EarningsEvent], ticker: str) -> str:
    """Format a beat/miss check result."""
    if event is None:
        return f"❓ No recent earnings data found for {ticker}"
    
    output = StringIO()
    output.write(f"\n{'='*60}\n")
    output.write(f"  📊 EARNINGS CHECK: {event.ticker}\n")
    output.write(f"{'='*60}\n\n")
    
    output.write(f"  Company:      {event.company_name}\n")
    output.write(f"  Report Date:  {event.report_date} ({event.report_time.value})\n")
    output.write(f"  Status:       {event.status.value}\n\n")
    
    if event.status == EventStatus.RELEASED:
        output.write(f"  EPS Estimate: ${event.eps_estimate:.2f}\n" if event.eps_estimate else "")
        output.write(f"  EPS Actual:   ${event.eps_actual:.2f}\n" if event.eps_actual else "")
        
        if event.eps_surprise is not None:
            direction = event.surprise_direction
            if direction == SurpriseDirection.BEAT:
                output.write(f"\n  ✅ BEAT by {event.eps_surprise:+.1%}\n")
            elif direction == SurpriseDirection.MISS:
                output.write(f"\n  ❌ MISSED by {event.eps_surprise:+.1%}\n")
            else:
                output.write(f"\n  ➡️ INLINE (within 1%)\n")
    else:
        output.write(f"  EPS Estimate: ${event.eps_estimate:.2f}\n" if event.eps_estimate else "")
        output.write(f"\n  ⏳ Not yet released\n")
    
    # Links
    links = []
    if event.ir_url:
        links.append(f"IR: {event.ir_url}")
    if event.press_release_url:
        links.append(f"PR: {event.press_release_url}")
    if event.sec_filing_url:
        links.append(f"SEC: {event.sec_filing_url}")
    
    if links:
        output.write(f"\n  📎 Links:\n")
        for link in links:
            output.write(f"     {link}\n")
    
    output.write(f"\n{'='*60}\n")
    return output.getvalue()


def export_csv(events: list[EarningsEvent]) -> str:
    """Export events to CSV format."""
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ticker", "company", "date", "time", "status",
        "eps_estimate", "eps_actual", "eps_surprise", "surprise_direction",
        "ir_url", "press_release_url", "sec_filing_url"
    ])
    
    for event in events:
        writer.writerow([
            event.ticker,
            event.company_name,
            event.report_date,
            event.report_time.value,
            event.status.value,
            event.eps_estimate,
            event.eps_actual,
            event.eps_surprise,
            event.surprise_direction.value if event.surprise_direction else None,
            event.ir_url,
            event.press_release_url,
            event.sec_filing_url,
        ])
    
    return output.getvalue()


def export_json(events: list[EarningsEvent]) -> str:
    """Export events to JSON format."""
    data = []
    for event in events:
        data.append({
            "ticker": event.ticker,
            "company_name": event.company_name,
            "report_date": event.report_date,
            "report_time": event.report_time.value,
            "status": event.status.value,
            "eps_estimate": event.eps_estimate,
            "eps_actual": event.eps_actual,
            "eps_surprise": event.eps_surprise,
            "surprise_direction": event.surprise_direction.value if event.surprise_direction else None,
            "links": {
                "ir": event.ir_url,
                "press_release": event.press_release_url,
                "sec_filing": event.sec_filing_url,
            }
        })
    return json.dumps(data, indent=2)


# =============================================================================
# CLI COMMANDS
# =============================================================================


def cmd_today(args: argparse.Namespace) -> None:
    """Show today's earnings calendar."""
    date = datetime.now().strftime("%Y-%m-%d")
    print(f"\n📅 EARNINGS CALENDAR: {date}\n")
    events = get_mock_calendar(date)
    print(format_table(events, compact=args.compact))
    
    # Show released summary
    released = [e for e in events if e.status == EventStatus.RELEASED]
    if released:
        print("\n📢 Already Released Today:")
        for event in released:
            if event.surprise_direction == SurpriseDirection.BEAT:
                print(f"   ✅ {event.ticker} BEAT: ${event.eps_actual:.2f} vs ${event.eps_estimate:.2f} ({event.eps_surprise:+.1%})")
            elif event.surprise_direction == SurpriseDirection.MISS:
                print(f"   ❌ {event.ticker} MISSED: ${event.eps_actual:.2f} vs ${event.eps_estimate:.2f} ({event.eps_surprise:+.1%})")
        print()


def cmd_tomorrow(args: argparse.Namespace) -> None:
    """Show tomorrow's earnings calendar."""
    date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"\n📅 EARNINGS CALENDAR: {date}\n")
    events = get_mock_calendar(date)
    print(format_table(events, compact=args.compact))


def cmd_week(args: argparse.Namespace) -> None:
    """Show this week's earnings calendar."""
    print(f"\n📅 EARNINGS CALENDAR: This Week\n")
    today = datetime.now()
    
    for i in range(5):  # Mon-Fri
        date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        day_name = (today + timedelta(days=i)).strftime("%A")
        print(f"\n{day_name} ({date}):")
        events = get_mock_calendar(date)
        print(format_table(events, compact=True))


def cmd_date(args: argparse.Namespace) -> None:
    """Show earnings for specific date."""
    print(f"\n📅 EARNINGS CALENDAR: {args.date}\n")
    events = get_mock_calendar(args.date)
    print(format_table(events, compact=args.compact))


def cmd_check(args: argparse.Namespace) -> None:
    """Check if a ticker beat/missed."""
    event = get_mock_event(args.ticker)
    print(format_check_result(event, args.ticker))


def cmd_watch(args: argparse.Namespace) -> None:
    """Watch for earnings releases (simulated)."""
    import time
    
    print("\n👀 WATCHING FOR EARNINGS RELEASES")
    print("Press Ctrl+C to stop\n")
    
    tickers = args.ticker.split(",") if args.ticker else None
    
    # Simulated releases
    releases = [
        ("META", "Meta Platforms", 5.58, 5.25, "AMC", 2),
        ("NVDA", "NVIDIA Corporation", 4.65, 4.12, "AMC", 5),
    ]
    
    try:
        for ticker, company, actual, estimate, time_of_day, delay in releases:
            if tickers and ticker not in tickers:
                continue
                
            time.sleep(delay)
            surprise = (actual - estimate) / abs(estimate)
            direction = "BEAT" if surprise > 0.01 else "MISS" if surprise < -0.01 else "INLINE"
            symbol = "✅" if direction == "BEAT" else "❌" if direction == "MISS" else "➡️"
            
            print(f"🔔 [{datetime.now().strftime('%H:%M:%S')}] {ticker} ({time_of_day})")
            print(f"   {company}")
            print(f"   {symbol} {direction}: ${actual:.2f} vs ${estimate:.2f} ({surprise:+.1%})")
            print()
        
        print("⏳ Waiting for more releases...")
        while True:
            time.sleep(10)
            print(f"   [{datetime.now().strftime('%H:%M:%S')}] No new releases...")
            
    except KeyboardInterrupt:
        print("\n\n👋 Stopped watching.\n")


def cmd_export(args: argparse.Namespace) -> None:
    """Export earnings data."""
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    events = get_mock_calendar(date)
    
    if args.format == "csv":
        output = export_csv(events)
    elif args.format == "json":
        output = export_json(events)
    else:
        output = format_table(events)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ Exported to {args.output}")
    else:
        print(output)


# =============================================================================
# MAIN CLI ENTRYPOINT
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='feedspine earnings',
        description='Earnings calendar and estimates vs actuals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s today                    Show today's earnings calendar
  %(prog)s check AAPL               Check if Apple beat/missed
  %(prog)s watch --today            Watch for real-time releases
  %(prog)s export --format csv      Export to CSV
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # today
    today_parser = subparsers.add_parser('today', help="Today's earnings calendar")
    today_parser.add_argument('--compact', '-c', action='store_true', help='Compact output')
    today_parser.set_defaults(func=cmd_today)
    
    # tomorrow
    tomorrow_parser = subparsers.add_parser('tomorrow', help="Tomorrow's earnings calendar")
    tomorrow_parser.add_argument('--compact', '-c', action='store_true', help='Compact output')
    tomorrow_parser.set_defaults(func=cmd_tomorrow)
    
    # week
    week_parser = subparsers.add_parser('week', help="This week's earnings calendar")
    week_parser.set_defaults(func=cmd_week)
    
    # date
    date_parser = subparsers.add_parser('date', help="Earnings for specific date")
    date_parser.add_argument('date', help='Date in YYYY-MM-DD format')
    date_parser.add_argument('--compact', '-c', action='store_true', help='Compact output')
    date_parser.set_defaults(func=cmd_date)
    
    # check
    check_parser = subparsers.add_parser('check', help="Check if ticker beat/missed")
    check_parser.add_argument('ticker', help='Stock ticker symbol')
    check_parser.set_defaults(func=cmd_check)
    
    # watch
    watch_parser = subparsers.add_parser('watch', help="Watch for real-time releases")
    watch_parser.add_argument('--today', action='store_true', help='Only today')
    watch_parser.add_argument('--ticker', '-t', help='Specific tickers (comma-separated)')
    watch_parser.set_defaults(func=cmd_watch)
    
    # export
    export_parser = subparsers.add_parser('export', help="Export earnings data")
    export_parser.add_argument('--date', '-d', help='Date (default: today)')
    export_parser.add_argument('--format', '-f', choices=['csv', 'json', 'table'], default='table')
    export_parser.add_argument('--output', '-o', help='Output file path')
    export_parser.set_defaults(func=cmd_export)
    
    return parser


def main():
    """Main CLI entrypoint."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        # Default to 'today' if no command specified
        args.compact = False
        cmd_today(args)
    else:
        args.func(args)


if __name__ == '__main__':
    main()
