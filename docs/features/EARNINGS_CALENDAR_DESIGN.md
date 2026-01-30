# Earnings Calendar Feature Design

> **Tracking the full lifecycle of earnings events: from scheduled to released to filed.**

---

## 🎯 Working Demo (Start Here!)

**We have a working, runnable example:**

```bash
# Run the demo
cd feedspine
python examples/10_earnings_calendar_demo.py --date 2026-01-29

# Output:
# ======================================================================
#   📅 EARNINGS CALENDAR DEMO
# ======================================================================
# ✅ Found 3 companies reporting
#
# ┌────────┬────────┬─────────────────────────────┬──────────┬─────────────┬────────────────────────────┐
# │ TIME   │ TICKER │ COMPANY                     │ EPS EST  │ STATUS      │ LINKS                      │
# ├────────┼────────┼─────────────────────────────┼──────────┼─────────────┼────────────────────────────┤
# │ AMC    │ AAPL   │ Apple Inc.                  │ $2.35    │ 🕐 SCHEDULED │ [IR]                       │
# │ AMC    │ META   │ Meta Platforms, Inc.        │ $5.25    │ ✅ RELEASED  │ [IR] [PR]                  │
# │ AMC    │ MSFT   │ Microsoft Corporation       │ $2.78    │ 🕐 SCHEDULED │ [IR]                       │
# └────────┴────────┴─────────────────────────────┴──────────┴─────────────┴────────────────────────────┘
#
# 📢 Already released today:
#    🔔 META just released! EPS: $5.58 (+6.3% BEAT)
#    vs estimate: $5.25

# Watch mode (poll for changes)
python examples/10_earnings_calendar_demo.py --watch

# Export to CSV (Bloomberg-style)
python examples/10_earnings_calendar_demo.py --export earnings.csv
```

**What the demo implements:**
- ✅ `CalendarEvent` Pydantic model (FeedSpine convention)
- ✅ `CalendarAdapter` base class + `SECEdgarAdapter`, `FinnhubAdapter` 
- ✅ `CalendarService` with change detection
- ✅ Bloomberg-style table output with links
- ✅ CSV export matching your Excel workflow
- ✅ Watch mode with alerts

**What's stubbed (needs real implementation):**
- 🔲 Real SEC EDGAR API calls (uses py-sec-edgar)
- 🔲 Real Finnhub API calls (needs API key)
- 🔲 EntitySpine integration for entity resolution
- 🔲 Observation storage for estimates

---

## The Problem You're Describing

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        THE EARNINGS CALENDAR PROBLEM                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  Bloomberg/FactSet give you:                                                        │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │  A big list of all companies reporting today                               │    │
│  │  + When they're expected (AMC, BMO)                                        │    │
│  │  + The estimate                                                            │    │
│  │  + Later: the actual fills in                                              │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  What they DON'T give you:                                                          │
│  • "NOTIFY me when AAPL just reported" (change detection)                          │
│  • "When exactly did this data arrive?" (captured_at timestamp)                    │
│  • "What was scheduled vs what actually happened?" (revision tracking)             │
│  • "Show me ONLY the NEW ones since I last checked"                                │
│  • "The press release came out, but the 10-Q isn't filed yet"                      │
│                                                                                      │
│  Your workflow today:                                                               │
│  1. Export CSV from Bloomberg throughout the day                                    │
│  2. Feed into macro to detect "new" actuals                                        │
│  3. Manually track which are new vs already seen                                   │
│                                                                                      │
│  What we want:                                                                       │
│  • System tracks the calendar automatically                                         │
│  • Detects when estimate → actual transition happens                               │
│  • Sends notification/webhook                                                       │
│  • Tracks full timeline with our own timestamps                                    │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Where Does Calendar Data Come From?

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        EARNINGS CALENDAR DATA SOURCES                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  PRIMARY SOURCES (where the data originates):                                       │
│  ─────────────────────────────────────────────                                      │
│                                                                                      │
│  1. COMPANY IR WEBSITES                                                             │
│     • Investor Relations calendar page                                              │
│     • "Apple will report Q1 2026 results on January 30, 2026"                      │
│     • Usually announced 2-4 weeks before                                           │
│     • Example: https://investor.apple.com/investor-relations/                      │
│                                                                                      │
│  2. PRESS RELEASES (News Wires)                                                    │
│     • PR Newswire, Business Wire, GlobeNewswire                                    │
│     • "Apple Reports Record Q1 2026 Results"                                       │
│     • This IS the actual earnings announcement                                     │
│     • Bloomberg/FactSet monitor these wires                                        │
│                                                                                      │
│  3. SEC FILINGS                                                                     │
│     • 8-K Item 2.02: "Results of Operations" (same day as PR usually)             │
│     • 10-Q/10-K: Official quarterly/annual report (days/weeks later)              │
│     • XBRL data is authoritative                                                   │
│                                                                                      │
│  4. EXCHANGE CALENDARS                                                              │
│     • NYSE/NASDAQ maintain calendars                                               │
│     • Less detailed but reliable for dates                                         │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                      │
│  AGGREGATORS (where Bloomberg/FactSet get their data):                             │
│  ────────────────────────────────────────────────────                              │
│                                                                                      │
│  Bloomberg:                                                                          │
│  • Monitors news wires (PR Newswire, Business Wire)                                │
│  • Scrapes company IR websites                                                     │
│  • Has analysts who manually verify                                                │
│  • Terminal: ERN <GO> function                                                     │
│                                                                                      │
│  FactSet:                                                                            │
│  • Similar wire monitoring                                                          │
│  • Partnerships with companies for direct announcements                            │
│  • FactSet Workstation calendar view                                               │
│                                                                                      │
│  Zacks:                                                                              │
│  • Wire monitoring                                                                  │
│  • Focus on estimates + actuals comparison                                         │
│  • Zacks.com/earnings/earnings-calendar                                            │
│                                                                                      │
│  Refinitiv/I/B/E/S:                                                                 │
│  • Institutional-grade                                                              │
│  • Very fast (sub-second on major names)                                           │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## The Earnings Event Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        EARNINGS EVENT LIFECYCLE                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  TIMELINE for Apple Q1 FY2026:                                                      │
│                                                                                      │
│  Jan 10    Company IR page updated                                                  │
│  ────────  "Apple will report Q1 2026 results on Jan 30, 2026 after market close" │
│            │                                                                        │
│            ▼  EVENT CREATED (status: SCHEDULED)                                    │
│            ┌────────────────────────────────────────┐                              │
│            │ scheduled_on: 2026-01-30               │                              │
│            │ report_time: AMC (after market close)  │                              │
│            │ status: SCHEDULED                      │                              │
│            │ announced_on: 2026-01-10               │                              │
│            └────────────────────────────────────────┘                              │
│                                                                                      │
│  Jan 15    Date revised (rare but happens)                                         │
│  ────────  "Apple reschedules to Feb 1, 2026"                                      │
│            │                                                                        │
│            ▼  EVENT UPDATED (revision tracked)                                     │
│            ┌────────────────────────────────────────┐                              │
│            │ scheduled_on: 2026-02-01  (changed!)   │                              │
│            │ previous_scheduled_on: 2026-01-30      │                              │
│            │ revision_count: 1                      │                              │
│            └────────────────────────────────────────┘                              │
│                                                                                      │
│  Jan 30    Press release hits the wire (4:30 PM ET)                                │
│  16:30     "Apple Reports Record First Quarter Results"                            │
│            │                                                                        │
│            ▼  EARNINGS RELEASED (status: RELEASED)                                 │
│            ┌────────────────────────────────────────┐                              │
│            │ status: RELEASED                       │                              │
│            │ released_at: 2026-01-30 16:30:00      │                              │
│            │ actual_eps: $2.40                      │                              │
│            │ actual_revenue: $124.3B                │                              │
│            │ source: PR_NEWSWIRE                    │                              │
│            └────────────────────────────────────────┘                              │
│            │                                                                        │
│            │  ⚡ NOTIFICATION TRIGGERED ⚡                                          │
│            │  "AAPL just reported! BEAT +5.2%"                                     │
│                                                                                      │
│  Jan 30    8-K filed with SEC (same day, often within hours)                       │
│  19:15     Item 2.02 - Results of Operations                                       │
│            │                                                                        │
│            ▼  8-K FILED (source added)                                             │
│            ┌────────────────────────────────────────┐                              │
│            │ filed_8k_at: 2026-01-30 19:15:00      │                              │
│            │ accession_8k: 0000320193-26-000015    │                              │
│            └────────────────────────────────────────┘                              │
│                                                                                      │
│  Feb 15    10-Q filed with SEC (official quarterly report)                         │
│            │                                                                        │
│            ▼  10-Q FILED (status: FILED)                                           │
│            ┌────────────────────────────────────────┐                              │
│            │ status: FILED                          │                              │
│            │ filed_10q_at: 2026-02-15              │                              │
│            │ accession_10q: 0000320193-26-000042   │                              │
│            │ xbrl_eps: $2.40  (authoritative)      │                              │
│            └────────────────────────────────────────┘                              │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model: Enhanced Event

