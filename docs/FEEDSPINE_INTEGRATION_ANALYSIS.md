# FeedSpine Integration Analysis

**Date**: January 24, 2026  
**Purpose**: Identify pain points, opportunities, and improvements for FeedSpine based on py-sec-edgar integration experience.

---

## Current Integration Overview

py-sec-edgar uses FeedSpine as the core feed capture framework with these components:

| FeedSpine Component | py-sec-edgar Usage |
|---------------------|-------------------|
| `FeedSpine` orchestrator | `FilingDownloader`, `FilingCapture`, `UnifiedFeedService` |
| `DuckDBStorage` | Primary storage in 4+ locations |
| `FeedAdapter` protocol | `SecRssFeedAdapter`, `SecDailyIndexAdapter`, `SecQuarterlyIndexAdapter` |
| `Enricher` protocol | `SECSubmissionEnricher`, `SECFinancialEnricher`, `SECEntityEnricher` |
| `Record` / `RecordCandidate` | Filing metadata storage |
| `Layer` (BRONZE/SILVER/GOLD) | Data quality tracking |
| `StorageBackend` protocol | Query interface |

---

## Pain Points

### 1. **Untyped `record.content` Access** ⚠️ HIGH IMPACT

**Problem**: All domain data lives in `record.content: dict[str, Any]`. Every access is a string key lookup with no type safety.

**Evidence** (20+ occurrences):
```python
# py_sec_edgar/enrichers/financial_enricher.py:111
form_type = record.content.get("form_type", "").upper()

# py_sec_edgar/enrichers/submission_enricher.py:140
cik = record.content.get("cik", "").lstrip("0") or "0"

# py_sec_edgar/graph/enricher.py:236-239
company_name = record.content.get("company_name", "Unknown Company")
cik = record.content.get("cik", "")
form_type = record.content.get("form_type", "")
filed_date = record.content.get("filed_date", "")
```

**Issues**:
- No IDE autocomplete
- Typos cause silent failures (`record.content.get("form_tyep")` returns `None`)
- No validation that required fields exist
- Every consumer must know the schema
- Type coercion scattered everywhere (`.upper()`, `.lstrip("0")`)

**Desired**:
```python
# Type-safe access
record.content.form_type  # str, required
record.content.cik        # CIK object
record.content.filed_date # date object
```

---

### 2. **Duplicate Orchestrators** ⚠️ HIGH IMPACT

**Problem**: Three separate classes do essentially the same thing:

| Class | Location | Purpose |
|-------|----------|---------|
| `FilingDownloader` | `download/downloader.py` | Download filings |
| `FilingCapture` | `pipeline/capture.py` | Fetch filings (pipeline) |
| `UnifiedFeedService` | `services/unified_feed.py` | Collect filings |

**All three**:
- Create `DuckDBStorage`
- Create `FeedSpine`
- Register SEC adapters
- Call `spine.collect()`
- Convert `Record` → `Filing`

**Root cause**: FeedSpine doesn't provide enough high-level abstraction, so py-sec-edgar keeps creating wrappers.

---

### 3. **Record → Domain Object Conversion Duplication** ⚠️ MEDIUM IMPACT

**Problem**: `_record_to_filing()` function duplicated in multiple files:

```python
# download/downloader.py:58-71
def _record_to_filing(record: Record) -> Filing:
    content = record.content
    return Filing(
        accession_number=AccessionNumber.from_string(content["accession_number"]),
        form_type=content.get("form_type", ""),
        ...
    )

# services/unified_feed.py:96-110  
def _record_to_filing(record: Record) -> Filing:
    # Same code again
```

**Issues**:
- DRY violation
- Different files might diverge
- Business logic scattered

---

### 4. **Storage Created in Multiple Places** ⚠️ MEDIUM IMPACT

**Problem**: `DuckDBStorage` instantiated with hardcoded paths in 4+ locations:

```python
# pipeline/capture.py:95
self._storage = DuckDBStorage(str(db_path))

# download/downloader.py:164
self._storage = DuckDBStorage(str(db_path))

# services/unified_feed.py:169
self._storage = DuckDBStorage(str(db_path))
```

**Issues**:
- No shared connection pool
- Potential for multiple connections to same database
- Configuration scattered

---

### 5. **Query API is Storage-Specific** ⚠️ MEDIUM IMPACT

**Problem**: FeedSpine's query API uses generic filters, but py-sec-edgar needs domain queries.

**What FeedSpine provides**:
```python
async for record in storage.query(
    filters={"content.form_type": {"$in": ["10-K", "10-Q"]}},
    limit=100,
):
    ...
```

