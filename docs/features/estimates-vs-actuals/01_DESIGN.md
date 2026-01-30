# Estimates vs Actuals: A First-Class Feature

> **Design document for comparing consensus estimates to reported actuals, detecting earnings surprises, and generating derived observations.**

---

## Real-World Context: The Excel Workflow

This design is informed by a production Excel-based earnings tracking system. Understanding that workflow is critical:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              ORIGINAL EXCEL EARNINGS TRACKER                                            │
├──────────┬────────┬────────┬────────┬────────┬─────────────────────────────────────────────────────────┤
│   TIME   │ TICKER │ SOURCE │ MKTCAP │INDUSTRY│   EPS                    │   REVENUE                    │
│          │        │        │        │        │ ACT │ EST │ YoY │SURP%│YoY%│ ACT │ EST │ YoY │SURP%│YoY%│
├──────────┼────────┼────────┼────────┼────────┼─────┼─────┼─────┼─────┼────┼─────┼─────┼─────┼─────┼────┤
│4/23 20:15│ AAPL   │   Z    │ 49,924 │ TECH   │2.18 │2.10 │1.85 │+3.8%│+18%│119.2│117.5│98.4 │+1.4%│+21%│
│4/23 20:15│ MSFT   │   B    │ 44,516 │ TECH   │2.95 │2.80 │2.50 │+5.4%│+18%│ 65.1│ 64.0│54.2 │+1.7%│+20%│
│4/23 20:13│ INTC   │   F    │ 13,686 │ SEMI   │0.42 │0.55 │0.78 │-24% │-46%│ 12.7│ 14.1│19.2 │-10% │-34%│
└──────────┴────────┴────────┴────────┴────────┴─────┴─────┴─────┴─────┴────┴─────┴─────┴─────┴─────┴────┘

 KEY INSIGHTS:
 ─────────────
 1. TIME = when company released (not when we captured)
 2. SOURCE = Z(acks), B(loomberg), F(actSet) - each has DIFFERENT actuals!
 3. YoY = Same quarter last year (third comparison dimension)
 4. Multiple ticker formats for joining across systems
 5. Quarterly is primary focus (annual exists but less important)
```

### Critical Design Requirements (From Production Usage)

| Requirement | Why It Matters |
|-------------|----------------|
| **Two timestamps** | `released_at` (when company announced) vs `processed_at` (when we captured) |
| **Source-specific actuals** | Bloomberg, FactSet, Zacks report DIFFERENT "actual" numbers! |
| **YoY comparable** | Not just ACT vs EST, also ACT vs SAME_QUARTER_LAST_YEAR |
| **Multiple ticker formats** | `AAPL`, `AAPL US`, `AAPL-US`, `US0378331005` for cross-system joins |
| **Source indicator** | "Z", "B", "F" to know which vendor's methodology |
| **Quarterly focus** | Quarterly estimates matter most for trading |

---

## The Problem Space

The simple example in the archetypes guide hides a LOT of complexity:

```python
# Too simple - what does this actually mean?
comparison = await storage.compare_estimates_actuals(
    period="2024:Q4",
    metric="eps",
)
```

### Questions This Raises

1. **What are we comparing?**
   - Which estimate? (consensus mean? median? high? low?)
   - Which actual? (GAAP? adjusted? preliminary? audited?)
   - From which source? (FactSet consensus? Bloomberg? I/B/E/S?)

2. **Scope of comparison?**
   - All companies? One sector? One company?
   - All periods? Just Q4? Just most recent?

3. **Timing concerns?**
   - What if estimate was updated AFTER the actual came out?
   - What's the "final" pre-announcement estimate?
   - How do we handle estimate revisions?

4. **Real-time use cases?**
   - "Alert me when a company beats/misses"
   - "Show me all surprises in the last hour"
   - "What companies report after close today?"

5. **Derived data?**
   - Can we CREATE new observations from comparisons?
   - Surprise percentage, beat/miss flag, revision history?

---

## Proposed API Design

### Core Concepts

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ESTIMATES vs ACTUALS MODEL                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ESTIMATE                           ACTUAL                 COMPARABLE       │
│  ────────                           ──────                 ──────────       │
│  metric: eps                        metric: eps            metric: eps      │
│  scope: CONSENSUS                   scope: REPORTED        scope: REPORTED  │
│  basis: ADJUSTED                    basis: GAAP            basis: GAAP      │
│  source: factset                    source: zacks          source: sec      │
│  as_of: 2024-10-28 (pre-report)    released_at: Oct 31    period: 2023:Q4  │
│                                     processed_at: Oct 31   (same qtr, -1yr)│
│                                                                              │
│         ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │
│         │   SURPRISE   │      │   YoY GROWTH │      │   TIMING     │       │
│         │              │      │              │      │              │       │
│         │  actual: 2.18│      │  actual: 2.18│      │ released_at  │       │
│         │  estimate:2.10│     │  prior:  1.85│      │ = company    │       │
│         │  diff: +0.08 │      │  growth: +18%│      │   announced  │       │
│         │  pct: +3.8%  │      │              │      │              │       │
│         │  beat: true  │      │              │      │ processed_at │       │
│         └──────────────┘      └──────────────┘      │ = we captured│       │
│                                                      └──────────────┘       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1. Flexible Query API

```python
from feedspine.analysis import EstimateActualComparison
from feedspine.domain import EstimateScope, MetricBasis

