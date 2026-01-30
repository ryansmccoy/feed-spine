# Implementation Plan: Estimates vs Actuals

> **Phased roadmap for building the comparison engine.**

---

## Phase 1: Core Comparison Engine (v0.1.0)

### Goal
Basic single-entity and batch comparison functionality.

### Deliverables

#### 1.1 Data Models
```
feedspine/src/feedspine/analysis/
├── __init__.py
├── comparison.py          # ComparisonResult dataclass
├── estimate_actual.py     # EstimateActualComparison class
└── exceptions.py          # ComparisonError, NoEstimateError, etc.
```

**ComparisonResult fields:**
- `entity_id`, `metric_code`, `period_key`
- `estimate: Observation | None`
- `actual: Observation`
- `difference: Decimal | None`
- `surprise_pct: float | None`
- `beat: bool | None`
- `direction: Literal["BEAT", "MISS", "INLINE", "NO_ESTIMATE"]`

#### 1.2 Core Methods

| Method | Description | Priority |
|--------|-------------|----------|
| `compare()` | Single entity comparison | P0 |
| `compare_all()` | Async generator for batch | P0 |
| `_resolve_estimate()` | Find pre-announcement estimate | P0 |
| `_resolve_actual()` | Find authoritative actual | P0 |

#### 1.3 Query Parameters

```python
class CompareParams:
    entity_id: str
    metric_code: str
    period: str
    
    # Estimate selection
    estimate_scope: EstimateScope = CONSENSUS
    estimate_basis: MetricBasis = ADJUSTED
    estimate_source: str | None = None  # None = any
    estimate_as_of: datetime | str = "pre_announcement"
    
    # Actual selection
    actual_basis: MetricBasis = ADJUSTED
    actual_source: str | None = None  # None = authoritative
    
    # Output
    include_metadata: bool = True
```

### Tasks

- [ ] Create `feedspine/src/feedspine/analysis/` package
- [ ] Implement `ComparisonResult` dataclass
- [ ] Implement `EstimateActualComparison` class
- [ ] Implement `compare()` method
- [ ] Implement `compare_all()` async generator
- [ ] Implement `_resolve_estimate()` with "pre_announcement" logic
- [ ] Implement `_resolve_actual()` with authority ranking
- [ ] Add unit tests for all methods
- [ ] Add integration test with sample data

### Estimated Effort: 3-5 days

---

## Phase 2: Real-Time Features (v0.2.0)

### Goal
Detect new actuals as they arrive, time-windowed queries.

### Deliverables

#### 2.1 New Methods

| Method | Description | Priority |
|--------|-------------|----------|
| `recent_actuals()` | Actuals in time window | P0 |
| `watch_transitions()` | Streaming detection | P1 |
| `pending_reports()` | What's expected soon | P1 |

#### 2.2 Time Window Queries

```python
# "What came in the last 30 minutes?"
recent = await comparator.recent_actuals(
    since=datetime.utcnow() - timedelta(minutes=30),
    metric_codes=["eps", "revenue"],
    include_surprise=True,
)

# "What's expected after market close today?"
pending = await comparator.pending_reports(
    scheduled_after=datetime.utcnow(),
    scheduled_before=datetime.utcnow() + timedelta(hours=4),
)
```

#### 2.3 Streaming Interface

```python
async for event in comparator.watch_transitions(
    metric_codes=["eps"],
    poll_interval_seconds=60,
    min_surprise_pct=None,  # All surprises
):
    # event.type: "NEW_ACTUAL" | "ESTIMATE_UPDATED" | "REVISED_ACTUAL"
    pass
```

### Tasks

- [ ] Implement `recent_actuals()` with time filtering
- [ ] Implement `pending_reports()` using Events
- [ ] Implement `watch_transitions()` async generator
- [ ] Add polling loop with configurable interval
- [ ] Add callback/webhook support
- [ ] Add unit tests
- [ ] Add integration test with simulated real-time data

### Estimated Effort: 3-4 days

---

## Phase 3: Derived Observations (v0.3.0)

### Goal
Create storable surprise observations that can be queried.

### Deliverables

#### 3.1 Derived Metrics

