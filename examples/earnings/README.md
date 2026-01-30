# Earnings Calendar & Estimates vs Actuals - Demo Suite

> **A complete, end-to-end demonstration of the earnings feature across all interfaces.**

## 🎯 Philosophy: Simple, Intuitive Interfaces

Every interface should feel **natural**:
- CLI: Like `git` - verb commands, sensible defaults
- Python API: Like pandas - chainable, discoverable
- REST API: Like Stripe - predictable, well-documented
- WebSocket: Like Slack - subscribe and get updates

---

## Quick Start (30 seconds)

```bash
# What's reporting today?
feedspine earnings today

# Did Apple beat?
feedspine earnings check AAPL

# Watch for releases (real-time)
feedspine earnings watch --today
```

That's it. Start there, go deeper as needed.

---

## Demo Suite Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           EARNINGS DEMO SUITE                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  11_earnings_cli_demo.py         CLI Interface                                      │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  $ feedspine earnings today                                                         │
│  $ feedspine earnings check AAPL                                                    │
│  $ feedspine earnings watch --today                                                 │
│                                                                                      │
│  12_earnings_python_api_demo.py  Python API                                         │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  calendar = EarningsCalendar()                                                      │
│  result = await calendar.check("AAPL")                                              │
│  df = await calendar.today().to_dataframe()                                         │
│                                                                                      │
│  13_earnings_rest_api_demo.py    REST API (FastAPI)                                 │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  GET  /v1/earnings/today                                                            │
│  GET  /v1/earnings/check/{ticker}                                                   │
│  POST /v1/earnings/compare                                                          │
│                                                                                      │
│  14_earnings_websocket_demo.py   Real-time WebSocket                                │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  ws://localhost:8000/v1/ws/earnings                                                 │
│  → Subscribe to releases as they happen                                             │
│                                                                                      │
│  15_earnings_full_workflow.py    Complete End-to-End                                │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  Load data → Store observations → Track calendar → Compare → Alert                  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Interface Design Principles

### 1. CLI: Verb-First Commands

```bash
# Pattern: feedspine <domain> <verb> [target] [options]

# Calendar commands
feedspine earnings today              # What's reporting today?
feedspine earnings tomorrow           # What's tomorrow?
feedspine earnings week               # This week's calendar
feedspine earnings date 2026-01-30    # Specific date

# Check commands  
feedspine earnings check AAPL         # Did AAPL beat/miss?
feedspine earnings check AAPL Q4      # Specific quarter
feedspine earnings check --sector Tech --period Q4  # Batch

# Watch commands (real-time)
feedspine earnings watch              # All releases
feedspine earnings watch --today      # Today only
feedspine earnings watch --ticker AAPL,MSFT  # Specific tickers

# Export commands
feedspine earnings export today --format csv -o earnings.csv
feedspine earnings export today --format excel -o earnings.xlsx
feedspine earnings export today --format json  # stdout
```

### 2. Python API: Fluent & Chainable

```python
from feedspine.earnings import calendar, compare

# One-liner to check if Apple beat
result = await calendar.check("AAPL")
print(f"AAPL {result.direction}: {result.surprise:+.1%}")

# Fluent API for calendar queries
df = await (
    calendar
    .date("2026-01-30")
    .sector("Technology")
    .with_estimates()
    .with_links()
    .to_dataframe()
)

# Compare estimates to actuals
comparison = await compare("AAPL", "2026:Q1")
print(comparison)  # Pretty-printed summary

# Batch operations
async for result in compare.all(period="2026:Q1"):
    if result.beat:
        print(f"✅ {result.ticker}: {result.surprise:+.1%}")
```

### 3. REST API: RESTful & Predictable

```
GET  /v1/earnings/calendar/{date}     → List events for date
GET  /v1/earnings/calendar/today      → Today's events
GET  /v1/earnings/check/{ticker}      → Quick beat/miss check
POST /v1/earnings/compare             → Detailed comparison
GET  /v1/earnings/releases/recent     → Recent releases (last N hours)
GET  /v1/earnings/export/{date}.csv   → Download CSV
```

### 4. WebSocket: Subscribe & Receive

```javascript
// Connect
ws = new WebSocket("ws://localhost:8000/v1/ws/earnings");

// Subscribe to releases
ws.send(JSON.stringify({
  action: "subscribe",
  channel: "releases",
  filters: { min_market_cap: 1000000000 }  // $1B+
}));

// Receive alerts
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`🔔 ${data.ticker} ${data.direction}: ${data.surprise}%`);
};
```

---

## Running the Demos

```bash
cd feedspine

# 1. Calendar Demo (standalone, no setup)
python examples/earnings/11_earnings_cli_demo.py

# 2. Python API Demo
python examples/earnings/12_earnings_python_api_demo.py

# 3. REST API Demo (starts server)
python examples/earnings/13_earnings_rest_api_demo.py
# Then: curl http://localhost:8000/v1/earnings/today

# 4. WebSocket Demo
python examples/earnings/14_earnings_websocket_demo.py

# 5. Full Workflow (end-to-end)
python examples/earnings/15_earnings_full_workflow.py
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              END-TO-END DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  DATA SOURCES                    PROCESSING                    INTERFACES           │
│  ────────────                    ──────────                    ──────────           │
│                                                                                      │
│  ┌─────────────┐                                               ┌─────────────┐      │
│  │ SEC EDGAR   │──┐                                        ┌──→│ CLI         │      │
│  └─────────────┘  │                                        │   └─────────────┘      │
│                   │   ┌─────────────┐   ┌─────────────┐    │                        │
│  ┌─────────────┐  ├──→│ Calendar    │──→│ Comparison  │────┼──→┌─────────────┐      │
│  │ Finnhub     │──┤   │ Service     │   │ Engine      │    │   │ Python API  │      │
│  └─────────────┘  │   └─────────────┘   └─────────────┘    │   └─────────────┘      │
│                   │          │                │             │                        │
│  ┌─────────────┐  │          ▼                ▼             ├──→┌─────────────┐      │
│  │ EntitySpine │──┘   ┌─────────────┐   ┌─────────────┐    │   │ REST API    │      │
│  │ (estimates) │      │ Entity      │   │ Observation │    │   └─────────────┘      │
│  └─────────────┘      │ Resolution  │   │ Storage     │    │                        │
│                       └─────────────┘   └─────────────┘    └──→┌─────────────┐      │
│                                                                │ WebSocket   │      │
│                                                                └─────────────┘      │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Checklist for Demos

Each demo should show these capabilities:

| Feature | 11 CLI | 12 Python | 13 REST | 14 WS | 15 Full |
|---------|--------|-----------|---------|-------|---------|
| Today's calendar | ✅ | ✅ | ✅ | ✅ | ✅ |
| Check beat/miss | ✅ | ✅ | ✅ | - | ✅ |
| Real-time alerts | ✅ | ✅ | - | ✅ | ✅ |
| Export CSV | ✅ | ✅ | ✅ | - | ✅ |
| Historical compare | ✅ | ✅ | ✅ | - | ✅ |
| Entity resolution | - | ✅ | ✅ | ✅ | ✅ |
| Estimate lookup | - | ✅ | ✅ | ✅ | ✅ |
| Links (IR, PR, 8-K) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Surprise calculation | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Next: Start with Demo 11 (CLI)

The CLI is the most discoverable interface. Let's build that first:

```bash
# This should "just work"
feedspine earnings today
```
