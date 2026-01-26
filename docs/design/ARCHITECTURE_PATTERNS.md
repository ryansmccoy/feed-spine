# Architecture Patterns Analysis

## Overview

This document analyzes architectural patterns from successful data tools that FeedSpine has adopted, could adopt, or has intentionally avoided. Understanding these patterns helps explain FeedSpine's design decisions and identifies potential improvements.

---

## Pattern 1: Protocol-Based Design

### Where It's Used

| Project | Implementation | Success Level |
|---------|----------------|---------------|
| **FeedSpine** | Python `typing.Protocol` | ✅ Core design |
| **FastAPI** | Dependencies, Pydantic | ✅ Very successful |
| **Zope/Pyramid** | `zope.interface` | ✅ Battle-tested |
| **SQLAlchemy 2.0** | Type hints, protocols | ✅ Modern approach |

### Pattern Description

Define interfaces as protocols (structural subtyping) rather than abstract base classes (nominal subtyping):

```python
# Protocol approach (FeedSpine uses this)
from typing import Protocol

class StorageBackend(Protocol):
    """Any class with these methods works."""
    
    async def store(self, record: Record) -> None: ...
    async def get(self, record_id: str) -> Record | None: ...

# Usage - no inheritance required
class MyStorage:  # Just implement the methods
    async def store(self, record: Record) -> None:
        # Custom implementation
        pass
    
    async def get(self, record_id: str) -> Record | None:
        return None

# Type checker accepts MyStorage as StorageBackend
def use_storage(storage: StorageBackend): ...
use_storage(MyStorage())  # ✅ Works
```

### Benefits FeedSpine Gets

1. **No framework lock-in** - Users don't inherit from FeedSpine classes
2. **Easy testing** - Mock any component trivially
3. **Gradual adoption** - Use only what you need
4. **Type safety** - IDE/mypy validates compatibility

### Lessons from FastAPI

FastAPI's dependency injection shows how protocols enable composition:

```python
# FastAPI pattern
from fastapi import Depends

def get_db():
    return Database()

@app.get("/items")
def read_items(db = Depends(get_db)):
    return db.query()

# FeedSpine could adopt similar DI
from feedspine import Depends

async def get_storage():
    return SQLiteStorage("data.db")

@pipeline.step
async def collect(storage = Depends(get_storage)):
    # storage is injected
    pass
```

### Potential FeedSpine Enhancement

```python
# Current FeedSpine
async with FeedSpine(storage=SQLiteStorage(...)) as fs:
    pass

# Enhanced with DI container (future consideration)
from feedspine import Container, inject

container = Container()
container.register(StorageBackend, SQLiteStorage("data.db"))
container.register(SearchBackend, ElasticsearchSearch(...))

@inject(container)
async def my_pipeline(storage: StorageBackend, search: SearchBackend):
    # Dependencies injected automatically
    pass
```

---

## Pattern 2: Medallion Architecture

### Where It's Used

| Project | Implementation | Success Level |
|---------|----------------|---------------|
| **FeedSpine** | Bronze/Silver/Gold layers | ✅ Core design |
| **Databricks** | Delta Lake medallion | ✅ Industry standard |
| **Azure Synapse** | Raw/Curated/Workspace | ✅ Enterprise |
| **dbt** | Staging/Intermediate/Marts | ✅ Transform layer |

### Pattern Description

Data flows through quality tiers with clear semantics:

```
┌─────────────────────────────────────────────────────────────┐
│  RAW DATA                                                    │
│  (Bronze Layer)                                              │
│  - Exactly as received                                       │
│  - No transformations                                        │
│  - Source of truth                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Validation
┌─────────────────────────────────────────────────────────────┐
│  CLEANED DATA                                                │
│  (Silver Layer)                                              │
│  - Validated schema                                          │
│  - Standardized formats                                      │
│  - Deduplicated                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Enrichment
┌─────────────────────────────────────────────────────────────┐
│  ENRICHED DATA                                               │
│  (Gold Layer)                                                │
│  - Business logic applied                                    │
│  - Aggregations computed                                     │
│  - Ready for consumption                                     │
└─────────────────────────────────────────────────────────────┘
```