| Metric Code | Description | Unit |
|-------------|-------------|------|
| `earnings_surprise` | (actual - estimate) / \|estimate\| | percent |
| `earnings_surprise_abs` | actual - estimate | currency |
| `earnings_beat` | 1 if beat, 0 if miss, null if no estimate | flag |
| `estimate_revision` | Change in estimate over time | percent |

#### 3.2 Auto-Derivation Pipeline

```python
# Configure which derived observations to create
derivation_config = DerivedObservationConfig(
    create_surprise_pct=True,
    create_surprise_abs=True,
    create_beat_flag=True,
    source_key=SourceKey(vendor="feedspine", feed="derived:earnings"),
)

# Run derivation when new actual arrives
async def on_new_actual(actual: Observation):
    derived = await comparator.derive_observations(actual, config=derivation_config)
    await storage.store_many(derived)
```

#### 3.3 Query Derived Data

```python
# "Show me all big misses in Q4"
big_misses = await storage.query_observations(
    metric_code="earnings_surprise",
    period="2024:Q4",
    max_value=-0.10,  # -10% or worse
)

# "What percentage of companies beat in Q4?"
beat_rate = await storage.aggregate(
    metric_code="earnings_beat",
    period="2024:Q4",
    aggregation="mean",
)
```

### Tasks

- [ ] Define derived metric specifications
- [ ] Implement `derive_observations()` method
- [ ] Implement `DerivedObservationConfig` class
- [ ] Add auto-derivation trigger on new actuals
- [ ] Add metadata tracking (source estimate, source actual)
- [ ] Add unit tests
- [ ] Add query examples

### Estimated Effort: 2-3 days

---

## Phase 4: Multi-Source Comparison (v0.4.0)

### Goal
Compare estimates from different vendors, track consensus spread.

### Deliverables

#### 4.1 Multi-Source Methods

| Method | Description |
|--------|-------------|
| `compare_sources()` | Compare same metric across vendors |
| `consensus_spread()` | High/low/mean/median across sources |
| `source_accuracy()` | Historical accuracy by source |

#### 4.2 Cross-Vendor Analysis

```python
# Compare FactSet vs Bloomberg for AAPL EPS
multi = await comparator.compare_sources(
    entity_id="aapl",
    metric_code="eps",
    period="2024:Q4",
    sources=["factset", "bloomberg", "ibes"],
)

for source, result in multi.by_source.items():
    print(f"{source}: Est ${result.estimate.value} → Surprise {result.surprise_pct:+.1%}")

# Which vendor was closest?
print(f"Most accurate: {multi.most_accurate_source}")
```

#### 4.3 Consensus Statistics

```python
spread = await comparator.consensus_spread(
    entity_id="aapl",
    metric_code="eps",
    period="2024:Q4",
)

print(f"High: ${spread.high}")
print(f"Low: ${spread.low}")
print(f"Mean: ${spread.mean}")
print(f"Median: ${spread.median}")
print(f"Std Dev: ${spread.std_dev}")
print(f"Analyst Count: {spread.analyst_count}")
```

### Tasks

- [ ] Implement `compare_sources()` method
- [ ] Implement `consensus_spread()` method
- [ ] Implement `source_accuracy()` (requires historical data)
- [ ] Add "most accurate source" logic
- [ ] Add source agreement/disagreement metrics
- [ ] Add unit tests

### Estimated Effort: 2-3 days

---

## Phase 5: Ecosystem Integrations (v0.5.0)

### Goal
Deep integration with EntitySpine, py-sec-edgar, and CaptureSpine.

### Deliverables

See [06_INTEGRATIONS.md](06_INTEGRATIONS.md) for full details.

#### 5.1 EntitySpine Integration
- Use `Entity` resolution for identifier mapping
- Use `CorporateAction` history for split adjustments
- Use `Event` for earnings calendar

#### 5.2 py-sec-edgar Integration
- Extract actuals from 10-Q/10-K XBRL
- Extract guidance from 8-K filings
- Parse earnings press releases

#### 5.3 CaptureSpine Integration
- Real-time filing detection
- ReplayService for historical comparisons
- Lakehouse layers for storage

### Tasks

- [ ] EntitySpine: Add `get_split_adjusted_value()` helper
- [ ] EntitySpine: Add `get_fx_rate()` helper
- [ ] py-sec-edgar: Add XBRL earnings extractor
- [ ] py-sec-edgar: Add 8-K guidance parser
- [ ] CaptureSpine: Add filing arrival webhook
- [ ] Add end-to-end integration tests

