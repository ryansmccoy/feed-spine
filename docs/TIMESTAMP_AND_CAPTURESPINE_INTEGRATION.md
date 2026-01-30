# Timestamp Semantics & CaptureSpine Integration Analysis

## Executive Summary

This document answers two questions:
1. **Are there more timestamps we should consider?** Yes - there are at least 12 distinct temporal concepts
2. **What would FeedSpine need to absorb CaptureSpine's workload?** A significant feature set spanning 8 major categories

---

## Part 1: The Complete Timestamp Taxonomy

### Current Three-Timestamp Model (EntitySpine/FeedSpine)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CURRENT MODEL (EntitySpine)                       │
├─────────────────────────────────────────────────────────────────────┤
│  period      │ What time the measurement covers (FY2024Q3)          │
│  as_of       │ When the value was known to the market               │
│  captured_at │ When we ingested it into our system                  │
└─────────────────────────────────────────────────────────────────────┘
```

### CaptureSpine's Additional Timestamps

CaptureSpine adds several more temporal concepts:

```
┌─────────────────────────────────────────────────────────────────────┐
│                  CAPTURESPINE TEMPORAL MODEL                         │
├─────────────────────────────────────────────────────────────────────┤
│  fetched_at     │ When we performed the HTTP request                │
│  published_at   │ When the source says it was published (RSS date)  │
│  first_seen_at  │ When we FIRST observed this unique record         │
│  last_seen_at   │ Most recent time we saw this record               │
│  event_time     │ When the underlying event occurred                │
│  seen_at        │ Each individual sighting timestamp                │
└─────────────────────────────────────────────────────────────────────┘
```

### The Complete Taxonomy: 12 Timestamps You Actually Need

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class CompleteTemporalModel:
    """All the timestamps that matter for financial data."""
    
    # ═══════════════════════════════════════════════════════════════
    # CATEGORY 1: MEASUREMENT TIME (What period does this measure?)
    # ═══════════════════════════════════════════════════════════════
    
    period_start: datetime
    """Start of measurement period (e.g., 2024-01-01 for Q1)"""
    
    period_end: datetime
    """End of measurement period (e.g., 2024-03-31 for Q1)"""
    
    # ═══════════════════════════════════════════════════════════════
    # CATEGORY 2: KNOWLEDGE TIME (When did we/market learn this?)
    # ═══════════════════════════════════════════════════════════════
    
    event_time: Optional[datetime] = None
    """When the actual event occurred (dividend declared, merger announced)"""
    
    announced_at: Optional[datetime] = None
    """When publicly announced (press release, 8-K timestamp)"""
    
    published_at: Optional[datetime] = None
    """When the source document was published (RSS pubDate, SEC acceptance)"""
    
    as_of: datetime = None
    """Effective knowledge time - when you could have known this.
    Usually = max(announced_at, published_at) but can differ."""
    
    # ═══════════════════════════════════════════════════════════════
    # CATEGORY 3: INGESTION TIME (When did our system capture this?)
    # ═══════════════════════════════════════════════════════════════
    
    fetched_at: datetime = None
    """When we made the HTTP request to retrieve the data"""
    
    first_seen_at: datetime = None
    """When we FIRST observed this unique record (critical for PIT)"""
    
    last_seen_at: datetime = None
    """Most recent observation (useful for freshness/staleness)"""
    
    captured_at: datetime = None
    """When the record was persisted to our database"""
    
    # ═══════════════════════════════════════════════════════════════
    # CATEGORY 4: EFFECTIVITY TIME (When does this apply?)
    # ═══════════════════════════════════════════════════════════════
    
    effective_date: Optional[datetime] = None
    """When the value becomes effective (split effective date)"""
    
    record_date: Optional[datetime] = None
    """Date of record (who's entitled to dividend)"""
    
    ex_date: Optional[datetime] = None
    """Ex-dividend/ex-rights date"""
    
    payment_date: Optional[datetime] = None
    """When cash/shares actually distributed"""
```

### Why Each Category Matters

#### Category 1: Measurement Time
**Used for:** Aligning data across vendors, joining financials to prices

```python
# Problem: Bloomberg calls it "Q1 2024", FactSet calls it "FY2024 Q1"
# Solution: Normalize to period_start/period_end

# Apple fiscal Q1 2024 = calendar Q4 2023
period_start = date(2023, 10, 1)
period_end = date(2023, 12, 31)

# Now we can join Apple financials to daily prices unambiguously
```

#### Category 2: Knowledge Time
**Used for:** Point-in-time queries, backtesting, lookahead bias prevention

```python
# A company reports earnings after market close on Feb 1
event_time = datetime(2024, 2, 1, 17, 0, 0)  # 5 PM ET

# The SEC filing is accepted at 5:30 PM
published_at = datetime(2024, 2, 1, 17, 30, 0)

# Your backtest on Feb 1 during market hours CANNOT use this data
# as_of = published_at = 5:30 PM Feb 1
```

