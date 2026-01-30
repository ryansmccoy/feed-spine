# 📊 Estimates vs Actuals Feature

> **A first-class feature for comparing consensus estimates to reported actuals, detecting earnings surprises, and generating derived observations.**

---

## 📁 Documentation Structure

Documents are numbered in **logical reading order** (design → plan → build → integrate → track):

| # | Document | Purpose |
|---|----------|---------|
| 01 | [01_DESIGN.md](01_DESIGN.md) | Core API design and data models |
| 02 | [02_IMPLEMENTATION_PLAN.md](02_IMPLEMENTATION_PLAN.md) | Phased implementation roadmap |
| 03 | [03_TEST_PLAN.md](03_TEST_PLAN.md) | Test strategy and test cases |
| 04 | [04_EXAMPLES.md](04_EXAMPLES.md) | Usage examples and recipes |
| 05 | [05_SPINE_CORE_INTEGRATION.md](05_SPINE_CORE_INTEGRATION.md) | Pipeline, Workflow, Registry patterns |
| 06 | [06_CAPTURE_SPINE_INTEGRATION.md](06_CAPTURE_SPINE_INTEGRATION.md) | UI, alerts, execution tracking |
| 07 | [07_TODO.md](07_TODO.md) | Task tracking and progress |
| — | [mockups/](mockups/) | React component mockups (EarningsTable, EarningsPage) |

---

## 🎯 Feature Overview

### The Problem

Financial analysts constantly need to answer:
- "Did Apple beat earnings estimates?"
- "What companies reported in the last hour?"
- "Show me all Q4 surprises greater than 5%"
- "How did the Street estimate compare to the actual?"

This requires comparing:
- **Estimates** (analyst consensus, company guidance, vendor forecasts)
- **Actuals** (reported results from SEC filings, earnings calls, company announcements)

### The Solution

FeedSpine provides a `EstimateActualComparison` engine that:

1. **Queries flexibly** - by entity, period, metric, source, time window
2. **Handles timing correctly** - "pre-announcement" estimate resolution
3. **Supports real-time** - detect new actuals as they arrive
4. **Creates derived data** - surprises become queryable observations
5. **Integrates across the ecosystem** - EntitySpine, py-sec-edgar, CaptureSpine

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ESTIMATES VS ACTUALS FLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │  ESTIMATES   │     │   ACTUALS    │     │   EVENTS     │                │
│  │              │     │              │     │              │                │
│  │ FactSet      │     │ SEC 10-Q/K   │     │ Earnings     │                │
│  │ Bloomberg    │     │ 8-K          │     │ Calendar     │                │
│  │ I/B/E/S      │     │ Press Release│     │              │                │
│  │ Refinitiv    │     │ Company IR   │     │              │                │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                    │                    │                         │
│         └────────────────────┼────────────────────┘                         │
│                              │                                              │
│                              ▼                                              │
│                    ┌──────────────────┐                                     │
│                    │    FeedSpine     │                                     │
│                    │   Observation    │                                     │
│                    │     Storage      │                                     │
│                    └────────┬─────────┘                                     │
│                             │                                               │
│                             ▼                                               │
│                    ┌──────────────────┐                                     │
│                    │  EstimateActual  │                                     │
│                    │   Comparison     │                                     │
│                    │     Engine       │                                     │
│                    └────────┬─────────┘                                     │
│                             │                                               │
│            ┌────────────────┼────────────────┐                              │
│            │                │                │                              │
│            ▼                ▼                ▼                              │
│     ┌────────────┐   ┌────────────┐   ┌────────────┐                       │
│     │  Queries   │   │  Derived   │   │   Alerts   │                       │
│     │            │   │   Obs      │   │            │                       │
│     │ compare()  │   │ surprise%  │   │ real-time  │                       │
│     │ compare_all│   │ beat/miss  │   │ webhooks   │                       │
│     │ recent()   │   │ direction  │   │ streams    │                       │
│     └────────────┘   └────────────┘   └────────────┘                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Design Decisions

### 1. Beat/Miss Tolerance: **Zero**
A beat is strictly `actual > estimate`. No tolerance bands.
- Reasoning: Tolerance is subjective and varies by use case
- Users can apply their own tolerance in queries

### 2. Missing Estimates: **Show Data Anyway**
Companies without analyst coverage still appear in results.
- `estimate` field is `None`
- `surprise_pct` is `None`
- Allows filtering: `if result.estimate is not None`

### 3. Currency Handling: **Auto-Normalize**
Use exchange rates from the estimate's `as_of` date.
- Convert to a common currency (usually USD)
- Store original values in metadata for audit

### 4. Split Adjustments: **Auto-Adjust**
Apply corporate action adjustments automatically.
- Use EntitySpine's corporate action history
- Adjust historical estimates to current basis
- Store both adjusted and unadjusted values

---

## 🚀 Quick Start

```python
from feedspine.analysis import EstimateActualComparison

# Initialize
comparator = EstimateActualComparison(storage)

# Single company comparison
result = await comparator.compare(
    entity_id="aapl",
    metric_code="eps",
    period="2024:Q4",
)

print(f"Beat: {result.beat}, Surprise: {result.surprise_pct:+.1%}")

# Batch comparison
async for r in comparator.compare_all(period="2024:Q4", metric_code="eps"):
    print(f"{r.entity_id}: {r.direction} by {r.surprise_pct:+.1%}")

# Real-time detection
recent = await comparator.recent_actuals(
    since=datetime.utcnow() - timedelta(minutes=30),
)
```

---

## 📚 Related Documentation

- [DATA_ARCHETYPES_GUIDE.md](../../DATA_ARCHETYPES_GUIDE.md) - Understanding observations
- [API_DESIGN_AND_CONTRACTS.md](../../API_DESIGN_AND_CONTRACTS.md) - REST/WebSocket API contracts
- [MULTI_VENDOR_EPS_GUIDE.md](../../../entityspine/docs/guides/MULTI_VENDOR_EPS_GUIDE.md) - Multi-vendor EPS complexity
- [FINANCIAL_DATA_PITFALLS.md](../../../entityspine/docs/guides/FINANCIAL_DATA_PITFALLS.md) - Common data problems
- [TIMESTAMP_AND_CAPTURESPINE_INTEGRATION.md](../../TIMESTAMP_AND_CAPTURESPINE_INTEGRATION.md) - Temporal model

---

## 📈 Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Documentation & Design | ✅ Complete | All 7 docs + mockups |
| Phase 2: Service Layer | ✅ Complete | `EarningsCalendarService` working |
| Phase 3: Real Connectors | ⏳ Not Started | SEC, Finnhub, Yahoo |
| Phase 4: spine-core Workflow | ⏳ Not Started | Pipeline registration |
| Phase 5: capture-spine UI | ⏳ Not Started | EarningsTable, EarningsPage |
| Phase 6: Testing | ⏳ Not Started | Unit, integration, E2E |

See [07_TODO.md](07_TODO.md) for detailed task breakdown.

---

*Making earnings surprises a first-class citizen in your data pipeline.* 📊
