# API Design & System Architecture

> **How FeedSpine, EntitySpine, and other systems interact - interfaces, contracts, and integration patterns.**

---

## The Architecture Question

You asked the key question: **Who owns what?**

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT ARCHITECTURE QUESTION                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   "Does FeedSpine or EntitySpine manage financial data?"                            │
│   "Where do prices live?"                                                           │
│   "How do frontends/other apps consume this data?"                                  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Proposed Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              LIBRARY RESPONSIBILITIES                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │                           EntitySpine                                       │    │
│  │                        "The Domain Model"                                   │    │
│  │                                                                             │    │
│  │  OWNS:                                                                      │    │
│  │  • Entity definitions (Company, Security, Person)                          │    │
│  │  • Identity resolution (ticker → canonical ID)                             │    │
│  │  • Corporate actions (splits, dividends, mergers)                          │    │
│  │  • Events (earnings calendar, corporate events)                            │    │
│  │  • Fiscal calendars                                                        │    │
│  │  • Relationships (subsidiary_of, security_of)                              │    │
│  │  • Domain enums (MetricCategory, EstimateScope, etc.)                      │    │
│  │                                                                             │    │
│  │  DOES NOT OWN:                                                              │    │
│  │  • Storage implementation                                                   │    │
│  │  • Time-series optimization                                                 │    │
│  │  • Feed ingestion                                                          │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                              │
│                                      │ uses domain models                           │
│                                      ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │                           FeedSpine                                         │    │
│  │                     "The Data Engineering Layer"                            │    │
│  │                                                                             │    │
│  │  OWNS:                                                                      │    │
│  │  • Observation storage (financial metrics over time)                       │    │
│  │  • Price storage (high-frequency time-series)                              │    │
│  │  • Document storage (filings, reports)                                     │    │
│  │  • Feed adapters (FactSet, Bloomberg, SEC, etc.)                           │    │
│  │  • Deduplication & supersession                                            │    │
│  │  • Point-in-time queries                                                   │    │
│  │  • Multi-vendor conflict resolution                                        │    │
│  │  • Estimates vs Actuals comparison engine                                  │    │
│  │                                                                             │    │
│  │  DOES NOT OWN:                                                              │    │
│  │  • Domain definitions (imports from EntitySpine)                           │    │
│  │  • Business logic beyond data management                                   │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                              │
│                                      │ exposes via                                  │
│                                      ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────────┐    │
│  │                        API Layer (New!)                                     │    │
│  │                   "The Interface Contract"                                  │    │
│  │                                                                             │    │
│  │  PROVIDES:                                                                  │    │
│  │  • REST API (OpenAPI/Swagger specification)                                │    │
│  │  • GraphQL API (optional, for flexible queries)                            │    │
│  │  • WebSocket streams (real-time earnings alerts)                           │    │
│  │  • SDK/Client libraries (Python, TypeScript)                               │    │
│  │  • Data contracts (Pydantic models = JSON Schema)                          │    │
│  │                                                                             │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Where Do Prices Live?

**Prices belong in FeedSpine** but with specialized storage:

```python
# FeedSpine handles ALL time-series data, including prices
from feedspine.storage import create_storage

# Observations (EPS, Revenue) - PostgreSQL/TimescaleDB
obs_storage = create_storage(
    "postgresql://localhost/feedspine",
    data_type="observations",
)

# Prices (ticks, OHLCV) - Specialized columnar storage
price_storage = create_storage(
    "questdb://localhost:9000",  # Or ClickHouse, or TimescaleDB
    data_type="prices",
)

# Same FeedSpine interface, different backend
await obs_storage.store(eps_observation)
await price_storage.store(price_tick)
```

### Price + Earnings Integration

```python
from feedspine.analysis import EarningsPriceAnalysis

analyzer = EarningsPriceAnalysis(obs_storage, price_storage)

# "How did AAPL perform around Q4 2024 earnings?"
result = await analyzer.earnings_price_reaction(
    entity_id="aapl",
    period="2024:Q4",
    
    # Price windows
    pre_days=5,      # 5 days before announcement
    post_days=5,     # 5 days after announcement
    
    # Include surprise context
    include_surprise=True,
)

print(f"Surprise: {result.surprise_pct:+.1%}")
print(f"Price before: ${result.price_pre}")
print(f"Price after: ${result.price_post}")
print(f"Price change: {result.price_change_pct:+.1%}")
print(f"Earnings drift: {result.post_earnings_drift:+.1%}")
```

---

## The "Real Operating EPS" Problem