```python
from dataclasses import dataclass, field
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum
from typing import Optional


class EarningsEventStatus(Enum):
    """Status of an earnings event in its lifecycle."""
    TENTATIVE = "tentative"      # Rumored/unconfirmed date
    SCHEDULED = "scheduled"      # Company confirmed date
    REVISED = "revised"          # Date changed from original
    RELEASED = "released"        # Earnings announced (press release)
    FILED_8K = "filed_8k"        # 8-K submitted to SEC
    FILED_10Q = "filed_10q"      # 10-Q submitted (quarterly)
    FILED_10K = "filed_10k"      # 10-K submitted (annual)
    COMPLETED = "completed"      # All filings in, event closed


class ReportTime(Enum):
    """When during the day earnings are released."""
    BMO = "bmo"      # Before Market Open
    AMC = "amc"      # After Market Close
    DMH = "dmh"      # During Market Hours
    UNKNOWN = "unknown"


@dataclass
class EarningsEvent:
    """
    Full lifecycle tracking for an earnings event.
    
    This goes beyond EntitySpine's Event model to track
    the complete timeline from scheduled → released → filed.
    """
    
    # Identity
    id: str
    entity_id: str
    fiscal_year: int
    fiscal_quarter: int  # 1-4, or 0 for annual
    
    # Scheduling
    status: EarningsEventStatus
    scheduled_on: date
    report_time: ReportTime
    
    # Timeline tracking (our timestamps)
    announced_on: Optional[date] = None          # When company announced the date
    announced_captured_at: Optional[datetime] = None  # When WE captured that
    
    # Revisions
    original_scheduled_on: Optional[date] = None  # First scheduled date
    revision_count: int = 0
    revision_history: list[dict] = field(default_factory=list)
    
    # Release (press release / earnings call)
    released_at: Optional[datetime] = None        # Actual announcement time
    released_captured_at: Optional[datetime] = None  # When we captured it
    release_source: Optional[str] = None          # "PR_NEWSWIRE", "BUSINESS_WIRE", etc.
    
    # Preliminary results (from press release)
    preliminary_eps: Optional[Decimal] = None
    preliminary_revenue: Optional[Decimal] = None
    preliminary_guidance: Optional[dict] = None
    
    # SEC Filings
    filed_8k_at: Optional[datetime] = None
    accession_8k: Optional[str] = None
    
    filed_10q_at: Optional[datetime] = None      # Or 10-K for Q4
    accession_10q: Optional[str] = None
    
    # XBRL actuals (authoritative)
    xbrl_eps: Optional[Decimal] = None
    xbrl_revenue: Optional[Decimal] = None
    
    # Estimates (snapshot at release time)
    consensus_eps_at_release: Optional[Decimal] = None
    consensus_revenue_at_release: Optional[Decimal] = None
    
    # Computed
    @property
    def period_key(self) -> str:
        if self.fiscal_quarter == 0:
            return f"{self.fiscal_year}:FY"
        return f"{self.fiscal_year}:Q{self.fiscal_quarter}"
    
    @property
    def surprise_pct(self) -> Optional[float]:
        if self.preliminary_eps and self.consensus_eps_at_release:
            return float(
                (self.preliminary_eps - self.consensus_eps_at_release) 
                / abs(self.consensus_eps_at_release)
            )
        return None
    
    @property
    def is_complete(self) -> bool:
        """Event is complete when 10-Q/10-K is filed."""
        return self.status in (
            EarningsEventStatus.FILED_10Q,
            EarningsEventStatus.FILED_10K,
            EarningsEventStatus.COMPLETED,
        )
    
    @property
    def days_until(self) -> Optional[int]:
        """Days until scheduled release (negative if past)."""
        if self.scheduled_on:
            return (self.scheduled_on - date.today()).days
        return None
```

---

## Calendar View (SQL-like)

You mentioned wanting views like SQL databases. Here's how we can support that:

```python
@dataclass
class CalendarViewConfig:
    """Configuration for a calendar view (like Bloomberg ERN export)."""
    
    name: str
    description: str
    
    # Filters
    date_range: tuple[date, date]        # Start, end dates
    report_times: list[ReportTime] = None  # BMO, AMC, DMH
    min_market_cap: Optional[float] = None
    sectors: Optional[list[str]] = None
    indices: Optional[list[str]] = None   # "SP500", "NASDAQ100"
    
    # Columns to include
    columns: list[str] = field(default_factory=lambda: [
        "scheduled_on",
        "report_time",
        "ticker",
        "company_name",
        "sector",
        "market_cap",
        "consensus_eps",
        "consensus_revenue",
        "actual_eps",        # Filled when released
        "actual_revenue",
        "surprise_pct",
        "status",
    ])
    
    # Change detection
    track_changes: bool = True            # Enable change detection
    notify_on_release: bool = True        # Alert when actual appears
    notify_on_revision: bool = False      # Alert when date changes


class CalendarViewService:
    """
    SQL-like views over earnings calendar data.
    """
    
    def __init__(self, event_store, entity_store, obs_storage):
        self.event_store = event_store
        self.entity_store = entity_store
        self.obs_storage = obs_storage
        self._views: dict[str, CalendarViewConfig] = {}
    
    def create_view(self, config: CalendarViewConfig) -> str:
        """Create a named view (like CREATE VIEW in SQL)."""
        self._views[config.name] = config
        return config.name
    
    async def query_view(
        self,
        view_name: str,
        as_of: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Query a view as of a specific time.
        
        Like: SELECT * FROM my_earnings_view
        """
        config = self._views[view_name]
        
        # Get events in date range
        events = await self.event_store.query_events(
            event_type=EventType.EARNINGS_RELEASE,
            scheduled_after=config.date_range[0],
            scheduled_before=config.date_range[1],
        )
        
        # Apply filters
        if config.report_times:
            events = [e for e in events if e.report_time in config.report_times]
        
        if config.min_market_cap:
            # Filter by market cap (need entity lookup)
            filtered = []
            for e in events:
                entity = await self.entity_store.get(e.entity_id)
                if entity.market_cap and entity.market_cap >= config.min_market_cap:
                    filtered.append(e)
            events = filtered
        
        # Build DataFrame with requested columns
        rows = []
        for event in events:
            entity = await self.entity_store.get(event.entity_id)
            
            # Get current estimate
            estimate = await self.obs_storage.get_observation(
                entity_id=event.entity_id,
                metric_code="eps",
                period=event.period_key,
                scope="CONSENSUS",
                as_of=as_of,
            )
            
            row = {
                "scheduled_on": event.scheduled_on,
                "report_time": event.report_time.value,
                "ticker": entity.ticker,
                "company_name": entity.name,
                "sector": entity.sector,
                "market_cap": entity.market_cap,
                "consensus_eps": estimate.value if estimate else None,
                "actual_eps": event.preliminary_eps,
                "surprise_pct": event.surprise_pct,
                "status": event.status.value,
                # Our timestamps
                "released_at": event.released_at,
                "captured_at": event.released_captured_at,
            }
            rows.append(row)
        
        return pd.DataFrame(rows)
    
    async def get_changes_since(
        self,
        view_name: str,
        since: datetime,
    ) -> list[dict]:
        """
        Get changes since last check.
        
        This is what Bloomberg DOESN'T give you!
        """
        config = self._views[view_name]
        
        changes = []
        
        # Find events that transitioned to RELEASED since `since`
        events = await self.event_store.query_events(
            event_type=EventType.EARNINGS_RELEASE,
            scheduled_after=config.date_range[0],
            scheduled_before=config.date_range[1],
            status=EarningsEventStatus.RELEASED,
            released_captured_after=since,  # Key filter!
        )
        
        for event in events:
            changes.append({
                "type": "NEW_RELEASE",
                "entity_id": event.entity_id,
                "event": event,
                "detected_at": event.released_captured_at,
            })
        
        # Find date revisions
        if config.notify_on_revision:
            revised = await self.event_store.query_events(
                revised_after=since,
            )
            for event in revised:
                changes.append({
                    "type": "DATE_REVISED",
                    "entity_id": event.entity_id,
                    "event": event,
                    "old_date": event.revision_history[-1]["old_date"],
                    "new_date": event.scheduled_on,
                })
        
        return changes
```

---

## Usage: Creating Views Like Bloomberg Export

```python
# Create a view matching your Bloomberg export
calendar_service = CalendarViewService(event_store, entity_store, obs_storage)

# "Today's Earnings" view
today_view = CalendarViewConfig(
    name="today_earnings",
    description="All earnings scheduled for today",
    date_range=(date.today(), date.today()),
    min_market_cap=1_000_000_000,  # $1B+
    columns=[
        "scheduled_on", "report_time", "ticker", "company_name",
        "sector", "market_cap", "consensus_eps", "consensus_revenue",
        "actual_eps", "actual_revenue", "surprise_pct", "status",
        "released_at", "captured_at",  # OUR timestamps!
    ],
    track_changes=True,
    notify_on_release=True,
)
calendar_service.create_view(today_view)

# Query it (like your Bloomberg export)
df = await calendar_service.query_view("today_earnings")
print(df)

# WHAT BLOOMBERG DOESN'T DO:
# Check for changes since last query
last_check = datetime.utcnow() - timedelta(minutes=30)
changes = await calendar_service.get_changes_since("today_earnings", since=last_check)

for change in changes:
    if change["type"] == "NEW_RELEASE":
        event = change["event"]
        print(f"🆕 {event.entity_id} just reported!")
        print(f"   EPS: ${event.preliminary_eps} vs Est ${event.consensus_eps_at_release}")
        print(f"   Surprise: {event.surprise_pct:+.1%}")
        print(f"   Released: {event.released_at}")
        print(f"   We captured at: {event.released_captured_at}")
```

---

## Data Ingestion: How We Get Calendar Data

### Option 1: SEC EDGAR (Free, Authoritative, Delayed)

```python
from py_sec_edgar.feeds import EDGARFeed

async def ingest_from_sec():
    """
    Monitor SEC for new filings.
    
    Pros: Free, authoritative
    Cons: 8-K may be hours after press release, 10-Q is days/weeks later
    """
    feed = EDGARFeed()
    
    async for filing in feed.watch(form_types=["8-K", "10-Q", "10-K"]):
        if filing.form_type == "8-K":
            # Check if it's Item 2.02 (Results of Operations)
            items = await filing.get_items()
            if "2.02" in items:
                # This is an earnings-related 8-K
                event = await find_or_create_event(
                    cik=filing.cik,
                    period=extract_period_from_8k(filing),
                )
                event.filed_8k_at = filing.accepted_at
                event.accession_8k = filing.accession_number
                event.status = EarningsEventStatus.FILED_8K
                await event_store.update(event)
        
        elif filing.form_type in ("10-Q", "10-K"):
            # Official quarterly/annual report
            event = await find_or_create_event(
                cik=filing.cik,
                period=extract_period_from_filing(filing),
            )
            
            # Extract XBRL data
            xbrl = XBRLExtractor(filing)
            event.xbrl_eps = xbrl.get_eps_diluted()
            event.xbrl_revenue = xbrl.get_revenue()
            
            if filing.form_type == "10-Q":
                event.filed_10q_at = filing.accepted_at
                event.accession_10q = filing.accession_number
                event.status = EarningsEventStatus.FILED_10Q
            else:
                event.filed_10k_at = filing.accepted_at
                event.accession_10k = filing.accession_number
                event.status = EarningsEventStatus.FILED_10K
            
            await event_store.update(event)
```

### Option 2: News Wire APIs (Fast, Costs Money)

