---
title: "Temporal Provenance"
type: reference
status: active
tags: [feedspine]
created: 2026-01-01
updated: 2026-06-15
---
# feedspine — Temporal Provenance

## Why Two Time Axes?

Every record in feedspine answers two distinct temporal questions:

| Axis | Field | Question |
|---|---|---|
| **Valid time** | `published_at` | When did the source say this happened? |
| **Transaction time** | `captured_at` | When did feedspine ingest it? |

These axes are **independent**. A filing published by SEC on 2025-01-10 might
be ingested by your pipeline on 2025-01-11 (backfill lag), and you need to
distinguish both to write correct PIT queries.

---

## Definitions

### Valid Time (`published_at`)

Set by the **source** — not by feedspine. It is the authoritative date from the
publisher. Never modify it during enrichment.

Examples:
- SEC RSS: `<pubDate>Fri, 10 Jan 2025 17:30:00 EST</pubDate>` → `published_at`
- Polygon Earnings API: `earnings_date` field → `published_at`

### Transaction Time (`captured_at`)

Set by `Metadata(source=..., captured_at=utcnow())` **at capture time**. It is
the system's record of when we saw the data.

Stored in `Metadata.captured_at` and surfaced via `record.metadata.captured_at`.

---

## Diagram: Bi-Temporal Record Lifecycle

```
Real world timeline (valid time)                                source time
──────────────────────────────────────────────────────────────────────────►
  ↑                      ↑
  Event occurs           Source publishes (published_at)
  (e.g. filing date)


Database timeline (transaction time / captured_at)
──────────────────────────────────────────────────────────────────────────►
                               ↑
                               Pipeline ingests (captured_at)


published_at  can be BEFORE captured_at  → normal case (we see it after it happens)
published_at  == captured_at             → near-real-time feed
published_at  > captured_at             → ⚠️ clock skew — investigate source
```

---

## Query Patterns

### 1. As-of Transaction Time — "What had we ingested by Jan 11?"

```sql
SELECT * FROM records
WHERE source = 'sec.rss'
  AND captured_at <= '2025-01-11T23:59:59Z'
ORDER BY published_at DESC;
```

Use case: replay — reproduce the exactly what your pipeline saw at a given moment.

---

### 2. As-of Valid Time — "What did the source report before Jan 10?"

```sql
SELECT * FROM records
WHERE source = 'sec.rss'
  AND published_at <= '2025-01-10T23:59:59Z'
ORDER BY published_at DESC;
```

Use case: business reporting — "show me all 8-K filings before market close on Jan 10".

---

### 3. Both Axes — Full PIT Query

```sql
SELECT * FROM records
WHERE source = 'sec.rss'
  AND published_at  <= '2025-01-10T23:59:59Z'   -- what the source claimed
  AND captured_at   <= '2025-01-11T12:00:00Z'    -- what we knew by noon next day
ORDER BY published_at DESC;
```

Use case: audit / compliance — "reproduce our exact data set at time T".

---

### 4. Latest — Current View

```python
# Python (using storage backend)
records = storage.query(
    Query(source="sec.rss", limit=100, order_by="published_at desc")
)
```

```sql
-- SQL
SELECT * FROM records
WHERE source = 'sec.rss'
ORDER BY published_at DESC
LIMIT 100;
```

Use case: dashboards, enrichment pipelines, latest filings feeds.

---

## Change History via Sightings

`Sighting` records add a third, lightweight layer:

```
natural_key  source        seen_at          is_new  raw_data_hash
─────────────────────────────────────────────────────────────────
sec-001      sec.rss       2025-01-10       True    abc123
sec-001      sec.rss       2025-01-11       False   abc123   ← same content
sec-001      sec.rss       2025-01-15       True    def456   ← content changed!
```

- `is_new=True` on first appearance → use to track debut dates
- `is_new=True` on content change → use as a change-capture indicator
- `raw_data_hash` change → indicates what changed

**Evidence:** `src/feedspine/models/sighting.py` — `class Sighting`

---

## When to Add a Third Time Axis

feedspine's two axes cover most needs. Add a third axis if you need to:

| Scenario | Third axis | Notes |
|---|---|---|
| Multi-vendor data (e.g. SEC + Bloomberg both publish earnings) | `vendor_publish_time` per source | Store vendor-specific `published_at` per sighting, not on base record |
| Regulatory backfill (re-ingesting historical data) | `effective_date` | Separate from `published_at`; set by business logic |
| Syndicated feeds (your feed re-publishes another) | `origin_published_at` | Store originating source's timestamp alongside your `captured_at` |

Use `TemporalEnvelope` from spine-core (which carries `event_time`, `publish_time`,
`ingest_time`, `effective_time`) as the recommended three+one timestamp model.
See spine-core's `TemporalEnvelope` documentation for details.

---

## Bitemporal vs. Tritemporal — Summary

| Model | Axes | When to use |
|---|---|---|
| **Unitemporal** | `published_at` only | Simple read-only archive, no corrections |
| **Bitemporal** | `published_at` + `captured_at` | Standard feedspine usage — handles lag and replay |
| **Tritemporal** | + `effective_date` or `vendor_publish_time` | Multi-vendor reconciliation, regulatory reporting at a specific date |

Start with bitemporal (feedspine default). Add the third axis only when a
concrete query requirement cannot be satisfied with just `published_at` and `captured_at`.
