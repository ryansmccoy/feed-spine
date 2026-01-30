# Examples: Estimates vs Actuals

> **Practical recipes and usage patterns.**

---

## Quick Start

```python
from feedspine.storage import create_storage
from feedspine.analysis import EstimateActualComparison

# Connect to storage
storage = await create_storage("postgresql://localhost/feedspine")

# Create comparator
comparator = EstimateActualComparison(storage)
```

---

## Recipe 1: Did Apple Beat Earnings?

The most basic question.

```python
result = await comparator.compare(
    entity_id="aapl",
    metric_code="eps",
    period="2024:Q4",
)

if result.beat:
    print(f"✅ AAPL BEAT by {result.surprise_pct:+.1%}")
    print(f"   Estimate: ${result.estimate.value}")
    print(f"   Actual:   ${result.actual.value}")
else:
    print(f"❌ AAPL MISSED by {result.surprise_pct:+.1%}")
```

**Output:**
```
✅ AAPL BEAT by +3.8%
   Estimate: $2.10
   Actual:   $2.18
```

---

## Recipe 2: All Q4 2024 Earnings Surprises

Generate a full earnings season report.

```python
beats, misses, no_coverage = [], [], []

async for r in comparator.compare_all(
    period="2024:Q4",
    metric_code="eps",
):
    if r.estimate is None:
        no_coverage.append(r)
    elif r.beat:
        beats.append(r)
    else:
        misses.append(r)

total = len(beats) + len(misses)
print(f"📊 Q4 2024 Earnings Summary")
print(f"   Total reported: {total + len(no_coverage)}")
print(f"   With coverage:  {total}")
print(f"   Beat rate:      {len(beats)/total:.0%}")
print()

# Top 5 beats
print("🏆 Biggest Beats:")
for r in sorted(beats, key=lambda x: x.surprise_pct, reverse=True)[:5]:
    print(f"   {r.entity_id}: {r.surprise_pct:+.1%}")

# Top 5 misses
print("\n💔 Biggest Misses:")
for r in sorted(misses, key=lambda x: x.surprise_pct)[:5]:
    print(f"   {r.entity_id}: {r.surprise_pct:+.1%}")
```

**Output:**
```
📊 Q4 2024 Earnings Summary
   Total reported: 487
   With coverage:  423
   Beat rate:      68%

🏆 Biggest Beats:
   NVDA: +22.3%
   META: +15.1%
   AMZN: +12.7%
   GOOGL: +9.4%
   MSFT: +7.2%

💔 Biggest Misses:
   INTC: -18.5%
   BA: -14.2%
   DIS: -11.8%
   NKE: -8.3%
   TGT: -6.1%
```

---

## Recipe 3: What Just Reported? (Real-Time)

Monitor for new actuals as they arrive.

```python
from datetime import datetime, timedelta

# What came in the last 30 minutes?
recent = await comparator.recent_actuals(
    since=datetime.utcnow() - timedelta(minutes=30),
    include_surprise=True,
)

if not recent:
    print("📭 No new actuals in the last 30 minutes")
else:
    print(f"🆕 {len(recent)} companies just reported:")
    for r in recent:
        direction = "BEAT" if r.beat else "MISS" if r.beat is False else "N/A"
        surprise = f"{r.surprise_pct:+.1%}" if r.surprise_pct else "no estimate"
        print(f"   {r.entity_id}: {direction} ({surprise})")
```

**Output:**
```
🆕 3 companies just reported:
   MSFT: BEAT (+4.2%)
   GOOGL: BEAT (+2.1%)
   SMALLCAP: N/A (no estimate)
```

---

## Recipe 4: Compare Across Vendors

See how different data vendors estimated the same company.

```python
multi = await comparator.compare_sources(
    entity_id="aapl",
    metric_code="eps",
    period="2024:Q4",
    sources=["factset", "bloomberg", "ibes", "refinitiv"],
)

print(f"📊 AAPL Q4 2024 EPS - Multi-Source Comparison")
print(f"   Actual: ${multi.actual.value}")
print()
print("   Pre-Announcement Estimates:")
for source, est in multi.estimates.items():
    surprise = (multi.actual.value - est.value) / abs(est.value)
    print(f"   {source:12}: ${est.value} → {surprise:+.1%} surprise")

print()
print(f"   Most accurate: {multi.most_accurate_source}")
```