### FeedSpine Implementation

```python
from feedspine.models import Layer, Record

# Data enters at Bronze
bronze_record = Record.from_candidate(candidate, layer=Layer.BRONZE)
await storage.store(bronze_record)

# Validation promotes to Silver
if validate(bronze_record):
    silver_record = bronze_record.promote(
        Layer.SILVER,
        enrichments={"validated_at": datetime.now(UTC)}
    )
    await storage.store(silver_record)

# Enrichment promotes to Gold
enriched_content = await enrich(silver_record)
gold_record = silver_record.promote(
    Layer.GOLD,
    enrichments=enriched_content
)
await storage.store(gold_record)
```

### Lessons from Databricks

Databricks' Delta Lake adds:
- **Time travel** - Query any historical version
- **ACID transactions** - Reliable updates
- **Schema enforcement** - Reject bad data

FeedSpine could adopt:
```python
# Potential enhancement: record versioning
@dataclass
class Record:
    version: int = 1
    previous_version_id: str | None = None

# Query historical versions
async for version in storage.get_versions(record_id):
    print(f"Version {version.version}: {version.content}")
```

---

## Pattern 3: Sighting/CDC Pattern

### Where It's Used

| Project | Implementation | Success Level |
|---------|----------------|---------------|
| **FeedSpine** | Sighting records | ✅ Unique approach |
| **Debezium** | Change Data Capture | ✅ Industry standard |
| **Temporal Tables** | SQL:2011 standard | ✅ Database native |
| **Event Sourcing** | Event log | ✅ Architectural pattern |

### Pattern Description

Track not just the data, but when you observed it:

```python
# FeedSpine Sighting
@dataclass
class Sighting:
    sighting_id: UUID
    natural_key: str
    seen_at: datetime
    source: str
    checksum: str | None = None  # Detect changes

# Every time we see a record, log it
sighting = Sighting(
    natural_key="SEC-AAPL-10K-2024",
    seen_at=datetime.now(UTC),
    source="sec-rss-feed"
)
is_first = await storage.record_sighting(sighting)

if is_first:
    # New record - ingest it
    await storage.store(record)
else:
    # Seen before - maybe check for updates
    pass
```

### Benefits

1. **Know when you first saw data** - Audit trail
2. **Track data freshness** - When was it last seen?
3. **Detect source reliability** - Which feeds are active?
4. **Support temporal queries** - "What did we know at time X?"

### Lessons from Debezium

Debezium's CDC captures every change:

```json
{
  "before": {"id": 1, "name": "Old"},
  "after": {"id": 1, "name": "New"},
  "source": {"table": "users", "ts_ms": 1234567890},
  "op": "u"  // update
}
```

FeedSpine could adopt change detection:

```python
# Enhanced sighting with change tracking
@dataclass
class Sighting:
    natural_key: str
    seen_at: datetime
    source: str
    checksum: str  # Hash of content
    change_type: Literal["new", "modified", "unchanged"]

async def record_sighting_with_change(sighting: Sighting) -> ChangeResult:
    previous = await storage.get_latest_sighting(sighting.natural_key)
    
    if previous is None:
        sighting.change_type = "new"
    elif previous.checksum != sighting.checksum:
        sighting.change_type = "modified"
    else:
        sighting.change_type = "unchanged"
    
    await storage.record_sighting(sighting)
    return ChangeResult(change_type=sighting.change_type)
```

---

## Pattern 4: Decorator-Based Sources (dlt Pattern)

### Where It's Used

