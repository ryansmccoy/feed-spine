# FeedSpine + EntitySpine: Multi-Vendor Data Pipeline

## How They Work Together

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   RAW FEEDS              FEEDSPINE               ENTITYSPINE        │
│   ─────────              ─────────               ──────────         │
│   ┌─────────┐                                                       │
│   │FactSet  │──┐        ┌──────────────┐                           │
│   │ API     │  │        │              │      ┌────────────────┐   │
│   └─────────┘  │        │  Feed        │      │ Entity         │   │
│   ┌─────────┐  ├───────►│  Ingestion   ├─────►│ Resolution     │   │
│   │Bloomberg│  │        │              │      │                │   │
│   │ Files   │  │        │  • Rate limit│      │ • CIK→Entity   │   │
│   └─────────┘  │        │  • Parse     │      │ • CUSIP merge  │   │
│   ┌─────────┐  │        │  • Validate  │      │ • Ticker map   │   │
│   │ SEC     │──┘        │  • Store     │      └────────────────┘   │
│   │ XBRL    │           │              │             │              │
│   └─────────┘           └──────────────┘             │              │
│                                │                     │              │
│                                ▼                     ▼              │
│                         ┌─────────────────────────────────┐        │
│                         │        STORAGE LAYER            │        │
│                         │                                 │        │
│                         │  Bronze: Raw vendor records     │        │
│                         │  Silver: Observations w/ keys   │        │
│                         │  Gold: Reconciled + authoritative│       │
│                         └─────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## FeedSpine Responsibilities

FeedSpine handles the **data engineering** side:

| Responsibility | What It Does |
|----------------|--------------|
| **Feed Ingestion** | Poll APIs, parse files, handle rate limits |
| **Deduplication** | `natural_key` prevents re-processing same data |
| **Storage Backends** | SQLite, PostgreSQL, TimescaleDB, DuckDB |
| **Partitioning** | Time-based partitioning for large datasets |
| **Compression** | TimescaleDB compression for historical data |
| **Batch Processing** | Efficient bulk inserts (5,000+ records/batch) |

---

## EntitySpine Responsibilities

EntitySpine handles the **domain modeling** side:

| Responsibility | What It Does |
|----------------|--------------|
| **Domain Models** | `Observation`, `MetricSpec`, `FiscalPeriod` |
| **Entity Resolution** | Map CIK/CUSIP/Ticker to unified entity |
| **Metric Taxonomy** | Canonical keys for cross-vendor matching |
| **Supersession** | Track corrections/revisions |
| **Authority** | Determine which value is "authoritative" |

---

## The Bridge: Observation Adapters

FeedSpine adapters convert raw records into EntitySpine observations:

```python
# feedspine/adapters/factset_adapter.py

from feedspine.core import Feed, FeedAdapter
from entityspine.domain.observation import (
    Observation, MetricSpec, FiscalPeriod, SourceKey, ValueWithUnits
)
from entityspine.domain.enums import VendorNamespace, ObservationType

class FactSetFundamentalsAdapter(FeedAdapter):
    """Convert FactSet fundamentals to EntitySpine Observations."""
    
    def transform(self, record: dict) -> Observation:
        """Transform a raw FactSet record."""
        
        # Map FactSet field to MetricSpec
        metric = self._map_metric(record["field_name"])
        
        # Build fiscal period from FactSet's format
        period = FiscalPeriod.quarterly(
            year=record["fiscal_year"],
            quarter=record["fiscal_quarter"],
            fye_month=record.get("fye_month", 12),
        )
        
        # Normalize value
        value = ValueWithUnits.from_raw(
            raw_value=record["value"],
            scale=record.get("scale", 1),
            currency=record.get("currency", "USD"),
            unit=self._infer_unit(metric),
        )
        
        return Observation(
            entity_id=record["factset_entity_id"],  # Resolved later
            metric=metric,
            period=period,
            value=value,
            observation_type=ObservationType.ACTUAL,
            source_key=SourceKey.factset(record["field_name"]),
            as_of=record.get("as_of_date"),
        )
    
    def _map_metric(self, field_name: str) -> MetricSpec:
        """Map FactSet field to MetricSpec."""
        mapping = {
            "FF_EPS_DIL": MetricSpec.eps_vendor_normalized(PerShareType.DILUTED),
            "FF_EPS_BAS": MetricSpec.eps_vendor_normalized(PerShareType.BASIC),
            "FF_SALES": MetricSpec.revenue(),
            "FF_NET_INC": MetricSpec.net_income(),
            "FF_EBITDA": MetricSpec.ebitda(),
        }
        return mapping.get(field_name, MetricSpec.custom(field_name))
```