# Create comparison engine
comparator = EstimateActualComparison(storage)

# ═══════════════════════════════════════════════════════════════════
# USE CASE 1: Single company, specific metric
# "Did Apple beat EPS estimates for Q4 2024?"
# ═══════════════════════════════════════════════════════════════════

result = await comparator.compare(
    entity_id="aapl",
    metric_code="eps",
    period="2024:Q4",
    
    # Estimate specification
    estimate_scope=EstimateScope.CONSENSUS,      # Mean of analyst estimates
    estimate_basis=MetricBasis.ADJUSTED,         # Street (non-GAAP)
    estimate_source="factset",                   # Or "bloomberg", "ibes", "any"
    estimate_as_of="pre_announcement",           # Magic: last estimate BEFORE actual
    
    # Actual specification  
    actual_basis=MetricBasis.ADJUSTED,           # Compare apples to apples
    actual_source="company_reported",            # Prefer company's own number
)

print(f"Estimate: ${result.estimate.value}")     # $2.10
print(f"Actual: ${result.actual.value}")         # $2.18
print(f"Surprise: {result.surprise_pct:+.1%}")   # +3.8%
print(f"Beat: {result.beat}")                    # True

# ═══════════════════════════════════════════════════════════════════
# USE CASE 2: All companies in a period
# "Show me all Q4 2024 earnings surprises"
# ═══════════════════════════════════════════════════════════════════

async for result in comparator.compare_all(
    period="2024:Q4",
    metric_code="eps",
    
    # Filter options
    entity_ids=None,                 # All companies (or pass a list)
    sector="technology",             # Optional sector filter
    index_membership="sp500",        # Optional index filter
    
    # Estimate/actual specs (same as above)
    estimate_scope=EstimateScope.CONSENSUS,
    estimate_basis=MetricBasis.ADJUSTED,
    actual_basis=MetricBasis.ADJUSTED,
):
    print(f"{result.entity_id}: {result.surprise_pct:+.1%} ({'BEAT' if result.beat else 'MISS'})")

# ═══════════════════════════════════════════════════════════════════
# USE CASE 3: Real-time - new actuals in time window
# "What companies reported in the last 30 minutes?"
# ═══════════════════════════════════════════════════════════════════

from datetime import datetime, timedelta

recent = await comparator.recent_actuals(
    since=datetime.utcnow() - timedelta(minutes=30),
    metric_code="eps",
    
    # Automatically compare to pre-announcement estimate
    include_surprise=True,
)

for result in recent:
    print(f"🆕 {result.entity_id} just reported!")
    print(f"   Actual: ${result.actual.value} vs Est: ${result.estimate.value}")
    print(f"   Surprise: {result.surprise_pct:+.1%}")
    print(f"   Reported at: {result.actual.as_of}")

# ═══════════════════════════════════════════════════════════════════
# USE CASE 4: Detect NEW estimate-to-actual transitions
# "Alert me when ANY estimate becomes an actual"
# ═══════════════════════════════════════════════════════════════════