### Estimated Effort: 5-7 days

---

## Phase 6: API Contracts & External Interface (v0.6.0)

### Goal
Expose comparison engine via REST/WebSocket APIs with typed contracts.

### Deliverables

#### 6.1 API Contracts (Pydantic Models)

```python
# feedspine/api/contracts.py
from pydantic import BaseModel, Field

class CompareRequest(BaseModel):
    """Request to compare estimate vs actual."""
    entity_id: str
    metric_code: str = "eps"
    period: str  # "2024:Q4"
    estimate_source: str | None = None
    actual_source: str | None = None
    include_yoy: bool = True
    include_price_reaction: bool = False

class CompareResponse(BaseModel):
    """Response from comparison endpoint."""
    entity_id: str
    period: str
    metric_code: str
    identifiers: dict[str, str]  # Multi-ticker for joins
    estimate: ObservationResponse | None
    actual: ObservationResponse
    comparable: ObservationResponse | None  # YoY
    surprise_pct: float | None
    surprise_direction: Literal["BEAT", "MISS", "INLINE", "NO_ESTIMATE"]
    yoy_growth_pct: float | None
    released_at: datetime
    processed_at: datetime
    source: str  # "Z", "B", "F"
    price_reaction: PriceReactionResponse | None = None
```

#### 6.2 REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/compare` | POST | Single entity comparison |
| `/v1/compare/batch` | POST | Batch comparison |
| `/v1/recent` | GET | Recently reported actuals |
| `/v1/observations/{entity}` | GET | Query observations |
| `/v1/observations/{entity}/pit` | GET | Point-in-time query |
| `/v1/entities/resolve` | GET | Resolve identifier |

#### 6.3 WebSocket Streaming

```python
@app.websocket("/v1/stream/earnings")
async def earnings_stream(websocket: WebSocket):
    """Real-time earnings alerts."""
    async for event in comparator.watch_transitions():
        await websocket.send_json({
            "type": "NEW_ACTUAL",
            "entity_id": event.entity_id,
            "surprise_pct": event.surprise_pct,
            "direction": event.direction,
        })
```

#### 6.4 Generated Artifacts

- **OpenAPI spec** - Auto-generated from FastAPI + Pydantic
- **TypeScript types** - Generated from OpenAPI for frontend
- **Python SDK** - `FeedSpineClient` wrapper class

### Tasks

- [ ] Create `feedspine/api/` package
- [ ] Implement Pydantic request/response models
- [ ] Implement FastAPI routes
- [ ] Add WebSocket endpoint for streaming
- [ ] Add authentication (API key or OAuth)
- [ ] Generate OpenAPI spec
- [ ] Generate TypeScript types
- [ ] Create Python SDK client
- [ ] Add API integration tests
- [ ] Add rate limiting

### Estimated Effort: 4-5 days

---

## Phase 7: Price Integration (v0.7.0)

### Goal
Integrate price data to analyze stock performance around earnings.

### Deliverables

#### 7.1 Price Storage

```python
# Separate backend for high-frequency price data
price_storage = create_storage(
    "questdb://localhost:9000",
    data_type="prices",
)
```

#### 7.2 Earnings + Price Analysis

```python
class EarningsPriceAnalysis:
    """Analyze price reaction to earnings."""
    
    async def earnings_price_reaction(
        self,
        entity_id: str,
        period: str,
        pre_days: int = 5,
        post_days: int = 5,
    ) -> PriceReactionResult:
        """Price performance around earnings."""
        ...

# Usage
result = await analyzer.earnings_price_reaction("aapl", "2024:Q4")
print(f"Surprise: {result.surprise_pct:+.1%}")
print(f"Price before: ${result.price_pre}")
print(f"Price after: ${result.price_post}")
print(f"Post-earnings drift: {result.post_earnings_drift:+.1%}")
```

#### 7.3 Post-Earnings Announcement Drift (PEAD)

```python
# Academic pattern: stocks drift in direction of surprise
pead_results = await analyzer.pead_analysis(
    period="2024:Q4",
    drift_days=[1, 5, 10, 20, 60],
)

# Do beats continue to outperform?
print(f"Beats +1d drift: {pead_results.beats_1d:+.1%}")
print(f"Beats +60d drift: {pead_results.beats_60d:+.1%}")
```