**Output:**
```
📊 AAPL Q4 2024 EPS - Multi-Source Comparison
   Actual: $2.18

   Pre-Announcement Estimates:
   factset     : $2.10 → +3.8% surprise
   bloomberg   : $2.12 → +2.8% surprise
   ibes        : $2.11 → +3.3% surprise
   refinitiv   : $2.09 → +4.3% surprise

   Most accurate: bloomberg
```

---

## Recipe 5: Sector Performance

Break down beat/miss rates by sector.

```python
from collections import defaultdict

sector_stats = defaultdict(lambda: {"beat": 0, "miss": 0, "total": 0})

async for r in comparator.compare_all(period="2024:Q4", metric_code="eps"):
    # Get sector from entity metadata
    sector = r.actual.metadata.get("sector", "Unknown")
    
    sector_stats[sector]["total"] += 1
    if r.beat is True:
        sector_stats[sector]["beat"] += 1
    elif r.beat is False:
        sector_stats[sector]["miss"] += 1

print("📊 Q4 2024 Beat Rates by Sector")
print("-" * 40)

for sector, stats in sorted(sector_stats.items(), key=lambda x: x[1]["beat"]/max(x[1]["total"],1), reverse=True):
    if stats["total"] < 5:
        continue  # Skip small sectors
    beat_rate = stats["beat"] / stats["total"]
    print(f"{sector:20} {beat_rate:5.0%} ({stats['beat']}/{stats['total']})")
```

**Output:**
```
📊 Q4 2024 Beat Rates by Sector
----------------------------------------
Technology           78% (45/58)
Healthcare           71% (32/45)
Financials           68% (28/41)
Consumer Discretion  62% (24/39)
Industrials          58% (21/36)
Energy               52% (14/27)
Utilities            48% (11/23)
```

---

## Recipe 6: Create Derived Surprise Observations

Store surprises so they're queryable later.

```python
from feedspine.domain import Observation, MetricSpec, SourceKey
from datetime import datetime

async def store_surprise_observation(result):
    """Convert comparison result to storable observation."""
    
    if result.surprise_pct is None:
        return None  # No estimate, can't compute surprise
    
    surprise_obs = Observation(
        entity_id=result.entity_id,
        metric=MetricSpec(
            code="earnings_surprise_pct",
            category="derived",
        ),
        period=result.actual.period,
        value=result.surprise_pct,
        unit="percent",
        as_of=datetime.utcnow(),
        source=SourceKey(
            vendor="feedspine",
            feed="derived:earnings_surprise",
            authority=50,
        ),
        metadata={
            "base_metric": result.metric_code,
            "estimate_source": result.estimate.source.vendor,
            "estimate_value": float(result.estimate.value),
            "actual_source": result.actual.source.vendor,
            "actual_value": float(result.actual.value),
            "beat": result.beat,
            "direction": result.direction,
        },
    )
    
    await storage.store(surprise_obs)
    return surprise_obs

# Process all Q4 results
count = 0
async for r in comparator.compare_all(period="2024:Q4", metric_code="eps"):
    obs = await store_surprise_observation(r)
    if obs:
        count += 1

print(f"✅ Created {count} surprise observations")
```

---

## Recipe 7: Query Historical Surprises

After creating derived observations, query them.

```python
# Find all big misses in 2024
big_misses = await storage.query_observations(
    metric_code="earnings_surprise_pct",
    period_year=2024,
    max_value=-0.10,  # -10% or worse
)

print("💔 Big Misses in 2024:")
async for obs in big_misses:
    print(f"   {obs.entity_id} {obs.period}: {obs.value:+.1%}")

# Average surprise by quarter
for quarter in [1, 2, 3, 4]:
    avg = await storage.aggregate(
        metric_code="earnings_surprise_pct",
        period=f"2024:Q{quarter}",
        aggregation="mean",
    )
    print(f"Q{quarter} 2024 average surprise: {avg:+.2%}")
```

---

## Recipe 8: Real-Time Alert Pipeline

Set up continuous monitoring with alerts.