You mentioned needing to adjust EPS to get the "real" number. This is the **Non-GAAP adjustment** problem:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          EPS ADJUSTMENT CHAIN                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  GAAP EPS (as reported)                                                             │
│      │                                                                               │
│      │ - Restructuring charges                                                      │
│      │ - Litigation settlements                                                     │
│      │ - Asset impairments                                                          │
│      │ - Acquisition costs                                                          │
│      │ - Stock compensation (sometimes)                                             │
│      │ + Tax adjustments                                                            │
│      │                                                                               │
│      ▼                                                                               │
│  Adjusted EPS (company reported)                                                    │
│      │                                                                               │
│      │ - Additional analyst adjustments                                             │
│      │ - Discontinued operations                                                    │
│      │                                                                               │
│      ▼                                                                               │
│  "Street" EPS (what analysts compare to)                                            │
│      │                                                                               │
│      │ - Your custom adjustments                                                    │
│      │                                                                               │
│      ▼                                                                               │
│  Operating EPS from Continuing Operations (your target)                             │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Modeling Adjustments in FeedSpine

```python
from feedspine.domain import Observation, MetricSpec, AdjustmentChain
from entityspine.domain.enums import MetricBasis

# Store the GAAP EPS
gaap_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(
        code="eps",
        basis=MetricBasis.GAAP,
        scope=EstimateScope.REPORTED,
    ),
    value=Decimal("2.10"),
    period=period,
    source=sec_source,
)

# Store the company-reported adjusted EPS
adjusted_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(
        code="eps",
        basis=MetricBasis.ADJUSTED,  # Company's adjusted
        scope=EstimateScope.REPORTED,
    ),
    value=Decimal("2.18"),
    period=period,
    source=company_source,
    
    # Track the adjustments
    adjustments=AdjustmentChain([
        Adjustment(type="RESTRUCTURING", amount=Decimal("0.05")),
        Adjustment(type="STOCK_COMP", amount=Decimal("0.03")),
    ]),
    
    # Link to GAAP version
    derived_from="gaap_eps_observation_id",
)

# Calculate your own "operating EPS"
operating_eps = Observation(
    entity_id="aapl",
    metric=MetricSpec(
        code="eps",
        basis=MetricBasis.OPERATING,  # Your custom basis
        scope=EstimateScope.REPORTED,
    ),
    value=Decimal("2.15"),  # Your calculation
    period=period,
    source=SourceKey(vendor="internal", feed="custom_adjustments"),
    
    adjustments=AdjustmentChain([
        Adjustment(type="START_FROM_GAAP", amount=Decimal("2.10")),
        Adjustment(type="ADD_BACK_RESTRUCTURING", amount=Decimal("0.05")),
        # Didn't add back stock comp
    ]),
    
    derived_from="gaap_eps_observation_id",
)
```

### Adjustment Registry

```python
# Define what adjustments mean
STANDARD_ADJUSTMENTS = {
    "RESTRUCTURING": {
        "description": "Restructuring and severance charges",
        "typical_treatment": "add_back",
        "gaap_line": "Restructuring charges",
    },
    "STOCK_COMP": {
        "description": "Stock-based compensation expense",
        "typical_treatment": "add_back",  # Controversial!
        "gaap_line": "Stock-based compensation",
    },
    "LITIGATION": {
        "description": "Legal settlements and reserves",
        "typical_treatment": "add_back",
        "gaap_line": "Litigation expense",
    },
    "ACQUISITION": {
        "description": "M&A transaction and integration costs",
        "typical_treatment": "add_back",
        "gaap_line": "Acquisition-related costs",
    },
    "DISCONTINUED": {
        "description": "Discontinued operations",
        "typical_treatment": "exclude",
        "gaap_line": "Income from discontinued operations",
    },
}
```

---

## API Design: Interface Contracts

You're asking about **how external systems consume this data**. This is **API design** and **contracts**.

### What Are Contracts?

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              API CONTRACTS                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  CONTRACT = A promise about:                                                        │
│  • What data you can request (endpoints, methods)                                   │
│  • What format the data will be in (schemas)                                        │
│  • What errors you might get (error codes)                                          │
│  • How authentication works                                                         │
│  • Rate limits, pagination, etc.                                                    │
│                                                                                      │
│  FORMATS:                                                                           │
│  • OpenAPI/Swagger (REST APIs) - YAML/JSON spec                                    │
│  • GraphQL Schema (GraphQL APIs) - SDL                                             │
│  • Pydantic Models (Python) - generates JSON Schema                                │
│  • TypeScript types (frontend) - .d.ts files                                       │
│  • Protocol Buffers (gRPC) - .proto files                                          │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### FeedSpine API Contract (Proposed)

