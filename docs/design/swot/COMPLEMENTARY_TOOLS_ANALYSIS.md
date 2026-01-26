# Complementary Tools Integration Analysis

## Overview

This document analyzes tools that could **complement** FeedSpine (not replace it), providing capabilities that extend the framework's functionality without duplicating its core value.

---

## Integration Architecture Vision

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Application Layer                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   FastAPI    │  │   Trustfall  │  │   Streamlit  │  │    Slack     │    │
│  │  (REST API)  │  │   (Queries)  │  │ (Dashboard)  │  │   (Alerts)   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                             FeedSpine Core                                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐               │
│  │  Adapters  │ │  Storage   │ │   Search   │ │  Pipeline  │               │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘               │
├─────────────────────────────────────────────────────────────────────────────┤
│                          Infrastructure Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │    DuckDB    │  │ Elasticsearch│  │    Redis     │  │      S3      │    │
│  │  (Analytics) │  │   (Search)   │  │   (Cache)    │  │   (Blobs)    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                          Orchestration Layer                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │   Prefect    │  │   Dagster    │  │    Celery    │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Category 1: Query & Analytics

### Trustfall

**Already Covered:** See [TRUSTFALL_COMPARISON.md](TRUSTFALL_COMPARISON.md)

**Integration Summary:**
- GraphQL-like queries over FeedSpine data
- Cross-source query composition
- Priority: Medium (if complex queries needed)

---

### DuckDB

**What it is:** Embeddable analytical database (OLAP)

**Why integrate:**
- Fast analytical queries on FeedSpine data
- SQL interface familiar to analysts
- Embedded (no server needed)
- Excellent Parquet/CSV support
- Python-native

**Integration Approach:**

```python
# feedspine/storage/duckdb.py (already planned)

import duckdb
from feedspine.protocols import StorageBackend

class DuckDBStorage(StorageBackend):
    def __init__(self, path: str = ":memory:"):
        self.conn = duckdb.connect(path)
    
    async def store(self, record: Record) -> None:
        # Store as structured data
        self.conn.execute("""
            INSERT INTO records (id, natural_key, layer, content, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, [record.id, record.natural_key, record.layer.value, 
              json.dumps(record.content), json.dumps(record.metadata)])
    
    async def analytics_query(self, sql: str) -> list[dict]:
        """Direct SQL access for analytics."""
        return self.conn.execute(sql).fetchdf().to_dict('records')

# Usage
storage = DuckDBStorage("feedspine.duckdb")

# Analytical query
results = await storage.analytics_query("""
    SELECT 
        content->>'company' as company,
        COUNT(*) as filing_count,
        MAX(published_at) as latest_filing
    FROM records
    WHERE layer = 'GOLD' AND content->>'form_type' = '10-K'
    GROUP BY content->>'company'
    ORDER BY filing_count DESC
    LIMIT 10
""")
```

**Feature Mapping:**

| DuckDB Feature | FeedSpine Use |
|----------------|---------------|
| OLAP queries | Analytics on collected data |
| JSON functions | Query record.content |
| Parquet export | Data warehouse integration |
| Window functions | Time-series analysis |
| Full-text search | Supplement SearchBackend |

**Priority:** High (already on roadmap)

---

### Polars

**What it is:** Fast DataFrame library (Rust-powered)

**Why integrate:**
- Blazing fast data manipulation
- Lazy evaluation
- Better memory efficiency than Pandas
- SQL interface available
- Streaming support

**Integration Approach:**

```python
# feedspine/transform/polars.py

import polars as pl
from feedspine.models import Record

class PolarsTransformer:
    """Transform FeedSpine records using Polars."""
    
    @staticmethod
    def records_to_df(records: list[Record]) -> pl.DataFrame:
        """Convert records to Polars DataFrame."""
        return pl.DataFrame([
            {
                "id": r.record_id,
                "natural_key": r.natural_key,
                "layer": r.layer.value,
                "published_at": r.published_at,
                **r.content  # Flatten content
            }
            for r in records
        ])
    
    @staticmethod
    async def transform_batch(
        storage: StorageBackend,
        transform_fn: callable,
        layer: Layer = Layer.SILVER
    ) -> pl.DataFrame:
        """Batch transform with Polars."""
        records = [r async for r in storage.query(layer=layer)]
        df = PolarsTransformer.records_to_df(records)
        return transform_fn(df)

# Usage
async def enrich_filings():
    df = await PolarsTransformer.transform_batch(
        storage,
        lambda df: df.with_columns([
            pl.col("filed_at").str.to_date().alias("filed_date"),
            (pl.col("revenue") / 1_000_000).alias("revenue_millions"),
        ]).filter(pl.col("revenue_millions") > 100)
    )
```

