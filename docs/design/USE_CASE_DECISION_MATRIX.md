# Use Case Decision Matrix

## Overview

This guide helps you choose the right tool based on your specific use case. The answer to "Should I use FeedSpine?" depends entirely on **what you're trying to accomplish**.

---

## Quick Decision Flowchart

```
START: What's your primary goal?
│
├─► "Ingest data from 50+ standard sources (Salesforce, Stripe, etc.)"
│   └─► Use Airbyte or Meltano
│
├─► "Build complex DAG workflows with dependencies"
│   └─► Use Dagster or Airflow (+ FeedSpine for ingestion)
│
├─► "Monitor RSS feeds, APIs, or custom sources with data quality"
│   └─► Use FeedSpine ✓
│
├─► "Real-time streaming at massive scale"
│   └─► Use Kafka + Flink
│
├─► "Quick script to parse some feeds"
│   └─► Use feedparser (but consider FeedSpine if it'll grow)
│
└─► "Query across multiple APIs with GraphQL-like syntax"
    └─► Use Trustfall (+ FeedSpine for storage)
```

---

## Detailed Decision Matrix

### By Primary Use Case

| Use Case | Best Choice | Runner-Up | Avoid |
|----------|-------------|-----------|-------|
| **SEC EDGAR monitoring** | FeedSpine | Custom scripts | Airbyte (no connector) |
| **RSS/Atom aggregation** | FeedSpine | feedparser + custom | Airbyte |
| **SaaS data integration** | Airbyte | Meltano | FeedSpine (no connectors) |
| **Database replication** | Airbyte (CDC) | Debezium | FeedSpine |
| **Web scraping** | Scrapy | Playwright | FeedSpine |
| **Data quality pipeline** | FeedSpine | Great Expectations | Airbyte |
| **ML feature pipelines** | Dagster | Feast | FeedSpine |
| **Real-time analytics** | Kafka + ClickHouse | Benthos | FeedSpine |
| **Embedded data collection** | FeedSpine | dlt | Airbyte (too heavy) |
| **One-time data migration** | dlt | Airbyte | FeedSpine (overkill) |

---

### By Technical Requirements

| Requirement | FeedSpine | Airbyte | Meltano | dlt | Dagster |
|-------------|:---------:|:-------:|:-------:|:---:|:-------:|
| **Must be pip-installable** | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Must run without Docker** | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Must be async/non-blocking** | ✅ | ❌ | ❌ | ⚠️ | ⚠️ |
| **Must have <10 dependencies** | ✅ | ❌ | ❌ | ✅ | ❌ |
| **Must work in AWS Lambda** | ✅ | ❌ | ⚠️ | ✅ | ❌ |
| **Must have Web UI** | ❌ | ✅ | ⚠️ | ❌ | ✅ |
| **Must have 50+ connectors** | ❌ | ✅ | ✅ | ⚠️ | ❌ |
| **Must handle 1M+ records/day** | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| **Must track data lineage** | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ |
| **Must have data quality tiers** | ✅ | ❌ | ❌ | ❌ | ❌ |

---

### By Team Profile

| Team Type | Recommended Stack | Why |
|-----------|-------------------|-----|
| **Solo developer, Python expert** | FeedSpine + DuckDB | Maximum flexibility, minimal overhead |
| **Solo developer, SQL-first** | dlt + DuckDB | Schema inference, SQL transforms |
| **Small startup, move fast** | FeedSpine + Prefect | Simple, async, orchestrated |
| **Data team, many sources** | Airbyte + dbt | Connector breadth, analytics |
| **Enterprise, compliance-heavy** | Dagster + Airbyte | Lineage, governance, audit |
| **ML team, feature engineering** | Dagster + Feast | Asset-centric, ML-focused |
| **Finance, SEC/regulatory** | FeedSpine + PostgreSQL | Quality tiers, audit trail |

---

## Scenario-Based Recommendations

### Scenario 1: "I need to monitor SEC EDGAR filings"

**Best Choice: FeedSpine**

Why:
- Native RSS feed support
- Medallion architecture for data quality
- Sighting tracking (know when you first saw a filing)
- Natural key deduplication
- No heavyweight infrastructure