**What py-sec-edgar wants**:
```python
filings = await storage.get_filings_by_company("AAPL", forms=["10-K"])
filings = await storage.get_filings_by_date_range(start, end)
filings = await storage.search("risk factors climate")
```

**Result**: py-sec-edgar created `UnifiedStorage` bridge with domain methods, adding complexity.

---

### 6. **Enricher Registration is Ad-Hoc** ⚠️ LOW IMPACT

**Problem**: Enrichers are registered imperatively, with no clear pipeline visualization.

```python
# pipeline/capture.py:109-115
if self._enrich:
    from py_sec_edgar.enrichers import SECSubmissionEnricher
    self._submission_enricher = SECSubmissionEnricher(...)
    await self._submission_enricher.initialize()
    self._spine.register_enricher(self._submission_enricher)
```

**Issues**:
- No way to see the full enrichment pipeline at a glance
- Order of enrichers not explicit
- Hard to test individual enrichers
- Can't easily swap enrichers for different use cases

---

### 7. **Layer Promotion Rarely Used** ⚠️ LOW IMPACT

**Problem**: FeedSpine has BRONZE/SILVER/GOLD layers, but py-sec-edgar mostly ignores them.

**Evidence**: Most code treats everything as BRONZE:
```python
# Only SECSubmissionEnricher uses layers
if record.layer != Layer.BRONZE:
    return  # Skip
# ... do work ...
record = record.promote(Layer.SILVER, enrichments)
```

**Most queries don't filter by layer**:
```python
async for record in storage.query(filters=filters):  # Gets all layers
```

---

### 8. **No Batch Processing Support** ⚠️ MEDIUM IMPACT

**Problem**: Enrichers process records one at a time. For 10,000 filings, that's 10,000 HTTP requests.

```python
# Current: sequential
for record in records:
    result = await enricher.enrich(record)  # One at a time
```

**Desired**:
```python
# Batch: efficient
results = await enricher.enrich_batch(records[:100])
```

---

### 9. **Progress Reporting is Awkward** ⚠️ LOW IMPACT

**Problem**: FeedSpine's `ProgressReporter` protocol requires manual integration.

```python
# py-sec-edgar wraps it:
class RichProgressReporter:
    def __init__(self, reporter: ProgressReporter):
        ...
```

Would be cleaner if FeedSpine had built-in rich progress or a simpler callback API.

---

### 10. **No Connection/Resource Management** ⚠️ MEDIUM IMPACT

**Problem**: Each FeedSpine instance creates its own HTTP clients, storage connections, etc.

**Evidence**:
```python
# SecRssFeedAdapter creates its own client
async def initialize(self):
    self._client = httpx.AsyncClient(...)

# SECSubmissionEnricher creates another
async def initialize(self):
    self._client = httpx.AsyncClient(...)
```

**Desired**: Shared resource pool managed by FeedSpine.

---

## Alternatives to Pipeline Builder Pattern

You mentioned you're not a fan of the builder pattern. Here are alternative approaches:

### Alternative A: **Configuration Object Pattern**

```python
from feedspine import FeedSpine, Config

config = Config(
    storage=DuckDBStorage("./data.db"),
    feeds=[
        SecRssFeedAdapter(form_types=["10-K"]),
        SecDailyIndexAdapter(days=30),
    ],
    enrichers=[
        SECSubmissionEnricher(),
        SECFinancialEnricher(),
    ],
    settings={
        "max_concurrent": 10,
        "retry_attempts": 3,
    }
)

async with FeedSpine(config) as spine:
    result = await spine.collect()
```

**Pros**: Declarative, serializable to YAML/JSON, easy to test
**Cons**: Verbose for simple cases

---

### Alternative B: **Decorator/Registration Pattern**

```python
from feedspine import FeedSpine, feed, enricher

spine = FeedSpine(storage=DuckDBStorage("./data.db"))

@spine.feed
class MyRSSFeed(SecRssFeedAdapter):
    form_types = ["10-K", "10-Q"]

@spine.enricher(order=1)
class ParseSubmission(SECSubmissionEnricher):
    pass

@spine.enricher(order=2) 
class ExtractFinancials(SECFinancialEnricher):
    pass

result = await spine.collect()
```

**Pros**: Familiar Django/FastAPI style, explicit ordering
**Cons**: Magic, harder to configure dynamically

---

### Alternative C: **Functional Composition Pattern**

```python
from feedspine import collect, with_storage, with_feeds, with_enrichers

result = await collect(
    with_storage(DuckDBStorage("./data.db")),
    with_feeds(
        SecRssFeedAdapter(form_types=["10-K"]),
        SecDailyIndexAdapter(days=30),
    ),
    with_enrichers(
        SECSubmissionEnricher(),
        SECFinancialEnricher(),
    ),
)
```

