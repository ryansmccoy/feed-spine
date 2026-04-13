---
title: "Readme"
type: readme
status: active
tags: [feedspine]
---
# Feedspine — Examples

> **27 examples** across **7 categories** — auto-generated from docstrings.
> Regenerate: `python examples/generate_readme.py`

---

## Quick Start

```bash
# Run ALL examples (auto-discovered, isolated subprocesses)
python examples/run_all.py

# Run a single example
python examples/01_getting_started/01_quickstart.py
```

## Learning Path

Categories are numbered by conceptual dependency — start at `01` and work forward.

| # | Category | Examples | Description |
|---|----------|---------|-------------|
| 01 | `01_getting_started/` | 2 | Getting started — FeedSpine basics, multi-feed collection, dedup concepts. |
| 02 | `02_storage/` | 2 | Storage — DuckDB persistence, data type handling, checkpoints. |
| 03 | `03_domain_feeds/` | 1 | Domain feeds — SEC EDGAR daily filings, custom adapters. |
| 04 | `04_operations/` | 11 | Operations — FeedRun tracking, auto-key generation, smart sync strategies, checkpoints, enrichment. |
| 05 | `05_earnings/` | 7 | Earnings — Calendar API, CLI, REST, WebSocket, full workflows, estimates vs actuals. |
| 06 | `06_api/` | 3 | 07_api - API Examples |
| 07 | `07_cli/` | 1 | CLI Command Examples |

## Examples by Category

### 01_getting_started — Getting Started

| # | Example | Description |
|---|---------|-------------|
| 01 | [01_quickstart.py](01_getting_started/01_quickstart.py) | FeedSpine Quickstart Example |
| 02 | [02_multi_feed.py](01_getting_started/02_multi_feed.py) | FeedSpine Multi-Feed Collection Example |

### 02_storage — Storage

| # | Example | Description |
|---|---------|-------------|
| 01 | [01_duckdb_storage.py](02_storage/01_duckdb_storage.py) | FeedSpine with DuckDB Persistent Storage |
| 02 | [02_data_type_storage.py](02_storage/02_data_type_storage.py) | FeedSpine Data Type Aware Storage |

### 03_domain_feeds — Domain Feeds

| # | Example | Description |
|---|---------|-------------|
| 01 | [01_sec_edgar.py](03_domain_feeds/01_sec_edgar.py) | FeedSpine SEC EDGAR Filing Monitor |

### 04_operations — Operations

| # | Example | Description |
|---|---------|-------------|
| 01 | [01_operational_tracking.py](04_operations/01_operational_tracking.py) | FeedSpine Operational Tracking Example |
| 02 | [02_auto_key_generation.py](04_operations/02_auto_key_generation.py) | Example 8: Auto Key Generation for FeedSpine |
| 03 | [03_smart_sync_strategy.py](04_operations/03_smart_sync_strategy.py) | FeedSpine Example 07: Smart Sync Strategy Pattern |
| 04 | [04_checkpoint_management.py](04_operations/04_checkpoint_management.py) | FeedSpine Checkpoint Management Example |
| 05 | [05_enrichment_pipeline.py](04_operations/05_enrichment_pipeline.py) | FeedSpine Enrichment Pipeline Example |
| 06 | [06_schedule_management.py](04_operations/06_schedule_management.py) | FeedSpine Schedule Management Example |
| 07 | [07_health_monitoring.py](04_operations/07_health_monitoring.py) | FeedSpine Health Monitoring Example |
| 08 | [08_stats_and_metrics.py](04_operations/08_stats_and_metrics.py) | FeedSpine Stats and Metrics Example |
| 09 | [09_parquet_export.py](04_operations/09_parquet_export.py) | FeedSpine Parquet Export Example |
| 10 | [10_api_authentication.py](04_operations/10_api_authentication.py) | FeedSpine API Authentication Example |
| 11 | [11_collect_resume.py](04_operations/11_collect_resume.py) | FeedSpine Collect Resume Example |

### 05_earnings — Earnings

| # | Example | Description |
|---|---------|-------------|
| 01 | [01_earnings_calendar.py](05_earnings/01_earnings_calendar.py) | Earnings Calendar Demo - The Final Product |
| 02 | [02_earnings_cli.py](05_earnings/02_earnings_cli.py) | Earnings Calendar CLI Demo |
| 03 | [03_earnings_python_api.py](05_earnings/03_earnings_python_api.py) | Earnings Python API Demo |
| 04 | [04_earnings_rest_api.py](05_earnings/04_earnings_rest_api.py) | Earnings REST API Demo |
| 05 | [05_earnings_websocket.py](05_earnings/05_earnings_websocket.py) | Earnings WebSocket Demo |
| 06 | [06_earnings_full_workflow.py](05_earnings/06_earnings_full_workflow.py) | Full Earnings Workflow Demo |

### 06_api — Api

| # | Example | Description |
|---|---------|-------------|
| 01 | [01_unified_timeline.py](06_api/01_unified_timeline.py) | FeedSpine Unified Feed Timeline Example |
| 02 | [02_rss_atom_syndication.py](06_api/02_rss_atom_syndication.py) | FeedSpine RSS/Atom Syndication Example |
| 03 | [03_export_formats.py](06_api/03_export_formats.py) | FeedSpine Export Formats Example |

### 07_cli — Cli

| # | Example | Description |
|---|---------|-------------|
| 01 | [01_cli_walkthrough.py](07_cli/01_cli_walkthrough.py) | FeedSpine CLI Commands Walkthrough |

## Architecture Highlights

These examples include architecture diagrams — key for understanding data flow and component interaction.

### Earnings Calendar Demo - The Final Product
*From [01_earnings_calendar.py](05_earnings/01_earnings_calendar.py)*

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │ SEC EDGAR   │     │  Finnhub    │     │   Yahoo     │
    │  Adapter    │     │  Adapter    │     │  Adapter    │
    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
           │                   │                   │
           └───────────────────┴───────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │  CalendarService │  (aggregates, dedupes)
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  EntitySpine     │  (resolve entities)
                    │  Event + payload │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  ObsStorage      │  (get estimates)
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────────────────────────────┐
                    │  Output: Table, CSV, WebSocket, Webhook  │
                    └──────────────────────────────────────────┘
```

## Infrastructure

| File | Purpose |
|------|---------|
| [`_registry.py`](_registry.py) | Auto-discovers examples via AST — no hardcoded lists |
| [`run_all.py`](run_all.py) | Runs every example as an isolated subprocess (60s timeout) |
| [`generate_readme.py`](generate_readme.py) | Generates this README from docstrings |

---

*Generated on 2026-02-15 from 27 examples across 7 categories.*
