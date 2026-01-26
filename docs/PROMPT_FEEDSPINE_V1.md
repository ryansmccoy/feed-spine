# FeedSpine - Enhancement & Integration Prompt (v1.1)

**For: Claude Opus 4.5 (Extended Thinking Mode)**

---

## 🚀 DO THIS FIRST (Before Any Changes)

### Step 1: Understand the Existing Codebase (20 min)

```
EXPLORE IN THIS ORDER:
1. feedspine/src/feedspine/__init__.py      → Package exports
2. feedspine/src/feedspine/models/          → Existing domain models
3. feedspine/src/feedspine/protocols/       → Existing protocols
4. feedspine/src/feedspine/storage/         → Storage backends
5. feedspine/src/feedspine/adapter/         → Feed adapters
```

### Step 2: Read Design Documents (10 min)

```
REQUIRED READING:
1. feedspine/GUARDRAILS.md                    → Non-negotiable standards
2. feedspine/docs/design/framework-design.md  → Architecture decisions
3. feedspine/docs/design/ARCHITECTURE_PATTERNS.md → Patterns in use
```

### Step 3: Run Existing Tests

```bash
cd feedspine
pytest tests/ -v --tb=short
```

**Understand what works before changing anything.**

### Step 4: Identify Enhancement Targets

After reading the code, identify:
- [ ] Which models need updating for EntitySpine alignment?
- [ ] Which protocols need the new warnings/limits pattern?
- [ ] What tests need to be added for new capabilities?

---

## ⚠️ CRITICAL: This is an EXISTING Package

FeedSpine is a **fully developed** package with:
- Working storage backends (DuckDB, Memory)
- Feed adapters (RSS, JSON, etc.)
- Deduplication logic
- Async throughout

**Your job**: Enhance and integrate, NOT rewrite.

---

## ⚠️ CRITICAL: Read These First

### Development Standards

| Order | Document | Location | Why |
|-------|----------|----------|-----|
| **1** | GUARDRAILS.md | `feedspine/GUARDRAILS.md` | Non-negotiable code standards |
| **2** | manifesto.md | `feedspine/docs/design/manifesto.md` | Design philosophy |
| **3** | .cursorrules | `feedspine/.cursorrules` | AI coding patterns |

### Design Documents

| Order | Document | Key Focus |
|-------|----------|-----------|
| **4** | `framework-design.md` | Core architecture |
| **5** | `ARCHITECTURE_PATTERNS.md` | Storage, adapters, protocols |
| **6** | `implementation-roadmap.md` | Development phases |
| **7** | `PY_SEC_EDGAR_V4_READINESS.md` | py-sec-edgar integration |

All design docs are in `feedspine/docs/design/`.

---

## ⚡ EXISTING PACKAGE STRUCTURE

FeedSpine already has this structure - **understand it before changing**:

```
feedspine/src/feedspine/
├── __init__.py              # Exports
├── adapter/                 # Feed adapters (existing)
├── api/                     # API layer
├── blob/                    # Blob storage
├── cache/                   # Caching
├── cli.py                   # CLI interface
├── composition/             # DI/composition
├── core/                    # Core utilities
├── enricher/                # Data enrichment
├── executor/                # Task execution
├── http/                    # HTTP utilities
├── metrics/                 # Metrics collection
├── models/                  # Domain models ← CHECK THESE
├── notifier/                # Notifications
├── pipeline.py              # Main pipeline
├── protocols/               # Protocol definitions ← CHECK THESE
├── queue/                   # Queue management
├── reporter/                # Reporting
├── scheduler/               # Scheduling
├── search/                  # Search functionality
├── storage/                 # Storage backends ← CHECK THESE
└── utils/                   # Utilities
```

---

## ⚡ What FeedSpine Does

**FeedSpine** is a **storage-agnostic feed capture framework**. It answers:

> "Have I seen this record before?"