---

## Multi-Vendor Pipeline Example

```python
"""
Full pipeline: Ingest EPS from multiple vendors, reconcile, query.
"""

import asyncio
from feedspine.storage import create_storage
from feedspine.feeds import FactSetFeed, BloombergFeed, SECXBRLFeed
from feedspine.adapters import FactSetAdapter, BloombergAdapter, SECAdapter
from entityspine.domain.observation import Observation, MetricSpec, FiscalPeriod
from entityspine.services import EntityService, ObservationService

async def main():
    # =========================================================================
    # 1. Setup Storage (FeedSpine)
    # =========================================================================
    storage = create_storage(
        "postgresql://localhost/financial_data",
        data_type="observations",
    )
    await storage.initialize()
    
    # =========================================================================
    # 2. Setup Services (EntitySpine)
    # =========================================================================
    entity_service = EntityService(storage)
    observation_service = ObservationService(storage)
    
    # =========================================================================
    # 3. Define Feeds
    # =========================================================================
    feeds = [
        FactSetFeed(
            api_key="...",
            dataset="fundamentals",
            adapter=FactSetAdapter(),
        ),
        BloombergFeed(
            source_dir="/data/bloomberg/fundamentals",
            adapter=BloombergAdapter(),
        ),
        SECXBRLFeed(
            adapter=SECAdapter(),
        ),
    ]
    
    # =========================================================================
    # 4. Ingest from All Sources
    # =========================================================================
    for feed in feeds:
        print(f"Processing {feed.name}...")
        
        async for raw_record in feed.fetch():
            # Transform to Observation
            obs: Observation = feed.adapter.transform(raw_record)
            
            # Resolve entity (EntitySpine)
            entity = await entity_service.resolve(
                cik=raw_record.get("cik"),
                cusip=raw_record.get("cusip"),
                ticker=raw_record.get("ticker"),
            )
            obs = obs.with_entity_id(entity.entity_id)
            
            # Store with dedup (FeedSpine)
            await observation_service.store(obs)
        
        print(f"  Completed {feed.name}")
    
    # =========================================================================
    # 5. Query Reconciled Data
    # =========================================================================
    
    # Get Apple Q4 2024 EPS from all sources
    aapl = await entity_service.get_by_ticker("AAPL")
    period = FiscalPeriod.quarterly(2024, 4, fye_month=9)
    
    print("\n=== AAPL Q4 2024 EPS ===\n")
    
    # All EPS values
    async for obs in observation_service.query(
        entity_id=aapl.entity_id,
        metric_code=MetricCode.EPS,
        period=period,
    ):
        print(f"{obs.source_key.vendor.value:12} | {str(obs.metric):35} | ${obs.value.value_normalized}")
    
    # Authoritative value (prefers SEC, then vendors)
    auth = await observation_service.get_authoritative(
        entity_id=aapl.entity_id,
        metric=MetricSpec.eps_gaap_diluted(),
        period=period,
    )
    print(f"\nAuthoritative (GAAP): ${auth.value.value_normalized}")

asyncio.run(main())
```

