"""
Query Optimization Utilities for Large Datasets.

This module provides strategies for handling:
- Millions of records (10M+)
- Gigabytes of storage (100GB+)
- Terabytes of time-series data

Key strategies:
1. Cursor-based pagination (no OFFSET)
2. Partitioning helpers
3. Batch processing
4. Index recommendations
5. Query plan analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Callable, Generic, Iterator, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Cursor-Based Pagination (10x faster than OFFSET for large datasets)
# =============================================================================


@dataclass
class Cursor:
    """
    Opaque cursor for pagination.
    
    Why cursor > OFFSET:
    - OFFSET 1000000 still scans 1M rows
    - Cursor uses index to jump directly
    - Consistent results with concurrent writes
    
    Example:
        cursor = None
        while True:
            page, cursor = await storage.get_page(cursor, limit=100)
            if not page:
                break
            process(page)
    """
    
    key: str
    captured_at: datetime
    
    def encode(self) -> str:
        """Encode cursor to string for API responses."""
        import base64
        import json
        
        data = {
            "k": self.key,
            "t": self.captured_at.isoformat(),
        }
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    
    @classmethod
    def decode(cls, encoded: str) -> "Cursor":
        """Decode cursor from string."""
        import base64
        import json
        
        data = json.loads(base64.urlsafe_b64decode(encoded))
        return cls(
            key=data["k"],
            captured_at=datetime.fromisoformat(data["t"]),
        )


@dataclass
class Page(Generic[T]):
    """
    Page of results with cursor.
    
    Attributes:
        items: List of items in this page
        next_cursor: Cursor for next page (None if last page)
        has_more: Whether more pages exist
        total_estimate: Estimated total count (optional)
    """
    
    items: list[T]
    next_cursor: Cursor | None = None
    has_more: bool = False
    total_estimate: int | None = None


async def paginate_with_cursor(
    query_fn: Callable[[Cursor | None, int], tuple[list[T], bool]],
    cursor: Cursor | None = None,
    page_size: int = 100,
) -> Page[T]:
    """
    Generic cursor-based pagination.
    
    Args:
        query_fn: Function that takes (cursor, limit) and returns (items, has_more)
        cursor: Starting cursor (None for first page)
        page_size: Items per page
    
    Returns:
        Page with items and next cursor
    """
    items, has_more = await query_fn(cursor, page_size + 1)
    
    # Check if there are more results
    if len(items) > page_size:
        items = items[:page_size]
        has_more = True
    
    # Build next cursor from last item
    next_cursor = None
    if has_more and items:
        last = items[-1]
        if hasattr(last, "key") and hasattr(last, "captured_at"):
            next_cursor = Cursor(key=last.key, captured_at=last.captured_at)
    
    return Page(items=items, next_cursor=next_cursor, has_more=has_more)


# =============================================================================
# Batch Processing (Memory-Efficient)
# =============================================================================


@dataclass
class BatchConfig:
    """
    Configuration for batch processing.
    
    Attributes:
        batch_size: Records per batch
        max_memory_mb: Stop if memory exceeds this
        progress_interval: Log progress every N batches
        on_batch_complete: Callback after each batch
    """
    
    batch_size: int = 1000
    max_memory_mb: int = 512
    progress_interval: int = 10
    on_batch_complete: Callable[[int, int], None] | None = None


def batch_iterator(
    items: Iterator[T],
    batch_size: int = 1000,
) -> Iterator[list[T]]:
    """
    Yield items in batches.
    
    Memory-efficient: only holds one batch at a time.
    
    Example:
        for batch in batch_iterator(records, batch_size=1000):
            storage.batch_upsert(batch)
    """
    batch: list[T] = []
    
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    
    if batch:
        yield batch


async def process_in_batches(
    items: Iterator[T],
    processor: Callable[[list[T]], Any],
    config: BatchConfig | None = None,
) -> int:
    """
    Process items in batches with progress tracking.
    
    Args:
        items: Iterator of items to process
        processor: Function to process each batch
        config: Batch configuration
        
    Returns:
        Total items processed
    """
    config = config or BatchConfig()
    total = 0
    batch_num = 0
    
    for batch in batch_iterator(items, config.batch_size):
        await processor(batch)
        total += len(batch)
        batch_num += 1
        
        if config.on_batch_complete:
            config.on_batch_complete(batch_num, total)
        
        if batch_num % config.progress_interval == 0:
            logger.info(f"Processed {total:,} records ({batch_num} batches)")
    
    return total


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
        
        partitions.append(TimePartition(
            name=f"{table_prefix}_{current.strftime('%Y%m')}",
            start=current,
            end=next_month,
        ))
        
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
    statements = []
    
    for p in partitions:
        sql = f"""