**Priority:** Medium (nice-to-have for analytics)

---

## Category 2: Data Quality & Validation

### Great Expectations

**What it is:** Data quality framework with declarative expectations

**Why integrate:**
- Validate data between medallion layers
- Generate data documentation
- Alerting on quality issues
- Industry standard for data quality

**Integration Approach:**

```python
# feedspine/quality/great_expectations.py

import great_expectations as gx
from feedspine.protocols import StorageBackend
from feedspine.models import Layer

class DataQualityValidator:
    """Validate data quality using Great Expectations."""
    
    def __init__(self, storage: StorageBackend):
        self.storage = storage
        self.context = gx.get_context()
    
    async def validate_promotion(
        self, 
        record: Record,
        from_layer: Layer,
        to_layer: Layer
    ) -> tuple[bool, dict]:
        """Validate record before layer promotion."""
        
        suite = self._get_suite_for_promotion(from_layer, to_layer)
        
        # Convert record to pandas for GX
        df = pd.DataFrame([record.content])
        
        result = self.context.run_validation_operator(
            "action_list_operator",
            assets_to_validate=[{
                "batch": df,
                "expectation_suite": suite
            }]
        )
        
        return result.success, result.to_json_dict()
    
    def _get_suite_for_promotion(
        self, 
        from_layer: Layer, 
        to_layer: Layer
    ) -> str:
        """Get expectation suite for layer transition."""
        if from_layer == Layer.BRONZE and to_layer == Layer.SILVER:
            return "bronze_to_silver_suite"
        elif from_layer == Layer.SILVER and to_layer == Layer.GOLD:
            return "silver_to_gold_suite"
        raise ValueError(f"No suite for {from_layer} -> {to_layer}")

# Example expectation suite
bronze_to_silver_expectations = {
    "expectations": [
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "natural_key"}},
        {"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": "natural_key"}},
        {"expectation_type": "expect_column_values_to_be_unique", "kwargs": {"column": "natural_key"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "published_at"}},
    ]
}
```

**Feature Mapping:**

| GX Feature | FeedSpine Use |
|------------|---------------|
| Expectations | Promotion validation |
| Data docs | Record documentation |
| Checkpoints | Pipeline validation |
| Alerts | Quality notifications |

**Priority:** Medium (valuable for production)

---

### Pandera

**What it is:** Statistical data validation for Pandas/Polars

**Why integrate:**
- Lighter weight than Great Expectations
- Schema-based validation
- Integrates with Pydantic mindset
- Good for DataFrame validation

**Integration Approach:**

```python
# feedspine/quality/pandera.py

import pandera as pa
from pandera.typing import DataFrame, Series

class SECFilingSchema(pa.DataFrameModel):
    """Schema for SEC filing records."""
    
    natural_key: Series[str] = pa.Field(unique=True, nullable=False)
    form_type: Series[str] = pa.Field(isin=["10-K", "10-Q", "8-K", "S-1"])
    filed_at: Series[pa.DateTime] = pa.Field(nullable=False)
    company_cik: Series[str] = pa.Field(str_length={"min_value": 10, "max_value": 10})
    
    @pa.check("filed_at")
    def not_future_date(cls, series: Series[pa.DateTime]) -> Series[bool]:
        return series <= pd.Timestamp.now()

# Usage in promotion
@pa.check_types
def promote_to_silver(df: DataFrame[SECFilingSchema]) -> DataFrame:
    """Pandera validates input automatically."""
    return df.assign(promoted_at=pd.Timestamp.now())
```

**Priority:** Low (Pydantic may be sufficient)

---

## Category 3: Search & Retrieval

### Elasticsearch

**What it is:** Distributed search and analytics engine

**Why integrate:**
- Full-text search at scale
- Aggregations and analytics
- Industry standard
- Real-time indexing

**Integration Approach:**