Output:
```
Processing FactSet Fundamentals...
  Completed FactSet Fundamentals
Processing Bloomberg Files...
  Completed Bloomberg Files
Processing SEC XBRL...
  Completed SEC XBRL

=== AAPL Q4 2024 EPS ===

SEC          | EPS (diluted)                       | $1.46
SEC          | EPS (basic)                         | $1.48
FACTSET      | EPS (diluted) [vendor_normalized]   | $2.20
BLOOMBERG    | EPS (diluted) [vendor_normalized]   | $2.19

Authoritative (GAAP): $1.46
```

---

## Storage Recommendations by Data Volume

FeedSpine automatically recommends storage based on scale:

| Volume | Backend | Partitioning | Compression |
|--------|---------|--------------|-------------|
| < 100K | SQLite | No | No |
| 100K - 10M | PostgreSQL | No | Optional |
| 10M - 100M | PostgreSQL | Monthly | Yes |
| 100M - 1B | TimescaleDB | Monthly | Yes |
| > 1B | TimescaleDB + Sharding | Daily | Aggressive |

```python
from feedspine.storage import get_storage_recommendations, DataType

# Get recommendations
rec = get_storage_recommendations(
    data_type=DataType.OBSERVATIONS,
    estimated_rows=50_000_000,  # 50M observations
)

print(rec)
# {
#     "backend": "postgresql",
#     "partitioning": {"enabled": True, "column": "captured_at", "interval": "month"},
#     "indexes": {"primary": ["entity_id", "metric_key", "period_key"], "use_brin": True},
#     "compression": {"enabled": True, "after_days": 30},
#     "batch_size": 5000,
#     "notes": ["PostgreSQL with proper indexing should handle well"]
# }
```

---

## Key Integration Points

### 1. Entity Resolution

Before storing observations, resolve the entity:

```python
# Raw record has CUSIP
raw = {"cusip": "037833100", "metric": "eps", "value": 1.46}

# Resolve to unified entity
entity = await entity_service.resolve(cusip=raw["cusip"])
# entity.entity_id = "aapl"
# entity.identifiers = {"cik": "320193", "cusip": "037833100", "ticker": "AAPL"}

# Now store observation with unified entity_id
obs = Observation(entity_id=entity.entity_id, ...)
```

### 2. Canonical Key Matching

Match observations across vendors using canonical keys:

```python
# FactSet EPS and Bloomberg EPS with same metric definition
factset_metric = MetricSpec.eps_vendor_normalized()
bloomberg_metric = MetricSpec.eps_vendor_normalized()

# Same canonical key = same metric
assert factset_metric.canonical_key == bloomberg_metric.canonical_key
# "eps:per_share:gaap:vendor_normalized:diluted:total"
```

### 3. Supersession Tracking

Track revisions automatically:

```python
# First observation
obs1 = Observation(..., observation_id="obs_001")
await observation_service.store(obs1)

# Revised observation (same entity/metric/period, different as_of)
obs2 = Observation(
    ...,
    observation_id="obs_002",
    supersedes_id="obs_001",  # Links to previous
)
await observation_service.store(obs2)

# Query gets latest non-superseded
latest = await observation_service.get_authoritative(...)
assert latest.observation_id == "obs_002"
```

---

## Summary

| Layer | Tool | Purpose |
|-------|------|---------|
| **Ingestion** | FeedSpine | Poll feeds, parse, rate limit |
| **Storage** | FeedSpine | PostgreSQL, partitioning, compression |
| **Domain Model** | EntitySpine | Observation, MetricSpec, FiscalPeriod |
| **Entity Resolution** | EntitySpine | Unify CIK/CUSIP/Ticker |
| **Authority** | EntitySpine | Pick authoritative value |
| **Queries** | Both | FeedSpine storage + EntitySpine logic |

The two libraries are designed to work together:
- **FeedSpine** = Data engineering (how to get and store data)
- **EntitySpine** = Domain modeling (what the data means)