### Tasks

- [ ] Design price storage interface
- [ ] Implement `EarningsPriceAnalysis` class
- [ ] Implement `earnings_price_reaction()` method
- [ ] Implement `pead_analysis()` for drift studies
- [ ] Add `include_price_reaction` to compare endpoints
- [ ] Add price data adapters (vendor TBD)
- [ ] Add unit tests

### Estimated Effort: 4-5 days

---

## Phase 8: Adjustment Tracking (v0.8.0)

### Goal
Track the adjustment chain from GAAP to Operating EPS.

### Deliverables

#### 8.1 Adjustment Chain Model

```python
@dataclass
class Adjustment:
    """Single adjustment line item."""
    type: str  # "RESTRUCTURING", "STOCK_COMP", etc.
    amount: Decimal
    description: str | None = None
    gaap_line: str | None = None  # Where it appears in GAAP

@dataclass
class AdjustmentChain:
    """Chain of adjustments from GAAP to final."""
    adjustments: list[Adjustment]
    
    @property
    def total_adjustment(self) -> Decimal:
        return sum(a.amount for a in self.adjustments)
```

#### 8.2 EPS Adjustment Flow

```
GAAP EPS ($2.10)
    │
    │ + Restructuring charges ($0.05)
    │ + Litigation settlement ($0.02)
    │ + Acquisition costs ($0.01)
    │ - Tax impact ($0.02)
    ▼
Adjusted EPS ($2.16)  ← Company reported
    │
    │ - Stock comp ($0.03)  ← Your decision
    ▼
Operating EPS ($2.13)  ← What you compare
```

#### 8.3 Usage

```python
# Store GAAP EPS with adjustment chain
gaap_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(code="eps", basis=MetricBasis.GAAP),
    value=Decimal("2.10"),
    source=sec_source,
)

adjusted_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(code="eps", basis=MetricBasis.ADJUSTED),
    value=Decimal("2.16"),
    source=company_source,
    adjustments=AdjustmentChain([
        Adjustment("RESTRUCTURING", Decimal("0.05")),
        Adjustment("LITIGATION", Decimal("0.02")),
        Adjustment("ACQUISITION", Decimal("0.01")),
        Adjustment("TAX_IMPACT", Decimal("-0.02")),
    ]),
    derived_from=gaap_eps.id,
)

# Query with lineage
history = await storage.get_adjustment_lineage(adjusted_eps.id)
print(f"Started from GAAP: ${history.origin.value}")
for adj in history.adjustments:
    print(f"  {adj.type}: ${adj.amount:+}")
print(f"Final: ${adjusted_eps.value}")
```

### Tasks

- [ ] Design `Adjustment` and `AdjustmentChain` dataclasses
- [ ] Add `adjustments` field to Observation
- [ ] Add `derived_from` field to Observation
- [ ] Implement `get_adjustment_lineage()` query
- [ ] Create standard adjustment type registry
- [ ] Add XBRL extraction for adjustment line items
- [ ] Add unit tests

### Estimated Effort: 3-4 days

---

## Milestones

| Version | Features | Target Date |
| v0.1.0 | Core comparison | +2 weeks |
| v0.2.0 | Real-time detection | +4 weeks |
| v0.3.0 | Derived observations | +5 weeks |
| v0.4.0 | Multi-source | +7 weeks |
| v0.5.0 | Full integrations | +10 weeks |
| v0.6.0 | API Layer | +12 weeks |
| v0.7.0 | Price integration | +14 weeks |
| v0.8.0 | Adjustment tracking | +16 weeks |

---

## Dependencies

### Required
- FeedSpine observation storage (exists)
- EntitySpine domain models (exists)

### Optional (enhances functionality)
- py-sec-edgar XBRL parser (exists, needs adapter)
- CaptureSpine real-time feeds (exists, needs integration)
- FactSet/Bloomberg adapters (future)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Pre-announcement estimate timing complex | Start with explicit timestamps, add magic later |
| Split adjustment edge cases | Use EntitySpine's tested corporate action logic |
| Real-time performance | Use indexed queries, cache recent comparisons |
| Multi-source conflicts | Document clear precedence rules |

---

*Build incrementally, test continuously, ship often.* 🚀