async for event in comparator.watch_transitions(
    metric_codes=["eps", "revenue"],
    
    # Only alert on significant surprises
    min_surprise_pct=0.05,  # 5%+ surprise
    
    # Real-time polling interval
    poll_interval_seconds=60,
):
    print(f"🚨 {event.entity_id} {event.metric_code} surprise!")
    print(f"   Direction: {'BEAT' if event.beat else 'MISS'}")
    print(f"   Magnitude: {event.surprise_pct:+.1%}")
    
    # Feed back into FeedSpine as derived observation!
    await create_surprise_observation(event)
```

### 2. The "Pre-Announcement Estimate" Problem

This is subtle but critical. Which estimate do we compare against?

```
Timeline:
───────────────────────────────────────────────────────────────────►

Oct 1         Oct 15        Oct 28        Oct 31        Nov 5
  │             │             │             │             │
  ▼             ▼             ▼             ▼             ▼
Est: $2.05   Est: $2.08   Est: $2.10   ACTUAL: $2.18  Est: $2.20
                                        (reported)     (post-hoc!)

Which estimate matters for surprise calculation?
─────────────────────────────────────────────────
✓ Oct 28 ($2.10) - Last estimate BEFORE announcement
✗ Nov 5 ($2.20)  - This is AFTER the fact, useless for surprise
```

**Solution: `estimate_as_of` parameter**

```python
# Explicit timestamp
result = await comparator.compare(
    ...,
    estimate_as_of=datetime(2024, 10, 28),  # Specific date
)

# Magic values
result = await comparator.compare(
    ...,
    estimate_as_of="pre_announcement",  # Auto: last estimate before actual.as_of
)

result = await comparator.compare(
    ...,
    estimate_as_of="30d_prior",  # 30 days before actual
)
```

### 3. Multi-Source Comparison

What if you want to compare estimates from different vendors?

```python
# Compare FactSet vs Bloomberg consensus for the same company
comparison = await comparator.compare_sources(
    entity_id="aapl",
    metric_code="eps",
    period="2024:Q4",
    
    sources=["factset", "bloomberg", "ibes"],
    
    # Returns estimates from each source + the actual
)

print("Pre-announcement estimates by source:")
for source, estimate in comparison.estimates.items():
    print(f"  {source}: ${estimate.value}")
    
print(f"\nActual: ${comparison.actual.value}")
print(f"\nSurprises:")
for source, surprise in comparison.surprises.items():
    print(f"  vs {source}: {surprise.pct:+.1%}")
```

### 4. Creating Derived Observations (Feeding Back)

**This is the key insight** - surprises are themselves observations that can be stored and queried!

```python
from feedspine.domain import Observation, MetricSpec, SourceKey
from entityspine.domain.enums import MetricCategory

# When an actual comes in, create a SURPRISE observation
async def create_surprise_observation(comparison_result):
    """Convert a comparison result into a storable observation."""
    
    surprise_obs = Observation(
        entity_id=comparison_result.entity_id,
        
        # New metric: earnings surprise percentage
        metric=MetricSpec(
            code="earnings_surprise",
            category=MetricCategory.DERIVED,
            basis=comparison_result.actual.metric.basis,
            per_share=True,
        ),
        
        period=comparison_result.period,
        
        # The surprise value
        value=comparison_result.surprise_pct,
        unit="percent",
        
        # Timestamp: when we computed this
        as_of=datetime.utcnow(),
        
        # Source: our own calculation
        source=SourceKey(
            vendor="feedspine",
            feed="derived:earnings_surprise",
            authority=50,  # Lower than primary sources
        ),
        
        # Rich metadata for audit trail
        metadata={
            "estimate_source": comparison_result.estimate.source.vendor,
            "estimate_value": float(comparison_result.estimate.value),
            "estimate_as_of": comparison_result.estimate.as_of.isoformat(),
            "actual_source": comparison_result.actual.source.vendor,
            "actual_value": float(comparison_result.actual.value),
            "actual_as_of": comparison_result.actual.as_of.isoformat(),
            "beat": comparison_result.beat,
            "calculation_method": "simple_pct",
        },
    )
    
    await storage.store(surprise_obs)
    return surprise_obs

