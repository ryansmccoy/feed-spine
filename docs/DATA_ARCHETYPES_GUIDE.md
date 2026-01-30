# 📊 Understanding Financial Data Archetypes

> **A practical guide to the different types of data in financial systems and how FeedSpine manages each one.**

---

## 🎯 Why Data Types Matter

Not all data is created equal. A stock price tick at 10:31:05 AM is fundamentally different from "Apple's Q4 2024 EPS was $1.50." If you treat them the same way, you'll either:

- **Waste storage** on data that doesn't need versioning
- **Lose history** on data that absolutely needs it
- **Kill query performance** with the wrong indexes

FeedSpine recognizes **five primary data archetypes** and optimizes storage and queries for each.

---

## 🏛️ The Five Data Archetypes

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FINANCIAL DATA UNIVERSE                         │
├──────────────┬──────────────┬───────────────┬───────────┬──────────┤
│ OBSERVATIONS │    EVENTS    │   ENTITIES    │ DOCUMENTS │  PRICES  │
│              │              │               │           │          │
│  "EPS was    │ "Earnings    │ "Apple Inc    │ "10-K     │ "AAPL =  │
│   $1.50"     │  call on     │  CIK 320193"  │  filing   │  $185.23 │
│              │  Jan 30"     │               │  PDF"     │  @10:31" │
│              │              │               │           │          │
│ 📈 Time-     │ 📅 Calendar  │ 🏢 Master     │ 📄 Content│ ⚡ High  │
│    Series    │    Based     │    Data       │    Store  │ Frequency│
└──────────────┴──────────────┴───────────────┴───────────┴──────────┘
```

---

## 1️⃣ Observations: Measured Facts Over Time

### What They Are

An **observation** is a measured fact about an entity for a specific time period. It's the bread and butter of financial analysis.

```
┌─────────────────────────────────────────────────────────────┐
│                     OBSERVATION                              │
│                                                              │
│  Entity: Apple Inc (CIK 320193)                             │
│  Metric: EPS (diluted, GAAP)                                │
│  Period: Q4 FY2024                                          │
│  Value:  $2.18 per share                                    │
│                                                              │
│  📍 THREE TIMESTAMPS:                                        │
│  ├─ period:      Oct 1 - Dec 31, 2024 (what it measures)   │
│  ├─ as_of:       Jan 30, 2025 (when it became known)       │
│  └─ captured_at: Jan 30, 2025 14:32:15 (when we got it)    │
│                                                              │
│  📦 PROVENANCE:                                              │
│  └─ Source: SEC 10-Q filing 0000320193-25-000001           │
└─────────────────────────────────────────────────────────────┘
```

### Why Versioning Matters

The same fact can be reported multiple times with different values!

```
Timeline of AAPL Q4 2024 EPS:
─────────────────────────────────────────────────────────────────►

Jan 30 (earnings call)     Feb 28 (10-K filed)      Mar 15 (restatement)
     │                          │                        │
     ▼                          ▼                        ▼
  $2.18                      $2.19                    $2.17
  (preliminary)              (audited)               (corrected)
  
FeedSpine tracks ALL THREE with supersession chain:
  obs_1 (preliminary) ──superseded_by──► obs_2 (audited) ──superseded_by──► obs_3 (corrected)
```

### FeedSpine Observation Storage

```python
from feedspine.storage import create_storage
from feedspine.adapters.observations import ObservationAdapter

# Create observation-optimized storage
storage = create_storage(
    "postgresql://localhost/feedspine",
    data_type="observations",  # Enables time-partitioning
    use_timescale=True,        # 10x compression for old data
)

# Adapter deduplicates by observation_key automatically
adapter = ObservationAdapter(
    unique_on=["entity_id", "metric_key", "period_key", "as_of", "source_id"]
)

# Ingesting from FactSet
async for obs in adapter.fetch(factset_fundamentals_feed):
    await storage.store(obs)
    # Automatic: check observation_key, track supersession, partition by captured_at