| Project | Implementation | Success Level |
|---------|----------------|---------------|
| **dlt** | `@dlt.source`, `@dlt.resource` | ✅ Very ergonomic |
| **Prefect** | `@flow`, `@task` | ✅ Popular |
| **Dagster** | `@asset`, `@op` | ✅ Popular |
| **FeedSpine** | Class-based adapters | ⚠️ More verbose |

### dlt Pattern

```python
import dlt

@dlt.source
def github_source(api_token: str):
    return [
        repos(api_token),
        issues(api_token),
    ]

@dlt.resource(primary_key="id", write_disposition="merge")
def repos(api_token: str):
    for repo in fetch_repos(api_token):
        yield repo

# Simple, declarative, type-inferred
pipeline = dlt.pipeline(destination="duckdb")
pipeline.run(github_source(token))
```

### FeedSpine Current Pattern

```python
# FeedSpine uses classes
class GitHubReposAdapter(BaseFeedAdapter):
    def __init__(self, api_token: str):
        super().__init__(name="github-repos")
        self.token = api_token
    
    async def _fetch_items(self):
        for repo in await fetch_repos(self.token):
            yield repo
    
    async def _to_candidate(self, item) -> RecordCandidate:
        return RecordCandidate(
            natural_key=f"github-{item['id']}",
            content=item,
        )
```

### Potential Enhancement: Decorator API

```python
# Future FeedSpine decorator API (additive, not replacement)
from feedspine import feed, resource

@feed(name="github")
def github_feed(api_token: str):
    return [repos(api_token), issues(api_token)]

@resource(natural_key="id")
async def repos(api_token: str):
    async for repo in fetch_repos(api_token):
        yield repo

# Usage
async with FeedSpine() as fs:
    fs.register(github_feed(token="..."))
    await fs.collect()
```

### Why FeedSpine Uses Classes

1. **Explicit over implicit** - Clear what's happening
2. **Protocol compatibility** - Classes implement protocols cleanly
3. **State management** - Rate limiting, connections, etc.
4. **Testing** - Easy to mock/subclass

The decorator approach could be **additive**—simple cases use decorators, complex cases use classes.

---

## Pattern 5: Asset-Centric Design (Dagster Pattern)

### Where It's Used

| Project | Implementation | Success Level |
|---------|----------------|---------------|
| **Dagster** | Software-defined assets | ✅ Revolutionary |
| **dbt** | Models as assets | ✅ SQL standard |
| **Terraform** | Resources as code | ✅ Infrastructure |
| **FeedSpine** | Record-centric | ⚠️ Different model |

### Dagster Pattern

```python
from dagster import asset, Definitions

@asset
def raw_filings():
    """Raw SEC filings - the asset, not the process."""
    return fetch_sec_filings()

@asset(deps=[raw_filings])
def cleaned_filings(raw_filings):
    """Cleaned filings depend on raw."""
    return clean(raw_filings)

@asset(deps=[cleaned_filings])
def filing_analytics(cleaned_filings):
    """Analytics depend on cleaned."""
    return analyze(cleaned_filings)

# Dagster figures out execution order, caching, etc.
defs = Definitions(assets=[raw_filings, cleaned_filings, filing_analytics])
```

### FeedSpine's Record-Centric Model

```python
# FeedSpine focuses on records, not assets
async with FeedSpine() as fs:
    # Collect records
    await fs.collect()
    
    # Records flow through layers
    async for record in fs.storage.query(layer=Layer.BRONZE):
        # Each record is processed
        silver = process(record)
        await fs.storage.store(silver)
```

### Potential Enhancement: Asset View

FeedSpine could add an asset abstraction **on top** of records:

```python
# Future: Asset-like API
from feedspine import asset, FeedSpine

@asset(source="sec-edgar", layer=Layer.BRONZE)
async def sec_filings(fs: FeedSpine):
    """SEC filings as an asset."""
    await fs.collect()
    return await fs.storage.query(layer=Layer.BRONZE)

@asset(deps=[sec_filings], layer=Layer.SILVER)
async def validated_filings(sec_filings):
    """Validated filings."""
    return [f for f in sec_filings if validate(f)]

# Execution graph
pipeline = Pipeline([sec_filings, validated_filings])
await pipeline.materialize()
```