```python
async def ingest_from_news_wires():
    """
    Monitor news wires for press releases.
    
    Pros: Fast (real-time)
    Cons: Costs money, need to parse unstructured text
    """
    # These require paid subscriptions
    sources = [
        PRNewswireAPI(api_key=os.environ["PRNEWSWIRE_KEY"]),
        BusinessWireAPI(api_key=os.environ["BUSINESSWIRE_KEY"]),
        GlobeNewswireAPI(api_key=os.environ["GLOBENEWSWIRE_KEY"]),
    ]
    
    for source in sources:
        async for release in source.watch(keywords=["earnings", "quarterly results"]):
            # Parse the press release
            parsed = parse_earnings_release(release.content)
            
            if parsed:
                event = await find_or_create_event(
                    ticker=parsed.ticker,
                    period=parsed.period,
                )
                
                event.status = EarningsEventStatus.RELEASED
                event.released_at = release.published_at
                event.released_captured_at = datetime.utcnow()  # OUR timestamp
                event.release_source = source.name
                
                event.preliminary_eps = parsed.eps
                event.preliminary_revenue = parsed.revenue
                event.preliminary_guidance = parsed.guidance
                
                # Snapshot the estimate at release time
                estimate = await obs_storage.get_observation(
                    entity_id=event.entity_id,
                    metric_code="eps",
                    period=event.period_key,
                    scope="CONSENSUS",
                    as_of=event.released_at,
                )
                event.consensus_eps_at_release = estimate.value if estimate else None
                
                await event_store.update(event)
                
                # 🔔 TRIGGER NOTIFICATION
                await notify_new_release(event)
```

### Option 3: Vendor Feed (FactSet, Bloomberg, Zacks)

```python
async def ingest_from_vendor_calendar(vendor: str):
    """
    Poll vendor calendar for updates.
    
    Pros: Pre-parsed, includes estimates
    Cons: Costs money, may not have our timestamps
    """
    if vendor == "zacks":
        api = ZacksCalendarAPI(api_key=os.environ["ZACKS_KEY"])
    elif vendor == "factset":
        api = FactSetCalendarAPI(api_key=os.environ["FACTSET_KEY"])
    
    # Get today's calendar
    calendar = await api.get_calendar(date=date.today())
    
    for item in calendar:
        event = await find_or_create_event(
            ticker=item.ticker,
            period=item.period,
        )
        
        captured_at = datetime.utcnow()  # When WE captured this
        
        # Check for status change
        old_status = event.status
        
        if item.actual_eps is not None and event.preliminary_eps is None:
            # New actual appeared!
            event.status = EarningsEventStatus.RELEASED
            event.released_at = item.announced_at  # Vendor's timestamp
            event.released_captured_at = captured_at  # OUR timestamp
            event.preliminary_eps = item.actual_eps
            event.preliminary_revenue = item.actual_revenue
            
            if old_status != EarningsEventStatus.RELEASED:
                # 🔔 This is a NEW release!
                await notify_new_release(event)
        
        elif item.scheduled_date != event.scheduled_on:
            # Date was revised
            event.revision_history.append({
                "old_date": event.scheduled_on,
                "new_date": item.scheduled_date,
                "captured_at": captured_at,
            })
            event.scheduled_on = item.scheduled_date
            event.revision_count += 1
            event.status = EarningsEventStatus.REVISED
        
        await event_store.update(event)
```

### Option 4: Company IR Website Scraping (Free, Slow)

```python
async def ingest_from_ir_websites():
    """
    Scrape company IR websites for calendar info.
    
    Pros: Free, early access to scheduled dates
    Cons: Slow, unreliable, different format per company
    """
    # This would need per-company scrapers
    scrapers = {
        "AAPL": AppleIRScraper(),
        "MSFT": MicrosoftIRScraper(),
        # ...
    }
    
    for ticker, scraper in scrapers.items():
        try:
            calendar_info = await scraper.get_upcoming_earnings()
            
            if calendar_info:
                event = await find_or_create_event(
                    ticker=ticker,
                    period=calendar_info.period,
                )
                
                if event.scheduled_on != calendar_info.date:
                    # Date announced or changed
                    event.scheduled_on = calendar_info.date
                    event.report_time = calendar_info.time
                    event.announced_on = date.today()
                    event.announced_captured_at = datetime.utcnow()
                    event.status = EarningsEventStatus.SCHEDULED
                    
                    await event_store.update(event)
        
        except Exception as e:
            logger.error(f"Failed to scrape {ticker} IR: {e}")
```

---

## The "What's New" Query You Actually Want

```python
class CalendarChangeDetector:
    """
    Detects changes in the earnings calendar.
    
    This solves the problem: "Show me ONLY what changed since I last looked"
    """
    
    def __init__(self, event_store):
        self.event_store = event_store
        self._last_check: dict[str, datetime] = {}  # view_name -> timestamp
    
    async def get_new_releases(
        self,
        since: datetime,
        min_market_cap: Optional[float] = None,
    ) -> list[EarningsEvent]:
        """
        Companies that reported since `since`.
        
        This is the killer feature Bloomberg doesn't provide.
        """
        return await self.event_store.query_events(
            status=EarningsEventStatus.RELEASED,
            released_captured_after=since,  # Using OUR timestamp
            min_market_cap=min_market_cap,
        )
    
    async def get_upcoming_today(
        self,
        report_time: Optional[ReportTime] = None,
    ) -> list[EarningsEvent]:
        """What's expected to report today (that hasn't yet)."""
        return await self.event_store.query_events(
            scheduled_on=date.today(),
            status=EarningsEventStatus.SCHEDULED,
            report_time=report_time,
        )
    
    async def get_date_changes(
        self,
        since: datetime,
    ) -> list[EarningsEvent]:
        """Companies that changed their earnings date."""
        return await self.event_store.query_events(
            status=EarningsEventStatus.REVISED,
            revised_captured_after=since,
        )
    
    async def poll_and_notify(
        self,
        view_name: str,
        callback,
    ):
        """
        Continuously poll for changes and notify.
        
        This replaces your manual CSV export workflow.
        """
        while True:
            last = self._last_check.get(view_name, datetime.utcnow() - timedelta(hours=1))
            
            new_releases = await self.get_new_releases(since=last)
            
            for event in new_releases:
                await callback(event)
            
            self._last_check[view_name] = datetime.utcnow()
            await asyncio.sleep(60)  # Check every minute


# Usage
detector = CalendarChangeDetector(event_store)

async def on_new_release(event: EarningsEvent):
    print(f"🚨 {event.entity_id} just reported!")
    print(f"   EPS: ${event.preliminary_eps}")
    print(f"   Surprise: {event.surprise_pct:+.1%}")
    print(f"   Released at: {event.released_at}")
    print(f"   We captured at: {event.released_captured_at}")
    
    # Your existing workflow can continue here
    # - Update spreadsheet
    # - Trigger alerts
    # - Queue for comparison analysis

# Replace your Bloomberg export + macro workflow
asyncio.run(detector.poll_and_notify("today", on_new_release))
```

---

## Matching Your Bloomberg CSV Export

Looking at your attached CSV, here's how we'd replicate that view:

```python
async def export_bloomberg_style_csv(output_path: str, date_filter: date = None):
    """
    Export in the same format as Bloomberg ERN export.
    
    Columns match your CSV:
    - Company info (ticker, name, sector, market cap)
    - Timing (date, AMC/BMO)
    - Estimates (EPS est, Rev est)
    - Actuals (EPS act, Rev act) - filled in when released
    - Our additions: released_at, captured_at, status
    """
    date_filter = date_filter or date.today()
    
    events = await event_store.query_events(
        scheduled_on=date_filter,
    )
    
    rows = []
    for event in events:
        entity = await entity_store.get(event.entity_id)
        
        # Get estimates
        eps_est = await obs_storage.get_observation(
            entity_id=event.entity_id,
            metric_code="eps",
            period=event.period_key,
            scope="CONSENSUS",
        )
        rev_est = await obs_storage.get_observation(
            entity_id=event.entity_id,
            metric_code="revenue",
            period=event.period_key,
            scope="CONSENSUS",
        )
        
        row = {
            # Identity (like Bloomberg)
            "TICKER": entity.ticker,
            "COMPANY_NAME": entity.name,
            "SECTOR": entity.sector,
            "INDUSTRY": entity.industry,
            "MARKET_CAP": entity.market_cap,
            
            # Timing (like Bloomberg)
            "DATE": event.scheduled_on,
            "TIME": event.report_time.value.upper(),  # "AMC", "BMO"
            
            # Estimates (like Bloomberg)
            "EPS_EST": eps_est.value if eps_est else None,
            "REV_EST": rev_est.value if rev_est else None,
            
            # Actuals (filled in when released)
            "EPS_ACT": event.preliminary_eps,
            "REV_ACT": event.preliminary_revenue,
            "SURPRISE_PCT": event.surprise_pct,
            
            # OUR ADDITIONS (what Bloomberg doesn't give you)
            "STATUS": event.status.value,
            "RELEASED_AT": event.released_at,          # When company announced
            "CAPTURED_AT": event.released_captured_at,  # When we captured
            "SOURCE": event.release_source,
            "FILED_8K": event.filed_8k_at,
            "FILED_10Q": event.filed_10q_at,
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    
    return df
```

---

## Summary: What We're Building

| Feature | Bloomberg/FactSet | Our System |
|---------|-------------------|------------|
| Scheduled dates | ✅ | ✅ |
| Estimates | ✅ | ✅ |
| Actuals (when released) | ✅ | ✅ |
| When WE captured it | ❌ | ✅ `captured_at` |
| "What's new since X?" | ❌ Manual diff | ✅ `get_new_releases(since=...)` |
| Notifications | ❌ | ✅ Webhooks/streams |
| Date revision tracking | ❌ | ✅ `revision_history` |
| Full lifecycle (PR → 8-K → 10-Q) | Partial | ✅ Full tracking |
| SQL-like views | Limited | ✅ `create_view()` |
| Free? | ❌ $$$$ | ✅ (with SEC data) |

---

## Source Authority Tracking