```

### Common Queries

```python
# "What was AAPL's EPS for Q4 2024?"
obs = await storage.get_observation(
    entity_id="aapl",
    metric="eps:diluted:gaap",
    period="2024:Q4",
    authoritative=True,  # Gets non-superseded, prefers SEC
)

# "Show me EPS history for AAPL"
async for obs in storage.query_observations(
    entity_id="aapl",
    metric="eps:diluted:gaap",
    since="2020-01-01",
):
    print(f"{obs.period}: ${obs.value}")

# "Compare estimates to actuals for all companies in Q4"
comparison = await storage.compare_estimates_actuals(
    period="2024:Q4",
    metric="eps",
)
```

### Point-in-Time Queries (First-Class Feature)

**Critical for backtesting - prevents lookahead bias.**

```python
from datetime import datetime

# WRONG: This returns the CURRENT (possibly restated) value
current = await storage.get_authoritative(
    entity_id="aapl",
    metric_key="eps:per_share:gaap:reported:diluted:total",
    period_key="2024:quarterly:4:0",
)
# Returns $2.17 (restated value)

# RIGHT: Point-in-time query - what was known THEN
pit = await storage.query_pit(
    entity_id="aapl",
    metric_key="eps:per_share:gaap:reported:diluted:total",
    period_key="2024:quarterly:4:0",
    as_of=datetime(2024, 2, 1),  # Query as of Feb 1
)
# Returns $2.18 (preliminary value known at that time)

# BACKTESTING: Batch PIT queries for efficiency
backtest_queries = [
    {"entity_id": "aapl", "metric_key": "eps:...", "period_key": "2024:quarterly:1:0", "as_of": datetime(2024, 5, 1)},
    {"entity_id": "msft", "metric_key": "eps:...", "period_key": "2024:quarterly:1:0", "as_of": datetime(2024, 5, 1)},
    # ... 500 more companies
]
results = await storage.query_pit_batch(backtest_queries)

# REVISION HISTORY: See how a value changed over time
history = await storage.get_revision_history(
    entity_id="aapl",
    metric_key="eps:per_share:gaap:reported:diluted:total",
    period_key="2024:quarterly:4:0",
)
for obs in history:
    print(f"{obs['as_of']}: ${obs['value_normalized']}")
# 2024-01-30: $2.18 (preliminary)
# 2024-02-28: $2.19 (audited)
# 2024-03-15: $2.17 (corrected)
```

---

## 2️⃣ Events: Things That Happen

### What They Are

An **event** is a point-in-time occurrence. Unlike observations (which measure periods), events happen at specific moments.

```
┌─────────────────────────────────────────────────────────────┐
│                        EVENT                                 │
│                                                              │
│  Type: EARNINGS_RELEASE                                     │
│  Entity: Apple Inc                                          │
│  Scheduled: Jan 30, 2025 @ 4:30 PM ET                      │
│  Status: CONFIRMED                                          │
│                                                              │
│  📅 LIFECYCLE:                                               │
│  SCHEDULED → CONFIRMED → OCCURRED → [CANCELLED]            │
│      │           │           │                              │
│   "planned"  "official"  "happened"                        │
│                                                              │
│  🔗 RELATED:                                                 │
│  └─ Produces observations (EPS, Revenue for Q4 2024)       │
└─────────────────────────────────────────────────────────────┘
```

### Event Types in Finance

| Category | Event Types |
|----------|-------------|
| **Earnings** | Earnings release, Earnings call, Guidance update |
| **Corporate Actions** | Dividend, Stock split, Merger, Spinoff |
| **Regulatory** | SEC filing, Investor day, Annual meeting |
| **Market** | IPO, Delisting, Index addition/removal |
| **Calendar** | Ex-dividend date, Record date, Pay date |

### FeedSpine Event Storage

```python
from feedspine.adapters.events import EventAdapter

adapter = EventAdapter(
    unique_on=["entity_id", "event_type", "scheduled_date"],
    status_field="status",  # Track lifecycle changes
)

