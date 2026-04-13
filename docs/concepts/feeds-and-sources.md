---
title: "Feeds And Sources"
type: reference
status: active
tags: [feedspine]
created: 2026-01-01
updated: 2026-06-15
---
# feedspine — Feeds, Sources & Change Capture

## Overview

feedspine is the **data ingestion layer** of the Spine ecosystem. It collects
records from external sources (RSS feeds, REST APIs, file drops), deduplicates them,
enriches them, and stores them in a queryable, provenance-tracked store.

```
External Source → FeedAdapter → Pipeline → Storage Backend
                                  │
                           Dedupe │ Enrich │ Validate
```

---

## Core Primitives

### `RecordCandidate`

The atomic unit produced by every `FeedAdapter`. It is a raw, unvalidated record
before deduplication.

```python
RecordCandidate(
    natural_key="sec-filing-0001234567-25-000001",  # normalized: lowercase, stripped
    published_at=datetime(..., tzinfo=UTC),
    content={"form_type": "10-K", "cik": "...", ...},
    metadata=Metadata(source="sec.rss", source_type="rss"),
)
```

Key behavior:
- `natural_key` is **auto-normalized** (lowercase + strip whitespace)
- `content_hash` is computed as SHA-256 of canonical JSON (sorted keys)
  — identical content always produces the same 16-char hex string

**Evidence:** `src/feedspine/models/record.py` — `class RecordCandidate`

---

### `Record`

A `RecordCandidate` that has been persisted. Adds:

- `id` — UUID primary key
- `layer` — `BRONZE | SILVER | GOLD` (medallion architecture tier)
- `first_seen_at` — when this `natural_key` was first captured
- `last_seen_at` — most recent sighting
- `version` — incremented on content change

**Evidence:** `src/feedspine/models/record.py` — `class Record`

---

### `Layer` (Medallion Tiers)

```
BRONZE  Raw, as-captured from source
  ↓     validate + deduplicate
SILVER  Clean, normalized, unique natural_key
  ↓     enrich (entity links, tags, derived fields)
GOLD    Analytics-ready, enriched
```

**Evidence:** `src/feedspine/models/base.py` — `class Layer`

---

### `Sighting`

Every time we encounter a `natural_key` (new or repeat), a `Sighting` is recorded:

```python
Sighting(
    id="sight-abc",
    natural_key="sec-filing-001",
    source="sec.rss",
    is_new=True,              # False on repeat
    raw_data_hash="abc123...",
    seen_at=utcnow(),
)
```

Sightings form the provenance audit trail — they tell you **when** each feed
first reported a record and whether the content changed since last seen.

**Evidence:** `src/feedspine/models/sighting.py` — `class Sighting`

---

### `Metadata`

Lightweight provenance bag attached to every record:

| Field | Description |
|---|---|
| `source` | Feed name (e.g. `"sec.rss"`) |
| `source_type` | Adapter type (e.g. `"rss"`, `"sec.daily_index"`) |
| `captured_at` | When the record was captured (transaction time) |
| `extra` | Arbitrary key-value bag for adapter-specific metadata |

**Evidence:** `src/feedspine/models/base.py` — `class Metadata`

---

## Sources & Adapters

### `FeedAdapter` Protocol

Any adapter must implement:

```python
class FeedAdapter(Protocol):
    async def fetch(self) -> AsyncIterator[RecordCandidate]: ...
```

Built-in adapters in `src/feedspine/adapter/`:

| Adapter | Source |
|---|---|
| `RSSFeedAdapter` | RSS/Atom XML feeds |
| `SECEdgarAdapter` | SEC EDGAR API |
| `PolygonEarningsAdapter` | Polygon.io earnings data |
| `JsonFileAdapter` | Local JSON files |
| `CSVAdapter` | CSV files |

Rate limiting is built in via `AdapterRateLimiter` (token bucket per host).

**Evidence:** `src/feedspine/adapter/base.py` — `class FeedAdapter`, `class BaseFeedAdapter`

### `FeedError`

Adapter errors are wrapped in `FeedError(message, source, cause)` to clearly
attribute which feed failed. Feed errors do not stop other feeds — `CollectionResult`
tracks per-feed error counts.

---

## The Feed Pipeline

### `Feed` — Main Entry Point