### Why FeedSpine Uses Records

1. **Simpler mental model** - Records are concrete, assets are abstract
2. **Fine-grained control** - Operate on individual records
3. **Streaming-friendly** - Process records as they arrive
4. **Storage-centric** - Records naturally map to storage

For complex pipelines, **use Dagster WITH FeedSpine** rather than rebuilding Dagster's capabilities.

---

## Pattern 6: Schema Inference (dlt Pattern)

### Where It's Used

| Project | Implementation | Success Level |
|---------|----------------|---------------|
| **dlt** | Automatic inference | ✅ Developer-friendly |
| **Airbyte** | JSON Schema discovery | ✅ Standard approach |
| **pandas** | dtype inference | ⚠️ Sometimes surprising |
| **FeedSpine** | Explicit Pydantic | ⚠️ More work |

### dlt Pattern

```python
# dlt infers schema from data
@dlt.resource
def users():
    yield {"id": 1, "name": "Alice", "age": 30}
    yield {"id": 2, "name": "Bob", "age": 25}

# dlt automatically creates:
# - Table with columns (id: INT, name: VARCHAR, age: INT)
# - Handles new columns automatically
# - Manages schema evolution
```

### FeedSpine Pattern

```python
# FeedSpine requires explicit models
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    age: int

# Record content is typed
candidate = RecordCandidate(
    natural_key=f"user-{user.id}",
    content=user.model_dump(),  # Explicit
)
```

### Trade-offs

| Aspect | Schema Inference (dlt) | Explicit Schema (FeedSpine) |
|--------|----------------------|---------------------------|
| Developer speed | ✅ Fast start | ⚠️ More upfront work |
| Data quality | ⚠️ Surprises possible | ✅ Catches errors |
| Schema evolution | ✅ Automatic | ⚠️ Manual migration |
| Documentation | ⚠️ Implicit | ✅ Self-documenting |
| Type safety | ⚠️ Runtime only | ✅ Static analysis |

### Potential Enhancement: Optional Inference

```python
# Future: Opt-in schema inference
from feedspine import infer_schema

@feed(name="flexible-source", schema_mode="infer")
async def flexible_feed():
    """Let FeedSpine infer schema."""
    yield {"any": "data", "here": 123}

# Or explicit mode (current behavior)
@feed(name="strict-source", schema_mode="strict", model=MyModel)
async def strict_feed():
    yield MyModel(field="value")
```

---

## Pattern 7: Streaming Iterators

### Where It's Used

| Project | Implementation | Success Level |
|---------|----------------|---------------|
| **FeedSpine** | `AsyncIterator` | ✅ Native async |
| **Trustfall** | Lazy iterators | ✅ Memory efficient |
| **Kafka Streams** | Continuous processing | ✅ Streaming standard |
| **dlt** | Generators | ✅ Simple |

### Pattern Description

Process data item-by-item rather than loading everything into memory:

```python
# FeedSpine uses AsyncIterator throughout
class FeedAdapter(Protocol):
    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        """Yields candidates one at a time."""
        ...

class StorageBackend(Protocol):
    async def query(self, ...) -> AsyncIterator[Record]:
        """Yields records one at a time."""
        ...

# Memory usage stays constant regardless of data size
async for record in storage.query(layer=Layer.GOLD):
    process(record)  # Only one record in memory
```

### Benefits

1. **Constant memory** - Process unlimited data
2. **Early termination** - Stop when you have enough
3. **Backpressure** - Natural flow control
4. **Composition** - Chain iterators easily

### Lessons from Trustfall

Trustfall's iterator model enables query optimization:

```python
# Trustfall only fetches what's needed
results = execute_query(adapter, schema, query, args)

# If you only need 10 results, only 10 are fetched
for i, result in enumerate(results):
    if i >= 10:
        break  # Underlying iterators stop
    print(result)
```

FeedSpine already does this, but could add more:

```python
# Potential: Query optimization hints
async for record in storage.query(
    layer=Layer.GOLD,
    limit=10,
    _hint="stop_early"  # Tell storage to not over-fetch
):
    process(record)
```

---

## Pattern 8: Plugin/Extension System

### Where It's Used

| Project | Implementation | Success Level |
|---------|----------------|---------------|
| **pytest** | Entry points | ✅ Very successful |
| **FastAPI** | Middleware, dependencies | ✅ Flexible |
| **Airflow** | Providers | ✅ Large ecosystem |
| **FeedSpine** | Protocols (no discovery) | ⚠️ Manual |

### pytest Pattern

```python
# pytest discovers plugins via entry points
# pyproject.toml
[project.entry-points.pytest11]
my_plugin = "my_package.pytest_plugin"

# Plugin code
def pytest_configure(config):
    # Automatically called
    pass
```

### FeedSpine Current State

```python
# Manual registration
from feedspine import FeedSpine
from my_adapter import MyAdapter

fs = FeedSpine()
fs.register_feed(MyAdapter())  # Explicit
```

### Potential Enhancement: Plugin Discovery

```python
# Future: Entry point discovery
# pyproject.toml
[project.entry-points."feedspine.adapters"]
sec = "my_package.adapters:SECAdapter"
rss = "my_package.adapters:RSSAdapter"

[project.entry-points."feedspine.storage"]
duckdb = "my_package.storage:DuckDBStorage"

# FeedSpine discovers plugins
from feedspine import FeedSpine, discover_plugins

plugins = discover_plugins()
# {'adapters': {'sec': SECAdapter, 'rss': RSSAdapter},
#  'storage': {'duckdb': DuckDBStorage}}

# Use discovered plugins
fs = FeedSpine(storage=plugins['storage']['duckdb']())
fs.register_feed(plugins['adapters']['sec']())
```

---

## Patterns Intentionally Avoided

### 1. Heavy Inheritance Hierarchies

**Why avoided:**
- Protocol-based design is more flexible
- No diamond problem
- Easier testing

### 2. Configuration Files for Everything

**Why avoided:**
- Python code is more powerful
- IDE support for code (not YAML)
- Type checking works

```python
# We use Python, not YAML
# NOT: config/feeds.yaml
# YES: 
feeds = [
    RSSAdapter(url="..."),
    APIAdapter(endpoint="..."),
]
```

### 3. Built-in Scheduling

**Why avoided:**
- Scheduling is a solved problem (cron, Prefect)
- Adding it increases complexity
- Users have preferences

### 4. Heavy ORM

**Why avoided:**
- Raw SQL is often simpler
- ORMs add complexity
- Protocol-based storage is flexible enough

---

## Summary: Architecture Decision Record

| Pattern | FeedSpine Status | Rationale |
|---------|------------------|-----------|
| Protocol-based design | ✅ Adopted | Core flexibility |
| Medallion architecture | ✅ Adopted | Data quality |
| Sighting tracking | ✅ Adopted | Unique value |
| Decorator API | 🔜 Consider | Ergonomics |
| Asset-centric | ❌ Avoided | Use Dagster instead |
| Schema inference | 🔜 Consider | Optional feature |
| Streaming iterators | ✅ Adopted | Memory efficiency |
| Plugin discovery | 🔜 Consider | Ecosystem growth |
| Heavy inheritance | ❌ Avoided | Flexibility |
| YAML configuration | ❌ Avoided | Code is better |
| Built-in scheduling | ❌ Avoided | Use Prefect/cron |

FeedSpine's architecture is **intentionally focused**: do feed capture well, integrate with specialized tools for everything else.
