# Framework Design

**Complete FeedSpine framework specification**

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FEEDSPINE ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│      SOURCES        │     │     FEEDSPINE       │     │     CONSUMERS       │
├─────────────────────┤     ├─────────────────────┤     ├─────────────────────┤
│ SEC EDGAR           │     │                     │     │                     │
│ Press Releases      │────▶│  Fetch → Parse →    │────▶│  REST API           │
│ RSS Feeds           │     │  Store → Index      │     │  CLI Client         │
│ News APIs           │     │                     │     │  Python SDK         │
│ Regulatory Filings  │     │  DuckDB + Files     │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

---

## Data Model

### The Two Timestamps

Every record has two critical timestamps:

| Timestamp | Meaning | Use Case |
|-----------|---------|----------|
| `published_at` | When SOURCE published it | "What happened on 2024-01-15?" |
| `captured_at` | When WE captured it | "What's new since my last check?" |

**Why both?**
- Research: Filter by published date
- Trading: Filter by captured date (what moved markets)
- Compliance: Audit trail of when you knew something

### Core Models

```python
@dataclass
class Record:
    """A parsed, deduplicated record from any feed."""
    
    record_id: str
    
    # Identity (deduplication key)
    region: str = "GLOBAL"
    record_type: str = ""             # 'sec.10_k', 'rss.entry'
    unique_id: str = ""               # Natural key (accession, guid)
    
    # Display
    title: str | None = None
    url: str | None = None
    summary: str | None = None
    
    # Entity linkage
    entity_type: str | None = None    # 'cik', 'ticker'
    entity_id: str | None = None
    
    # THE TWO TIMESTAMPS
    published_at: datetime | None = None
    captured_at: datetime
    
    # Flexible data
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def natural_key(self) -> tuple[str, str, str]:
        """The deduplication key."""
        return (self.region, self.record_type, self.unique_id)
```

### DuckDB Schema

```sql
CREATE TABLE records (
    record_id VARCHAR PRIMARY KEY,
    
    -- Identity (deduplication key)
    region VARCHAR NOT NULL DEFAULT 'GLOBAL',
    record_type VARCHAR NOT NULL,
    unique_id VARCHAR NOT NULL,
    
    -- Display
    title VARCHAR,
    url VARCHAR,
    summary VARCHAR,
    
    -- Entity linkage
    entity_type VARCHAR,
    entity_id VARCHAR,
    
    -- THE TWO TIMESTAMPS
    published_at TIMESTAMP,
    captured_at TIMESTAMP NOT NULL,
    
    -- Tracking
    seen_count INTEGER DEFAULT 1,
    last_seen_at TIMESTAMP,
    metadata JSON DEFAULT '{}',
    
    UNIQUE (region, record_type, unique_id)
);

CREATE TABLE content_blobs (
    blob_id VARCHAR PRIMARY KEY,
    record_id VARCHAR REFERENCES records,
    content_hash VARCHAR UNIQUE NOT NULL,
    mime_type VARCHAR,
    size_bytes INTEGER,
    storage_tier VARCHAR NOT NULL,
    storage_path VARCHAR,
    body BLOB,
    captured_at TIMESTAMP NOT NULL
);
```

---

## Storage Tiers

FeedSpine supports hybrid storage based on content size:

| Tier | Size | Storage | Access |
|------|------|---------|--------|
| **database** | < 1 MB | DuckDB BLOB | Inline queries |
| **filesystem** | 1-100 MB | Content-addressed | File read |
| **s3** | > 100 MB | Cloud object storage | Pre-signed URLs |

### Automatic Tier Selection

```python
def get_storage_tier(size_bytes: int, mime_type: str) -> str:
    # MIME types that always go to filesystem
    FILESYSTEM_MIMES = {"application/pdf", "text/html", "text/plain"}
    
    if mime_type in FILESYSTEM_MIMES:
        return "filesystem"
    
    if size_bytes <= 1_000_000:  # 1 MB
        return "database"
    elif size_bytes <= 100_000_000:  # 100 MB
        return "filesystem"
    else:
        return "s3"
```

---

## Feed Adapters

Each feed type has an adapter that handles:

1. **Fetch**: Get raw data from source
2. **Parse**: Convert to `Record` objects
3. **Checkpoint**: Track progress for resume

### Adapter Protocol

```python
class FeedAdapter(Protocol):
    """Protocol for feed adapters."""
    
    feed_type: str
    
    def fetch(self, config: FeedConfig) -> Iterator[FetchResult]:
        """Fetch raw content from feed."""
        ...
    
    def parse(self, result: FetchResult) -> ParseResult:
        """Parse raw content into records."""
        ...
    
    def get_checkpoint(self) -> dict[str, Any]:
        """Get current checkpoint for resume."""
        ...
    
    def set_checkpoint(self, data: dict[str, Any]) -> None:
        """Restore checkpoint from saved state."""
        ...
```

### Built-in Adapters

| Adapter | Feed Type | Example |
|---------|-----------|---------|
| `RSSAdapter` | RSS/Atom | News feeds, blogs |
| `SEC_RSSAdapter` | SEC RSS | EDGAR company feeds |
| `SEC_DailyAdapter` | SEC Daily Index | Daily filings list |
| `SEC_FullAdapter` | SEC Full Index | Historical backfill |
| `APIAdapter` | REST APIs | News APIs, data providers |

---

## Pipeline Processing

### Medallion Architecture

```
┌─────────┐     ┌──────────┐     ┌────────┐
│  BRONZE │────▶│  SILVER  │────▶│  GOLD  │
│  (raw)  │     │ (parsed) │     │(intel) │
└─────────┘     └──────────┘     └────────┘
     │               │               │
     ▼               ▼               ▼
  items          records        insights
```

| Layer | Content | Example |
|-------|---------|---------|
| **Bronze** | Raw fetched content | HTML, XML, JSON |
| **Silver** | Parsed, normalized records | `Record` objects |
| **Gold** | Intelligence/insights | Extracted entities, summaries |

### Pipeline Stages

```python
# Bronze: Fetch
async def fetch_feed(config: FeedConfig) -> list[FetchResult]:
    adapter = get_adapter(config.feed_type)
    return list(adapter.fetch(config))

# Silver: Parse + Dedupe
async def process_results(results: list[FetchResult]) -> list[Record]:
    records = []
    for result in results:
        parsed = adapter.parse(result)
        for record in parsed.records:
            if not store.exists(record.natural_key):
                store.save(record)
                records.append(record)
    return records

# Gold: Extract Intelligence
async def extract_intelligence(records: list[Record]) -> list[Insight]:
    insights = []
    for record in records:
        if record.record_type == "sec.8_k":
            insight = await llm.classify_8k(record)
            insights.append(insight)
    return insights
```

---

## Deduplication

### Natural Key Strategy

Each domain defines a natural key for deduplication:

| Domain | Natural Key | Example |
|--------|-------------|---------|
| SEC EDGAR | `accession_number` | `0000320193-24-000001` |
| RSS | `guid` or `link` | `https://example.com/post/123` |
| News API | `article_id` | `uuid-from-provider` |

### Dedup Flow

```python
def save_record(record: Record) -> bool:
    """Save record, return True if new."""
    
    key = (record.region, record.record_type, record.unique_id)
    
    existing = store.get_by_key(key)
    if existing:
        # Update seen_count, last_seen_at
        existing.seen_count += 1
        existing.last_seen_at = datetime.now()
        store.update(existing)
        return False  # Not new
    else:
        store.insert(record)
        return True  # New record
```

---

## Query Interface

### Time-Based Queries

```python
# What's new since I last checked?
new_filings = store.query(
    record_type="sec.*",
    captured_after=last_check_time
)

# What was published on a specific date?
historical = store.query(
    record_type="sec.10_k",
    published_between=(date(2024, 1, 1), date(2024, 1, 31))
)

# Combined: What did I capture that was published today?
todays_capture = store.query(
    published_on=date.today(),
    captured_after=market_open
)
```

### Entity Queries

```python
# All Apple filings
apple = store.query(entity_id="AAPL")

# All 8-K filings for tech companies
tech_8ks = store.query(
    record_type="sec.8_k",
    entity_id__in=["AAPL", "MSFT", "GOOGL"]
)
```
