# Task Tracking: Estimates vs Actuals

> **Implementation progress and task status.**

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ✅ | Complete |
| 🔄 | In Progress |
| ⏳ | Not Started |
| ❌ | Blocked |

---

## Phase 1: Documentation & Design ✅

| Task | Status | Notes |
|------|--------|-------|
| Core API design (01_DESIGN.md) | ✅ | ComparisonResult, resolution logic |
| Implementation plan (02_IMPLEMENTATION_PLAN.md) | ✅ | 4-phase roadmap |
| Test plan (03_TEST_PLAN.md) | ✅ | Unit, integration, property-based |
| Usage examples (04_EXAMPLES.md) | ✅ | CLI, Python API, streaming |
| spine-core integration (05_SPINE_CORE_INTEGRATION.md) | ✅ | Pipeline, Workflow, Registry patterns |
| capture-spine integration (06_CAPTURE_SPINE_INTEGRATION.md) | ✅ | Record types, adapter, alerts |
| UI mockups | ✅ | EarningsTable.tsx, EarningsPage.tsx |

---

## Phase 2: Service Layer 🔄

| Task | Status | Notes |
|------|--------|-------|
| `EarningsCalendarService` class | ✅ | `feedspine/src/feedspine/earnings/service.py` |
| Mock connectors (SEC, Finnhub) | ✅ | Working with sample data |
| `CalendarEvent` model | ✅ | Full metadata schema |
| `SurpriseResult` model | ✅ | Beat/miss calculation |
| `fetch_calendar()` method | ✅ | Returns CalendarResult |
| `watch_releases()` method | ✅ | Generator for streaming |
| `compute_surprise()` method | ✅ | Calculates beat/miss |
| `store_calendar()` method | ✅ | Mock persistence |
| Package `__init__.py` | ✅ | Public exports |

---

## Phase 3: Real Connectors ⏳

| Task | Status | Notes |
|------|--------|-------|
| SEC EDGAR connector | ⏳ | Parse 8-K filings for earnings |
| Finnhub API connector | ⏳ | Estimates and calendar |
| Yahoo Finance connector | ⏳ | Calendar backup source |
| FactSet connector | ⏳ | Premium estimates data |
| Connector interface protocol | ⏳ | `EarningsSource` protocol |

---

## Phase 4: spine-core Workflow ⏳

| Task | Status | Notes |
|------|--------|-------|
| `@register_pipeline("earnings.ingest_calendar")` | ⏳ | |
| `@register_pipeline("earnings.enrich_estimates")` | ⏳ | |
| `@register_workflow("earnings.daily_calendar")` | ⏳ | |
| `CaptureSpineAdapter` in spine-core | ⏳ | POST results to capture-spine |
| Alert on workflow failure | ⏳ | Wire to alerts framework |

---

## Phase 5: capture-spine UI ⏳

| Task | Status | Notes |
|------|--------|-------|
| `EarningsTable.tsx` component | ⏳ | Copy from mockups, wire to API |
| `EarningsPage.tsx` page | ⏳ | Dual-panel layout |
| API hook `useEarnings()` | ⏳ | TanStack Query |
| Route `/earnings` | ⏳ | Add to router |
| Alert rule for earnings beats | ⏳ | Configure in alert_rules |

---

## Phase 6: Testing ⏳

| Task | Status | Notes |
|------|--------|-------|
| Unit tests for service | ⏳ | pytest |
| Integration tests with mock data | ⏳ | |
| E2E test with capture-spine | ⏳ | |

---

## Demo Files Created

| File | Purpose |
|------|---------|
| `feedspine/examples/earnings/demo_10_*.py` | Service API demos |
| `feedspine/examples/earnings/demo_11_*.py` | (if created) |

---

## File Index

### feedspine
```
feedspine/
├── src/feedspine/earnings/
│   ├── __init__.py         ✅ Public exports
│   └── service.py          ✅ EarningsCalendarService
├── docs/features/estimates-vs-actuals/
│   ├── README.md           ✅ Overview
│   ├── 01_DESIGN.md        ✅ API design
│   ├── 02_IMPLEMENTATION_PLAN.md  ✅ Roadmap
│   ├── 03_TEST_PLAN.md     ✅ Test strategy
│   ├── 04_EXAMPLES.md      ✅ Usage examples
│   ├── 05_SPINE_CORE_INTEGRATION.md  ✅ Pipeline architecture
│   ├── 06_CAPTURE_SPINE_INTEGRATION.md  ✅ UI & execution tracking
│   ├── 07_TODO.md          ✅ This file
│   └── mockups/
│       ├── README.md       ✅ Mockup overview
│       ├── EarningsTable.tsx  ✅ Table component
│       └── EarningsPage.tsx   ✅ Page layout
```

### spine-core (planned)
```
spine-core/packages/spine-core/src/spine/
├── adapters/
│   └── capture_spine.py    ⏳ CaptureSpineAdapter
```

### capture-spine (planned)
```
capture-spine/frontend/src/
├── components/earnings/
│   ├── EarningsTable.tsx   ⏳
│   └── EarningsWidget.tsx  ⏳
├── pages/
│   └── EarningsPage.tsx    ⏳
└── hooks/
    └── useEarnings.ts      ⏳
```
