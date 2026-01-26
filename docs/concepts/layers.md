# The Layer System

FeedSpine uses a **medallion architecture** with three data quality layers:
Bronze, Silver, and Gold. This pattern comes from modern data engineering
and provides clear semantics for data quality.

## Overview

| Layer | Purpose | Quality | Example |
|-------|---------|---------|---------|
| 🥉 **Bronze** | Raw capture | As-received | Raw JSON from API |
| 🥈 **Silver** | Cleaned data | Validated, normalized | Parsed, deduplicated |
| 🥇 **Gold** | Enriched data | Production-ready | With ML predictions |

## Bronze Layer

The Bronze layer stores data **exactly as received** from the source.

### Characteristics
- Unmodified source data
- May contain duplicates
- May have invalid fields
- Preserves original structure

### When to Use
- Initial feed capture
- Audit trail / compliance
- Debugging source issues
- Replaying failed processing

### Example

```python
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.base import Metadata
from datetime import datetime, timezone

# Raw data from SEC EDGAR
raw_data = {
    "accessionNumber": "0001193125-24-123456",
    "filingDate": "2024-01-15",
    "form": "10-K",
    "size": 1234567,
    # ... exactly as received
}

candidate = RecordCandidate(
    natural_key="0001193125-24-123456",
    published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
    content=raw_data,  # Unmodified!
    metadata=Metadata(source="sec-edgar-feed"),
)

# Bronze record - raw capture
bronze = Record.from_candidate(candidate, record_id="rec-001")
assert bronze.layer == Layer.BRONZE
```

## Silver Layer

The Silver layer contains **cleaned and validated** data.

### Characteristics
- Validated against schema
- Normalized values
- Duplicates removed
- Type-safe fields

### Transformations
- Parse dates from strings
- Normalize company names
- Validate required fields
- Remove invalid records

### Example

```python
from feedspine.models.base import Layer

# Promote with validation and normalization
silver = bronze.promote(
    target_layer=Layer.SILVER,
    enrichments={
        # Normalized values
        "company_name": "Apple Inc.",  # Standardized from "APPLE INC"
        "filing_date": datetime(2024, 1, 15, tzinfo=timezone.utc),
        "form_type": "10-K",
        # Validation flags
        "schema_valid": True,
        "required_fields_present": True,
    },
)
assert silver.layer == Layer.SILVER
```

## Gold Layer

The Gold layer is **production-ready, enriched** data.

### Characteristics
- Business logic applied
- ML/AI enrichments
- Cross-referenced data
- Aggregations computed

### Enrichments
- Sentiment analysis scores
- Category classifications
- Related entity links
- Computed metrics

### Example

```python
# Promote with ML enrichments
gold = silver.promote(
    target_layer=Layer.GOLD,
    enrichments={
        # ML predictions
        "sentiment_score": 0.72,
        "risk_category": "medium",
        # Cross-references
        "related_filings": ["rec-002", "rec-003"],
        # Computed fields
        "revenue_growth_yoy": 0.15,
    },
)
assert gold.layer == Layer.GOLD
```

## Promotion Rules

Records can only move **forward** through layers:

```
Bronze → Silver → Gold  ✅
Gold → Silver           ❌ (raises ValueError)
Bronze → Bronze         ❌ (raises ValueError)
```

### Code

```python
# Valid promotions
silver = bronze.promote(Layer.SILVER)
gold = silver.promote(Layer.GOLD)

# Invalid promotions raise ValueError
try:
    bronze.promote(Layer.BRONZE)  # Same layer
except ValueError as e:
    print(e)  # "Cannot promote to same or lower layer"

try:
    gold.promote(Layer.SILVER)  # Backward
except ValueError as e:
    print(e)  # "Cannot promote to same or lower layer"
```

## Storage Partitioning

Each layer can be stored separately for:
- Different retention policies
- Performance optimization
- Access control
- Cost management

```python
# Query specific layer
bronze_records = storage.query(layer=Layer.BRONZE)
gold_records = storage.query(layer=Layer.GOLD)

# Count by layer
bronze_count = await storage.count(layer=Layer.BRONZE)
gold_count = await storage.count(layer=Layer.GOLD)
```

## Best Practices

### 1. Never Modify Bronze
Bronze is your audit trail. Create a new Silver record instead.

### 2. Validate at Silver Boundary
All validation happens when promoting from Bronze to Silver.

### 3. Keep Gold Lean
Only include fields needed for consumption. Heavy enrichment
can be stored in related tables.

### 4. Use Timestamps
Track when records were promoted for debugging:

```python
print(record.created_at)   # When first captured (Bronze)
print(record.updated_at)   # When last promoted
```

## See Also

- [Architecture Overview](architecture.md)
- [Record API Reference](../reference/feedspine/models/record.md)
- [Storage Backend](../reference/feedspine/protocols/storage.md)