```python
# feedspine/search/elasticsearch.py (already planned)

from elasticsearch import AsyncElasticsearch
from feedspine.protocols import SearchBackend

class ElasticsearchSearch(SearchBackend):
    def __init__(self, hosts: list[str], index: str = "feedspine"):
        self.client = AsyncElasticsearch(hosts)
        self.index = index
    
    async def index(
        self, 
        record_id: str, 
        content: dict,
        metadata: dict | None = None
    ) -> None:
        await self.client.index(
            index=self.index,
            id=record_id,
            document={
                "content": content,
                "metadata": metadata,
                "indexed_at": datetime.now(UTC).isoformat()
            }
        )
    
    async def search(
        self,
        query: str,
        filters: dict | None = None,
        limit: int = 10
    ) -> SearchResponse:
        body = {
            "query": {
                "bool": {
                    "must": [{"multi_match": {"query": query, "fields": ["content.*"]}}],
                    "filter": self._build_filters(filters) if filters else []
                }
            },
            "size": limit,
            "highlight": {"fields": {"content.*": {}}}
        }
        
        result = await self.client.search(index=self.index, body=body)
        return self._to_search_response(result)
```

**Priority:** High (planned feature)

---

### Meilisearch

**What it is:** Fast, typo-tolerant search engine

**Why integrate:**
- Simpler than Elasticsearch
- Great for user-facing search
- Typo tolerance built-in
- Easy deployment

**Integration Approach:**

```python
# feedspine/search/meilisearch.py

from meilisearch_python_async import Client
from feedspine.protocols import SearchBackend

class MeilisearchSearch(SearchBackend):
    def __init__(self, url: str, api_key: str, index: str = "records"):
        self.client = Client(url, api_key)
        self.index_name = index
    
    async def initialize(self) -> None:
        index = await self.client.get_or_create_index(self.index_name)
        await index.update_searchable_attributes([
            "content.title", "content.company", "content.text"
        ])
        await index.update_filterable_attributes([
            "layer", "metadata.source", "published_at"
        ])
    
    async def search(
        self,
        query: str,
        filters: dict | None = None,
        limit: int = 10
    ) -> SearchResponse:
        index = self.client.index(self.index_name)
        
        filter_str = self._build_filter_string(filters) if filters else None
        
        result = await index.search(
            query,
            filter=filter_str,
            limit=limit,
            attributes_to_highlight=["content.title", "content.text"]
        )
        
        return SearchResponse(
            results=[SearchResult(
                record_id=hit["id"],
                score=1.0,  # Meilisearch doesn't expose scores
                highlights=hit.get("_formatted", {})
            ) for hit in result.hits],
            total_count=result.estimated_total_hits,
            query_time_ms=result.processing_time_ms
        )
```

**Priority:** Medium (simpler alternative to Elasticsearch)

---

### Vector Databases (Chroma, Pinecone, Qdrant)

**What it is:** Databases optimized for similarity search

**Why integrate:**
- Semantic search (not just keywords)
- RAG (Retrieval Augmented Generation)
- Clustering and similarity
- AI/ML workflows

**Integration Approach:**

```python
# feedspine/search/chroma.py

import chromadb
from feedspine.protocols import SearchBackend

class ChromaSearch(SearchBackend):
    """Vector search using Chroma."""
    
    def __init__(self, path: str = ".chroma", collection: str = "feedspine"):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"}
        )
    
    async def index(
        self,
        record_id: str,
        content: dict,
        metadata: dict | None = None
    ) -> None:
        # Convert content to text for embedding
        text = self._content_to_text(content)
        
        self.collection.upsert(
            ids=[record_id],
            documents=[text],
            metadatas=[{**(metadata or {}), "content_keys": list(content.keys())}]
        )
    
    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filters: dict | None = None
    ) -> SearchResponse:
        """Search by semantic similarity."""
        
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=filters
        )
        
        return SearchResponse(
            results=[
                SearchResult(
                    record_id=id,
                    score=1 - dist,  # Convert distance to similarity
                    metadata=meta
                )
                for id, dist, meta in zip(
                    results['ids'][0],
                    results['distances'][0],
                    results['metadatas'][0]
                )
            ],
            search_type=SearchType.SEMANTIC
        )
    
    def _content_to_text(self, content: dict) -> str:
        """Flatten content to searchable text."""
        parts = []
        for key, value in content.items():
            if isinstance(value, str):
                parts.append(f"{key}: {value}")
        return "\n".join(parts)
```

**Priority:** Medium (valuable for AI workflows)

---

## Category 4: Orchestration

### Prefect

**What it is:** Modern workflow orchestration

**Why integrate:**
- Already listed as FeedSpine executor option
- Schedule feed collection
- Handle retries and failures
- Monitoring and observability

**Integration Approach:**