**Pros**: Composable, no classes needed
**Cons**: Less discoverable, unfamiliar to OOP devs

---

### Alternative D: **Preset/Profile Pattern** ⭐ RECOMMENDED

```python
from feedspine import FeedSpine
from feedspine.presets import sec_filings  # Domain-specific preset

# One-liner for common use case
spine = FeedSpine.from_preset(sec_filings, data_dir="./sec_data")

# Or customize
spine = FeedSpine.from_preset(
    sec_filings,
    data_dir="./sec_data",
    forms=["10-K", "10-Q"],
    enrichers=["submission", "financial"],  # String names for ease
)

result = await spine.collect()
```

**Pros**: Simple defaults, customize when needed, domain-aware
**Cons**: Requires maintaining presets

---

### Alternative E: **Fluent Method Chaining (not builder)**

```python
from feedspine import FeedSpine

spine = (
    FeedSpine(storage=DuckDBStorage("./data.db"))
    .add_feed(SecRssFeedAdapter(form_types=["10-K"]))
    .add_feed(SecDailyIndexAdapter(days=30))
    .add_enricher(SECSubmissionEnricher())
    .add_enricher(SECFinancialEnricher())
)

# Spine is immediately usable, no .build() needed
result = await spine.collect()
```

**Pros**: Readable, returns working instance immediately
**Cons**: Mutable state

---

## What's Missing from FeedSpine

### 1. **Typed Content Schemas** 🔴 CRITICAL

FeedSpine needs a way to define typed content schemas per domain.

**Proposed Solution**:
```python
from feedspine import FeedSpine, ContentSchema
from pydantic import BaseModel

class SECFilingContent(BaseModel):
    """Typed content for SEC filings."""
    accession_number: str
    form_type: str
    company_name: str
    cik: str
    filed_date: date
    
    class Config:
        extra = "allow"  # Allow additional fields

# FeedSpine validates content against schema
spine = FeedSpine(
    storage=storage,
    content_schema=SECFilingContent,  # Validates on store
)

# Now record.content is typed
record = await storage.get(record_id)
record.content.form_type  # IDE knows this is str
record.content.filed_date  # IDE knows this is date
```

---

### 2. **Domain Query Methods** 🔴 CRITICAL

FeedSpine's generic `query(filters={...})` is too low-level.

**Proposed Solution**: Query builder or domain-specific extension point.

```python
# Option A: Query builder
records = await storage.query_builder()
    .where(form_type="10-K")
    .where(filed_date__gte=date(2024, 1, 1))
    .order_by("-filed_date")
    .limit(100)
    .execute()

# Option B: Domain extension
class SECStorage(DuckDBStorage):
    async def get_filings_by_company(self, ticker: str, forms: list[str]) -> list[Record]:
        ...
    
    async def get_filings_by_date(self, start: date, end: date) -> list[Record]:
        ...

# Option C: Plugin system
storage.register_query_plugin("sec", SECQueryPlugin())
filings = await storage.sec.by_company("AAPL")
```

---

### 3. **Resource Pool / Shared HTTP Client** 🟡 IMPORTANT

Multiple adapters/enrichers creating their own HTTP clients is wasteful.

**Proposed Solution**:
```python
from feedspine import FeedSpine, ResourcePool

pool = ResourcePool(
    http_client=httpx.AsyncClient(timeout=30),
    rate_limiter=RateLimiter(requests_per_second=10),
)

spine = FeedSpine(storage=storage, resources=pool)

# Adapters/enrichers access shared resources
class MyAdapter(FeedAdapter):
    async def fetch(self):
        client = self.resources.http_client  # Shared
        await self.resources.rate_limiter.acquire()
        ...
```

---

### 4. **Batch Enrichment API** 🟡 IMPORTANT

Current enricher protocol is single-record:

```python
class Enricher(Protocol):
    async def enrich(self, record: Record) -> EnrichmentResult: ...
```

**Proposed Addition**:
```python
class BatchEnricher(Protocol):
    async def enrich_batch(self, records: list[Record]) -> list[EnrichmentResult]: ...
    
    @property
    def batch_size(self) -> int:
        return 100  # Process 100 at a time
```

---

### 5. **Record-to-Domain Converter Registry** 🟡 IMPORTANT

py-sec-edgar has `_record_to_filing()` duplicated everywhere.

**Proposed Solution**:
```python
from feedspine import FeedSpine, record_converter

@record_converter("sec_filing")
def record_to_filing(record: Record) -> Filing:
    return Filing(
        accession_number=record.content["accession_number"],
        ...
    )

# Usage
filing = spine.convert(record, to="sec_filing")
# Or: filing = record.as_("sec_filing")
```