```python
import asyncio

async def earnings_alert_pipeline():
    """Monitor for earnings surprises and send alerts."""
    
    print("👀 Starting earnings monitor...")
    
    async for event in comparator.watch_transitions(
        metric_codes=["eps", "revenue"],
        poll_interval_seconds=60,
    ):
        # Determine alert level
        if event.surprise_pct is None:
            level = "ℹ️"  # No estimate
        elif abs(event.surprise_pct) > 0.10:
            level = "🚨"  # Big surprise (>10%)
        elif abs(event.surprise_pct) > 0.05:
            level = "⚠️"  # Notable surprise (>5%)
        else:
            level = "📊"  # Normal
        
        # Format message
        direction = "BEAT" if event.beat else "MISS" if event.beat is False else "REPORTED"
        surprise = f"{event.surprise_pct:+.1%}" if event.surprise_pct else "no estimate"
        
        message = f"{level} {event.entity_id} {direction} on {event.metric_code}: {surprise}"
        print(message)
        
        # Store as derived observation
        await store_surprise_observation(event)
        
        # Send webhook/notification (your implementation)
        # await send_webhook(message)
        # await send_slack_alert(message)

# Run forever
asyncio.run(earnings_alert_pipeline())
```

**Output:**
```
👀 Starting earnings monitor...
📊 AAPL BEAT on eps: +3.8%
🚨 NVDA BEAT on eps: +22.3%
⚠️ MSFT BEAT on eps: +6.1%
ℹ️ SMALLCAP REPORTED on eps: no estimate
🚨 INTC MISS on eps: -18.5%
```

---

## Recipe 9: Integration with EntitySpine

Use EntitySpine for entity resolution and corporate actions.

```python
from entityspine import EntityStore
from entityspine.domain import CorporateAction

# EntitySpine for entity metadata
entity_store = EntityStore("postgresql://localhost/entityspine")

async def enriched_comparison(ticker: str, period: str):
    """Comparison with full entity context."""
    
    # Resolve entity
    entity = await entity_store.resolve(ticker=ticker)
    
    # Check for corporate actions that might affect comparison
    actions = await entity_store.get_corporate_actions(
        entity_id=entity.id,
        since=period_start(period),
        types=["STOCK_SPLIT", "REVERSE_SPLIT"],
    )
    
    if actions:
        print(f"⚠️ Corporate action(s) in period: {[a.action_type for a in actions]}")
    
    # Get comparison
    result = await comparator.compare(
        entity_id=entity.id,  # Use canonical ID
        metric_code="eps",
        period=period,
    )
    
    # Enrich with entity data
    result.entity_name = entity.name
    result.sector = entity.sector
    result.industry = entity.industry
    
    return result
```

---

## Recipe 10: Integration with py-sec-edgar

Extract actuals directly from SEC filings.

```python
from py_sec_edgar import FilingParser
from py_sec_edgar.xbrl import XBRLExtractor

async def extract_actual_from_filing(accession_number: str):
    """Extract EPS actual from SEC 10-Q/10-K filing."""
    
    # Parse the filing
    parser = FilingParser()
    filing = await parser.fetch(accession_number)
    
    # Extract XBRL data
    xbrl = XBRLExtractor(filing)
    eps_facts = xbrl.get_facts("EarningsPerShareDiluted")
    
    if not eps_facts:
        return None
    
    # Get the most recent period's value
    latest = max(eps_facts, key=lambda f: f.period_end)
    
    # Create observation
    actual = Observation(
        entity_id=filing.cik,
        metric=MetricSpec(
            code="eps",
            basis="GAAP",
            scope="REPORTED",
            per_share=True,
        ),
        period=FiscalPeriod.from_dates(latest.period_start, latest.period_end),
        value=latest.value,
        unit=latest.unit,
        as_of=filing.accepted_at,
        source=SourceKey(
            vendor="sec",
            feed=f"xbrl:{filing.form_type.lower()}",
            authority=100,  # SEC is most authoritative
        ),
        metadata={
            "accession_number": accession_number,
            "form_type": filing.form_type,
            "xbrl_concept": "EarningsPerShareDiluted",
        },
    )
    
    return actual

# Use in pipeline
async def process_new_filing(accession: str):
    actual = await extract_actual_from_filing(accession)
    if actual:
        await storage.store(actual)
        
        # Immediately compare to estimates
        result = await comparator.compare(
            entity_id=actual.entity_id,
            metric_code="eps",
            period=actual.period.key,
        )
        
        print(f"🆕 New filing: {actual.entity_id} {result.direction}")
```

