"""
Data Type Enumeration and Storage Optimization Hints.

Defines the five primary data archetypes and their optimal storage characteristics.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any


class DataType(str, Enum):
    """
    Primary data archetypes with different storage/query patterns.
    
    Each type has optimal:
    - Partitioning strategy
    - Index types
    - Compression settings
    - Query patterns
    """
    
    # Measured facts over fiscal periods (EPS, Revenue, etc.)
    # High: versioning, provenance | Low: volume, frequency
    OBSERVATIONS = "observations"
    
    # Point-in-time occurrences (earnings calls, dividends)
    # High: status tracking, calendar queries | Low: volume
    EVENTS = "events"
    
    # Master data (companies, securities, people)
    # High: identity resolution, relationships | Low: change frequency
    ENTITIES = "entities"
    
    # Content blobs with metadata (filings, reports)
    # High: content size | Low: query frequency
    DOCUMENTS = "documents"
    
    # High-frequency time-series (ticks, quotes)
    # High: volume, query speed | Low: versioning needs
    PRICES = "prices"
    
    # Let FeedSpine analyze and choose
    AUTO_DETECT = "auto"
    
    # Generic record storage (current default)
    GENERIC = "generic"


@dataclass(frozen=True)
class DataTypeConfig:
    """
    Storage configuration hints for each data type.
    
    Attributes:
        partition_by: Column to partition by (for large datasets)
        partition_interval: Partition size ('day', 'week', 'month', 'year')
        primary_index: Columns for primary lookup
        secondary_indexes: Additional indexes for common queries
        use_brin: Use BRIN index for time columns (smaller, faster for ordered data)
        use_gin: Use GIN index for JSONB columns
        compression: Enable compression for old data (TimescaleDB)
        compression_after_days: Compress data older than N days
        retention_days: Auto-delete data older than N days (0 = keep forever)
        batch_size: Optimal batch size for inserts
        enable_versioning: Track version history
        enable_supersession: Track supersession chains
    """
    
    data_type: DataType
    partition_by: str | None = None
    partition_interval: str = "month"
    primary_index: tuple[str, ...] = ()
    secondary_indexes: tuple[tuple[str, ...], ...] = ()
    use_brin: bool = False
    use_gin: bool = True
    compression: bool = False
    compression_after_days: int = 7
    retention_days: int = 0
    batch_size: int = 1000
    enable_versioning: bool = True
    enable_supersession: bool = False


# Optimal configurations for each data type
DATA_TYPE_CONFIGS: dict[DataType, DataTypeConfig] = {
    DataType.OBSERVATIONS: DataTypeConfig(
        data_type=DataType.OBSERVATIONS,
        partition_by="captured_at",
        partition_interval="month",
        primary_index=("entity_id", "metric_key", "period_key"),
        secondary_indexes=(
            ("entity_id", "captured_at"),
            ("metric_key", "period_key"),
            ("as_of",),
            ("observation_key",),  # For deduplication
        ),
        use_brin=True,  # Time-ordered data benefits from BRIN
        use_gin=True,   # For JSONB content queries
        compression=True,
        compression_after_days=30,
        retention_days=0,  # Keep forever
        batch_size=5000,
        enable_versioning=True,
        enable_supersession=True,  # Observations can supersede each other
    ),
    
    DataType.EVENTS: DataTypeConfig(
        data_type=DataType.EVENTS,
        partition_by="scheduled_at",
        partition_interval="month",
        primary_index=("entity_id", "event_type", "scheduled_at"),
        secondary_indexes=(
            ("event_type", "status"),
            ("scheduled_at", "status"),  # Calendar queries
            ("entity_id", "fiscal_year", "fiscal_quarter"),
        ),
        use_brin=True,
        use_gin=True,
        compression=True,
        compression_after_days=90,
        retention_days=0,
        batch_size=1000,
        enable_versioning=True,
        enable_supersession=False,  # Events don't supersede, they have status
    ),
    
    DataType.ENTITIES: DataTypeConfig(
        data_type=DataType.ENTITIES,
        partition_by=None,  # Entities don't partition well
        primary_index=("entity_id",),
        secondary_indexes=(
            ("entity_type",),
            ("name",),  # For search
        ),
        use_brin=False,  # Not time-ordered
        use_gin=True,   # For identifier JSONB
        compression=False,
        batch_size=500,
        enable_versioning=True,  # Track name changes, etc.
        enable_supersession=False,
    ),
    
    DataType.DOCUMENTS: DataTypeConfig(
        data_type=DataType.DOCUMENTS,
        partition_by="filed_at",
        partition_interval="month",
        primary_index=("document_id",),
        secondary_indexes=(
            ("entity_id", "form_type"),
            ("accession_number",),  # SEC natural key
            ("filed_at",),
        ),
        use_brin=True,
        use_gin=True,  # For metadata JSONB
        compression=True,
        compression_after_days=7,
        retention_days=0,
        batch_size=100,  # Documents are large
        enable_versioning=False,  # Documents are immutable
        enable_supersession=False,
    ),
    
    DataType.PRICES: DataTypeConfig(
        data_type=DataType.PRICES,
        partition_by="timestamp",
        partition_interval="day",  # Higher granularity for prices
        primary_index=("symbol", "timestamp"),
        secondary_indexes=(
            ("symbol", "exchange"),
        ),
        use_brin=True,
        use_gin=False,  # No JSONB for prices
        compression=True,
        compression_after_days=1,  # Compress quickly
        retention_days=365,  # Consider retention for tick data
        batch_size=100_000,  # High throughput
        enable_versioning=False,  # Ticks are immutable
        enable_supersession=False,
    ),
    
    DataType.GENERIC: DataTypeConfig(
        data_type=DataType.GENERIC,
        partition_by="captured_at",
        partition_interval="month",
        primary_index=("natural_key",),
        secondary_indexes=(
            ("layer",),
            ("captured_at",),
        ),
        use_brin=True,
        use_gin=True,
        compression=False,
        batch_size=1000,
        enable_versioning=True,
        enable_supersession=False,
    ),
}


def get_config(data_type: DataType) -> DataTypeConfig:
    """Get optimal configuration for a data type."""
    return DATA_TYPE_CONFIGS.get(data_type, DATA_TYPE_CONFIGS[DataType.GENERIC])


# Alias for backward compatibility
get_config_for_type = get_config


def get_storage_recommendations(data_type: DataType, estimated_rows: int = 0) -> dict[str, Any]:
    """
    Get storage recommendations for a data type and scale.
    
    Args:
        data_type: Type of data
        estimated_rows: Expected number of rows (for scaling advice)
        
    Returns:
        Dict with recommendations for:
        - backend: Recommended storage backend
        - partitioning: Partitioning strategy
        - indexes: Index recommendations
        - compression: Compression settings
        - batch_size: Optimal batch size
    """
    config = get_config(data_type)
    
    recommendations = {
        "backend": "sqlite" if estimated_rows < 1_000_000 else "postgresql",
        "partitioning": {
            "enabled": config.partition_by is not None and estimated_rows > 10_000_000,
            "column": config.partition_by,
            "interval": config.partition_interval,
        },
        "indexes": {
            "primary": list(config.primary_index),
            "secondary": [list(idx) for idx in config.secondary_indexes],
            "use_brin": config.use_brin and estimated_rows > 1_000_000,
            "use_gin": config.use_gin,
        },
        "compression": {
            "enabled": config.compression and estimated_rows > 1_000_000,
            "after_days": config.compression_after_days,
        },
        "batch_size": config.batch_size,
        "versioning": config.enable_versioning,
        "supersession": config.enable_supersession,
    }
    
    # Scale-specific recommendations
    if estimated_rows > 1_000_000_000:  # 1B+
        recommendations["backend"] = "timescale"
        recommendations["notes"] = [
            "Use TimescaleDB for automatic partitioning and compression",
            "Consider continuous aggregates for common queries",
            "Enable compression aggressively for older data",
        ]
    elif estimated_rows > 100_000_000:  # 100M+
        recommendations["backend"] = "postgresql"
        recommendations["notes"] = [
            "Use PostgreSQL with partitioning enabled",
            "Consider read replicas for query load",
            "Enable connection pooling (PgBouncer)",
        ]
    elif estimated_rows > 1_000_000:  # 1M+
        recommendations["backend"] = "postgresql"
        recommendations["notes"] = [
            "PostgreSQL with proper indexing should handle well",
            "Consider enabling compression for older data",
        ]
    else:
        recommendations["notes"] = [
            "SQLite is sufficient for this scale",
            "Consider upgrading to PostgreSQL if concurrent access needed",
        ]
    
    return recommendations


def detect_data_type(sample_records: list[dict[str, Any]]) -> DataType:
    """
    Auto-detect data type from sample records.
    
    Looks for characteristic fields:
    - Observations: metric, period, value, as_of
    - Events: event_type, scheduled_at, status
    - Entities: identifiers, entity_type
    - Documents: content, accession_number, form_type
    - Prices: symbol, price, bid, ask, volume
    """
    if not sample_records:
        return DataType.GENERIC
    
    # Check first few records
    samples = sample_records[:10]
    field_counts: dict[str, int] = {}
    
    for record in samples:
        content = record.get("content", record)
        for field in content.keys() if isinstance(content, dict) else []:
            field_counts[field] = field_counts.get(field, 0) + 1
    
    # Scoring based on characteristic fields
    observation_fields = {"metric", "period", "value", "as_of", "entity_id", "observation_type"}
    event_fields = {"event_type", "scheduled_at", "status", "occurred_at", "fiscal_year"}
    entity_fields = {"identifiers", "entity_type", "name", "cik", "lei", "ticker"}
    document_fields = {"accession_number", "form_type", "filed_at", "content_url", "exhibits"}
    price_fields = {"symbol", "price", "bid", "ask", "volume", "timestamp", "exchange"}
    
    def score(characteristic_fields: set[str]) -> int:
        return sum(field_counts.get(f, 0) for f in characteristic_fields)
    
    scores = {
        DataType.OBSERVATIONS: score(observation_fields),
        DataType.EVENTS: score(event_fields),
        DataType.ENTITIES: score(entity_fields),
        DataType.DOCUMENTS: score(document_fields),
        DataType.PRICES: score(price_fields),
    }
    
    best = max(scores, key=scores.get)  # type: ignore
    if scores[best] == 0:
        return DataType.GENERIC
    
    return best