```python
# FeedSpine approach
from feedspine import FeedSpine
from feedspine.adapter.rss import RSSAdapter

async with FeedSpine(storage=DuckDBStorage("sec.duckdb")) as fs:
    fs.register_feed(RSSAdapter(
        url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-K&output=atom",
        name="sec-10k-filings"
    ))
    result = await fs.collect()
```

Alternatives considered:
- **Airbyte**: No SEC connector, would need custom development
- **Custom script**: Would reinvent deduplication, storage abstraction
- **Scrapy**: Overkill for structured feeds

---

### Scenario 2: "I need to sync Salesforce to our data warehouse"

**Best Choice: Airbyte or Meltano**

Why:
- Pre-built, maintained Salesforce connector
- Handles OAuth, pagination, rate limits
- Schema mapping to warehouse

```yaml
# Meltano approach
plugins:
  extractors:
    - name: tap-salesforce
      variant: meltanolabs
  loaders:
    - name: target-postgres
```

Why NOT FeedSpine:
- No pre-built Salesforce adapter
- Building one is significant effort
- Connector ecosystem matters for SaaS sources

---

### Scenario 3: "I need complex workflow orchestration with retries"

**Best Choice: Dagster or Prefect + FeedSpine**

Why:
- Dagster/Prefect excel at orchestration
- FeedSpine handles the ingestion
- Best of both worlds

```python
# Prefect + FeedSpine approach
from prefect import flow, task
from feedspine import FeedSpine

@task(retries=3)
async def collect_sec_filings():
    async with FeedSpine() as fs:
        return await fs.collect()

@task
async def process_filings(result):
    # Transform, analyze, etc.
    pass

@flow
async def sec_pipeline():
    result = await collect_sec_filings()
    await process_filings(result)
```

Why NOT FeedSpine alone:
- FeedSpine has basic executors
- Complex DAGs need dedicated orchestrator

---

### Scenario 4: "I need real-time streaming at scale"

**Best Choice: Kafka + Flink or Benthos**

Why:
- Sub-second latency requirements
- Millions of events per second
- Exactly-once semantics at scale

Why NOT FeedSpine:
- FeedSpine is polling-based, not true streaming
- Not designed for massive scale
- Better suited for "near real-time" (minutes, not milliseconds)

---

### Scenario 5: "I'm prototyping and need something quick"

**Best Choice: dlt or FeedSpine**

| Criterion | Choose dlt | Choose FeedSpine |
|-----------|------------|------------------|
| Schema unknown upfront | ✅ | |
| Need data quality tiers | | ✅ |
| One-time load | ✅ | |
| Ongoing monitoring | | ✅ |
| Decorator-based API | ✅ | |
| Protocol-based extensibility | | ✅ |

```python
# dlt approach - schema inference
import dlt

@dlt.source
def my_api():
    return dlt.resource(fetch_data(), name="items")

pipeline = dlt.pipeline(destination="duckdb")
pipeline.run(my_api())
```

```python
# FeedSpine approach - explicit modeling
from feedspine import FeedSpine
from feedspine.models import RecordCandidate

async with FeedSpine() as fs:
    # Explicit record structure
    candidate = RecordCandidate(
        natural_key="item-123",
        content={"field": "value"}
    )
```

---

### Scenario 6: "I need to query across multiple APIs"

**Best Choice: Trustfall + FeedSpine**

Why:
- Trustfall provides cross-source query composition
- FeedSpine stores and manages the data
- GraphQL-like query interface

```graphql
# Trustfall query across SEC + stock data
{
    SECFiling(form_type: "10-K") {
        company @output
        ticker @output
        
        # Jump to different data source
        stockQuote {
            price @filter(op: ">", value: ["$min_price"]) @output
        }
    }
}
```

See: [TRUSTFALL_COMPARISON.md](TRUSTFALL_COMPARISON.md)

---

## Anti-Patterns: When NOT to Use FeedSpine

### ❌ Don't use FeedSpine when...