**Critical Insight:** Where the EPS came from matters!

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        EPS SOURCE HIERARCHY                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  AUTHORITY LEVEL     SOURCE              TIMING           RELIABILITY               │
│  ──────────────      ──────              ──────           ───────────               │
│                                                                                      │
│  100 (highest)       SEC 10-Q/10-K       Days/weeks       Audited, XBRL             │
│                      XBRL filing         after PR         authoritative             │
│                                                                                      │
│  90                  SEC 8-K             Same day         Official filing           │
│                      Item 2.02           (hours after PR) but not audited           │
│                                                                                      │
│  80                  Company PR          Immediate        May be preliminary        │
│                      Press release       (wire service)   "subject to change"       │
│                                                                                      │
│  70                  Vendor (Bloomberg)  Minutes          Parsed from PR            │
│                      Vendor (FactSet)    after PR         vendor methodology        │
│                      Vendor (Zacks)                                                 │
│                                                                                      │
│  60                  API (Finnhub)       Minutes/hours    Aggregated from           │
│                      API (Alpha Vantage) after PR         various sources           │
│                                                                                      │
│  50 (lowest)         Web scrape          Variable         May be delayed            │
│                      (Yahoo, Nasdaq)                      or incomplete             │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Why This Matters

```python
# Same company, same quarter, different EPS values!
observations = [
    # From press release (fast, preliminary)
    Observation(
        entity_id="aapl",
        metric=MetricSpec(code="eps", basis="ADJUSTED"),
        value=Decimal("2.18"),
        source=SourceKey(vendor="company", feed="press_release", authority=80),
        as_of=datetime(2026, 1, 30, 16, 30),  # 4:30 PM
    ),
    
    # From 8-K filing (same day, official)
    Observation(
        entity_id="aapl",
        metric=MetricSpec(code="eps", basis="GAAP"),  # Note: GAAP!
        value=Decimal("2.15"),  # Different number!
        source=SourceKey(vendor="sec", feed="8k", authority=90),
        as_of=datetime(2026, 1, 30, 19, 15),  # 7:15 PM
    ),
    
    # From 10-Q XBRL (weeks later, authoritative)
    Observation(
        entity_id="aapl",
        metric=MetricSpec(code="eps", basis="GAAP"),
        value=Decimal("2.15"),  # Confirmed
        source=SourceKey(vendor="sec", feed="10q_xbrl", authority=100),
        as_of=datetime(2026, 2, 15),
    ),
]

# When comparing to estimates, need to know:
# - Are we comparing GAAP or Adjusted?
# - Is this preliminary (PR) or final (10-Q)?
# - What authority level is acceptable?
```

### EarningsEvent Source Tracking

```python
@dataclass
class EarningsEvent:
    # ... existing fields ...
    
    # Source tracking (NEW)
    eps_sources: list[EPSSource] = field(default_factory=list)
    
    @property
    def best_eps(self) -> Optional[Decimal]:
        """Get highest-authority EPS we have."""
        if not self.eps_sources:
            return None
        return max(self.eps_sources, key=lambda s: s.authority).value
    
    @property
    def eps_source_type(self) -> Optional[str]:
        """Where did our best EPS come from?"""
        if not self.eps_sources:
            return None
        return max(self.eps_sources, key=lambda s: s.authority).source_type


@dataclass
class EPSSource:
    """Track where an EPS value came from."""
    value: Decimal
    basis: str  # "GAAP", "ADJUSTED"
    source_type: str  # "PRESS_RELEASE", "8K", "10Q", "VENDOR", "API"
    authority: int
    captured_at: datetime
    metadata: dict = field(default_factory=dict)  # accession_number, etc.
```

---

## Available Data Sources (Free/Low-Cost)

Here are data sources we can build adapters for:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        FREE/ACCESSIBLE DATA SOURCES                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  TIER 1: FREE, OFFICIAL, RELIABLE                                                   │
│  ─────────────────────────────────                                                  │
│                                                                                      │
│  1. SEC EDGAR                                                                       │
│     • RSS Feed: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=   │
│     • Full-Text Search API                                                          │
│     • XBRL API for financials                                                       │
│     • ✅ We already have py-sec-edgar!                                              │
│     • Latency: Minutes to hours after filing                                        │
│                                                                                      │
│  2. SEC EDGAR Company Facts API                                                     │
│     • https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json                      │
│     • All XBRL facts for a company                                                  │
│     • Free, no auth required                                                        │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                      │
│  TIER 2: FREE APIs (with limits)                                                    │
│  ───────────────────────────────                                                    │
│                                                                                      │
│  3. Finnhub (finnhub.io)                                                            │
│     • Earnings calendar: /calendar/earnings                                         │
│     • Free tier: 60 calls/minute                                                    │
│     • Has: date, EPS estimate, EPS actual, revenue, surprise                        │
│     • Good for testing!                                                             │
│                                                                                      │
│  4. Alpha Vantage                                                                   │
│     • EARNINGS endpoint                                                             │
│     • Free tier: 5 calls/minute, 500/day                                           │
│     • Has historical earnings                                                       │
│                                                                                      │
│  5. Financial Modeling Prep (FMP)                                                   │
│     • /earning_calendar endpoint                                                    │
│     • Free tier: 250 calls/day                                                      │
│     • Has estimates and actuals                                                     │
│                                                                                      │
│  6. Polygon.io                                                                      │
│     • /vX/reference/tickers/{ticker}/earnings                                       │
│     • Free tier: 5 calls/minute                                                     │
│     • Good data quality                                                             │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                      │
│  TIER 3: WEB SCRAPING (free but fragile)                                           │
│  ───────────────────────────────────────                                           │
│                                                                                      │
│  7. Nasdaq Earnings Calendar                                                        │
│     • https://www.nasdaq.com/market-activity/earnings                              │
│     • Requires scraping                                                             │
│     • Has BMO/AMC timing                                                            │
│                                                                                      │
│  8. Yahoo Finance                                                                   │
│     • https://finance.yahoo.com/calendar/earnings                                  │
│     • Requires scraping (or yfinance library)                                      │
│     • Often delayed                                                                 │
│                                                                                      │
│  9. Zacks.com                                                                       │
│     • https://www.zacks.com/earnings/earnings-calendar                             │
│     • Requires scraping                                                             │
│     • Good historical data                                                          │
│                                                                                      │
│  10. Earnings Whispers                                                              │
│      • https://www.earningswhispers.com/calendar                                   │
│      • Has "whisper" numbers (unofficial expectations)                             │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                      │
│  TIER 4: RSS/ATOM FEEDS                                                            │
│  ──────────────────────                                                            │
│                                                                                      │
│  11. SEC EDGAR RSS                                                                  │
│      • https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-Q       │
│      • Real-time new filings                                                        │
│      • Can filter by form type                                                      │
│                                                                                      │
│  12. PR Newswire RSS (limited)                                                      │
│      • https://www.prnewswire.com/rss/                                             │
│      • Financial news releases                                                      │
│      • Need to filter for earnings                                                  │
│                                                                                      │
│  13. Business Wire RSS                                                              │
│      • https://www.businesswire.com/portal/site/home/news/                         │
│      • Similar to PR Newswire                                                       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Adapter Pattern Design

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncIterator, Optional


@dataclass
class RawCalendarItem:
    """
    Normalized calendar item from any source.
    
    Adapters convert source-specific formats to this common format.
    """
    # Identity
    ticker: str
    company_name: Optional[str] = None
    
    # Timing
    scheduled_date: Optional[date] = None
    report_time: Optional[str] = None  # "BMO", "AMC", "DMH"
    
    # Period
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None  # 1-4, None for annual
    
    # Estimates
    eps_estimate: Optional[Decimal] = None
    revenue_estimate: Optional[Decimal] = None
    
    # Actuals (if released)
    eps_actual: Optional[Decimal] = None
    revenue_actual: Optional[Decimal] = None
    
    # Metadata
    source: str  # "finnhub", "sec", "nasdaq", etc.
    source_url: Optional[str] = None
    fetched_at: datetime = None  # When WE fetched it
    raw_data: Optional[dict] = None  # Original response for debugging