---

## Recipe 11: Earnings Calendar Integration

Combine with events for full picture.

```python
from entityspine.domain import Event, EventType

async def upcoming_with_estimates():
    """Show upcoming earnings with pre-existing estimates."""
    
    # Get events from EntitySpine
    events = await entity_store.query_events(
        event_type=EventType.EARNINGS_RELEASE,
        scheduled_after=datetime.utcnow(),
        scheduled_before=datetime.utcnow() + timedelta(days=7),
    )
    
    print("📅 Upcoming Earnings (Next 7 Days)")
    print("-" * 60)
    
    for event in sorted(events, key=lambda e: e.scheduled_on):
        # Get current estimate
        estimate = await storage.get_observation(
            entity_id=event.entity_id,
            metric_code="eps",
            period=event.fiscal_period_str,
            scope="CONSENSUS",
        )
        
        est_str = f"${estimate.value}" if estimate else "no estimate"
        
        print(f"{event.scheduled_on:%m/%d %H:%M} | {event.entity_id:6} | Est: {est_str}")
```

**Output:**
```
📅 Upcoming Earnings (Next 7 Days)
------------------------------------------------------------
01/30 16:30 | AAPL   | Est: $2.10
01/30 16:30 | META   | Est: $5.25
01/31 06:00 | AMZN   | Est: $1.85
01/31 16:00 | GOOGL  | Est: $1.95
02/01 08:00 | XOM    | Est: $2.45
02/02 14:00 | SMALL  | no estimate
```

---

## Recipe 12: Export to DataFrame

For analysis in pandas/notebooks.

```python
import pandas as pd

async def comparison_to_dataframe(period: str, metric: str = "eps") -> pd.DataFrame:
    """Export comparison results to pandas DataFrame."""
    
    rows = []
    async for r in comparator.compare_all(period=period, metric_code=metric):
        rows.append({
            "entity_id": r.entity_id,
            "period": r.period_key,
            "metric": r.metric_code,
            "estimate": float(r.estimate.value) if r.estimate else None,
            "estimate_source": r.estimate.source.vendor if r.estimate else None,
            "actual": float(r.actual.value),
            "actual_source": r.actual.source.vendor,
            "surprise_pct": r.surprise_pct,
            "beat": r.beat,
            "direction": r.direction,
        })
    
    df = pd.DataFrame(rows)
    return df

# Use in Jupyter
df = await comparison_to_dataframe("2024:Q4")
df.describe()

# Filter to tech sector
tech = df[df["entity_id"].isin(tech_tickers)]
tech["surprise_pct"].hist(bins=50)
```

---

*Copy, paste, customize. These recipes are your starting point.* 🍳

---

## Recipe 13: REST API Client Usage

Consuming the comparison engine via API.

```python
# Using the Python SDK
from feedspine_client import FeedSpineClient

client = FeedSpineClient(
    base_url="https://api.example.com",
    api_key="your_api_key",
)

# Single comparison
result = await client.compare("AAPL", "2024:Q4")
print(f"AAPL {result.surprise_direction} by {result.surprise_pct:.1%}")

# Batch comparison
batch = await client.compare_batch(period="2024:Q4", sector="Technology")
print(f"Tech beat rate: {batch.beat_rate:.0%}")

# Recent actuals
recent = await client.recent_actuals(since_minutes=30)
for r in recent.results:
    print(f"🆕 {r.entity_id}: {r.surprise_direction}")
```

### Using Raw HTTP

```python
import httpx

async with httpx.AsyncClient(base_url="https://api.example.com") as client:
    response = await client.post(
        "/v1/compare",
        json={"entity_id": "AAPL", "period": "2024:Q4"},
        headers={"Authorization": "Bearer your_api_key"},
    )
    data = response.json()
    print(f"Surprise: {data['surprise_pct']}")
```

### TypeScript/JavaScript

```typescript
// Generated types from OpenAPI
import { CompareRequest, CompareResponse } from './feedspine-types';

const response = await fetch('https://api.example.com/v1/compare', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Authorization': 'Bearer your_api_key',
  },
  body: JSON.stringify({ entity_id: 'AAPL', period: '2024:Q4' } as CompareRequest),
});

const data: CompareResponse = await response.json();
console.log(`${data.entity_id} ${data.surprise_direction}`);
```