### Core Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Feed Ingestion** | Pull data from any source (RSS, JSON, files, APIs) |
| **Deduplication** | Identify duplicates via `natural_key` |
| **Sighting Tracking** | Track first_seen, last_seen for every record |
| **Layer Management** | Bronze → Silver → Gold medallion architecture |
| **Storage Agnostic** | Memory, DuckDB, PostgreSQL, or custom backends |

### What FeedSpine Does NOT Do

| NOT Owned | Who Owns It |
|-----------|-------------|
| Entity resolution ("Who is this CIK?") | **EntitySpine** |
| Filing downloads | **py-sec-edgar** |
| UI/CLI | **py-sec-edgar** |
| Domain semantics ("What does this data mean?") | Consumers |

---

## ⚡ ECOSYSTEM CONTEXT: Where FeedSpine Fits

FeedSpine is part of a **three-package ecosystem**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PY-SEC-EDGAR ECOSYSTEM                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           py-sec-edgar                               │   │
│  │                     (Main Application Layer)                         │   │
│  │  • CLI interface, filing workflows, SEC EDGAR API                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                    │                          │
│                              ▼                    ▼                          │
│  ┌──────────────────────────────────┐   ┌──────────────────────────────┐   │
│  │      FeedSpine ◀── YOU           │   │        EntitySpine           │   │
│  │       (Data Ingestion)           │   │     (Identity Resolution)    │   │
│  │  • Feed deduplication            │   │  • Ticker/CIK → Entity       │   │
│  │  • Sighting tracking             │   │  • Claims with provenance    │   │
│  │  • Bronze/Silver/Gold layers     │   │  • Merge/rename history      │   │
│  └──────────────────────────────────┘   └──────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### FeedSpine's Role in the Ecosystem

| User Action | py-sec-edgar | FeedSpine | EntitySpine |
|-------------|--------------|-----------|-------------|
| `sec-edgar monitor` | Start monitor | **Track new filings, dedup** | — |
| `sec-edgar refresh-symbology` | Trigger refresh | **Fetch SEC/GLEIF feeds** | Store identifiers |
| Download filings | Download orchestration | **Track what's downloaded** | — |
| Detect new filings | — | **Sighting.is_new = True** | — |

### Integration Points

1. **py-sec-edgar** uses FeedSpine for feed monitoring:
   ```python
   # py-sec-edgar registers SEC feeds with FeedSpine
   spine = FeedSpine(storage=DuckDBStorage("feeds.db"))
   spine.register_feed("sec-rss", SecRssFeedAdapter())
   
   # Collect new filings
   result = await spine.collect("sec-rss")
   for sighting in result.sightings:
       if sighting.is_new:
           # New filing! Download it
           download_filing(sighting.natural_key)
   ```

2. **EntitySpine** (optional) can consume FeedSpine symbology data:
   ```python
   # FeedSpine collects symbology
   spine.register_feed("sec-tickers", SecTickersFeed())
   await spine.collect("sec-tickers")
   
   # EntitySpine processes deduplicated records
   for record in spine.query(source="sec-tickers", layer=Layer.SILVER):
       entity_store.store_claim(record_to_claim(record))
   ```

See `entityspine/docs/design/09_FEEDSPINE_INTEGRATION_ANALYSIS.md` for full ecosystem documentation.

---

## ⚡ CORE DATA MODEL

### RecordCandidate (Input)

```python
@dataclass
class RecordCandidate:
    """Raw record from a feed, awaiting storage decision."""
    
    natural_key: str       # Unique ID within this feed (e.g., "0000320193-24-000082")
    published_at: datetime
    content: dict[str, Any]  # Arbitrary payload
    metadata: Metadata     # Source, tags, etc.
    
    # natural_key is normalized: lowercase, stripped
    # Used for exact-match deduplication
```

### Record (Stored)