class CalendarAdapter(ABC):
    """
    Base class for calendar data source adapters.
    
    Each data source implements this interface.
    """
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source."""
        pass
    
    @property
    @abstractmethod
    def authority_level(self) -> int:
        """Authority level (50-100) for source ranking."""
        pass
    
    @abstractmethod
    async def get_calendar(
        self,
        start_date: date,
        end_date: date,
    ) -> list[RawCalendarItem]:
        """Get calendar items for a date range."""
        pass
    
    @abstractmethod
    async def watch(
        self,
        poll_interval_seconds: int = 60,
    ) -> AsyncIterator[RawCalendarItem]:
        """Watch for new/updated items (streaming)."""
        pass
    
    async def get_for_ticker(
        self,
        ticker: str,
        periods: int = 4,
    ) -> list[RawCalendarItem]:
        """Get historical earnings for a specific ticker."""
        raise NotImplementedError(f"{self.source_name} doesn't support ticker lookup")


# ═══════════════════════════════════════════════════════════════════════════════════
# ADAPTER IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════════

class SECEdgarAdapter(CalendarAdapter):
    """
    SEC EDGAR filings as calendar source.
    
    Uses py-sec-edgar to monitor 8-K and 10-Q filings.
    """
    
    source_name = "sec_edgar"
    authority_level = 95
    
    def __init__(self):
        from py_sec_edgar.feeds import EDGARFeed
        self.feed = EDGARFeed()
    
    async def get_calendar(self, start_date: date, end_date: date) -> list[RawCalendarItem]:
        """Get filings in date range."""
        items = []
        
        # Query 8-K (earnings announcements) and 10-Q (quarterly reports)
        filings = await self.feed.search(
            form_types=["8-K", "10-Q", "10-K"],
            filed_after=start_date,
            filed_before=end_date,
        )
        
        for filing in filings:
            # Only include earnings-related 8-Ks
            if filing.form_type == "8-K":
                if not await self._is_earnings_8k(filing):
                    continue
            
            item = RawCalendarItem(
                ticker=await self._cik_to_ticker(filing.cik),
                company_name=filing.company_name,
                scheduled_date=filing.filed_date,
                fiscal_year=filing.fiscal_year,
                fiscal_quarter=filing.fiscal_quarter,
                source=self.source_name,
                source_url=filing.url,
                fetched_at=datetime.utcnow(),
                raw_data={"accession_number": filing.accession_number},
            )
            
            # Extract XBRL data if 10-Q/10-K
            if filing.form_type in ("10-Q", "10-K"):
                xbrl = await self._extract_xbrl(filing)
                item.eps_actual = xbrl.get("eps_diluted")
                item.revenue_actual = xbrl.get("revenue")
            
            items.append(item)
        
        return items
    
    async def watch(self, poll_interval_seconds: int = 60) -> AsyncIterator[RawCalendarItem]:
        """Watch SEC RSS feed for new filings."""
        async for filing in self.feed.watch(
            form_types=["8-K", "10-Q", "10-K"],
            poll_interval=poll_interval_seconds,
        ):
            if filing.form_type == "8-K" and not await self._is_earnings_8k(filing):
                continue
            
            yield RawCalendarItem(
                ticker=await self._cik_to_ticker(filing.cik),
                company_name=filing.company_name,
                scheduled_date=filing.filed_date,
                source=self.source_name,
                fetched_at=datetime.utcnow(),
                raw_data={"accession_number": filing.accession_number},
            )


class FinnhubAdapter(CalendarAdapter):
    """
    Finnhub.io API adapter.
    
    Free tier: 60 calls/minute
    Good for: Testing, real-time calendar
    """
    
    source_name = "finnhub"
    authority_level = 65
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
    
    async def get_calendar(self, start_date: date, end_date: date) -> list[RawCalendarItem]:
        """Get earnings calendar from Finnhub."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/calendar/earnings",
                params={
                    "from": start_date.isoformat(),
                    "to": end_date.isoformat(),
                    "token": self.api_key,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        items = []
        for row in data.get("earningsCalendar", []):
            items.append(RawCalendarItem(
                ticker=row["symbol"],
                company_name=None,  # Finnhub doesn't include this
                scheduled_date=date.fromisoformat(row["date"]),
                report_time=self._map_hour(row.get("hour")),
                fiscal_year=row.get("year"),
                fiscal_quarter=row.get("quarter"),
                eps_estimate=Decimal(str(row["epsEstimate"])) if row.get("epsEstimate") else None,
                eps_actual=Decimal(str(row["epsActual"])) if row.get("epsActual") else None,
                revenue_estimate=Decimal(str(row["revenueEstimate"])) if row.get("revenueEstimate") else None,
                revenue_actual=Decimal(str(row["revenueActual"])) if row.get("revenueActual") else None,
                source=self.source_name,
                fetched_at=datetime.utcnow(),
                raw_data=row,
            ))
        
        return items
    
    def _map_hour(self, hour: str) -> Optional[str]:
        return {"bmo": "BMO", "amc": "AMC", "dmh": "DMH"}.get(hour)


class AlphaVantageAdapter(CalendarAdapter):
    """
    Alpha Vantage API adapter.
    
    Free tier: 5 calls/minute, 500/day
    Good for: Historical earnings data
    """
    
    source_name = "alpha_vantage"
    authority_level = 60
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
    
    async def get_for_ticker(self, ticker: str, periods: int = 4) -> list[RawCalendarItem]:
        """Get earnings history for a ticker."""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.base_url,
                params={
                    "function": "EARNINGS",
                    "symbol": ticker,
                    "apikey": self.api_key,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        items = []
        for row in data.get("quarterlyEarnings", [])[:periods]:
            items.append(RawCalendarItem(
                ticker=ticker,
                scheduled_date=date.fromisoformat(row["reportedDate"]),
                fiscal_year=int(row["fiscalDateEnding"][:4]),
                eps_estimate=Decimal(row["estimatedEPS"]) if row.get("estimatedEPS") != "None" else None,
                eps_actual=Decimal(row["reportedEPS"]) if row.get("reportedEPS") != "None" else None,
                source=self.source_name,
                fetched_at=datetime.utcnow(),
                raw_data=row,
            ))
        
        return items


class NasdaqScraperAdapter(CalendarAdapter):
    """
    Nasdaq.com earnings calendar scraper.
    
    Free but fragile (HTML scraping).
    Good for: BMO/AMC timing, company names
    """
    
    source_name = "nasdaq_scrape"
    authority_level = 55
    
    async def get_calendar(self, start_date: date, end_date: date) -> list[RawCalendarItem]:
        """Scrape Nasdaq earnings calendar."""
        import httpx
        from bs4 import BeautifulSoup
        
        items = []
        current = start_date
        
        while current <= end_date:
            url = f"https://www.nasdaq.com/market-activity/earnings?date={current.isoformat()}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                # Parse the table... (implementation depends on HTML structure)
                # This is fragile and needs maintenance
                
            current += timedelta(days=1)
        
        return items


class YahooFinanceAdapter(CalendarAdapter):
    """
    Yahoo Finance via yfinance library.
    
    Free but rate-limited.
    Good for: Quick ticker lookups
    """
    
    source_name = "yahoo_finance"
    authority_level = 55
    
    async def get_for_ticker(self, ticker: str, periods: int = 4) -> list[RawCalendarItem]:
        """Get earnings history using yfinance."""
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        earnings = stock.earnings_dates
        
        items = []
        for idx, row in earnings.head(periods).iterrows():
            items.append(RawCalendarItem(
                ticker=ticker,
                company_name=stock.info.get("longName"),
                scheduled_date=idx.date(),
                eps_estimate=Decimal(str(row["EPS Estimate"])) if pd.notna(row.get("EPS Estimate")) else None,
                eps_actual=Decimal(str(row["Reported EPS"])) if pd.notna(row.get("Reported EPS")) else None,
                source=self.source_name,
                fetched_at=datetime.utcnow(),
            ))
        
        return items
```

---

## Customizable Calendar View (Your Bloomberg EVTS Request)

```python
@dataclass
class CalendarColumn:
    """Column definition for calendar view."""
    name: str                    # Column header
    field: str                   # Data field to pull
    format: str = None           # Format string (e.g., "{:.2f}", "{:%Y-%m-%d}")
    source: str = "event"        # "event", "entity", "observation"
    width: int = None            # Column width hint


class CustomCalendarView:
    """
    Customizable calendar view matching Bloomberg EVTS export.
    
    Users can define which columns appear and how they're formatted.
    """
    
    # Preset column definitions
    STANDARD_COLUMNS = {
        # From Event
        "ticker": CalendarColumn("TICKER", "entity.ticker"),
        "company_name": CalendarColumn("COMPANY", "entity.name"),
        "scheduled_date": CalendarColumn("DATE", "event.scheduled_on", "{:%Y-%m-%d}"),
        "report_time": CalendarColumn("TIME", "event.report_time"),
        "status": CalendarColumn("STATUS", "event.status"),
        
        # From Entity
        "sector": CalendarColumn("SECTOR", "entity.sector"),
        "industry": CalendarColumn("INDUSTRY", "entity.industry"),
        "market_cap": CalendarColumn("MKTCAP", "entity.market_cap", "{:,.0f}"),
        "exchange": CalendarColumn("EXCH", "entity.exchange"),
        
        # From Observations
        "eps_estimate": CalendarColumn("EPS EST", "obs.eps.consensus", "{:.2f}"),
        "eps_actual": CalendarColumn("EPS ACT", "event.preliminary_eps", "{:.2f}"),
        "eps_surprise": CalendarColumn("EPS SURP%", "computed.eps_surprise", "{:+.1%}"),
        "rev_estimate": CalendarColumn("REV EST", "obs.revenue.consensus", "{:,.0f}"),
        "rev_actual": CalendarColumn("REV ACT", "event.preliminary_revenue", "{:,.0f}"),
        "rev_surprise": CalendarColumn("REV SURP%", "computed.rev_surprise", "{:+.1%}"),
        
        # Our additions (what Bloomberg doesn't have)
        "released_at": CalendarColumn("RELEASED", "event.released_at", "{:%H:%M:%S}"),
        "captured_at": CalendarColumn("CAPTURED", "event.released_captured_at", "{:%H:%M:%S}"),
        "source": CalendarColumn("SOURCE", "event.release_source"),
        "filed_8k": CalendarColumn("8-K FILED", "event.filed_8k_at", "{:%Y-%m-%d}"),
        "filed_10q": CalendarColumn("10-Q FILED", "event.filed_10q_at", "{:%Y-%m-%d}"),
    }
    
    # Bloomberg-like presets
    PRESETS = {
        "bloomberg_evts": [
            "ticker", "company_name", "scheduled_date", "report_time",
            "sector", "market_cap", "eps_estimate", "eps_actual",
            "eps_surprise", "rev_estimate", "rev_actual", "rev_surprise",
        ],
        "minimal": [
            "ticker", "scheduled_date", "report_time", "eps_estimate",
            "eps_actual", "eps_surprise",
        ],
        "full_tracking": [
            "ticker", "company_name", "scheduled_date", "report_time",
            "status", "eps_estimate", "eps_actual", "eps_surprise",
            "released_at", "captured_at", "source", "filed_8k", "filed_10q",
        ],
    }
    
    def __init__(
        self,
        columns: list[str] = None,
        preset: str = "bloomberg_evts",
        custom_columns: list[CalendarColumn] = None,
    ):
        if columns:
            self.columns = [self.STANDARD_COLUMNS[c] for c in columns]
        elif preset:
            self.columns = [self.STANDARD_COLUMNS[c] for c in self.PRESETS[preset]]
        else:
            self.columns = []
        
        if custom_columns:
            self.columns.extend(custom_columns)
    
    async def render(
        self,
        events: list[EarningsEvent],
        entity_store,
        obs_storage,
        format: str = "dataframe",  # "dataframe", "csv", "json", "excel"
    ) -> pd.DataFrame:
        """Render events using configured columns."""
        
        rows = []
        for event in events:
            entity = await entity_store.get(event.entity_id)
            
            row = {}
            for col in self.columns:
                value = await self._resolve_value(col, event, entity, obs_storage)
                if col.format and value is not None:
                    row[col.name] = col.format.format(value)
                else:
                    row[col.name] = value
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        if format == "csv":
            return df.to_csv(index=False)
        elif format == "json":
            return df.to_json(orient="records")
        elif format == "excel":
            # Returns bytes for Excel file
            output = io.BytesIO()
            df.to_excel(output, index=False)
            return output.getvalue()
        else:
            return df


# Usage
view = CustomCalendarView(preset="bloomberg_evts")
df = await view.render(todays_events, entity_store, obs_storage)
print(df)

# Or with custom columns
view = CustomCalendarView(
    columns=["ticker", "company_name", "eps_actual", "eps_surprise"],
    custom_columns=[
        CalendarColumn("MY_FIELD", "entity.custom_field"),
    ],
)
```

---

## URL & Link Tracking (Bloomberg-Style)

**Key Insight:** Bloomberg CSV exports include clickable links to:
- SEC filings (10-Q, 8-K, 10-K)
- Press releases
- Investor Relations pages
- Conference call registration
- Earnings webcast replay

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        LINK TYPES IN EARNINGS EVENTS                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  LINK TYPE              SOURCE                    HOW TO GET IT                     │
│  ─────────              ──────                    ─────────────                     │
│                                                                                      │
│  SEC Filing (10-Q)      EDGAR                     Direct from py-sec-edgar         │
│  sec_10q_url            Authoritative             https://sec.gov/Archives/...     │
│                                                                                      │
│  SEC Filing (8-K)       EDGAR                     Direct from py-sec-edgar         │
│  sec_8k_url             Item 2.02                 https://sec.gov/Archives/...     │
│                                                                                      │
│  Press Release          News Wire                 Captured during ingestion        │
│  press_release_url      PR Newswire, Biz Wire     https://prnewswire.com/...       │
│                                                                                      │
│  Investor Relations     Company website           Stored in EntitySpine            │
│  ir_website_url         Standard patterns         https://investor.apple.com       │
│                                                                                      │
│  Conference Call        IR website / PR           Extracted from PR text           │
│  conference_call_url    Usually registration      https://webcast.company.com/...  │
│                                                                                      │
│  Webcast Replay         IR website / 8-K          Appears after call ends          │
│  webcast_replay_url     Often in 8-K exhibit      https://edge.media-server.com/.. │
│                                                                                      │
│  Earnings Presentation  IR website                Linked from PR or IR page        │
│  presentation_url       Usually PDF/PPT           https://investor.apple.com/...   │
│                                                                                      │
│  Supplemental Data      IR website                Company-specific                 │
│  supplemental_url       Excel/PDF downloads       https://investor.apple.com/...   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Enhanced EarningsEvent with Links

```python
@dataclass
class EarningsEventLinks:
    """
    All URLs related to an earnings event.
    
    Bloomberg has these because they maintain relationship tracking.
    We can build the same thing.
    """
    
    # SEC Filings (from py-sec-edgar)
    sec_8k_url: Optional[str] = None           # Item 2.02 Results of Operations
    sec_8k_exhibit_url: Optional[str] = None   # Often has the actual PR as exhibit
    sec_10q_url: Optional[str] = None          # Quarterly report
    sec_10k_url: Optional[str] = None          # Annual report
    sec_xbrl_viewer_url: Optional[str] = None  # Interactive XBRL viewer
    
    # Press Release
    press_release_url: Optional[str] = None        # Original wire URL
    press_release_pdf_url: Optional[str] = None    # PDF version if available
    press_release_wire: Optional[str] = None       # "PR_NEWSWIRE", "BUSINESS_WIRE"
    
    # Investor Relations (from EntitySpine)
    ir_website_url: Optional[str] = None           # Main IR landing page
    ir_events_url: Optional[str] = None            # Events/calendar page
    ir_financial_url: Optional[str] = None         # Financial results archive
    
    # Conference Call
    conference_call_url: Optional[str] = None      # Registration/dial-in
    conference_call_passcode: Optional[str] = None # If extracted from PR
    webcast_live_url: Optional[str] = None         # Live webcast URL
    webcast_replay_url: Optional[str] = None       # Replay (available after)
    replay_available_until: Optional[date] = None  # Expiration date
    
    # Presentations & Supplemental
    presentation_url: Optional[str] = None         # Earnings slides (PDF/PPT)
    supplemental_url: Optional[str] = None         # Supplemental data (Excel)
    transcript_url: Optional[str] = None           # Call transcript (if available)


@dataclass
class EarningsEvent:
    """Enhanced with links."""
    # ... existing fields ...
    
    # Links (NEW)
    links: EarningsEventLinks = field(default_factory=EarningsEventLinks)
```

### Where Each Link Comes From

```python
class LinkResolver:
    """
    Resolves and populates links for earnings events.
    
    Different sources for different link types.
    """
    
    def __init__(self, edgar_client, entity_store, pr_parser):
        self.edgar = edgar_client
        self.entity_store = entity_store
        self.pr_parser = pr_parser
    
    async def resolve_links(self, event: EarningsEvent) -> EarningsEventLinks:
        """Populate all available links for an event."""
        links = EarningsEventLinks()
        
        # 1. SEC Filing URLs (from py-sec-edgar)
        await self._resolve_sec_links(event, links)
        
        # 2. IR Website URLs (from EntitySpine)
        await self._resolve_ir_links(event, links)
        
        # 3. Press Release URLs (captured during ingestion)
        await self._resolve_pr_links(event, links)
        
        # 4. Conference Call URLs (extracted from PR or IR page)
        await self._resolve_call_links(event, links)
        
        return links
    
    async def _resolve_sec_links(self, event: EarningsEvent, links: EarningsEventLinks):
        """
        Build SEC filing URLs from accession numbers.
        
        We already have accession numbers from py-sec-edgar ingestion.
        """
        entity = await self.entity_store.get(event.entity_id)
        cik = entity.cik.lstrip("0")  # Remove leading zeros for URL
        cik_padded = entity.cik.zfill(10)  # Pad to 10 digits for path
        
        if event.accession_8k:
            accession_clean = event.accession_8k.replace("-", "")
            links.sec_8k_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/"
                f"{event.accession_8k}-index.htm"
            )
            # XBRL viewer
            links.sec_xbrl_viewer_url = (
                f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik_padded}"
                f"&accession_number={event.accession_8k}&xbrl_type=v"
            )
        
        if event.accession_10q:
            accession_clean = event.accession_10q.replace("-", "")
            links.sec_10q_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/"
                f"{event.accession_10q}-index.htm"
            )
        
        if event.accession_10k:
            accession_clean = event.accession_10k.replace("-", "")
            links.sec_10k_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/"
                f"{event.accession_10k}-index.htm"
            )
    
    async def _resolve_ir_links(self, event: EarningsEvent, links: EarningsEventLinks):
        """
        Get IR website URLs from EntitySpine.
        
        These should be stored as Entity attributes.
        """
        entity = await self.entity_store.get(event.entity_id)
        
        # IR URLs stored in entity
        links.ir_website_url = getattr(entity, 'ir_website_url', None)
        links.ir_events_url = getattr(entity, 'ir_events_url', None)
        links.ir_financial_url = getattr(entity, 'ir_financial_url', None)
        
        # If not stored, try to construct from common patterns
        if not links.ir_website_url and entity.website:
            links.ir_website_url = self._guess_ir_url(entity.website, entity.ticker)
    
    def _guess_ir_url(self, company_website: str, ticker: str) -> Optional[str]:
        """
        Guess IR URL from company website.
        
        Common patterns:
        - investor.apple.com
        - microsoft.com/investor
        - amazon.com/ir
        """
        # These are common patterns
        domain = company_website.replace("https://", "").replace("http://", "").rstrip("/")
        
        common_patterns = [
            f"https://investor.{domain}",
            f"https://{domain}/investor",
            f"https://{domain}/ir",
            f"https://{domain}/investors",
            f"https://ir.{domain}",
        ]
        
        # Could verify with HEAD requests, but that's slow
        # Return most common pattern
        return f"https://investor.{domain}"
    
    async def _resolve_pr_links(self, event: EarningsEvent, links: EarningsEventLinks):
        """
        Get press release URL.
        
        This should be captured when we ingest the PR.
        """
        # If we ingested from a news wire, we captured the URL
        if event.press_release_raw_url:
            links.press_release_url = event.press_release_raw_url
            links.press_release_wire = event.release_source
        
        # Or extract from 8-K exhibit (often Exhibit 99.1 is the PR)
        elif event.accession_8k:
            exhibit_url = await self.edgar.get_exhibit_url(
                accession=event.accession_8k,
                exhibit_number="99.1",
            )
            if exhibit_url:
                links.press_release_pdf_url = exhibit_url
    
    async def _resolve_call_links(self, event: EarningsEvent, links: EarningsEventLinks):
        """
        Extract conference call URLs.
        
        Sources:
        1. Parsed from press release text
        2. Scraped from IR website
        3. From 8-K exhibit
        """
        # Try to extract from press release content
        if event.press_release_content:
            call_info = self.pr_parser.extract_conference_call_info(
                event.press_release_content
            )
            if call_info:
                links.conference_call_url = call_info.get("registration_url")
                links.conference_call_passcode = call_info.get("passcode")
                links.webcast_live_url = call_info.get("webcast_url")
        
        # If we have IR events page, could scrape for call URL
        if not links.conference_call_url and links.ir_events_url:
            # This would require scraping the IR page
            pass
