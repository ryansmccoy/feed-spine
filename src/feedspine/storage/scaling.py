"""Time-based partitioning and scaling strategy utilities.

Extracted from :mod:`feedspine.storage.optimization` for single-responsibility.

Classes
-------
TimePartition
    Represents a time-based partition.

Functions
---------
generate_monthly_partitions
    Generate monthly partition definitions.
generate_partition_sql
    Generate SQL statements to create partitions.
get_scaling_recommendations
    Get scaling recommendations based on dataset size.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from feedspine.storage.analysis import recommend_indexes_for_queries

# Valid SQL identifier pattern — letters, digits, underscores only
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# =============================================================================
# Time-Based Partitioning Helpers
# =============================================================================


@dataclass
class TimePartition:
    """
    Represents a time-based partition.

    Attributes:
        name: Partition name (e.g., "records_202501")
        start: Partition start (inclusive)
        end: Partition end (exclusive)
    """

    name: str
    start: datetime
    end: datetime

    @property
    def size_days(self) -> int:
        return (self.end - self.start).days


def generate_monthly_partitions(
    start: datetime,
    end: datetime,
    table_prefix: str = "records",
) -> list[TimePartition]:
    """
    Generate monthly partition definitions.

    Args:
        start: First partition start
        end: Last partition end
        table_prefix: Table name prefix

    Returns:
        List of TimePartition objects
    """
    partitions = []
    current = datetime(start.year, start.month, 1)

    while current < end:
        # Calculate next month
        if current.month == 12:
            next_month = datetime(current.year + 1, 1, 1)
        else:
            next_month = datetime(current.year, current.month + 1, 1)

        partitions.append(
            TimePartition(
                name=f"{table_prefix}_{current.strftime('%Y%m')}",
                start=current,
                end=next_month,
            )
        )

        current = next_month

    return partitions


def generate_partition_sql(
    partitions: list[TimePartition],
    schema: str = "feedspine",
    parent_table: str = "records_partitioned",
) -> list[str]:
    """
    Generate SQL statements to create partitions.

    Returns list of CREATE TABLE statements.
    """
    if not _SAFE_IDENTIFIER_RE.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")
    if not _SAFE_IDENTIFIER_RE.match(parent_table):
        raise ValueError(f"Invalid table name: {parent_table!r}")

    statements = []

    for p in partitions:
        if not _SAFE_IDENTIFIER_RE.match(p.name):
            raise ValueError(f"Invalid partition name: {p.name!r}")
        sql = f"""
CREATE TABLE IF NOT EXISTS {schema}.{p.name}
PARTITION OF {schema}.{parent_table}
FOR VALUES FROM ('{p.start.isoformat()}') TO ('{p.end.isoformat()}');
        """.strip()
        statements.append(sql)

    return statements


# =============================================================================
# Scaling Strategies Documentation
# =============================================================================


SCALING_STRATEGIES = """
# FeedSpine Scaling Strategies

## Dataset Size Tiers

### Small (< 1M records, < 10GB)
- Standard PostgreSQL with proper indexes
- No partitioning needed
- Use connection pooling (pool_size=5)

### Medium (1M-100M records, 10GB-500GB)
- Enable partitioning by month
- Add BRIN indexes for time columns
- Use PgBouncer for connection pooling
- Consider TimescaleDB for time-series

### Large (100M+ records, 500GB+)
- TimescaleDB with compression (10x storage savings)
- Horizontal partitioning by feed_id
- Read replicas for analytics queries
- Materialized views for aggregations
- Consider ClickHouse for analytics

## Query Optimization Checklist

1. **Always use cursor pagination** instead of OFFSET
   - OFFSET 1M still scans 1M rows
   - Cursor uses index to skip directly

2. **Index JSONB fields you query**
   ```sql
   CREATE INDEX ix_content_ticker ON records ((content->>'ticker'));
   ```

3. **Use BRIN indexes for time columns**
   - 1000x smaller than B-tree
   - Perfect for append-only data

4. **Batch inserts (1000+ at a time)**
   - 100x faster than individual INSERTs
   - Use COPY for initial loads

5. **Run VACUUM ANALYZE regularly**
   - Updates query planner statistics
   - Reclaims dead tuple space

## TimescaleDB Benefits

For time-series data (observations, events):
- Automatic partitioning (chunks)
- 10x compression for old data
- Continuous aggregates (pre-computed rollups)
- Retention policies (auto-delete old data)

## Memory Tuning

For large datasets:
```
shared_buffers = 25% of RAM (max 8GB)
effective_cache_size = 75% of RAM
work_mem = 64MB-256MB (for sorts/joins)
maintenance_work_mem = 512MB-1GB (for VACUUM)
```

## Monitoring Queries

Check for slow queries:
```sql
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
```

Check table sizes:
```sql
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```
"""


def get_scaling_recommendations(
    record_count: int,
    storage_gb: float,
    query_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """
    Get scaling recommendations based on dataset size.

    Args:
        record_count: Estimated number of records
        storage_gb: Estimated storage in GB
        query_patterns: Common query patterns

    Returns:
        Dict with recommendations
    """
    recommendations: dict[str, Any] = {
        "tier": "small",
        "partitioning": False,
        "timescale": False,
        "read_replicas": False,
        "connection_pooling": "builtin",
        "indexes": [],
        "config_changes": [],
    }

    # Determine tier
    if record_count > 100_000_000 or storage_gb > 500:
        recommendations["tier"] = "large"
        recommendations["partitioning"] = True
        recommendations["timescale"] = True
        recommendations["read_replicas"] = True
        recommendations["connection_pooling"] = "pgbouncer"
        recommendations["config_changes"] = [
            "shared_buffers = 8GB",
            "effective_cache_size = 24GB",
            "work_mem = 256MB",
        ]
    elif record_count > 1_000_000 or storage_gb > 10:
        recommendations["tier"] = "medium"
        recommendations["partitioning"] = True
        recommendations["connection_pooling"] = "pgbouncer"
        recommendations["config_changes"] = [
            "shared_buffers = 2GB",
            "effective_cache_size = 6GB",
            "work_mem = 64MB",
        ]

    # Add index recommendations
    if query_patterns:
        recommendations["indexes"] = recommend_indexes_for_queries(query_patterns)

    return recommendations