# Events have status transitions (unlike observations)
event = await storage.get_event(event_id="...")
event.status = EventStatus.OCCURRED
event.actual_time = datetime.now()
await storage.update_event(event)
```

### Common Queries

```python
# "What earnings calls are next week?"
events = await storage.query_events(
    event_type="earnings_release",
    scheduled_between=("2025-02-03", "2025-02-07"),
    status=["scheduled", "confirmed"],
)

# "Show me all events for AAPL in 2024"
async for event in storage.entity_events("aapl", year=2024):
    print(f"{event.scheduled_at}: {event.event_type}")
```

---

## 3️⃣ Entities: The "Who" and "What"

### What They Are

An **entity** is a long-lived thing we track: a company, security, person, or exchange.

```
┌─────────────────────────────────────────────────────────────┐
│                       ENTITY                                 │
│                                                              │
│  Type: ISSUER                                               │
│  Name: Apple Inc                                            │
│                                                              │
│  🔑 IDENTIFIERS (many-to-one):                              │
│  ├─ CIK:       0000320193                                  │
│  ├─ LEI:       HWUPKR0MPOU8FGXBT394                        │
│  ├─ Ticker:    AAPL (NASDAQ)                               │
│  ├─ CUSIP:     037833100                                   │
│  └─ ISIN:      US0378331005                                │
│                                                              │
│  🔄 SLOWLY CHANGING:                                        │
│  ├─ Name changed: "Apple Computer" → "Apple Inc" (2007)    │
│  └─ Ticker changed: Never (stable)                         │
│                                                              │
│  🔗 RELATIONSHIPS:                                          │
│  ├─ subsidiary_of: None (top-level)                        │
│  └─ securities: [AAPL common, AAPL preferred, bonds...]    │
└─────────────────────────────────────────────────────────────┘
```

### The Identity Resolution Problem

```
Same company, different names in different systems:
─────────────────────────────────────────────────────

  FactSet:     "APPLE INC"        (entity_id: 05NJV2-E)
  Bloomberg:   "Apple Inc"        (BBG000B9XRY4)
  SEC:         "APPLE INC"        (CIK: 0000320193)
  Reuters:     "Apple Inc."       (RIC: AAPL.O)
  
FeedSpine resolves to ONE internal ID with all mappings:
  
  ┌─────────────────┐
  │  entity_123     │◄── FeedSpine canonical ID
  │                 │
  │  identifiers:   │
  │  ├─ cik: 320193 │
  │  ├─ lei: HWU... │
  │  ├─ factset: 05 │
  │  └─ bbg: BBG... │
  └─────────────────┘
```

### FeedSpine Entity Storage

```python
from feedspine.adapters.entities import EntityAdapter

adapter = EntityAdapter(
    # Multiple fields can identify the same entity
    identity_fields=["cik", "lei", "ticker:exchange"],
    merge_strategy="prefer_sec",  # SEC is authoritative
)

# Entity resolution happens automatically
await adapter.ingest(sec_entities)      # Creates entity_123
await adapter.ingest(factset_entities)  # Links to entity_123
await adapter.ingest(bloomberg_entities)  # Links to entity_123

# Query by ANY identifier
entity = await storage.resolve_entity(cik="0000320193")
entity = await storage.resolve_entity(ticker="AAPL", exchange="NASDAQ")
entity = await storage.resolve_entity(lei="HWUPKR0MPOU8FGXBT394")
# All return the same entity_123
```

---

## 4️⃣ Documents: Content with Metadata

### What They Are

A **document** is a blob of content (PDF, HTML, JSON) with rich metadata for discovery.

```
┌─────────────────────────────────────────────────────────────┐
│                      DOCUMENT                                │
│                                                              │
│  Type: SEC_FILING                                           │
│  Form: 10-K                                                 │
│  Accession: 0000320193-24-000123                           │
│                                                              │
│  📄 CONTENT:                                                 │
│  ├─ Primary: 10-K HTML (2.3 MB)                            │
│  ├─ Exhibits: [EX-21, EX-23, EX-31.1, EX-31.2, EX-32]     │
│  └─ XBRL: Instance + Schema + Calculations                 │
│                                                              │
│  🏷️ METADATA:                                               │
│  ├─ Filed: 2024-10-31                                      │
│  ├─ Period: FY2024                                         │
│  ├─ Filer: Apple Inc (CIK 320193)                         │
│  └─ Size: 15.2 MB total                                    │
│                                                              │
│  🔗 PRODUCES:                                                │
│  └─ Observations extracted from XBRL                       │
└─────────────────────────────────────────────────────────────┘
```

### FeedSpine Document Storage

```python
from feedspine.storage import create_storage
from feedspine.adapters.documents import DocumentAdapter