---

## Recipe 14: WebSocket Real-Time Stream

Subscribe to earnings alerts.

```python
import asyncio
import websockets

async def earnings_stream():
    """Listen for real-time earnings surprises."""
    
    uri = "wss://api.example.com/v1/stream/earnings"
    
    async with websockets.connect(uri) as ws:
        print("📡 Connected to earnings stream...")
        
        async for message in ws:
            event = json.loads(message)
            
            if event["type"] == "NEW_ACTUAL":
                emoji = "✅" if event["direction"] == "BEAT" else "❌"
                print(
                    f"{emoji} {event['entity_id']} "
                    f"{event['direction']} by {event['surprise_pct']:+.1%}"
                )

# Run the stream
asyncio.run(earnings_stream())
```

**Output:**
```
📡 Connected to earnings stream...
✅ AAPL BEAT by +3.8%
✅ MSFT BEAT by +5.2%
❌ INTC MISS by -12.3%
✅ GOOGL BEAT by +1.5%
```

---

## Recipe 15: Price Reaction Analysis

Analyze stock performance around earnings.

```python
from feedspine.analysis import EarningsPriceAnalysis

analyzer = EarningsPriceAnalysis(obs_storage, price_storage)

# Single stock analysis
result = await analyzer.earnings_price_reaction(
    entity_id="aapl",
    period="2024:Q4",
    pre_days=5,
    post_days=5,
)

print(f"📊 AAPL Q4 2024 Earnings Price Reaction")
print(f"   Surprise: {result.surprise_pct:+.1%}")
print(f"   Price T-5: ${result.price_pre:.2f}")
print(f"   Price T+0: ${result.price_close:.2f}")
print(f"   Price T+5: ${result.price_post:.2f}")
print(f"   Price change (announcement): {result.price_change_day:+.1%}")
print(f"   Price change (5 days): {result.price_change_5d:+.1%}")
```

**Output:**
```
📊 AAPL Q4 2024 Earnings Price Reaction
   Surprise: +3.8%
   Price T-5: $185.50
   Price T+0: $192.30 (gap up on beat)
   Price T+5: $195.20
   Price change (announcement): +3.7%
   Price change (5 days): +5.2%
```

### Post-Earnings Drift Study

```python
# Analyze drift across all Q4 earnings
pead = await analyzer.pead_analysis(
    period="2024:Q4",
    drift_days=[1, 5, 10, 20, 60],
)

print("📈 Post-Earnings Announcement Drift (Q4 2024)")
print("-" * 50)
print(f"{'Drift Window':<15} {'Beats':<12} {'Misses':<12}")
print("-" * 50)
print(f"{'Day +1':<15} {pead.beats_1d:+.2%:<12} {pead.misses_1d:+.2%:<12}")
print(f"{'Day +5':<15} {pead.beats_5d:+.2%:<12} {pead.misses_5d:+.2%:<12}")
print(f"{'Day +20':<15} {pead.beats_20d:+.2%:<12} {pead.misses_20d:+.2%:<12}")
print(f"{'Day +60':<15} {pead.beats_60d:+.2%:<12} {pead.misses_60d:+.2%:<12}")
```

**Output:**
```
📈 Post-Earnings Announcement Drift (Q4 2024)
--------------------------------------------------
Drift Window    Beats        Misses      
--------------------------------------------------
Day +1          +0.85%       -0.92%      
Day +5          +1.42%       -1.65%      
Day +20         +2.31%       -2.88%      
Day +60         +4.12%       -4.85%      
```

---

## Recipe 16: Adjustment Chain Tracking

Track GAAP → Adjusted → Operating EPS.

