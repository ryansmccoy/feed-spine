---
title: "Examples TOUR"
type: other
status: active
tags: [feedspine]
---
# feedspine — Examples Tour

> A curated walk through the most important examples. Run any example with:
> ```bash
> uv run python examples/{path}
> ```

---

## Getting Started

### Quickstart
**Concept:** Minimal feed collection  
**Location:** `examples/01_getting_started/01_quickstart.py`  
**What you'll see:** RSS adapter → Pipeline → MemoryStorage. A single collection with dedup results.  
**Why it matters:** The simplest possible feedspine pipeline — understand the core in 20 lines.

### Multi-Feed Collection
**Concept:** Multiple adapters, one pipeline  
**Location:** `examples/01_getting_started/02_multi_feed.py`  
**What you'll see:** Multiple `RSSFeedAdapter` instances fed through a single `FeedSpine` orchestrator. Aggregated results across feeds.  
**Why it matters:** Real collection pipelines pull from many sources — feedspine handles coordination.

---

## Storage & Persistence

### DuckDB Storage
**Concept:** Persistent storage with analytics capabilities  
**Location:** `examples/02_storage/01_duckdb.py`  
**What you'll see:** `DuckDBStorage` replacing `MemoryStorage`. Same pipeline code, persistent data. Demonstrates the protocol-first storage swap.  
**Why it matters:** Shows the storage tier progression — upgrade from memory to DuckDB without changing pipeline logic.

---

## Domain Feeds

### SEC EDGAR Filing Monitor
**Concept:** Real-world SEC feed adapter  
**Location:** `examples/03_domain_feeds/01_sec_edgar.py`  
**What you'll see:** `SECEdgarFilingAdapter` collecting SEC filings, natural key dedup, sighting history for each filing observation.  
**Why it matters:** This is the use case feedspine was built for — demonstrates real-world feed collection with domain-specific concerns.

---

## Operations

### Checkpoint/Resume
**Concept:** Fault-tolerant collection  
**Location:** `examples/04_operations/04_checkpoint.py`  
**What you'll see:** `CheckpointManager` with `FileCheckpointStore`. Collection that can resume from the last successful position after failure.  
**Why it matters:** Production feed collection must handle failures gracefully — checkpointing makes this automatic.

### Feed Health Monitoring
**Concept:** RAG-status feed health  
**Location:** `examples/04_operations/07_health.py`  
**What you'll see:** Health check across all configured feeds with Red/Amber/Green status reporting.  
**Why it matters:** Operators need to know which feeds are healthy at a glance — feedspine provides this out of the box.

### Enrichment Pipeline
**Concept:** Post-collection data enrichment  
**Location:** `examples/04_operations/05_enrichment.py`  
**What you'll see:** `BatchEnricher` applying metadata enrichment to collected records. Enrichment results with status tracking.  
**Why it matters:** Raw feed data is rarely sufficient — enrichment makes it useful.

### Stats & Metrics
**Concept:** Collection analytics  
**Location:** `examples/04_operations/08_stats.py`  
**What you'll see:** `CollectionMetrics` and `MetricsSummary` — items processed, new/duplicate counts, timing, success rates.  
**Why it matters:** Without metrics, you're flying blind. feedspine tracks everything automatically.

---

## Complete Workflows

### Earnings Calendar Pipeline
**Concept:** End-to-end domain pipeline  
**Location:** `examples/05_earnings/06_full_workflow.py`  
**What you'll see:** Full earnings data workflow from API collection to storage, including estimates vs. actuals comparison.  
**Why it matters:** Shows feedspine handling a complete, non-trivial data pipeline from start to finish.

---

## API & Output

### RSS/Atom Syndication
**Concept:** Re-publishing collected data as feeds  
**Location:** `examples/06_api/02_rss_syndication.py`  
**What you'll see:** Collected records re-published as RSS/Atom feeds via the API layer.  
**Why it matters:** feedspine isn't just a consumer — it can re-publish data in standard feed formats.

---

## CLI

### CLI Commands Walkthrough
**Concept:** Operational CLI  
**Location:** `examples/07_cli/01_cli.py`  
**What you'll see:** All major CLI commands: `collect run`, `feeds list`, `query records`, `health`, `stats`, `export`.  
**Why it matters:** Most day-to-day feedspine usage is through the CLI — this is the operator's guide.

---

## Running All Examples

```bash
# Run a specific example
uv run python examples/01_getting_started/01_quickstart.py

# Run all examples
uv run python examples/run_all.py
```

**Total examples:** 27 across 7 categories. See `examples/README.md` for the complete auto-generated index.