```python
@dataclass  
class Record:
    """Persisted record with full tracking."""
    
    record_id: str         # ULID
    natural_key: str       # Normalized
    layer: Layer           # BRONZE | SILVER | GOLD
    published_at: datetime
    captured_at: datetime  # When first ingested
    content: dict[str, Any]
    metadata: Metadata
    raw_data_hash: str     # Content fingerprint
```

### Sighting (Observation Tracking)

```python
@dataclass
class Sighting:
    """Tracks when a record was observed."""
    
    natural_key: str
    source: str            # Feed name
    seen_at: datetime
    is_new: bool           # First time seeing this key?
    record_id: str | None  # Link to stored record
    raw_data_hash: str     # For change detection
```

### Layer (Medallion Architecture)

```python
class Layer(Enum):
    BRONZE = "bronze"  # Raw, untouched
    SILVER = "silver"  # Normalized, deduplicated  
    GOLD = "gold"      # Enriched
```

---

## ⚡ CORE PROTOCOLS

### FeedAdapter Protocol

```python
class FeedAdapter(Protocol):
    """Adapts external data sources to FeedSpine records."""
    
    @property
    def name(self) -> str:
        """Unique feed identifier."""
        ...
    
    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        """Yield records from the source."""
        ...
```

### StorageProtocol

```python
class StorageProtocol(Protocol):
    """Storage backend interface."""
    
    async def initialize(self) -> None: ...
    async def close(self) -> None: ...
    
    async def store(self, record: Record) -> None: ...
    async def get(self, record_id: str) -> Record | None: ...
    async def get_by_natural_key(self, key: str) -> Record | None: ...
    
    async def record_sighting(self, sighting: Sighting) -> None: ...
    async def get_sightings(self, natural_key: str) -> list[Sighting]: ...
```

---

## ⚡ DEDUPLICATION LOGIC

FeedSpine's core value: **Only process each record once**.

### How Deduplication Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       DEDUPLICATION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Feed yields RecordCandidate                                            │
│  ─────────────────────────────                                          │
│          │                                                               │
│          ▼                                                               │
│  ┌─────────────────────────────────────┐                                │
│  │ Normalize natural_key               │                                │
│  │ (lowercase, strip, hash content)    │                                │
│  └─────────────────────────────────────┘                                │
│          │                                                               │
│          ▼                                                               │
│  ┌─────────────────────────────────────┐                                │
│  │ Check storage for natural_key       │                                │
│  └─────────────────────────────────────┘                                │
│          │                                                               │
│          ├──────────────────────────────────────┐                       │
│          │                                      │                       │
│          ▼                                      ▼                       │
│  ┌───────────────────┐              ┌───────────────────┐              │
│  │ NOT FOUND         │              │ FOUND             │              │
│  │ ─────────         │              │ ─────             │              │
│  │ Create Record     │              │ Record Sighting   │              │
│  │ sighting.is_new=T │              │ sighting.is_new=F │              │
│  └───────────────────┘              └───────────────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### natural_key Examples

| Feed | natural_key Format | Example |
|------|-------------------|---------|
| SEC RSS | Accession number | `0000320193-24-000082` |
| SEC Tickers | `cik:{cik}` | `cik:0000320193` |
| GLEIF | LEI | `HWUPKR0MPOU8FGXBT394` |
| Press Release | `{source}:{id}` | `businesswire:20240115001234` |

### Content Hash for Change Detection

Even if `natural_key` matches, content might have changed:

```python
def compute_content_hash(content: dict) -> str:
    """Hash content for change detection."""
    serialized = json.dumps(content, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]
```

---

## ⚡ MEDALLION LAYERS

### When to Use Each Layer

| Layer | Store When | Query When |
|-------|------------|------------|
| **BRONZE** | Raw data arrives | Audit trail, debugging |
| **SILVER** | After normalization | Normal queries |
| **GOLD** | After enrichment | Analytics, ML features |

### Layer Promotion