```

### Press Release Parser (Extracting URLs from Text)

```python
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ConferenceCallInfo:
    """Extracted conference call details from press release."""
    date: Optional[date] = None
    time: Optional[str] = None  # "5:00 PM ET"
    dial_in_us: Optional[str] = None
    dial_in_intl: Optional[str] = None
    passcode: Optional[str] = None
    registration_url: Optional[str] = None
    webcast_url: Optional[str] = None
    replay_url: Optional[str] = None
    replay_available_until: Optional[date] = None


class PressReleaseParser:
    """
    Extract structured data from earnings press release text.
    
    Press releases follow common patterns that can be parsed.
    """
    
    # Regex patterns for common elements
    WEBCAST_PATTERNS = [
        r'webcast[^.]*(?:at|available at|accessible at)\s*(https?://[^\s<>"]+)',
        r'(https?://[^\s<>"]*webcast[^\s<>"]*)',
        r'(https?://[^\s<>"]*investor[^\s<>"]*event[^\s<>"]*)',
        r'live\s+(?:audio\s+)?webcast[^.]*?\s*(https?://[^\s<>"]+)',
    ]
    
    DIAL_IN_PATTERNS = [
        r'(?:dial-in|call-in|phone)[^:]*:\s*(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
        r'domestic[^:]*:\s*(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
        r'U\.S\.[^:]*:\s*(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
    ]
    
    PASSCODE_PATTERNS = [
        r'(?:passcode|conference id|access code)[^:]*:\s*(\d+)',
        r'(?:code|id)[^:]*:\s*(\d{6,})',
    ]
    
    REGISTRATION_PATTERNS = [
        r'(?:register|registration)[^.]*(?:at|visit)\s*(https?://[^\s<>"]+)',
        r'(https?://[^\s<>"]*register[^\s<>"]*)',
    ]
    
    def extract_conference_call_info(self, pr_text: str) -> Optional[ConferenceCallInfo]:
        """Extract conference call details from press release text."""
        info = ConferenceCallInfo()
        
        # Normalize text
        text = pr_text.lower()
        
        # Look for webcast URL
        for pattern in self.WEBCAST_PATTERNS:
            match = re.search(pattern, pr_text, re.IGNORECASE)
            if match:
                info.webcast_url = match.group(1)
                break
        
        # Look for dial-in numbers
        for pattern in self.DIAL_IN_PATTERNS:
            match = re.search(pattern, pr_text, re.IGNORECASE)
            if match:
                info.dial_in_us = match.group(1)
                break
        
        # Look for passcode
        for pattern in self.PASSCODE_PATTERNS:
            match = re.search(pattern, pr_text, re.IGNORECASE)
            if match:
                info.passcode = match.group(1)
                break
        
        # Look for registration URL
        for pattern in self.REGISTRATION_PATTERNS:
            match = re.search(pattern, pr_text, re.IGNORECASE)
            if match:
                info.registration_url = match.group(1)
                break
        
        # Only return if we found something
        if any([info.webcast_url, info.dial_in_us, info.registration_url]):
            return info
        
        return None
    
    def extract_presentation_url(self, pr_text: str) -> Optional[str]:
        """Extract investor presentation URL."""
        patterns = [
            r'(?:presentation|slides)[^.]*(?:available at|at)\s*(https?://[^\s<>"]+)',
            r'(https?://[^\s<>"]+\.pdf)',  # PDF links
            r'(https?://[^\s<>"]+\.pptx?)',  # PowerPoint links
        ]
        
        for pattern in patterns:
            match = re.search(pattern, pr_text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
```

### Adding Link Columns to Calendar View

```python
# Add to STANDARD_COLUMNS in CustomCalendarView
LINK_COLUMNS = {
    # SEC Filings
    "sec_8k_url": CalendarColumn("8-K LINK", "event.links.sec_8k_url"),
    "sec_10q_url": CalendarColumn("10-Q LINK", "event.links.sec_10q_url"),
    "sec_xbrl_url": CalendarColumn("XBRL VIEWER", "event.links.sec_xbrl_viewer_url"),
    
    # Press Release
    "pr_url": CalendarColumn("PRESS RELEASE", "event.links.press_release_url"),
    
    # Investor Relations
    "ir_url": CalendarColumn("IR WEBSITE", "event.links.ir_website_url"),
    "ir_events_url": CalendarColumn("IR EVENTS", "event.links.ir_events_url"),
    
    # Conference Call
    "call_url": CalendarColumn("CONF CALL", "event.links.conference_call_url"),
    "webcast_url": CalendarColumn("WEBCAST", "event.links.webcast_live_url"),
    "replay_url": CalendarColumn("REPLAY", "event.links.webcast_replay_url"),
    
    # Presentation
    "presentation_url": CalendarColumn("SLIDES", "event.links.presentation_url"),
}

# New preset with links
PRESETS["bloomberg_with_links"] = [
    "ticker", "company_name", "scheduled_date", "report_time",
    "eps_estimate", "eps_actual", "eps_surprise",
    "pr_url", "ir_url", "call_url", "sec_8k_url", "sec_10q_url",
]
```

### EntitySpine: Storing IR URLs

```python
# In EntitySpine, add IR website fields to Entity
@dataclass
class Entity:
    # ... existing fields ...
    
    # Investor Relations URLs (NEW)
    ir_website_url: Optional[str] = None      # https://investor.apple.com
    ir_events_url: Optional[str] = None       # .../events-and-presentations
    ir_financial_url: Optional[str] = None    # .../financial-information
    ir_sec_filings_url: Optional[str] = None  # .../sec-filings (or link to EDGAR)
    ir_stock_info_url: Optional[str] = None   # .../stock-information
    
    # These can be populated:
    # 1. Manually for key companies
    # 2. From SEC EDGAR (some filings include IR website)
    # 3. Scraped/inferred from company website
    # 4. From vendor data feeds (FactSet has this)
```

### Data Sources for IR URLs

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        WHERE TO GET IR WEBSITE URLS                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  1. SEC EDGAR                                                                       │
│     • Form 10-K cover page sometimes includes IR website                            │
│     • Not standardized, but often present                                           │
│     • Free!                                                                         │
│                                                                                      │
│  2. SEC Company Search                                                              │
│     • https://efts.sec.gov/LATEST/search-index?q=AAPL                              │
│     • Returns company website in results                                            │
│     • Can derive IR URL from patterns                                               │
│                                                                                      │
│  3. EDGAR Company Tickers JSON                                                      │
│     • https://www.sec.gov/files/company_tickers.json                               │
│     • Has ticker + CIK mapping                                                      │
│     • No IR URLs, but helps with entity resolution                                  │
│                                                                                      │
│  4. Vendor Data (FactSet, Refinitiv)                                               │
│     • Usually includes IR website field                                             │
│     • Costs money                                                                    │
│                                                                                      │
│  5. Wikipedia/Wikidata                                                              │
│     • Has company website                                                           │
│     • Can derive IR URL                                                             │
│                                                                                      │
│  6. Company Facts API + 10-K Parsing                                               │
│     • Parse 10-K HTML for "investor relations" links                               │
│     • Fragile but free                                                              │
│                                                                                      │
│  7. Manual Curation                                                                 │
│     • For S&P 500 companies, manually verify                                        │
│     • ~500 companies, one-time effort                                               │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### IR URL Discovery Script

```python
import asyncio
import httpx
from dataclasses import dataclass


@dataclass
class IRUrlDiscoveryResult:
    """Result of IR URL discovery for a company."""
    entity_id: str
    company_website: str
    discovered_ir_url: Optional[str] = None
    verified: bool = False
    error: Optional[str] = None


class IRUrlDiscoverer:
    """
    Discover and verify IR website URLs for entities.
    """
    
    # Common IR URL patterns
    PATTERNS = [
        "investor.{domain}",
        "{domain}/investor",
        "{domain}/investors",
        "{domain}/ir",
        "ir.{domain}",
        "{domain}/investor-relations",
    ]
    
    async def discover_ir_url(
        self,
        company_website: str,
        verify: bool = True,
    ) -> IRUrlDiscoveryResult:
        """
        Try to discover IR website URL from company domain.
        """
        domain = self._extract_domain(company_website)
        result = IRUrlDiscoveryResult(
            entity_id="",
            company_website=company_website,
        )
        
        # Try each pattern
        for pattern in self.PATTERNS:
            url = f"https://{pattern.format(domain=domain)}"
            
            if verify:
                if await self._verify_url(url):
                    result.discovered_ir_url = url
                    result.verified = True
                    return result
            else:
                result.discovered_ir_url = url
                return result
        
        return result
    
    async def _verify_url(self, url: str) -> bool:
        """Check if URL is valid and returns 200."""
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.head(url, timeout=10)
                return response.status_code == 200
        except Exception:
            return False
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return (
            url.replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .split("/")[0]
        )


# Batch discovery for S&P 500
async def discover_sp500_ir_urls(entity_store):
    """Discover IR URLs for all S&P 500 companies."""
    discoverer = IRUrlDiscoverer()
    
    sp500 = await entity_store.query(indices=["SP500"])
    
    results = []
    for entity in sp500:
        if entity.website and not entity.ir_website_url:
            result = await discoverer.discover_ir_url(
                company_website=entity.website,
                verify=True,
            )
            result.entity_id = entity.id
            
            if result.discovered_ir_url:
                # Update entity
                entity.ir_website_url = result.discovered_ir_url
                await entity_store.update(entity)
            
            results.append(result)
    
    return results
```

---

## EntitySpine Integration: Gap Analysis

**Good news:** EntitySpine already has most of what we need!

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        ENTITYSPINE vs EARNINGS CALENDAR NEEDS                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  EntitySpine Event (graph.py) ALREADY HAS:                                          │
│  ────────────────────────────────────────                                           │
│                                                                                      │
│  ✅ event_type          EventType.EARNINGS_RELEASE, EARNINGS_CALL, etc.             │
│  ✅ status              EventStatus (ANNOUNCED, IN_PROGRESS, COMPLETED, CANCELLED)  │
│  ✅ scheduled_on        When earnings are expected                                   │
│  ✅ occurred_on         When event actually happened                                 │
│  ✅ announced_on        When scheduled date was announced                            │
│  ✅ effective_date      For dividends, etc.                                         │
│  ✅ fiscal_year         Fiscal year (2025, etc.)                                    │
│  ✅ fiscal_quarter      1-4 for quarterly                                           │
│  ✅ report_time         "BMO", "AMC", "DURING"                                       │
│  ✅ amount              Could store EPS here                                        │
│  ✅ currency            "USD"                                                        │
│  ✅ entity_id           Links to Entity                                             │
│  ✅ source_system       "sec", "factset", "finnhub", etc.                           │
│  ✅ source_id           Accession number, etc.                                      │
│  ✅ captured_at         When we ingested                                             │
│  ✅ payload             dict for arbitrary extra data!                              │
│  ✅ evidence_filing_id  FK to SEC filing                                            │
│                                                                                      │
│  EventType enum ALREADY HAS:                                                        │
│  ──────────────────────────                                                         │
│                                                                                      │
│  ✅ EARNINGS_RELEASE    Quarterly/annual earnings                                   │
│  ✅ EARNINGS_CALL       Conference call                                             │
│  ✅ EARNINGS_GUIDANCE   Forward guidance                                            │
│  ✅ EARNINGS_REVISION   Analyst estimate revision                                   │
│                                                                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  GAPS - What EntitySpine Event is MISSING:                                          │
│  ─────────────────────────────────────────                                          │
│                                                                                      │
│  ❌ EventStatus gaps:                                                               │
│     - No RELEASED (press release out, but no 10-Q yet)                              │
│     - No FILED_8K, FILED_10Q status                                                 │
│     - No REVISED (date changed)                                                     │
│     - No TENTATIVE (unconfirmed)                                                    │
│                                                                                      │
│  ❌ Revision tracking:                                                              │
│     - No original_scheduled_on                                                      │
│     - No revision_count                                                             │
│     - No revision_history                                                           │
│                                                                                      │
│  ❌ Released/captured timestamps:                                                   │
│     - No released_at (when PR hit the wire)                                         │
│     - No released_captured_at (when WE saw it)                                      │
│                                                                                      │
│  ❌ Multiple accession numbers:                                                     │
│     - Only evidence_filing_id (one filing)                                          │
│     - Need accession_8k AND accession_10q                                           │
│                                                                                      │
│  ❌ Financial data:                                                                 │
│     - No preliminary_eps, preliminary_revenue                                       │
│     - No xbrl_eps, xbrl_revenue (authoritative)                                     │
│     - No consensus_eps_at_release (snapshot)                                        │
│                                                                                      │
│  ❌ Links:                                                                          │
│     - No press_release_url                                                          │
│     - No conference_call_url, webcast_url                                           │
│     - No ir_website_url                                                             │
│     - No presentation_url                                                           │
│                                                                                      │
│  ❌ Source authority:                                                               │
│     - No authority_level (PR=80, 10-Q=100)                                         │
│     - No source tracking for EPS (which source gave which number)                   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Recommendation: Use `payload` + Add EventStatus

The cleanest approach:

1. **Extend EventStatus** in EntitySpine (small change):
   ```python
   class EventStatus(str, Enum):
       # Existing
       ANNOUNCED = "announced"
       IN_PROGRESS = "in_progress"
       COMPLETED = "completed"
       CANCELLED = "cancelled"
       PENDING = "pending"
       UNKNOWN = "unknown"
       
       # NEW - Earnings lifecycle specific
       TENTATIVE = "tentative"       # Unconfirmed date
       SCHEDULED = "scheduled"       # Confirmed date (alias for ANNOUNCED?)
       REVISED = "revised"           # Date was changed
       RELEASED = "released"         # Press release out, no filing yet
       FILED = "filed"               # Filing submitted (8-K or 10-Q)
   ```

2. **Use payload** for earnings-specific data:
   ```python
   # Create an EntitySpine Event
   event = Event(
       event_type=EventType.EARNINGS_RELEASE,
       title="Apple Q1 FY2026 Earnings",
       entity_id="ent_aapl",
       scheduled_on=date(2026, 1, 30),
       fiscal_year=2026,
       fiscal_quarter=1,
       report_time="AMC",
       status=EventStatus.RELEASED,  # NEW status
       occurred_on=date(2026, 1, 30),  # When it actually happened
       source_system="pr_newswire",
       captured_at=datetime.utcnow(),
       
       # Earnings-specific data in payload
       payload={
           # Release details
           "released_at": "2026-01-30T16:30:00Z",
           "released_captured_at": "2026-01-30T16:31:45Z",
           "release_source": "PR_NEWSWIRE",
           
           # Financial results (preliminary from PR)
           "preliminary_eps": "2.40",
           "preliminary_revenue": "124300000000",
           
           # Consensus at release (for surprise calc)
           "consensus_eps_at_release": "2.35",
           "consensus_revenue_at_release": "121500000000",
           
           # Revision tracking
           "original_scheduled_on": "2026-01-28",
           "revision_count": 1,
           "revision_history": [
               {"from": "2026-01-28", "to": "2026-01-30", "captured_at": "2026-01-15T10:00:00Z"}
           ],
           
           # SEC filings
           "accession_8k": "0000320193-26-000015",
           "filed_8k_at": "2026-01-30T19:15:00Z",
           "accession_10q": None,  # Not filed yet
           "filed_10q_at": None,
           
           # XBRL actuals (when 10-Q filed)
           "xbrl_eps": None,
           "xbrl_revenue": None,
           
           # Source authority
           "eps_authority": 80,  # From press release
           
           # Links
           "links": {
               "press_release_url": "https://www.prnewswire.com/...",
               "sec_8k_url": "https://www.sec.gov/Archives/...",
               "ir_website_url": "https://investor.apple.com",
               "conference_call_url": "https://webcast.apple.com/...",
               "presentation_url": "https://investor.apple.com/q1-2026-slides.pdf",
           },
       },
   )
   ```

3. **Create FeedSpine wrapper** for typed access:
   ```python
   # In FeedSpine
   from entityspine.domain.graph import Event
   from dataclasses import dataclass
   from decimal import Decimal
   from datetime import datetime
   from typing import Optional
   
   
   @dataclass
   class EarningsEventPayload:
       """
       Typed wrapper for earnings-specific payload data.
       
       EntitySpine stores this in Event.payload as dict.
       This class provides typed access.
       """
       
       # Release details
       released_at: Optional[datetime] = None
       released_captured_at: Optional[datetime] = None
       release_source: Optional[str] = None
       
       # Financial results
       preliminary_eps: Optional[Decimal] = None
       preliminary_revenue: Optional[Decimal] = None
       xbrl_eps: Optional[Decimal] = None
       xbrl_revenue: Optional[Decimal] = None
       
       # Consensus snapshot
       consensus_eps_at_release: Optional[Decimal] = None
       consensus_revenue_at_release: Optional[Decimal] = None
       
       # Revision tracking
       original_scheduled_on: Optional[date] = None
       revision_count: int = 0
       revision_history: list[dict] = None
       
       # SEC filings
       accession_8k: Optional[str] = None
       filed_8k_at: Optional[datetime] = None
       accession_10q: Optional[str] = None
       filed_10q_at: Optional[datetime] = None
       
       # Source authority (50-100)
       eps_authority: int = 0
       
       # Links
       links: Optional[dict] = None
       
       @classmethod
       def from_payload(cls, payload: dict) -> "EarningsEventPayload":
           """Parse from Event.payload dict."""
           if not payload:
               return cls()
           return cls(
               released_at=_parse_datetime(payload.get("released_at")),
               released_captured_at=_parse_datetime(payload.get("released_captured_at")),
               release_source=payload.get("release_source"),
               preliminary_eps=_parse_decimal(payload.get("preliminary_eps")),
               preliminary_revenue=_parse_decimal(payload.get("preliminary_revenue")),
               # ... etc
           )
       
       def to_payload(self) -> dict:
           """Serialize to dict for Event.payload."""
           return {
               "released_at": self.released_at.isoformat() if self.released_at else None,
               # ... etc
           }
   
   
   class EarningsEvent:
       """
       FeedSpine wrapper around EntitySpine Event for earnings.
       
       Provides typed access to earnings-specific data stored in payload.
       """
       
       def __init__(self, event: Event):
           self._event = event
           self._payload = EarningsEventPayload.from_payload(event.payload)
       
       # Delegate core fields to underlying Event
       @property
       def event_id(self) -> str:
           return self._event.event_id
       
       @property
       def entity_id(self) -> str:
           return self._event.entity_id
       
       @property
       def scheduled_on(self) -> date:
           return self._event.scheduled_on
       
       @property
       def fiscal_year(self) -> int:
           return self._event.fiscal_year
       
       @property
       def fiscal_quarter(self) -> int:
           return self._event.fiscal_quarter
       
       @property
       def status(self) -> EventStatus:
           return self._event.status
       
       # Typed access to payload fields
       @property
       def released_at(self) -> Optional[datetime]:
           return self._payload.released_at
       
       @property
       def preliminary_eps(self) -> Optional[Decimal]:
           return self._payload.preliminary_eps
       
       @property
       def surprise_pct(self) -> Optional[float]:
           """Calculate EPS surprise percentage."""
           if self._payload.preliminary_eps and self._payload.consensus_eps_at_release:
               return float(
                   (self._payload.preliminary_eps - self._payload.consensus_eps_at_release)
                   / abs(self._payload.consensus_eps_at_release)
               )
           return None
       
       @property
       def sec_10q_url(self) -> Optional[str]:
           """Build SEC 10-Q URL from accession number."""
           if not self._payload.accession_10q:
               return None
           # Build URL logic...
       
       def to_event(self) -> Event:
           """Get underlying EntitySpine Event."""
           return self._event
   ```

### Why This Approach?

| Approach | Pros | Cons |
|----------|------|------|
| **Extend Event model** | Typed fields | Bloats EntitySpine with FeedSpine concerns |
| **Separate EarningsEvent** | Clean separation | Two models to maintain, FK complexity |
| **payload + wrapper** ✅ | Best of both: EntitySpine stays clean, FeedSpine has typed access | Need to serialize/deserialize |

The `payload` dict is **designed for this exact use case** - domain-specific extensions without bloating the core model.

### EntitySpine Changes Needed

**Minimal change - just extend EventStatus:**

```python
# In entityspine/domain/enums/events.py

class EventStatus(str, Enum):
    """Status of a business event."""
    
    # Existing
    ANNOUNCED = "announced"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PENDING = "pending"
    UNKNOWN = "unknown"
    
    # NEW - Lifecycle stages for calendar events
    TENTATIVE = "tentative"    # Rumored/unconfirmed
    SCHEDULED = "scheduled"    # Date confirmed (similar to ANNOUNCED)
    REVISED = "revised"        # Date was changed
    RELEASED = "released"      # Results announced (PR out)
    FILED = "filed"            # SEC filing submitted
```

**Optional - add IR URLs to Entity:**

```python
# In entityspine/domain/core.py - Entity class

# Add these optional fields:
ir_website_url: str | None = None      # https://investor.apple.com
ir_events_url: str | None = None       # Events & presentations page
ir_sec_filings_url: str | None = None  # SEC filings page (or EDGAR link)
```

This keeps EntitySpine as the **domain layer** (what things are) while FeedSpine handles **data engineering** (how to ingest, transform, track).

---

## Next Steps

1. **Add EarningsEvent to EntitySpine** (or create separate CalendarSpine?)
2. **Build SEC ingestion pipeline** (py-sec-edgar → events)
3. **Create view system** (SQL-like queries)
4. **Add change detection** (the killer feature)
5. **Build notification system** (webhooks, WebSocket)
6. **Populate IR URLs for key companies** (one-time curation)
7. **Add press release URL capture** (during ingestion)
8. **Optional: News wire integration** (for real-time)

Want me to start implementing any of these?