# Documents use blob storage + metadata DB
storage = create_storage(
    "postgresql://localhost/feedspine",
    blob_backend="s3://my-bucket/documents",
)

adapter = DocumentAdapter(
    unique_on=["accession_number"],  # SEC's natural key
    extract_metadata=True,
    store_content=True,
)

# Ingest filing
doc = await adapter.fetch_filing("0000320193-24-000123")
await storage.store_document(doc)

# Query by metadata (fast - uses DB)
filings = await storage.query_documents(
    form_type="10-K",
    filed_after="2024-01-01",
    filer_cik="0000320193",
)

# Get content (streams from blob storage)
content = await storage.get_document_content(doc.id)
```

---

## 5️⃣ Prices: High-Frequency Time-Series

### What They Are

**Prices** are high-frequency observations that need specialized storage because of sheer volume.

```
┌─────────────────────────────────────────────────────────────┐
│                       PRICES                                 │
│                                                              │
│  Volume: 1M+ ticks per day per active symbol               │
│  Latency: Microseconds matter                               │
│  Pattern: Append-only (never update)                        │
│                                                              │
│  📊 EXAMPLE (1 second of AAPL):                             │
│                                                              │
│  10:31:05.001  $185.23  100 shares   NASDAQ                │
│  10:31:05.003  $185.24  250 shares   NASDAQ                │
│  10:31:05.007  $185.23  50 shares    ARCA                  │
│  10:31:05.012  $185.25  500 shares   NASDAQ                │
│  ... (hundreds more in this second alone)                   │
│                                                              │
│  💡 KEY INSIGHT:                                             │
│  No versioning needed - each tick is immutable truth       │
└─────────────────────────────────────────────────────────────┘
```

### Why Prices Need Different Storage

| Aspect | Observations | Prices |
|--------|--------------|--------|
| Volume | ~1000/day/company | ~1M/day/symbol |
| Updates | Yes (restated) | No (append-only) |
| Queries | Point lookups | Aggregations (OHLCV) |
| Latency | Seconds OK | Milliseconds matter |
| Storage | Row-oriented (PostgreSQL) | Columnar (ClickHouse, QuestDB) |

### FeedSpine Price Storage

```python
from feedspine.storage import create_storage

# Price data uses specialized columnar storage
storage = create_storage(
    "questdb://localhost:9000",
    data_type="prices",
)

# Bulk ingest (no dedup - all ticks are unique)
await storage.bulk_insert_prices(ticks, batch_size=100_000)

# Aggregate queries (what prices are for)
ohlcv = await storage.get_ohlcv(
    symbol="AAPL",
    interval="1m",  # 1-minute bars
    start="2025-01-30 09:30:00",
    end="2025-01-30 16:00:00",
)
```

---

## 🎛️ Storage Backend Selection

FeedSpine automatically selects optimal storage based on data type:

```python
from feedspine.storage import create_storage, DataType

# Let FeedSpine choose the best backend
storage = create_storage(
    "postgresql://localhost/feedspine",
    data_type=DataType.AUTO_DETECT,  # Analyzes your data patterns
)