# Now surprises are queryable just like any other observation!
surprises = await storage.query_observations(
    metric_code="earnings_surprise",
    period="2024:Q4",
    min_value=-0.10,  # Misses of 10%+ (negative surprise)
)
```

### 5. Streaming / Real-Time Integration

```python
from feedspine.streams import ObservationStream

# Set up a stream that watches for new actuals
async def earnings_alert_pipeline():
    stream = ObservationStream(storage)
    
    # Subscribe to "actual" observations as they arrive
    async for obs in stream.subscribe(
        metric_codes=["eps", "revenue"],
        scope=EstimateScope.REPORTED,  # Only actuals, not estimates
    ):
        # Find the corresponding pre-announcement estimate
        estimate = await storage.get_observation(
            entity_id=obs.entity_id,
            metric_code=obs.metric.code,
            period=obs.period.key,
            scope=EstimateScope.CONSENSUS,
            as_of_before=obs.as_of,  # Must be BEFORE the actual
        )
        
        if estimate:
            # Calculate surprise
            surprise_pct = (obs.value - estimate.value) / abs(estimate.value)
            beat = obs.value > estimate.value
            
            # Create derived observation
            await create_surprise_observation(...)
            
            # Trigger alerts
            if abs(surprise_pct) > 0.05:
                await send_alert(
                    f"🚨 {obs.entity_id} {'BEAT' if beat else 'MISSED'} by {surprise_pct:+.1%}"
                )
```

---

## Data Model: ComparisonResult

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal

@dataclass
class ComparisonResult:
    """Result of comparing an estimate to an actual (and optionally YoY comparable)."""
    
    # ═══════════════════════════════════════════════════════════════════
    # IDENTITY
    # ═══════════════════════════════════════════════════════════════════
    entity_id: str
    metric_code: str
    period_key: str                # "2024:Q4"
    
    # Multiple ticker formats for joining across systems
    identifiers: dict[str, str]    # {"bbg": "AAPL US", "cusip": "037833100", ...}
    
    # ═══════════════════════════════════════════════════════════════════
    # THE THREE OBSERVATIONS
    # ═══════════════════════════════════════════════════════════════════
    estimate: Optional[Observation]     # Pre-announcement estimate (may be None)
    actual: Observation                 # The reported actual (required)
    comparable: Optional[Observation]   # Same quarter prior year (YoY)
    
    # ═══════════════════════════════════════════════════════════════════
    # TIMESTAMPS (Critical for audit)
    # ═══════════════════════════════════════════════════════════════════
    released_at: datetime          # When company ANNOUNCED (from actual)
    processed_at: datetime         # When OUR SYSTEM captured it
    estimate_as_of: Optional[datetime]  # When estimate was known
    
    # ═══════════════════════════════════════════════════════════════════
    # SOURCE TRACKING
    # ═══════════════════════════════════════════════════════════════════
    source: str                    # "Z" (Zacks), "B" (Bloomberg), "F" (FactSet)
    source_full: str               # "zacks", "bloomberg", "factset"
    
    # ═══════════════════════════════════════════════════════════════════
    # COMPUTED: SURPRISE (vs Estimate)
    # ═══════════════════════════════════════════════════════════════════
    difference: Optional[Decimal]       # actual - estimate (raw)
    surprise_pct: Optional[float]       # (actual - estimate) / |estimate|
    beat: Optional[bool]                # actual > estimate (None if no estimate)
    
    # ═══════════════════════════════════════════════════════════════════
    # COMPUTED: YoY GROWTH (vs Comparable)
    # ═══════════════════════════════════════════════════════════════════
    yoy_difference: Optional[Decimal]   # actual - comparable
    yoy_growth_pct: Optional[float]     # (actual - comparable) / |comparable|
    
    # ═══════════════════════════════════════════════════════════════════
    # OPTIONAL: Multi-source estimates
    # ═══════════════════════════════════════════════════════════════════
    estimates_by_source: Optional[dict[str, Observation]] = None
    
    @property
    def direction(self) -> Literal["BEAT", "MISS", "INLINE", "NO_ESTIMATE"]:
        """BEAT, MISS, INLINE, or NO_ESTIMATE."""
        if self.estimate is None:
            return "NO_ESTIMATE"
        if self.beat is True:
            return "BEAT"
        elif self.beat is False:
            return "MISS"
        else:
            return "INLINE"  # Exact match (tolerance = 0)
    
    @property
    def magnitude(self) -> Optional[str]:
        """Small, moderate, or large surprise."""
        if self.surprise_pct is None:
            return None
        pct = abs(self.surprise_pct)
        if pct < 0.03:
            return "SMALL"
        elif pct < 0.10:
            return "MODERATE"
        else:
            return "LARGE"


@dataclass
class ComparisonRow:
    """
    Flattened row format matching the Excel workflow.
    Designed for easy DataFrame/CSV export.
    """
    
    # Timing
    time: datetime                 # released_at
    processed: datetime            # processed_at
    
    # Identifiers (multiple formats for joining)
    ticker: str
    ticker_bbg: Optional[str]      # "AAPL US"
    cusip: Optional[str]
    isin: Optional[str]
    cik: Optional[str]
    
    # Source
    source: str                    # "Z", "B", "F"
    
    # Entity context
    mktcap: Optional[float]
    industry: Optional[str]
    sector: Optional[str]
    
    # EPS columns (matching Excel)
    eps_act: Optional[float]
    eps_est: Optional[float]
    eps_yoy: Optional[float]       # Same quarter last year
    eps_surp_pct: Optional[float]  # vs estimate
    eps_yoy_pct: Optional[float]   # vs last year
    
    # Revenue columns (matching Excel)
    rev_act: Optional[float]
    rev_est: Optional[float]
    rev_yoy: Optional[float]
    rev_surp_pct: Optional[float]
    rev_yoy_pct: Optional[float]
    
    # Period info
    period: str                    # "2024:Q4"
    fiscal_year: int
    fiscal_quarter: int
```