| Situation | Why | Use Instead |
|-----------|-----|-------------|
| You need 100+ pre-built connectors | No connector ecosystem | Airbyte, Meltano |
| You need a GUI for non-developers | CLI/code only | Airbyte Cloud |
| You need CDC from databases | Not designed for this | Debezium, Airbyte |
| You need sub-second latency | Polling-based | Kafka, Benthos |
| You need managed SaaS | Self-hosted only | Airbyte Cloud, Fivetran |
| You're doing one-time migration | Overkill | dlt, pandas |
| You need complex ML pipelines | Not the focus | Dagster, Kubeflow |

---

## Hybrid Architectures

### Pattern 1: FeedSpine + Airbyte

Use Airbyte for standard connectors, FeedSpine for custom feeds:

```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                          │
├──────────────────┬──────────────────────────────────────┤
│   SaaS APIs      │        Custom Feeds                  │
│  (Salesforce,    │      (SEC, RSS, APIs)                │
│   Stripe, etc.)  │                                      │
├──────────────────┼──────────────────────────────────────┤
│     Airbyte      │         FeedSpine                    │
├──────────────────┴──────────────────────────────────────┤
│                    Data Warehouse                        │
│                  (PostgreSQL, DuckDB)                    │
└─────────────────────────────────────────────────────────┘
```

### Pattern 2: FeedSpine + Dagster

Use Dagster for orchestration, FeedSpine for feed collection:

```python
from dagster import asset, Definitions
from feedspine import FeedSpine

@asset
async def sec_filings():
    """Collect SEC filings using FeedSpine."""
    async with FeedSpine() as fs:
        fs.register_feed(sec_rss_adapter)
        result = await fs.collect()
        return result.records

@asset(deps=[sec_filings])
def analyzed_filings(sec_filings):
    """Analyze collected filings."""
    # Dagster handles dependencies, retries, scheduling
    return analyze(sec_filings)
```

### Pattern 3: FeedSpine + dbt

Use FeedSpine for ingestion, dbt for transformation:

```
FeedSpine (Bronze) → DuckDB → dbt (Silver/Gold)
```

```sql
-- dbt model: silver_filings.sql
SELECT
    natural_key,
    content->>'company' as company,
    content->>'form_type' as form_type,
    published_at::date as filing_date
FROM {{ source('feedspine', 'records') }}
WHERE layer = 'BRONZE'
  AND content->>'form_type' IN ('10-K', '10-Q')
```

---

## Decision Checklist

Before choosing, answer these questions:

### 1. Source Type
- [ ] Standard SaaS (Salesforce, Stripe) → Airbyte/Meltano
- [ ] RSS/Atom feeds → FeedSpine
- [ ] Custom REST APIs → FeedSpine or dlt
- [ ] Databases (CDC) → Airbyte/Debezium
- [ ] Web scraping → Scrapy

### 2. Scale
- [ ] <10K records/day → Any tool works
- [ ] 10K-1M records/day → FeedSpine, dlt, Airbyte all fine
- [ ] >1M records/day → Airbyte, Kafka, or custom

### 3. Team
- [ ] Python developers → FeedSpine, dlt, Dagster
- [ ] SQL-first analysts → Meltano + dbt
- [ ] Mixed technical/non-technical → Airbyte (UI)

### 4. Operations
- [ ] Need managed service → Airbyte Cloud, Fivetran
- [ ] Self-hosted OK → FeedSpine, Dagster, Meltano
- [ ] Minimal infrastructure → FeedSpine, dlt

### 5. Data Quality
- [ ] Need Bronze/Silver/Gold → FeedSpine
- [ ] Need data contracts → FeedSpine + Great Expectations
- [ ] Basic validation OK → Any tool

---

## Summary Table

| If You Need... | Use This | Not That |
|----------------|----------|----------|
| SEC/RSS feed monitoring | **FeedSpine** | Airbyte |
| SaaS connectors | **Airbyte** | FeedSpine |
| Minimal dependencies | **FeedSpine** | Dagster |
| Complex orchestration | **Dagster** | FeedSpine alone |
| Schema inference | **dlt** | FeedSpine |
| Data quality layers | **FeedSpine** | Meltano |
| Web UI | **Airbyte** | FeedSpine |
| AWS Lambda deployment | **FeedSpine** | Airbyte |
| Cross-source queries | **Trustfall** | Native APIs |
| Production monitoring | **Prefect + FeedSpine** | FeedSpine alone |