```python
async with Feed(
    adapter=RSSFeedAdapter(url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&search_text=&action=getcurrent"),
    storage=SQLiteStorage(path="feeds.db"),
    enrichers=[EntityEnricher()],
) as feed:
    result = await feed.collect()
    print(f"New: {result.total_new}, Updated: {result.total_updated}")
```

Collect() pipeline:
1. **Fetch** — adapter yields `RecordCandidate` objects
2. **Validate** — schema validation, key normalization
3. **Deduplicate** — compare `content_hash` against stored record
4. **Enrich** — apply enrichers (entity linking, tagging)
5. **Store** — batch upsert to storage backend

**Evidence:** `src/feedspine/composition/feed.py` — `class Feed`; `src/feedspine/core/feedspine.py` — architecture diagram

---

## Change Capture

feedspine uses **content-hash deduplication** for change detection:

```
Incoming RecordCandidate
       │
       ▼
content_hash = SHA256(canonical_json(content))[:16]
       │
       ├── hash matches stored? → SIGHTING (is_new=False), no update
       │
       └── hash differs? → UPDATE record (bump version), SIGHTING (is_new=True for changed)
```

This gives you:
- **Exact deduplication**: same content, same source = skip
- **Change detection**: same key but changed content = version bump
- **Append-only sightings**: full history of when we saw each key

For CDC (Change Data Capture) use cases, query `Sighting` records filtered
by `is_new=True` to get only the deltas.

---

## Temporal Provenance

feedspine carries two time dimensions per record:

| Field | Axis | Stored on |
|---|---|---|
| `published_at` | **Valid time** — when the source says it happened | `RecordCandidate`, `Record` |
| `captured_at` | **Transaction time** — when we ingested it | `Metadata` |

> **Bi-temporal query example:**
> "Show me records the SEC published before Jan 1 2025 that we ingested after Jan 15"
> → `WHERE published_at < '2025-01-01' AND captured_at > '2025-01-15'`

For vendor-level timing, use spine-core's `TemporalEnvelope` which adds
`event_time` and `publish_time` alongside `ingest_time`. See
spine-core's `TemporalEnvelope` documentation.

---

## Quality

`QualityCheck` hooks can be registered on a `Feed` config to gate ingestion:

```python
config = FeedConfig(
    adapter=...,
    storage=...,
    quality_checks=[
        QualityCheck("required_fields", check_fn=has_required_fields),
    ],
)
```

Records failing `FAIL`-level checks are routed to the DLQ, not storage.
`WARN` checks log but pass through.

---

## Observations

`BaseObservation` is a domain-specific, typed record sub-type. Where `Record`
is generic (any feed), `BaseObservation` subclasses carry a typed
`observation_type` discriminator:

```python
class EarningsObservation(BaseObservation):
    observation_type: Literal["earnings_event"] = "earnings_event"
    eps_actual: float
    eps_estimate: float

    @computed_field
    @property
    def fingerprint(self) -> str:
        return f"earnings:{self.id}"
```

Observations are used for domain events that need typed schemas (vs.
generic `dict` content in `Record`).

**Evidence:** `src/feedspine/models/observation.py` — `class BaseObservation`

---

## `FeedSpineApp` Orchestrator

For multi-feed setups, `create_feed_spine()` returns an app that registers and runs all feeds concurrently:

```python
app = create_feed_spine(storage)
app.register_feed(rss_adapter)
app.register_feed(sec_daily_adapter)
result = await app.collect()
# result.total_new, result.errors, per-feed stats
```

**Evidence:** `src/feedspine/core/feedspine.py` — `class FeedSpine`, architecture diagram

---

## Summary Diagram

```
   External Sources
   ┌─────────┐ ┌════════════┐ ┌──────────┐
   │ SEC RSS │ │ REST API   │ │ CSV File │  ...
   └────┬────┘ └═════┬══════┘ └────┬─────┘
        │            │             │
        ▼            ▼             ▼
   ┌─────────────────────────────────────┐
   │         FeedAdapter.fetch()         │  yields RecordCandidate
   └──────────────────┬──────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────┐
   │              Pipeline               │
   │  Validate → Dedupe → Enrich → Store │
   │       (content_hash)                │
   └──────┬───────────┬──────────────────┘
          │           │
          ▼           ▼
   ┌─────────┐  ┌────────────┐
   │ Sighting│  │  Record    │  BRONZE → SILVER → GOLD
   │ (audit) │  │ (upserted) │
   └─────────┘  └────────────┘
```