---

## Query Patterns Summary

| Use Case | Method | Key Parameters |
|----------|--------|----------------|
| Single company surprise | `compare()` | `entity_id`, `metric_code`, `period` |
| All companies in period | `compare_all()` | `period`, optional filters |
| Recent actuals | `recent_actuals()` | `since` (datetime) |
| Compare across sources | `compare_sources()` | `sources` (list) |
| Real-time stream | `watch_transitions()` | `poll_interval`, `min_surprise_pct` |
| Historical surprises | `query_observations(metric="earnings_surprise")` | After creating derived obs |

---

## Implementation Phases

### Phase 1: Core Comparison (MVP)
- [ ] `compare()` - single entity comparison
- [ ] `compare_all()` - batch comparison
- [ ] "Pre-announcement" estimate resolution
- [ ] `ComparisonResult` dataclass

### Phase 2: Real-Time Features
- [ ] `recent_actuals()` - time-windowed queries
- [ ] `watch_transitions()` - streaming detection
- [ ] Webhook/callback support

### Phase 3: Derived Observations
- [ ] `create_surprise_observation()` helper
- [ ] Auto-derivation pipeline
- [ ] Surprise as queryable metric

### Phase 4: Multi-Source
- [ ] `compare_sources()` - cross-vendor comparison
- [ ] Source agreement/disagreement metrics
- [ ] "Best estimate" heuristics

### Phase 5: Integrations
- [ ] EntitySpine entity resolution
- [ ] py-sec-edgar XBRL extraction
- [ ] CaptureSpine real-time feeds
- [ ] Excel export matching original format

---

## Design Decisions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Beat tolerance?** | **Zero** - strictly `actual > estimate` | Tolerance is subjective; users can add their own |
| **Missing estimates?** | **Show data anyway** - `estimate=None`, `surprise_pct=None` | Small caps have no coverage but still report; allow filtering |
| **Currency normalization?** | **Auto-convert** using FX rate at estimate's `as_of` date | Must compare like-to-like; store original in metadata |
| **Split adjustment?** | **Auto-adjust** historical values to current basis | Use EntitySpine's corporate action history |
| **Default estimate basis?** | **Adjusted** (street consensus) for estimates, flexible for actual | Street estimates are adjusted; actual can be GAAP or adjusted |

---

## Additional Considerations

### Source-Specific Actuals (Critical Insight)

**Different vendors report different "actual" numbers!** This is not just about estimates:

```
Apple Q4 2024 EPS "Actual" by source:
────────────────────────────────────
Zacks:      $2.18
Bloomberg:  $2.19  
FactSet:    $2.18
SEC (GAAP): $2.17

Why the difference?
- Rounding rules
- Adjustment methodologies  
- Timing of capture
- Definition of "diluted"
```

**Solution:** Track source for BOTH estimate AND actual. Allow querying by source.

```python
result = await comparator.compare(
    entity_id="aapl",
    period="2024:Q4",
    estimate_source="factset",   # FactSet consensus
    actual_source="zacks",       # Zacks reported actual
)
# Returns Zacks's actual vs FactSet's estimate
```

### Annual vs Quarterly

**Quarterly is primary focus** for trading decisions, but annual exists:

```python
# Quarterly (default, most common)
result = await comparator.compare(
    entity_id="aapl",
    period="2024:Q4",
    periodicity="quarterly",  # Default
)

# Annual (less common but supported)
result = await comparator.compare(
    entity_id="aapl", 
    period="2024:FY",
    periodicity="annual",
)
```

### The YoY Comparable (Third Dimension)

Not just Actual vs Estimate, but also **Actual vs Same Quarter Last Year**:

```
┌────────────────────────────────────────────────────────────┐
│              THREE-WAY COMPARISON                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   ACTUAL (Q4 2024)     ESTIMATE (Q4 2024)     YoY (Q4 2023)│
│   ────────────────     ─────────────────     ─────────────│
│   $2.18                $2.10                 $1.85         │
│                                                            │
│   Surprise: +3.8%      Growth: +17.8%                     │
│   (vs estimate)        (vs prior year)                    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

```python
result = await comparator.compare(
    entity_id="aapl",
    period="2024:Q4",
    include_yoy=True,  # Also fetch Q4 2023 actual
)

print(f"Actual: ${result.actual.value}")
print(f"vs Estimate: {result.surprise_pct:+.1%}")
print(f"vs Last Year: {result.yoy_growth_pct:+.1%}")
```

---

## Example: Full Earnings Season Dashboard

```python
async def earnings_season_dashboard(quarter: str = "2024:Q4"):
    """Generate a complete earnings season summary."""
    
    comparator = EstimateActualComparison(storage)
    
    # Get all comparisons for the quarter
    results = []
    async for r in comparator.compare_all(
        period=quarter,
        metric_code="eps",
        estimate_scope=EstimateScope.CONSENSUS,
        estimate_basis=MetricBasis.ADJUSTED,
        actual_basis=MetricBasis.ADJUSTED,
    ):
        results.append(r)
    
    # Aggregate stats
    beats = [r for r in results if r.beat]
    misses = [r for r in results if not r.beat]
    
    print(f"📊 {quarter} Earnings Season Summary")
    print(f"=" * 40)
    print(f"Companies reported: {len(results)}")
    print(f"Beats: {len(beats)} ({len(beats)/len(results):.0%})")
    print(f"Misses: {len(misses)} ({len(misses)/len(results):.0%})")
    print()
    
    # Biggest surprises
    by_surprise = sorted(results, key=lambda r: r.surprise_pct, reverse=True)
    
    print("🏆 Top 5 Beats:")
    for r in by_surprise[:5]:
        print(f"  {r.entity_id}: {r.surprise_pct:+.1%}")
    
    print("\n💔 Top 5 Misses:")
    for r in by_surprise[-5:]:
        print(f"  {r.entity_id}: {r.surprise_pct:+.1%}")
    
    # Store derived observations for all surprises
    for r in results:
        await create_surprise_observation(r)
    
    print(f"\n✅ Created {len(results)} surprise observations in FeedSpine")