# Or be explicit
observation_store = create_storage(..., data_type=DataType.OBSERVATIONS)
event_store = create_storage(..., data_type=DataType.EVENTS)
entity_store = create_storage(..., data_type=DataType.ENTITIES)
document_store = create_storage(..., data_type=DataType.DOCUMENTS)
price_store = create_storage(..., data_type=DataType.PRICES)
```

### Recommended Backends by Data Type

| Data Type | Small (< 1M) | Medium (1-100M) | Large (100M+) |
|-----------|--------------|-----------------|---------------|
| **Observations** | SQLite | PostgreSQL | TimescaleDB |
| **Events** | SQLite | PostgreSQL | PostgreSQL |
| **Entities** | SQLite | PostgreSQL | PostgreSQL |
| **Documents** | Local FS | S3 + PostgreSQL | S3 + PostgreSQL |
| **Prices** | DuckDB | QuestDB | ClickHouse |

---

## 🏭 Industry Use Cases Beyond Finance

FeedSpine's data archetype model works for any domain with similar patterns:

### Healthcare / Life Sciences

| Finance Term | Healthcare Equivalent |
|--------------|----------------------|
| Observation | Lab result, Vital sign measurement |
| Event | Patient visit, Procedure, Diagnosis |
| Entity | Patient, Provider, Facility |
| Document | Medical record, Imaging study |
| Price | Real-time patient monitoring |

### IoT / Manufacturing

| Finance Term | IoT Equivalent |
|--------------|----------------|
| Observation | Sensor reading (temperature, pressure) |
| Event | Alert, Maintenance action, Failure |
| Entity | Device, Machine, Facility |
| Document | Maintenance log, Calibration cert |
| Price | High-frequency telemetry stream |

### E-Commerce / Retail

| Finance Term | Retail Equivalent |
|--------------|-------------------|
| Observation | Inventory level, Sales metric |
| Event | Order, Return, Promotion |
| Entity | Product, Customer, Store |
| Document | Invoice, Contract, Catalog |
| Price | Real-time pricing feed |

---

## 🧩 Putting It All Together

Here's how all five archetypes connect in a real financial workflow:

```
                           ┌─────────────────────┐
                           │      ENTITIES       │
                           │  "Who is Apple?"    │
                           └──────────┬──────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
   │   DOCUMENTS     │     │    EVENTS       │     │    PRICES       │
   │  "10-K filing"  │     │ "Earnings call" │     │ "AAPL @ $185"   │
   └────────┬────────┘     └────────┬────────┘     └─────────────────┘
            │                       │
            │  extracts             │  produces
            ▼                       ▼
   ┌─────────────────────────────────────────┐
   │              OBSERVATIONS               │
   │                                          │
   │   "EPS was $2.18 for Q4 2024"           │
   │   "Revenue was $119.2B for Q4 2024"     │
   │   "Guidance: Q1 2025 EPS $1.90-2.00"    │
   └─────────────────────────────────────────┘
```

### FeedSpine Unified Pipeline

```python
from feedspine import FeedSpine, Pipeline

async def financial_data_pipeline():
    async with FeedSpine() as fs:
        # 1. Entities first (master data)
        await fs.run(Pipeline("sec-entities"))
        await fs.run(Pipeline("factset-entities"))
        
        # 2. Documents (filings)
        await fs.run(Pipeline("sec-filings"))
        
        # 3. Events (earnings calendar)
        await fs.run(Pipeline("earnings-calendar"))
        
        # 4. Observations (extracted from documents + vendor feeds)
        await fs.run(Pipeline("factset-fundamentals"))
        await fs.run(Pipeline("sec-xbrl-extract"))
        
        # 5. Prices (market data)
        await fs.run(Pipeline("realtime-quotes"))
        
        # All data types automatically use appropriate storage!
```

---

## 📚 Further Reading

- [Architecture Analysis](./ARCHITECTURE_ANALYSIS.md) - Deep dive into FeedSpine internals
- [Storage Optimization](../src/feedspine/storage/optimization.py) - Query and insert optimization
- [Docker Setup](../docker/README.md) - Production database deployment

---

*FeedSpine: Because not all data deserves the same treatment.* 🎯