```python
# feedspine/api/contracts.py
"""
API Contracts - These Pydantic models define the public interface.
They auto-generate:
- JSON Schema (for validation)
- OpenAPI spec (for REST API)
- TypeScript types (for frontend)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════
# REQUEST CONTRACTS (What clients send us)
# ═══════════════════════════════════════════════════════════════════

class CompareRequest(BaseModel):
    """Request to compare estimate vs actual."""
    
    entity_id: str = Field(..., description="Entity identifier (ticker, CIK, etc.)")
    metric_code: str = Field(default="eps", description="Metric to compare")
    period: str = Field(..., description="Period key like '2024:Q4'")
    
    # Optional filters
    estimate_source: Optional[str] = Field(None, description="Vendor for estimate")
    actual_source: Optional[str] = Field(None, description="Vendor for actual")
    include_yoy: bool = Field(default=True, description="Include YoY comparable")
    include_price_reaction: bool = Field(default=False, description="Include price data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "AAPL",
                "metric_code": "eps",
                "period": "2024:Q4",
                "include_yoy": True,
            }
        }


class RecentActualsRequest(BaseModel):
    """Request for recently reported actuals."""
    
    since_minutes: int = Field(default=30, ge=1, le=1440)
    metric_codes: list[str] = Field(default=["eps", "revenue"])
    min_surprise_pct: Optional[float] = Field(None, description="Filter by surprise magnitude")
    sectors: Optional[list[str]] = Field(None, description="Filter by sector")


class BatchCompareRequest(BaseModel):
    """Request for batch comparison."""
    
    period: str
    metric_code: str = "eps"
    entity_ids: Optional[list[str]] = Field(None, description="Specific entities, or all")
    index: Optional[str] = Field(None, description="Filter by index membership")
    sector: Optional[str] = Field(None, description="Filter by sector")


# ═══════════════════════════════════════════════════════════════════
# RESPONSE CONTRACTS (What we send back)
# ═══════════════════════════════════════════════════════════════════

class ObservationResponse(BaseModel):
    """Single observation in API response."""
    
    entity_id: str
    metric_code: str
    period: str
    value: float
    unit: str
    
    # Timestamps
    as_of: datetime
    captured_at: datetime
    
    # Source
    source_vendor: str
    source_feed: str
    
    # Optional metadata
    adjustments: Optional[list[dict]] = None


class CompareResponse(BaseModel):
    """Response from comparison endpoint."""
    
    entity_id: str
    period: str
    metric_code: str
    
    # Identifiers for joining
    identifiers: dict[str, str]  # {"ticker": "AAPL", "cik": "320193", ...}
    
    # The comparison
    estimate: Optional[ObservationResponse]
    actual: ObservationResponse
    comparable: Optional[ObservationResponse]  # YoY
    
    # Computed values
    surprise_pct: Optional[float]
    surprise_direction: Literal["BEAT", "MISS", "INLINE", "NO_ESTIMATE"]
    yoy_growth_pct: Optional[float]
    
    # Timestamps
    released_at: datetime
    processed_at: datetime
    
    # Source
    source: str  # "Z", "B", "F"
    
    # Optional price reaction
    price_reaction: Optional[dict] = None


class BatchCompareResponse(BaseModel):
    """Response from batch comparison."""
    
    period: str
    metric_code: str
    
    # Summary stats
    total_companies: int
    companies_with_estimates: int
    beat_count: int
    miss_count: int
    beat_rate: float
    
    # Individual results
    results: list[CompareResponse]


class RecentActualsResponse(BaseModel):
    """Response for recent actuals."""
    
    since: datetime
    until: datetime
    count: int
    results: list[CompareResponse]


# ═══════════════════════════════════════════════════════════════════
# ERROR CONTRACTS
# ═══════════════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    """Standard error response."""
    
    error: str
    code: str
    details: Optional[dict] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Entity not found",
                "code": "ENTITY_NOT_FOUND",
                "details": {"entity_id": "INVALID_TICKER"},
            }
        }
```

### REST API Endpoints