```python
# Promote from Bronze to Silver
async def promote_to_silver(
    spine: FeedSpine,
    record: Record,
    normalizer: Normalizer
) -> Record:
    """Normalize and deduplicate."""
    normalized_content = normalizer.normalize(record.content)
    
    return Record(
        record_id=record.record_id,
        natural_key=record.natural_key,
        layer=Layer.SILVER,
        content=normalized_content,
        ...
    )
```

---

## ⚡ CRITICAL: Async Everywhere

FeedSpine is **fully async**. All protocol methods are async.

```python
# ✅ CORRECT
async def store(self, record: Record) -> None:
    await self._db.insert(record)

# ❌ WRONG - Sync in async codebase
def store(self, record: Record) -> None:
    self._db.insert(record)
```

---

## ⚡ CRITICAL: Type Annotations

**Every function MUST have complete type annotations.**

```python
# ✅ CORRECT
async def query(
    self,
    source: str | None = None,
    layer: Layer | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[Record]:
    ...

# ❌ WRONG - Missing types
async def query(self, source=None, layer=None, since=None, limit=100):
    ...
```

**Enforcement:** `mypy --strict`

---

## ⚡ KNOWN PAIN POINTS (Address These)

From `FEEDSPINE_INTEGRATION_ANALYSIS.md`:

| Pain Point | Problem | Solution |
|------------|---------|----------|
| **Untyped content** | `record.content: dict[str, Any]` lacks safety | Use `TypedRecord` and `ContentSchema` |
| **Multiple orchestrators** | 3 classes doing same thing | Single `FeedSpine` class |
| **Storage created everywhere** | Inconsistent setup | Factory pattern or DI |
| **Layer promotion unused** | Records stay in Bronze | Clear promotion workflow |

---

## ⚡ TIMESTAMP CONVENTIONS

**Always use timezone-aware UTC.**

```python
from datetime import datetime, timezone

def utc_now() -> datetime:
    """Get current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)

# Store as ISO-8601 with Z suffix
def to_iso8601(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

**NEVER use:** `datetime.now()`, `datetime.utcnow()` (naive datetimes)

---

## ⚡ Storage Backend Patterns

### DuckDB (Default for persistence)

```python
from feedspine.storage.duckdb import DuckDBStorage

storage = DuckDBStorage("feeds.db")
await storage.initialize()

# Tables created:
# - records (record_id, natural_key, layer, content, ...)
# - sightings (id, natural_key, source, seen_at, is_new, ...)
```

### Memory (For testing)

```python
from feedspine.storage.memory import MemoryStorage

storage = MemoryStorage()
await storage.initialize()
```

---

## ⚡ Testing Requirements

### Enhancement Phases (Work with Existing Code)

### Phase 1: Audit Existing Code

**Tasks**:
1. Review `models/` - Do they match the design docs?
2. Review `protocols/` - Are they complete?
3. Review `storage/` - DuckDB/Memory implementations
4. Run existing tests - What's the coverage?

```bash
pytest tests/ --cov=feedspine --cov-report=term-missing
```

**🔴 CHECKPOINT 1: Document gaps**:
- List any missing protocol methods
- List any models that need updating
- List any tests that need to be added

---

### Phase 2: Align with Design Docs

**Tasks**:
1. Update models to match `framework-design.md`
2. Ensure protocols match `ARCHITECTURE_PATTERNS.md`
3. Add any missing timestamp UTC enforcement

**🔴 CHECKPOINT 2: Tests still pass**:
```bash
pytest tests/ -v
mypy feedspine/src/feedspine/ --strict
```

---

### Phase 3: EntitySpine Integration Prep

**Tasks**:
1. Review how FeedSpine will provide data to EntitySpine
2. Add any adapter methods needed for symbology feeds
3. Document the integration interface

**🔴 CHECKPOINT 3: Integration tests**:
```bash
pytest tests/integration/ -v
```

---

### Phase 4: py-sec-edgar Integration

**Tasks**:
1. Create SEC RSS adapter if not exists
2. Create SEC tickers adapter if not exists
3. Wire into py-sec-edgar's feed monitoring

**🔴 FINAL CHECKPOINT: Full test suite**:
```bash
pytest tests/ --cov=feedspine --cov-fail-under=80
```

---

### Test Directory Structure

```
tests/
├── conftest.py
├── unit/
│   ├── test_record.py
│   ├── test_sighting.py
│   ├── test_layer.py
│   └── test_dedup.py
├── adapters/
│   ├── test_rss_adapter.py
│   ├── test_json_adapter.py
│   └── test_storage_backends.py
└── integration/
    ├── test_full_collection.py
    ├── test_deduplication_flow.py
    └── test_layer_promotion.py