```python
# Store observation with adjustment chain
gaap_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(code="eps", basis=MetricBasis.GAAP),
    value=Decimal("2.10"),
    period=period,
    source=sec_source,
)
await storage.store(gaap_eps)

adjusted_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(code="eps", basis=MetricBasis.ADJUSTED),
    value=Decimal("2.18"),
    period=period,
    source=company_source,
    adjustments=AdjustmentChain([
        Adjustment("RESTRUCTURING", Decimal("0.05"), "Severance costs"),
        Adjustment("ACQUISITION", Decimal("0.02"), "M&A transaction fees"),
        Adjustment("LITIGATION", Decimal("0.01"), "Patent settlement"),
    ]),
    derived_from=gaap_eps.id,
)
await storage.store(adjusted_eps)

# Query the lineage
lineage = await storage.get_adjustment_lineage(adjusted_eps.id)

print(f"📋 EPS Adjustment Lineage")
print(f"   GAAP EPS:     ${lineage.origin.value}")
for adj in lineage.adjustments:
    print(f"   + {adj.type}: ${adj.amount} ({adj.description})")
print(f"   Adjusted EPS: ${lineage.final.value}")
```

**Output:**
```
📋 EPS Adjustment Lineage
   GAAP EPS:     $2.10
   + RESTRUCTURING: $0.05 (Severance costs)
   + ACQUISITION: $0.02 (M&A transaction fees)
   + LITIGATION: $0.01 (Patent settlement)
   Adjusted EPS: $2.18
```

### Custom Operating EPS

```python
# You decide stock comp should be added back too
operating_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(code="eps", basis=MetricBasis.OPERATING),
    value=Decimal("2.25"),  # Your calculation
    period=period,
    source=SourceKey(vendor="internal", feed="custom_adjustments"),
    adjustments=AdjustmentChain([
        Adjustment("START_FROM_ADJUSTED", Decimal("2.18")),
        Adjustment("STOCK_COMP", Decimal("0.07"), "SBC is non-cash"),
    ]),
    derived_from=adjusted_eps.id,
)

# Now compare to estimate using YOUR operating EPS
result = await comparator.compare(
    entity_id="aapl",
    period="2024:Q4",
    actual_basis=MetricBasis.OPERATING,  # Use your adjusted number
)
print(f"vs Street estimate: {result.surprise_pct:+.1%}")
```

---

## Recipe 17: Full Dashboard Export (Excel-like)

Match the original Excel workflow with all columns.

```python
async def full_earnings_dashboard(
    period: str,
    output_path: str = "earnings_dashboard.xlsx",
):
    """Export full earnings dashboard matching Excel format."""
    
    rows = []
    async for r in comparator.compare_all(
        period=period,
        metric_codes=["eps", "revenue"],
        include_yoy=True,
        include_identifiers=True,
    ):
        # Get entity metadata
        entity = await entity_store.get(r.entity_id)
        
        rows.append({
            # Timing
            "TIME": r.released_at.strftime("%m/%d %H:%M"),
            
            # Identifiers (for joins)
            "TICKER": entity.identifiers.get("ticker", r.entity_id.upper()),
            "BBG": entity.identifiers.get("bbg", ""),
            "ISIN": entity.identifiers.get("isin", ""),
            
            # Source
            "SOURCE": r.source[0].upper(),  # "Z", "B", "F"
            
            # Metadata
            "MKTCAP": entity.market_cap,
            "SECTOR": entity.sector,
            "INDUSTRY": entity.industry,
            
            # EPS
            "EPS_ACT": r.eps.actual.value if r.eps else None,
            "EPS_EST": r.eps.estimate.value if r.eps and r.eps.estimate else None,
            "EPS_YOY": r.eps.comparable.value if r.eps and r.eps.comparable else None,
            "EPS_SURP%": r.eps.surprise_pct if r.eps else None,
            "EPS_YOY%": r.eps.yoy_growth_pct if r.eps else None,
            
            # Revenue
            "REV_ACT": r.revenue.actual.value if r.revenue else None,
            "REV_EST": r.revenue.estimate.value if r.revenue and r.revenue.estimate else None,
            "REV_YOY": r.revenue.comparable.value if r.revenue and r.revenue.comparable else None,
            "REV_SURP%": r.revenue.surprise_pct if r.revenue else None,
            "REV_YOY%": r.revenue.yoy_growth_pct if r.revenue else None,
        })
    
    # Create DataFrame and export
    df = pd.DataFrame(rows)
    df.to_excel(output_path, index=False)
    
    print(f"📊 Exported {len(df)} companies to {output_path}")
    return df

# Generate the dashboard
df = await full_earnings_dashboard("2024:Q4")
```

---

*Copy, paste, customize. These recipes are your starting point.* 🍳