```python
# feedspine/executor/prefect.py (already planned)

from prefect import flow, task
from feedspine import FeedSpine

@task(retries=3, retry_delay_seconds=60)
async def collect_feed(feed_name: str, storage_config: dict):
    """Collect a single feed."""
    async with FeedSpine(**storage_config) as fs:
        fs.register_feed(get_feed_by_name(feed_name))
        result = await fs.collect()
        return result.new_count

@flow(name="feedspine-collection")
async def daily_collection(feeds: list[str]):
    """Daily collection of all registered feeds."""
    results = []
    for feed in feeds:
        count = await collect_feed(feed, STORAGE_CONFIG)
        results.append({"feed": feed, "count": count})
    return results

# Deploy with schedule
if __name__ == "__main__":
    from prefect.deployments import Deployment
    
    deployment = Deployment.build_from_flow(
        flow=daily_collection,
        name="daily-sec-collection",
        parameters={"feeds": ["sec-rss", "sec-full-index"]},
        schedule={"cron": "0 6 * * *"}  # 6 AM daily
    )
    deployment.apply()
```

**Priority:** High (planned feature)

---

### Celery

**What it is:** Distributed task queue

**Why integrate:**
- Scale collection horizontally
- Background processing
- Reliable task execution
- Widely deployed

**Integration Approach:**

```python
# feedspine/executor/celery.py

from celery import Celery
from feedspine import FeedSpine

app = Celery('feedspine', broker='redis://localhost:6379/0')

@app.task(bind=True, max_retries=3)
def collect_feed_task(self, feed_config: dict, storage_config: dict):
    """Celery task for feed collection."""
    import asyncio
    
    async def _collect():
        async with FeedSpine(**storage_config) as fs:
            feed = create_feed_from_config(feed_config)
            fs.register_feed(feed)
            return await fs.collect()
    
    try:
        result = asyncio.run(_collect())
        return {"status": "success", "new_count": result.new_count}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

# Usage
collect_feed_task.delay(
    feed_config={"type": "rss", "url": "https://..."},
    storage_config={"backend": "postgres", "dsn": "..."}
)
```

**Priority:** Medium (Prefect may be preferred)

---

## Category 5: API & Web

### FastAPI

**What it is:** Modern Python web framework

**Why integrate:**
- Expose FeedSpine as API
- Webhook endpoints
- Management interface
- Type-safe with Pydantic

**Integration Approach:**

```python
# feedspine/api/fastapi.py

from fastapi import FastAPI, BackgroundTasks, Query
from feedspine import FeedSpine
from feedspine.models import Record, Layer

def create_app(storage_config: dict) -> FastAPI:
    app = FastAPI(title="FeedSpine API")
    
    @app.on_event("startup")
    async def startup():
        app.state.fs = FeedSpine(**storage_config)
        await app.state.fs.initialize()
    
    @app.on_event("shutdown")
    async def shutdown():
        await app.state.fs.close()
    
    @app.get("/records", response_model=list[Record])
    async def list_records(
        layer: Layer = Query(Layer.GOLD),
        limit: int = Query(100, le=1000),
        offset: int = Query(0)
    ):
        records = []
        async for record in app.state.fs.storage.query(
            layer=layer, limit=limit, offset=offset
        ):
            records.append(record)
        return records
    
    @app.get("/records/{natural_key}")
    async def get_record(natural_key: str):
        return await app.state.fs.storage.get_by_natural_key(natural_key)
    
    @app.post("/collect")
    async def trigger_collection(background_tasks: BackgroundTasks):
        background_tasks.add_task(app.state.fs.collect)
        return {"status": "collection_started"}
    
    @app.get("/search")
    async def search(q: str, limit: int = 10):
        return await app.state.fs.search.search(q, limit=limit)
    
    return app

# Run with: uvicorn feedspine.api.fastapi:create_app --factory
```

**Priority:** High (common deployment pattern)

---

### Streamlit

**What it is:** Data app framework

**Why integrate:**
- Quick dashboards
- Data exploration
- Admin interface
- Prototyping

**Integration Approach:**