---

### 6. **First-Class Checkpoint/Resume** 🟡 IMPORTANT

py-sec-edgar implements its own checkpoint system. Should be in FeedSpine.

**Current** (py-sec-edgar):
```python
from py_sec_edgar.services.checkpoint import CheckpointManager
checkpoint = CheckpointManager(...)
```

**Proposed** (in FeedSpine):
```python
spine = FeedSpine(
    storage=storage,
    checkpoint=True,  # Auto-checkpoint on collect
)

# Resume from checkpoint
result = await spine.collect(resume=True)

# Or explicit
checkpoint = await spine.create_checkpoint()
# ... later ...
result = await spine.collect(from_checkpoint=checkpoint)
```

---

### 7. **Pipeline Visualization** 🟢 NICE TO HAVE

No way to see the registered feeds/enrichers and their order.

**Proposed**:
```python
print(spine.describe())
# Output:
# FeedSpine Pipeline
# ==================
# Storage: DuckDBStorage(./data.db)
# 
# Feeds:
#   1. sec.rss (SecRssFeedAdapter) - form_types: ['10-K']
#   2. sec.daily (SecDailyIndexAdapter) - days: 30
#
# Enrichers:
#   1. SECSubmissionEnricher - BRONZE → SILVER
#   2. SECFinancialEnricher - SILVER → GOLD
```

---

### 8. **Built-in Metrics/Observability** 🟢 NICE TO HAVE

No metrics collection out of the box.

**Proposed**:
```python
from feedspine import FeedSpine
from feedspine.metrics import PrometheusExporter

spine = FeedSpine(
    storage=storage,
    metrics=PrometheusExporter(port=9090),
)

# Auto-exposed metrics:
# feedspine_records_collected_total{feed="sec.rss"}
# feedspine_enrichment_duration_seconds{enricher="submission"}
# feedspine_storage_query_duration_seconds{operation="query"}
```

---

### 9. **Conditional Enrichment** 🟢 NICE TO HAVE

Enrichers currently check eligibility inside `enrich()`. Should be declarative.

**Current**:
```python
class SECFinancialEnricher:
    async def enrich(self, record):
        # Check inside method
        if record.layer != Layer.SILVER:
            return EnrichmentResult(status=SKIPPED)
        if record.content.get("form_type") not in ["10-K", "10-Q"]:
            return EnrichmentResult(status=SKIPPED)
        ...
```

**Proposed**:
```python
@enricher(
    requires_layer=Layer.SILVER,
    requires_content={"form_type": ["10-K", "10-Q"]},
    produces_layer=Layer.GOLD,
)
class SECFinancialEnricher:
    async def enrich(self, record):
        # Only called if conditions met
        ...
```

---

### 10. **Event Hooks** 🟢 NICE TO HAVE

No way to hook into lifecycle events.

**Proposed**:
```python
spine = FeedSpine(storage=storage)

@spine.on("record_stored")
async def notify_on_new_filing(record: Record):
    if record.content.get("form_type") == "8-K":
        await send_alert(record)

@spine.on("enrichment_complete")
async def log_enrichment(record: Record, result: EnrichmentResult):
    logger.info(f"Enriched {record.natural_key}: {result.status}")

@spine.on("collection_complete")
async def summarize(result: CollectionResult):
    print(f"Collected {result.total_new} new records")
```

---

## Recommended FeedSpine Improvements Priority

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| 🔴 P0 | Typed Content Schemas | Medium | High - Eliminates #1 pain point |
| 🔴 P0 | Domain Query Builder | Medium | High - Eliminates #5 pain point |
| 🟡 P1 | Resource Pool | Low | Medium - Cleaner resource management |
| 🟡 P1 | Batch Enrichment | Low | Medium - Performance improvement |
| 🟡 P1 | Record Converter Registry | Low | Medium - DRY improvement |
| 🟡 P1 | Built-in Checkpoint | Medium | Medium - Common need |
| 🟢 P2 | Pipeline Visualization | Low | Low - DX improvement |
| 🟢 P2 | Conditional Enrichment Decorators | Low | Low - Cleaner code |
| 🟢 P2 | Event Hooks | Medium | Low - Extensibility |
| 🟢 P2 | Metrics/Observability | Medium | Low - Production readiness |

---

## Discussion Questions

1. **Typed Content**: Should schemas be Pydantic, dataclass, or TypedDict?
2. **Query Builder**: SQL-like DSL or method chaining?
3. **Presets**: Should FeedSpine ship with domain presets (SEC, RSS, etc.) or leave to extensions?
4. **Breaking Changes**: What version bump for typed content? (Likely 1.0)
5. **Backward Compat**: How to support both typed and untyped content?
