# FeedSpine Framework Improvements

> **Scope**: FeedSpine as a standalone framework  
> **Date**: January 2026  
> **Status**: Analysis and Recommendations

---

## Current State Assessment

### Strengths ✅
- Clean protocol-based design (12 protocols)
- Solid deduplication logic via natural keys
- Good async support throughout
- Well-organized optional dependencies
- Comprehensive unit tests (~6,000 lines)

### Architecture Score: ⭐⭐⭐⭐ (4/5)

---

## Improvement Areas

### 1. Feed Composition Pattern Not Yet Implemented

**Current State**: The design doc exists at `docs/design/feed-composition-pattern.md` but `Feed` and `FeedConfig` classes don't exist in code.

**Gap**:
```python
# This is proposed but doesn't work today:
async with Feed(adapter=MyAdapter(), storage=MyStorage()) as feed:
    result = await feed.collect()

# Today you have to do:
spine = FeedSpine(storage=storage)
spine.register_feed(adapter)
result = await spine.collect()
```

**Recommendation**: Implement the Feed Composition Pattern as designed.

**Files to create**:
- `src/feedspine/composition/config.py` - FeedConfig dataclass
- `src/feedspine/composition/feed.py` - Feed context manager
- `src/feedspine/composition/ops.py` - Pipeline operators
- `src/feedspine/composition/preset.py` - Preset base class

---

### 2. CLI is Minimal

**Current State**: Only `version` and `info` commands in `cli.py` (36 lines total)

**Gap**: No practical CLI for data collection

**Recommendation**: Add essential commands:

```python
# Proposed CLI commands
feedspine collect <adapter> --storage <path>  # Run collection
feedspine list-records --limit 10             # Query records
feedspine export --format parquet             # Export data
feedspine status                              # Show pipeline status
feedspine init                                # Initialize project
```

---

### 3. No Typed Content Support

**Current State**: `Record.content` is `dict[str, Any]`

**Gap**: Consumers must cast/validate content manually

**Recommendation**: Add generic typed records:

```python
# Proposed: Generic typed record
from feedspine.models import TypedRecord

class SECRecord(TypedRecord[SECContent]):
    pass

# Content schema
class SECContent(BaseModel):
    accession_number: str
    form_type: str
    ...

# Usage - IDE knows the type!
record: SECRecord = ...
print(record.content.form_type)  # Autocomplete works
```

---

### 4. Storage Backends Limited

**Current State**: Only MemoryStorage and DuckDBStorage implemented

**Gap**: pyproject.toml lists PostgreSQL, SQLite, Redis but they don't exist

**Priority Backends to Add**:

| Backend | Use Case | Effort |
|---------|----------|--------|
| SQLiteStorage | Lightweight persistence | Medium |
| PostgreSQLStorage | Production deployments | Medium |
| RedisCache | Distributed caching | Low |

---

### 5. No Multi-Adapter Collection Strategy

**Current State**: `FeedSpine.collect()` runs adapters sequentially

**Gap**: No way to specify collection order, parallelism, or fallback

**Recommendation**: Add collection strategies:

```python
# Proposed: Collection strategy
from feedspine import FeedSpine, CollectionStrategy

spine = FeedSpine(
    storage=storage,
    collection_strategy=CollectionStrategy(
        parallel=True,
        max_concurrent=3,
        order=["quarterly", "daily", "rss"],  # Priority order
        stop_on_error=False,
    ),
)
```

---

### 6. Progress Reporting Not Integrated

**Current State**: `ProgressReporter` protocol exists but isn't used in `FeedSpine.collect()`

**Gap**: No way to get live progress updates during collection

**Recommendation**: Add progress to collect:

```python
# Proposed
async with FeedSpine(...) as spine:
    result = await spine.collect(progress=RichProgressReporter())
```

---

### 7. No Checkpoint/Resume Support

**Current State**: No built-in checkpointing

**Gap**: Long-running collections can't resume after failure

**Recommendation**: Add checkpoint support:

```python
# Proposed
async with Feed(
    adapter=adapter,
    storage=storage,
    checkpoint=FileCheckpoint("./checkpoints"),
) as feed:
    result = await feed.collect(resume=True)
```

---

### 8. Missing Rate Limiting at Framework Level

**Current State**: Rate limiting is adapter's responsibility

**Gap**: No centralized rate limiting, each adapter implements its own

**Recommendation**: Add framework-level rate limiter:

```python
# Proposed
from feedspine import Feed, RateLimiter

feed = Feed(
    adapter=adapter,
    storage=storage,
    rate_limiter=RateLimiter(requests_per_second=10),
)
```

---

### 9. No Query Builder

**Current State**: Storage backends have `query()` method but no fluent builder

**Gap**: Queries require knowing storage-specific filter syntax

**Recommendation**: Add query builder:

```python
# Proposed
from feedspine import Query

results = await storage.query(
    Query()
    .filter(layer=Layer.BRONZE)
    .filter(content__form_type="10-K")
    .order_by("-published_at")
    .limit(100)
)
```

---

### 10. Integration Tests Missing

**Current State**: Only unit tests exist

**Gap**: No tests for end-to-end workflows

**Recommendation**: Add integration test suite:

```
tests/
├── unit/           # ✅ Exists
├── integration/    # ❌ Missing
│   ├── test_rss_to_duckdb.py
│   ├── test_multi_adapter_dedup.py
│   └── test_checkpoint_resume.py
└── e2e/           # ❌ Missing
    └── test_full_pipeline.py
```

---

## Priority Matrix

| Improvement | Impact | Effort | Priority |
|-------------|--------|--------|----------|
| Feed Composition Pattern | High | Medium | P0 |
| Typed Content Support | High | Low | P0 |
| CLI Commands | Medium | Low | P1 |
| Progress Integration | Medium | Low | P1 |
| SQLite Backend | Medium | Medium | P1 |
| Query Builder | Medium | Medium | P2 |
| Checkpoint/Resume | Medium | Medium | P2 |
| Rate Limiter | Low | Low | P2 |
| PostgreSQL Backend | Low | Medium | P3 |
| Collection Strategy | Low | High | P3 |

---

## Implementation Roadmap

### Phase 1: Core Patterns (1-2 weeks)
1. Implement Feed Composition Pattern
2. Add TypedRecord generic
3. Add basic CLI commands

### Phase 2: Production Readiness (2-3 weeks)
4. Add SQLite storage backend
5. Integrate progress reporting
6. Add query builder
7. Add integration tests

### Phase 3: Scale Features (3-4 weeks)
8. Add checkpoint/resume
9. Add PostgreSQL backend
10. Add collection strategies

---

## Conclusion

FeedSpine has excellent architectural foundations. The main gap is that the **proposed Feed Composition Pattern exists only in docs**, not in code. Implementing this pattern will make the framework significantly more usable and Pythonic.