```

### Minimum Test Coverage: 80%

```bash
pytest --cov=feedspine --cov-fail-under=80
```

---

## ⚡ Common Mistakes to Avoid

### ❌ Sync in Async Codebase

```python
# WRONG
def fetch(self) -> list[Record]:
    return self._client.get()

# ✅ CORRECT
async def fetch(self) -> AsyncIterator[RecordCandidate]:
    async for item in self._client.get():
        yield item
```

### ❌ Missing natural_key Normalization

```python
# WRONG - Case-sensitive collision issues
natural_key = cik  # "320193" vs "0000320193"

# ✅ CORRECT - Normalize
natural_key = f"cik:{str(cik).zfill(10)}"  # "cik:0000320193"
```

### ❌ Ignoring Sighting for Duplicates

```python
# WRONG - Only store new records
if not await storage.get_by_natural_key(key):
    await storage.store(record)

# ✅ CORRECT - Always record sighting
existing = await storage.get_by_natural_key(key)
sighting = Sighting(
    natural_key=key,
    seen_at=utc_now(),
    is_new=(existing is None),
    record_id=existing.record_id if existing else new_record.record_id,
)
await storage.record_sighting(sighting)
```

---

## ⚡ EntitySpine v0.3.2 Integration (NEW)

FeedSpine can now integrate with EntitySpine v0.3.2's new **integration module** for seamless entity resolution.

### EntitySpine Integration Module

EntitySpine v0.3.2 provides:

```python
from entityspine.integration import (
    FilingFacts,           # Dataclass for filing metadata
    FilingEvidence,        # Filing provenance
    ingest_filing_facts,   # Bulk ingestion function
    IngestResult,          # Ingestion results with counts
)
from entityspine.integration.contracts import (
    ExtractedEntity,       # Entity extracted from filing
    ExtractedRelationship, # Relationship between entities
    ExtractedIdentifier,   # Identifier (LEI, CUSIP, etc.)
    ExtractedEvent,        # Business events
)
```

### FeedSpine → EntitySpine Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FEEDSPINE → ENTITYSPINE FLOW                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  FeedSpine collects SEC filings                                         │
│  ─────────────────────────────                                          │
│          │                                                               │
│          ▼                                                               │
│  ┌─────────────────────────────────────┐                                │
│  │ RecordCandidate                     │                                │
│  │   natural_key: "0001045810-24-029"  │                                │
│  │   content: { filing metadata }      │                                │
│  └─────────────────────────────────────┘                                │
│          │                                                               │
│          ▼                                                               │
│  ┌─────────────────────────────────────┐                                │
│  │ Transform to FilingFacts            │                                │
│  └─────────────────────────────────────┘                                │
│          │                                                               │
│          ▼                                                               │
│  ┌─────────────────────────────────────┐                                │
│  │ entityspine.ingest_filing_facts()   │                                │
│  │   Creates: Entities, Claims, Rels   │                                │
│  └─────────────────────────────────────┘                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Example: FeedSpine Record to EntitySpine

```python
from datetime import datetime
from feedspine.models import Record
from entityspine import SqliteStore
from entityspine.integration import (
    FilingFacts,
    FilingEvidence,
    ingest_filing_facts,
)