#### Category 3: Ingestion Time
**Used for:** Debugging, audit trails, reprocessing decisions

```python
# Scenario: Feed was down for 2 hours, then caught up
fetched_at = datetime(2024, 2, 1, 20, 0, 0)  # 8 PM (2 hrs late)
first_seen_at = datetime(2024, 2, 1, 20, 0, 0)  # Same as fetched

# But the data was actually available at 5:30 PM
published_at = datetime(2024, 2, 1, 17, 30, 0)

# For backtesting, use published_at (when market could know)
# For operations, use fetched_at (when YOUR system knew)
```

#### Category 4: Effectivity Time
**Used for:** Corporate actions, dividend calculations, index rebalancing

```python
# Apple announces 4:1 stock split
announced_at = date(2020, 7, 30)     # When announced
effective_date = date(2020, 8, 31)   # When split happens
record_date = date(2020, 8, 24)      # Who gets new shares

# Your portfolio system needs ALL THREE:
# - announced_at: When to update your models
# - record_date: Who's entitled to action
# - effective_date: When to adjust share counts
```

### Timestamp Decision Matrix

| Use Case | Primary Timestamp | Secondary | Notes |
|----------|------------------|-----------|-------|
| Backtesting | `as_of` / `published_at` | `first_seen_at` | Prevents lookahead bias |
| Live trading | `fetched_at` | `published_at` | Use freshest available |
| Audit trail | `captured_at` | `first_seen_at` | Prove what you knew when |
| Data quality | `last_seen_at` | `fetched_at` | Detect stale feeds |
| Corporate actions | `effective_date` | `record_date` | Adjust positions correctly |
| Reprocessing | `first_seen_at` | `fetched_at` | Don't double-count |

---

## Part 2: CaptureSpine Feature Analysis

### What CaptureSpine Does

CaptureSpine is a **full-featured feed capture and management system** with:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CAPTURESPINE ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│  │  FEEDS   │──▶│  FETCH   │──▶│  PARSE   │──▶│  ENRICH  │         │
│  │ (config) │   │ (HTTP)   │   │ (extract)│   │ (enhance)│         │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘         │
│       │                                             │                │
│       │         ┌──────────────────────────────────┘                │
│       │         │                                                    │
│       ▼         ▼                                                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│  │  TASKS   │   │ LAKEHOUSE│   │  REPLAY  │   │  SEARCH  │         │
│  │ (queue)  │   │ (storage)│   │ (PIT)    │   │ (index)  │         │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘         │
│       │              │              │              │                 │
│       └──────────────┴──────────────┴──────────────┘                 │
│                           │                                          │
│                           ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              FEATURES (35+ modules)                            │   │
│  │  alerts, auth, backup, batch_ingestion, discovery, jobs,     │   │
│  │  llm_transform, queue, reader, subscriptions, sync, tags...  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Feature Categories FeedSpine Would Need

#### 1. Feed Management & Scheduling (CRITICAL)

**Current CaptureSpine:**
```python
# From capture-spine/app/features/feeds/models.py
class FeedCreate(BaseModel):
    name: str
    base_url: str
    region: str | None = None
    schedule_cron: str | None = None  # "*/5 * * * *"
    enabled: bool = True
    poll_interval_seconds: int = 300
    market_hours_only: bool = False
    adaptive_polling: bool = True
```

**FeedSpine Gap:**
- ❌ No cron-based scheduling
- ❌ No adaptive polling (speed up when active, slow down overnight)
- ❌ No market hours awareness
- ✅ Has feed configuration

**Integration Effort:** Medium - Need scheduler with cron support

---

#### 2. Task Queue & Distributed Workers (CRITICAL)

**Current CaptureSpine:**
```python
# From capture-spine/app/features/tasks/models.py
class ClaimedFeed(BaseModel):
    """A feed claimed by a worker for polling."""
    feed_id: UUID
    feed_name: str
    worker_id: str
    claimed_at: datetime
    poll_interval_seconds: int
    next_poll_at: datetime | None

class FeedTaskStats(BaseModel):
    """Statistics about feed task queue."""
    total_feeds: int
    enabled_feeds: int
    active_workers: int
    claimed_feeds: int
    overdue_feeds: int
    feeds_with_errors: int
```

**FeedSpine Gap:**
- ❌ No distributed task queue
- ❌ No worker coordination
- ❌ No failure tracking
- ❌ No backpressure management

**Integration Effort:** High - Need Redis/PostgreSQL-based queue

---

#### 3. Point-in-Time Replay Service (CRITICAL)