```

---

---

## API Contracts & External Interface

For external consumption (frontends, other systems), see the full API design:

📄 **[API_DESIGN_AND_CONTRACTS.md](../../API_DESIGN_AND_CONTRACTS.md)**

### Key Contract Types

| Contract | Purpose |
|----------|---------|
| `CompareRequest` | Request to compare estimate vs actual |
| `CompareResponse` | Full comparison result with identifiers |
| `BatchCompareResponse` | Multiple comparisons with summary stats |
| `ObservationResponse` | Single observation in API format |
| `ErrorResponse` | Standard error format |

### Endpoints

```
POST /v1/compare           # Single comparison
POST /v1/compare/batch     # Batch comparison
GET  /v1/recent            # Recently reported actuals
GET  /v1/observations/{entity}     # Query observations
GET  /v1/observations/{entity}/pit # Point-in-time
WS   /v1/stream/earnings   # Real-time WebSocket
```

---

## Adjustment Tracking (GAAP → Operating)

The "real operating EPS" problem: often need to adjust from GAAP to get a comparable number.

### Adjustment Chain Model

```python
@dataclass
class Adjustment:
    """Single adjustment line item."""
    type: str              # "RESTRUCTURING", "STOCK_COMP", etc.
    amount: Decimal        # The adjustment amount (per share)
    description: str | None = None
    gaap_line: str | None = None  # Where it appears in GAAP

@dataclass
class AdjustmentChain:
    """Full chain from GAAP to final number."""
    adjustments: list[Adjustment]
    
    @property
    def total(self) -> Decimal:
        return sum(a.amount for a in self.adjustments)
```

### Flow Diagram

```
GAAP EPS ($2.10)
    │
    │ + Restructuring charges ($0.05)
    │ + Litigation settlement ($0.02)
    │ + Acquisition costs ($0.01)
    │ - Tax impact ($0.02)
    ▼
Adjusted EPS ($2.16)  ← Company reported "Non-GAAP"
    │
    │ - Stock comp ($0.03)  ← Your decision to add back or not
    ▼
Operating EPS ($2.13)  ← What you actually compare to estimate
```

### Standard Adjustment Types

| Type | Description | Typical Treatment |
|------|-------------|-------------------|
| `RESTRUCTURING` | Restructuring and severance | Add back |
| `STOCK_COMP` | Stock-based compensation | Controversial! |
| `LITIGATION` | Legal settlements | Add back |
| `ACQUISITION` | M&A transaction costs | Add back |
| `IMPAIRMENT` | Asset impairments | Add back |
| `DISCONTINUED` | Discontinued operations | Exclude |
| `TAX_ADJUSTMENT` | Non-recurring tax items | Varies |

### Usage

```python
# Store the chain
adjusted_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(code="eps", basis=MetricBasis.ADJUSTED),
    value=Decimal("2.16"),
    source=company_source,
    adjustments=AdjustmentChain([
        Adjustment("RESTRUCTURING", Decimal("0.05")),
        Adjustment("LITIGATION", Decimal("0.02")),
    ]),
    derived_from=gaap_eps.id,  # Link to GAAP version
)

# Query lineage
lineage = await storage.get_adjustment_lineage(adjusted_eps.id)
print(f"GAAP: ${lineage.origin.value}")
for adj in lineage.adjustments:
    print(f"  {adj.type}: ${adj.amount:+}")
print(f"Final: ${adjusted_eps.value}")
```

---

## Price Integration

Stock performance around earnings is a natural extension.

### Earnings + Price Analysis

```python
analyzer = EarningsPriceAnalysis(obs_storage, price_storage)

result = await analyzer.earnings_price_reaction(
    entity_id="aapl",
    period="2024:Q4",
    pre_days=5,   # 5 days before announcement
    post_days=5,  # 5 days after announcement
)

print(f"Surprise: {result.surprise_pct:+.1%}")
print(f"Price before: ${result.price_pre}")
print(f"Price after: ${result.price_post}")
print(f"Price change: {result.price_change_pct:+.1%}")
print(f"Post-earnings drift: {result.post_earnings_drift:+.1%}")
```

### Post-Earnings Announcement Drift (PEAD)

Academic research shows stocks continue to drift in the direction of the surprise:

```python
pead = await analyzer.pead_analysis(period="2024:Q4", drift_days=[1, 5, 20, 60])

print(f"Beats +1d drift: {pead.beats_1d:+.1%}")
print(f"Beats +60d drift: {pead.beats_60d:+.1%}")
print(f"Misses +1d drift: {pead.misses_1d:+.1%}")
print(f"Misses +60d drift: {pead.misses_60d:+.1%}")
```

---

*Earnings surprises are the heartbeat of financial markets. Let's make them a first-class citizen.* 📈