```python
# feedspine/api/routes.py
"""
REST API endpoints - The actual HTTP interface.
"""

from fastapi import FastAPI, Query, HTTPException
from feedspine.api.contracts import *

app = FastAPI(
    title="FeedSpine API",
    description="Financial data API for estimates, actuals, and comparisons",
    version="1.0.0",
)


# ═══════════════════════════════════════════════════════════════════
# COMPARISON ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.post("/v1/compare", response_model=CompareResponse)
async def compare_single(request: CompareRequest):
    """
    Compare estimate to actual for a single entity/period.
    
    Returns surprise percentage, direction, and optionally YoY growth.
    """
    result = await comparator.compare(
        entity_id=request.entity_id,
        metric_code=request.metric_code,
        period=request.period,
        estimate_source=request.estimate_source,
        actual_source=request.actual_source,
        include_yoy=request.include_yoy,
    )
    return CompareResponse.from_domain(result)


@app.post("/v1/compare/batch", response_model=BatchCompareResponse)
async def compare_batch(request: BatchCompareRequest):
    """
    Compare all companies in a period.
    
    Returns aggregate stats and individual results.
    """
    results = []
    async for r in comparator.compare_all(
        period=request.period,
        metric_code=request.metric_code,
        entity_ids=request.entity_ids,
    ):
        results.append(r)
    
    beats = [r for r in results if r.beat]
    
    return BatchCompareResponse(
        period=request.period,
        metric_code=request.metric_code,
        total_companies=len(results),
        companies_with_estimates=len([r for r in results if r.estimate]),
        beat_count=len(beats),
        miss_count=len(results) - len(beats),
        beat_rate=len(beats) / len(results) if results else 0,
        results=[CompareResponse.from_domain(r) for r in results],
    )


@app.get("/v1/recent", response_model=RecentActualsResponse)
async def recent_actuals(
    since_minutes: int = Query(default=30, ge=1, le=1440),
    metric_codes: list[str] = Query(default=["eps", "revenue"]),
):
    """
    Get recently reported actuals.
    
    Use for real-time earnings monitoring.
    """
    since = datetime.utcnow() - timedelta(minutes=since_minutes)
    results = await comparator.recent_actuals(since=since, metric_codes=metric_codes)
    
    return RecentActualsResponse(
        since=since,
        until=datetime.utcnow(),
        count=len(results),
        results=[CompareResponse.from_domain(r) for r in results],
    )


# ═══════════════════════════════════════════════════════════════════
# OBSERVATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/v1/observations/{entity_id}", response_model=list[ObservationResponse])
async def get_observations(
    entity_id: str,
    metric_code: str = Query(...),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    source: Optional[str] = Query(None),
):
    """
    Query observations for an entity.
    """
    obs = await storage.query_observations(
        entity_id=entity_id,
        metric_code=metric_code,
        since=since,
        until=until,
        source=source,
    )
    return [ObservationResponse.from_domain(o) for o in obs]


@app.get("/v1/observations/{entity_id}/pit", response_model=ObservationResponse)
async def get_observation_pit(
    entity_id: str,
    metric_code: str = Query(...),
    period: str = Query(...),
    as_of: datetime = Query(...),
):
    """
    Point-in-time query - what was known at a specific time.
    """
    obs = await storage.query_pit(
        entity_id=entity_id,
        metric_key=metric_code,
        period_key=period,
        as_of=as_of,
    )
    if not obs:
        raise HTTPException(status_code=404, detail="No observation found")
    return ObservationResponse.from_domain(obs)


# ═══════════════════════════════════════════════════════════════════
# ENTITY ENDPOINTS (delegates to EntitySpine)
# ═══════════════════════════════════════════════════════════════════

@app.get("/v1/entities/resolve")
async def resolve_entity(
    ticker: Optional[str] = Query(None),
    cik: Optional[str] = Query(None),
    isin: Optional[str] = Query(None),
):
    """
    Resolve any identifier to canonical entity.
    """
    entity = await entity_store.resolve(ticker=ticker, cik=cik, isin=isin)
    return {
        "id": entity.id,
        "name": entity.name,
        "identifiers": entity.identifiers,
        "sector": entity.sector,
        "industry": entity.industry,
    }
```

### OpenAPI Specification (Auto-Generated)

FastAPI + Pydantic automatically generates this:

```yaml
# Generated openapi.json / openapi.yaml
openapi: 3.0.0
info:
  title: FeedSpine API
  version: 1.0.0
  description: Financial data API for estimates, actuals, and comparisons

paths:
  /v1/compare:
    post:
      summary: Compare estimate to actual
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CompareRequest'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CompareResponse'

components:
  schemas:
    CompareRequest:
      type: object
      required:
        - entity_id
        - period
      properties:
        entity_id:
          type: string
          description: Entity identifier
        metric_code:
          type: string
          default: eps
        period:
          type: string
          description: Period key like '2024:Q4'
    
    CompareResponse:
      type: object
      properties:
        entity_id:
          type: string
        surprise_pct:
          type: number
          nullable: true
        surprise_direction:
          type: string
          enum: [BEAT, MISS, INLINE, NO_ESTIMATE]
        # ... etc
```