def record_to_filing_facts(record: Record) -> FilingFacts:
    """Convert FeedSpine Record to EntitySpine FilingFacts."""
    content = record.content
    
    return FilingFacts(
        evidence=FilingEvidence(
            accession_number=record.natural_key,
            form_type=content.get("form_type", ""),
            filed_date=datetime.fromisoformat(content.get("filed_date", "")),
            cik=content.get("cik", ""),
        ),
        registrant_name=content.get("company_name"),
        registrant_cik=content.get("cik"),
        registrant_ticker=content.get("ticker"),
        registrant_exchange=content.get("exchange"),
        registrant_sic=content.get("sic_code"),
    )

async def process_new_filings(
    spine: FeedSpine,
    entity_store: SqliteStore,
) -> None:
    """Process new filings through EntitySpine."""
    # Get new sightings from FeedSpine
    result = await spine.collect("sec-rss")
    
    for sighting in result.sightings:
        if sighting.is_new:
            record = await spine.storage.get(sighting.record_id)
            if record:
                # Transform to EntitySpine format
                facts = record_to_filing_facts(record)
                
                # Ingest into EntitySpine
                ingest_result = ingest_filing_facts(entity_store, facts)
                
                print(f"Created {ingest_result.entities_created} entities")
```

### EntitySpine Core Models (v0.3.2)

EntitySpine uses stdlib dataclasses (zero dependencies):

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Entity` | Legal identity | `primary_name`, `entity_type`, `jurisdiction` |
| `Security` | Tradeable instrument | `security_type`, `entity_id` |
| `Listing` | Exchange ticker | `ticker`, `exchange`, `security_id` |
| `IdentifierClaim` | Identifier with provenance | `scheme`, `value`, `confidence` |
| `Relationship` | Entity connections | `source_ref`, `target_ref`, `relationship_type` |

### EntitySpine Storage Tiers

| Tier | Backend | Dependencies | FeedSpine Integration |
|------|---------|--------------|----------------------|
| 0 | JSON | None | Testing only |
| 1 | SQLite | None | Development |
| 2 | DuckDB | `[duckdb]` | Matches FeedSpine |
| 3 | PostgreSQL | `[postgres]` | Production |

### Integration Best Practices

1. **Use FilingFacts contract**: Don't create entities directly - use the integration module
2. **Preserve provenance**: Always include `evidence_filing_id` on relationships
3. **Normalize identifiers**: Use `entityspine.integration.normalize` functions
4. **Handle duplicates**: EntitySpine will merge entities with matching CIK/identifiers

---

## Document Reference

| Document | Purpose |
|----------|---------|
| `GUARDRAILS.md` | Code standards (enforced) |
| `manifesto.md` | Design philosophy |
| `framework-design.md` | Core architecture |
| `ARCHITECTURE_PATTERNS.md` | Storage, adapters, protocols |
| `PY_SEC_EDGAR_V4_READINESS.md` | py-sec-edgar integration |
| `entityspine/.../09_FEEDSPINE_INTEGRATION_ANALYSIS.md` | Ecosystem context |

---

## Your First Tasks

1. **Read design docs** (30 min):
   - `GUARDRAILS.md` (code standards)
   - `manifesto.md` (philosophy)
   - `framework-design.md` (architecture)

2. **Understand ecosystem role**: FeedSpine handles ingestion/dedup, NOT resolution

3. **Check async consistency**: All protocol methods must be async

4. **Add type annotations**: Every function needs complete types

5. **Test deduplication**: natural_key normalization, sighting tracking

6. **Address pain points**: TypedRecord, single orchestrator, clear layer promotion

7. **Test EntitySpine integration**: Verify FilingFacts conversion works

---

*FeedSpine Development Prompt v1.1 | January 2026*
*Updated with EntitySpine v0.3.2 integration module*