**Current CaptureSpine:**
```python
# From capture-spine/app/features/replay/service.py
class ReplayService:
    async def as_of_items(self, as_of: datetime, feed_id: UUID = None):
        """Get items as they existed at a point in time."""
        
    async def as_of_records(self, as_of: datetime, record_type: str = None):
        """Get parsed records as of a timestamp."""
        
    async def cursor(self, start: datetime, end: datetime = None):
        """Create a replay cursor for iterating through time."""
        
    async def changes_since(self, since: datetime, until: datetime = None):
        """Get all changes between two timestamps."""
```

**FeedSpine Gap:**
- ✅ Has `query_pit()` and `query_pit_batch()` (added recently)
- ❌ No cursor-based iteration
- ❌ No `changes_since()` for incremental sync
- ❌ No feed-level PIT (only observation-level)

**Integration Effort:** Medium - Extend existing PIT implementation

---

#### 4. Medallion Architecture (Lakehouse) (IMPORTANT)

**Current CaptureSpine:**
```python
# From capture-spine/app/pipelines/lakehouse/layers.py
class BronzeRecord(BaseModel):
    """Raw ingested data - byte-perfect preservation."""
    item_id: UUID
    raw_content: bytes
    content_type: str
    fetched_at: datetime
    source_url: str

class SilverRecord(BaseModel):
    """Parsed/structured data."""
    record_id: UUID
    record_type: str
    parsed_fields: dict[str, Any]
    parse_version: str
    parsed_at: datetime

class GoldDocument(BaseModel):
    """Enriched, ready-to-use data."""
    document_id: UUID
    enrichments: dict[str, Any]
    enrichment_version: str
    enriched_at: datetime
    search_vector: str  # For full-text search
```

**FeedSpine Gap:**
- ✅ Has raw/parsed/canonical concept
- ❌ No explicit Bronze/Silver/Gold layers
- ❌ No content blob storage (for raw bytes)
- ❌ No versioned enrichments

**Integration Effort:** Medium - Add layer abstraction

---

#### 5. Enrichment Versioning (IMPORTANT)

**Current CaptureSpine:**
```python
# From capture-spine/app/pipelines/lakehouse/versioning.py
class EnrichmentVersion(BaseModel):
    """Track what version of enrichment a document has."""
    document_id: UUID
    enrichment_type: str  # "llm_summary", "entity_extraction"
    version: str         # "gpt4-v2.1", "spacy-3.5"
    enriched_at: datetime
    coverage_pct: float  # 0.0-1.0

# Enables: "Re-enrich all docs using old model version"
```

**FeedSpine Gap:**
- ❌ No enrichment version tracking
- ❌ No selective re-enrichment
- ❌ No coverage tracking

**Integration Effort:** Low-Medium - Add version metadata

---

#### 6. Sighting Lineage (IMPORTANT)

**Current CaptureSpine:**
```python
# From capture-spine/app/db/repos/sightings.py
class SightingsRepository:
    """Track when records were seen from which items.
    Critical for as-of replay queries."""
    
    async def insert(self, record_id, item_id, feed_id, seen_at):
        """Record that we saw this record at this time."""
    
    # Unique constraint: (record_id, feed_id, seen_at)
    # Allows: "Show me all the times we saw AAPL 10-K"
```

**FeedSpine Gap:**
- ❌ No lineage tracking (item → record → observation)
- ❌ No "when did we see this" history

**Integration Effort:** Medium - Add sighting table

---

#### 7. User Features (NICE-TO-HAVE)

**Current CaptureSpine:**
- User authentication & authorization
- Feed subscriptions per user
- User-specific alerts
- Personal discovery catalogs

**FeedSpine Gap:**
- ❌ All of the above (by design - FeedSpine is a library)

**Integration Effort:** N/A - Keep in application layer

---

#### 8. Operational Features (NICE-TO-HAVE)

**Current CaptureSpine:**
```python
# Alerts
class AlertType(str, Enum):
    FEED_OFFLINE = "feed_offline"
    FEED_RECOVERED = "feed_recovered"
    FEED_RATE_LIMITED = "feed_rate_limited"
    IMPORT_COMPLETED = "import_completed"

# Sync
class SyncExportResult(BaseModel):
    export_type: str
    file_path: str
    content_hash: str

# Backup
class BackupResult(BaseModel):
    backup_id: UUID
    s3_path: str
    size_bytes: int
```

**FeedSpine Gap:**
- ❌ Alert system
- ❌ Config sync/export
- ❌ Backup management

**Integration Effort:** Low - These can stay in application layer

---

### Integration Roadmap

#### Phase 1: Core Data Pipeline (Must Have)

| Feature | Effort | Priority |
|---------|--------|----------|
| Cron-based scheduling | Medium | P0 |
| Task queue basics | Medium | P0 |
| PIT cursor iteration | Low | P0 |
| `changes_since()` | Low | P0 |