### TypeScript Types (Auto-Generated from OpenAPI)

```typescript
// Generated from OpenAPI spec using openapi-typescript
// feedspine-client/types.ts

export interface CompareRequest {
  entity_id: string;
  metric_code?: string;
  period: string;
  estimate_source?: string | null;
  actual_source?: string | null;
  include_yoy?: boolean;
}

export interface CompareResponse {
  entity_id: string;
  period: string;
  metric_code: string;
  identifiers: Record<string, string>;
  estimate: ObservationResponse | null;
  actual: ObservationResponse;
  comparable: ObservationResponse | null;
  surprise_pct: number | null;
  surprise_direction: 'BEAT' | 'MISS' | 'INLINE' | 'NO_ESTIMATE';
  yoy_growth_pct: number | null;
  released_at: string;  // ISO datetime
  processed_at: string;
  source: string;
}

// Usage in React
const response = await fetch('/v1/compare', {
  method: 'POST',
  body: JSON.stringify({ entity_id: 'AAPL', period: '2024:Q4' }),
});
const data: CompareResponse = await response.json();
```

---

## WebSocket for Real-Time (Optional)

```python
# feedspine/api/websocket.py
"""
WebSocket endpoint for real-time earnings alerts.
"""

from fastapi import WebSocket

@app.websocket("/v1/stream/earnings")
async def earnings_stream(websocket: WebSocket):
    """
    WebSocket stream for real-time earnings surprises.
    
    Clients receive messages when new actuals are reported.
    """
    await websocket.accept()
    
    try:
        async for event in comparator.watch_transitions(
            metric_codes=["eps", "revenue"],
            poll_interval_seconds=30,
        ):
            await websocket.send_json({
                "type": "NEW_ACTUAL",
                "entity_id": event.entity_id,
                "metric_code": event.metric_code,
                "actual": event.actual.value,
                "surprise_pct": event.surprise_pct,
                "direction": event.direction,
                "released_at": event.released_at.isoformat(),
            })
    except Exception:
        await websocket.close()
```

```typescript
// Frontend WebSocket client
const ws = new WebSocket('wss://api.example.com/v1/stream/earnings');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.entity_id} ${data.direction} by ${data.surprise_pct}%`);
  // Update UI, trigger notification, etc.
};
```

---

## SDK / Client Library

```python
# feedspine-client/client.py
"""
Python SDK for consuming FeedSpine API.
"""

import httpx
from feedspine.api.contracts import CompareRequest, CompareResponse


class FeedSpineClient:
    """Client for FeedSpine API."""
    
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )
    
    async def compare(
        self,
        entity_id: str,
        period: str,
        metric_code: str = "eps",
        **kwargs,
    ) -> CompareResponse:
        """Compare estimate to actual."""
        request = CompareRequest(
            entity_id=entity_id,
            period=period,
            metric_code=metric_code,
            **kwargs,
        )
        response = await self.client.post("/v1/compare", json=request.model_dump())
        response.raise_for_status()
        return CompareResponse.model_validate(response.json())
    
    async def recent_actuals(self, since_minutes: int = 30) -> list[CompareResponse]:
        """Get recently reported actuals."""
        response = await self.client.get(
            "/v1/recent",
            params={"since_minutes": since_minutes},
        )
        response.raise_for_status()
        data = response.json()
        return [CompareResponse.model_validate(r) for r in data["results"]]


# Usage
async def main():
    client = FeedSpineClient("https://api.example.com", api_key="...")
    
    result = await client.compare("AAPL", "2024:Q4")
    print(f"AAPL {result.surprise_direction} by {result.surprise_pct}%")
```

---

## Summary: What Are These Called?

| Term | Meaning |
|------|---------|
| **Interface** | The methods/endpoints exposed to consumers |
| **Contract** | The agreed-upon format for requests/responses |
| **Schema** | The structure of data (JSON Schema, Pydantic) |
| **OpenAPI/Swagger** | Standard spec for REST APIs |
| **SDK** | Client library that wraps the API |
| **Protocol** | The communication rules (REST, GraphQL, gRPC) |

---

## Next Steps

1. **Define contracts first** (Pydantic models) - this is the foundation
2. **Build REST API** (FastAPI) - generates OpenAPI automatically  
3. **Generate TypeScript types** - for frontend
4. **Build SDK** - for Python consumers
5. **Add WebSocket** - for real-time features

Would you like me to:
1. Start implementing the API contracts?
2. Create a separate `feedspine-api` package structure?
3. Design the price storage integration?
4. Create the adjustment tracking system?

---

*APIs are promises. Contracts make those promises explicit.* 📝