```python
# examples/streamlit_dashboard.py

import streamlit as st
import asyncio
from feedspine import FeedSpine
from feedspine.storage.duckdb import DuckDBStorage

st.title("FeedSpine Dashboard")

@st.cache_resource
def get_storage():
    return DuckDBStorage("feedspine.duckdb")

storage = get_storage()

# Sidebar filters
layer = st.sidebar.selectbox("Layer", ["BRONZE", "SILVER", "GOLD"])
source = st.sidebar.text_input("Source filter")

# Main content
col1, col2, col3 = st.columns(3)

async def get_counts():
    counts = {}
    for l in ["BRONZE", "SILVER", "GOLD"]:
        counts[l] = await storage.count(layer=Layer[l])
    return counts

counts = asyncio.run(get_counts())

col1.metric("Bronze Records", counts["BRONZE"])
col2.metric("Silver Records", counts["SILVER"])
col3.metric("Gold Records", counts["GOLD"])

# Recent records
st.subheader("Recent Records")
async def get_recent():
    records = []
    async for r in storage.query(layer=Layer[layer], limit=10):
        records.append(r)
    return records

records = asyncio.run(get_recent())
for record in records:
    with st.expander(record.natural_key):
        st.json(record.content)
```

**Priority:** Low (nice-to-have for demos)

---

## Category 6: Notifications & Alerting

### Slack

**What it is:** Team communication platform

**Why integrate:**
- Alert on new records
- Pipeline failures
- Quality issues
- Team visibility

**Integration Approach:**

```python
# feedspine/notifier/slack.py

from slack_sdk.web.async_client import AsyncWebClient
from feedspine.protocols import Notifier, Notification, Severity

class SlackNotifier(Notifier):
    def __init__(self, token: str, channel: str):
        self.client = AsyncWebClient(token=token)
        self.channel = channel
    
    async def notify(self, notification: Notification) -> None:
        color = self._severity_to_color(notification.severity)
        
        await self.client.chat_postMessage(
            channel=self.channel,
            attachments=[{
                "color": color,
                "title": notification.title,
                "text": notification.message,
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in (notification.metadata or {}).items()
                ],
                "ts": notification.timestamp.timestamp()
            }]
        )
    
    def _severity_to_color(self, severity: Severity) -> str:
        return {
            Severity.INFO: "#36a64f",
            Severity.WARNING: "#ff9800",
            Severity.ERROR: "#f44336",
            Severity.CRITICAL: "#9c27b0",
        }[severity]
```

**Priority:** Medium (planned feature)

---

## Integration Priority Matrix

| Tool | Category | Priority | Effort | Value | Status |
|------|----------|----------|--------|-------|--------|
| **DuckDB** | Analytics | P0 | Low | High | ✅ Done |
| **Elasticsearch** | Search | P1 | Medium | High | ✅ Done |
| **FastAPI** | API | P1 | Low | High | ✅ Done |
| **Prefect** | Orchestration | P1 | Medium | High | ⏳ Planned |
| **Slack** | Notifications | P2 | Low | Medium | ⏳ Planned |
| **Chroma** | Vector Search | P2 | Medium | Medium | ⏳ Planned |
| **Meilisearch** | Search | P2 | Low | Medium | ⏳ Planned |
| **Great Expectations** | Data Quality | P2 | Medium | Medium | ⏳ Planned |
| **Polars** | Analytics | P3 | Low | Low | ⏳ Planned |
| **Celery** | Orchestration | P3 | Medium | Low | ⏳ Planned |
| **Trustfall** | Query | P3 | High | Medium | ⏳ Planned |
| **Streamlit** | Dashboard | P4 | Low | Low | ⏳ Planned |

---

## Recommended Integration Roadmap

### Phase 1: Core Integrations ✅ COMPLETE
- [x] Memory storage
- [x] SQLite storage
- [x] DuckDB storage (38 tests)
- [x] Basic FastAPI template (17 tests)

### Phase 2: Search & Scale (Current)
- [x] Elasticsearch search backend (18 tests)
- [ ] Prefect executor
- [ ] Slack notifications

### Phase 3: Advanced Features (Future)
- [ ] Meilisearch search backend
- [ ] Chroma vector search
- [ ] Great Expectations integration
- [ ] Celery executor

### Phase 4: Nice-to-Have (Eventually)
- [ ] Trustfall query layer
- [ ] Streamlit dashboard template
- [ ] Polars transformations

---

## Conclusion

FeedSpine's value is enhanced by integrations that:

1. **Extend query capabilities** (DuckDB, Elasticsearch, Trustfall)
2. **Enable production operations** (Prefect, Slack, FastAPI)
3. **Improve data quality** (Great Expectations)
4. **Enable AI workflows** (Chroma, vector search)

Focus on **high-value, low-effort** integrations first (DuckDB, FastAPI), then build out based on user demand.