#### Phase 2: Reliability & Scale (Should Have)

| Feature | Effort | Priority |
|---------|--------|----------|
| Distributed worker coordination | High | P1 |
| Failure tracking & retry | Medium | P1 |
| Sighting lineage | Medium | P1 |
| Enrichment versioning | Low | P1 |

#### Phase 3: Full Feature Parity (Could Have)

| Feature | Effort | Priority |
|---------|--------|----------|
| Medallion layer abstraction | Medium | P2 |
| Content blob storage | Medium | P2 |
| Adaptive polling | Medium | P2 |
| Feed discovery catalog | Low | P2 |

---

## Part 3: Recommended FeedSpine Enhancements

### 3.1 Enhanced Timestamp Support

```python
# feedspine/src/feedspine/domain/temporal.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class TemporalContext:
    """Complete temporal context for a data point."""
    
    # Measurement (what period)
    period_start: datetime
    period_end: datetime
    
    # Knowledge (when known)
    event_time: Optional[datetime] = None
    announced_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    as_of: Optional[datetime] = None  # Derived: max(announced, published)
    
    # Ingestion (when captured)
    fetched_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    
    # Effectivity (when applies)
    effective_date: Optional[datetime] = None
    record_date: Optional[datetime] = None
    ex_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    
    def knowledge_time(self) -> datetime:
        """When this was knowable to the market."""
        return self.as_of or self.published_at or self.announced_at or self.captured_at
    
    def ingestion_time(self) -> datetime:
        """When our system learned this."""
        return self.captured_at or self.first_seen_at or self.fetched_at
```

### 3.2 Replay Cursor

```python
# feedspine/src/feedspine/replay/cursor.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator, AsyncIterator

@dataclass
class ReplayCursor:
    """Iterate through time for backtesting."""
    
    start: datetime
    end: datetime
    step: timedelta = timedelta(days=1)
    
    def __iter__(self) -> Iterator[datetime]:
        current = self.start
        while current <= self.end:
            yield current
            current += self.step
    
    async def changes_since(
        self,
        storage: ObservationStorage,
        entity_ids: list[str] = None,
    ) -> AsyncIterator[Observation]:
        """Stream all changes between start and end."""
        # Implementation uses first_seen_at for filtering
        pass
```

### 3.3 Feed Scheduler

```python
# feedspine/src/feedspine/scheduling/scheduler.py

from dataclasses import dataclass
from datetime import datetime
from croniter import croniter

@dataclass
class FeedSchedule:
    """Schedule for when to poll a feed."""
    
    feed_id: str
    cron_expression: str  # "*/5 * * * *" = every 5 minutes
    market_hours_only: bool = False
    adaptive: bool = True
    min_interval_seconds: int = 60
    max_interval_seconds: int = 14400  # 4 hours
    
    def next_run(self, after: datetime = None) -> datetime:
        """Calculate next scheduled run time."""
        after = after or datetime.utcnow()
        cron = croniter(self.cron_expression, after)
        next_time = cron.get_next(datetime)
        
        if self.market_hours_only:
            next_time = self._adjust_for_market_hours(next_time)
        
        return next_time
```

---

## Summary: What FeedSpine Needs

### Already Has ✅
- Basic feed configuration
- Multi-vendor observation storage
- PIT queries (`query_pit`, `query_pit_batch`)
- Three-timestamp model (period, as_of, captured_at)
- PostgreSQL optimization

### Needs to Add 🔨

| Feature | Why |
|---------|-----|
| **More timestamps** | `first_seen_at`, `fetched_at`, `effective_date` for full coverage |
| **Cron scheduling** | Automated feed polling |
| **Task queue** | Reliable, distributed processing |
| **Replay cursor** | Efficient backtesting iteration |
| **Changes streaming** | Incremental sync support |
| **Sighting lineage** | Track data provenance |
| **Enrichment versioning** | Re-process with new models |

### Can Skip (Keep in App Layer) ❌
- User authentication
- Subscriptions/notifications
- UI/CLI features
- Backup management

---

## Conclusion

The three-timestamp model in EntitySpine/FeedSpine is a good start, but real-world financial data needs **12 distinct temporal concepts** across four categories:

1. **Measurement** - What period does this cover?
2. **Knowledge** - When could you have known this?
3. **Ingestion** - When did your system capture this?
4. **Effectivity** - When does this apply?

For FeedSpine to absorb CaptureSpine's workload, the priority should be:
1. **P0:** Scheduling, task queue, replay cursor
2. **P1:** Sighting lineage, enrichment versioning
3. **P2:** Medallion layers, adaptive polling

The user-facing features (auth, subscriptions, alerts) should stay in the application layer, not in FeedSpine as a library.