CREATE TABLE IF NOT EXISTS {schema}.{p.name}
PARTITION OF {schema}.{parent_table}
FOR VALUES FROM ('{p.start.isoformat()}') TO ('{p.end.isoformat()}');
        """.strip()
        statements.append(sql)
    
    return statements


# =============================================================================
# Query Plan Analysis
# =============================================================================


@dataclass
class QueryPlan:
    """
    Parsed query execution plan.
    
    Attributes:
        total_cost: Estimated total cost
        actual_time_ms: Actual execution time (if ANALYZE)
        rows_estimated: Estimated row count
        rows_actual: Actual row count (if ANALYZE)
        index_used: Whether an index was used
        index_name: Name of index used
        seq_scan: Whether a sequential scan was used
        warnings: Any optimization warnings
    """
    
    total_cost: float = 0.0
    actual_time_ms: float | None = None
    rows_estimated: int = 0
    rows_actual: int | None = None
    index_used: bool = False
    index_name: str | None = None
    seq_scan: bool = False
    warnings: list[str] = field(default_factory=list)


def analyze_query_plan(explain_output: list[dict[str, Any]]) -> QueryPlan:
    """
    Parse EXPLAIN ANALYZE output into QueryPlan.
    
    Usage:
        result = connection.execute(text("EXPLAIN (ANALYZE, FORMAT JSON) SELECT ..."))
        plan = analyze_query_plan(result.fetchone()[0])
    """
    plan = QueryPlan()
    
    if not explain_output:
        return plan
    
    root = explain_output[0].get("Plan", {})
    
    # Extract costs
    plan.total_cost = root.get("Total Cost", 0)
    plan.actual_time_ms = root.get("Actual Total Time")
    plan.rows_estimated = root.get("Plan Rows", 0)
    plan.rows_actual = root.get("Actual Rows")
    
    # Check for index usage
    node_type = root.get("Node Type", "")
    if "Index" in node_type:
        plan.index_used = True
        plan.index_name = root.get("Index Name")
    
    if node_type == "Seq Scan":
        plan.seq_scan = True
        plan.warnings.append("Sequential scan detected - consider adding an index")
    
    # Check for bad estimates
    if plan.rows_actual and plan.rows_estimated:
        ratio = plan.rows_actual / max(plan.rows_estimated, 1)
        if ratio > 10 or ratio < 0.1:
            plan.warnings.append(
                f"Row estimate off by {ratio:.1f}x - consider running ANALYZE"
            )
    
    return plan


# =============================================================================
# Index Recommendations
# =============================================================================


@dataclass
class IndexRecommendation:
    """
    Index recommendation based on query patterns.
    
    Attributes:
        table: Table name
        columns: Columns to index
        index_type: B-tree, GIN, BRIN, etc.
        reason: Why this index helps
        create_sql: SQL to create the index
        estimated_benefit: Expected speedup factor
    """
    
    table: str
    columns: list[str]
    index_type: str = "btree"
    reason: str = ""
    create_sql: str = ""
    estimated_benefit: float = 1.0


def recommend_indexes_for_queries(
    query_patterns: list[str],
    table: str = "records",
    schema: str = "feedspine",
) -> list[IndexRecommendation]:
    """
    Analyze query patterns and recommend indexes.
    
    Args:
        query_patterns: List of common queries
        table: Table name
        schema: Schema name
        
    Returns:
        List of IndexRecommendation objects
    """
    recommendations = []
    
    # Analyze each query pattern
    for query in query_patterns:
        query_lower = query.lower()
        
        # Check for JSONB field access
        if "content->>" in query_lower or "content->" in query_lower:
            # Extract field name
            import re
            match = re.search(r"content->>'(\w+)'", query)
            if match:
                field = match.group(1)
                idx_name = f"ix_{table}_content_{field}"
                recommendations.append(IndexRecommendation(
                    table=table,
                    columns=[f"(content->>'{field}')"],
                    index_type="btree",
                    reason=f"Speed up queries filtering by content.{field}",
                    create_sql=f"CREATE INDEX {idx_name} ON {schema}.{table} ((content->>'{field}'))",
                    estimated_benefit=10.0,
                ))
        
        # Check for time range queries
        if "captured_at" in query_lower and (">" in query or "<" in query):
            recommendations.append(IndexRecommendation(
                table=table,
                columns=["captured_at"],
                index_type="brin",
                reason="BRIN index for time-range queries (very small)",
                create_sql=f"CREATE INDEX ix_{table}_captured_brin ON {schema}.{table} USING BRIN (captured_at)",
                estimated_benefit=5.0,
            ))
    
    return recommendations


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
    recommendations = {
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
