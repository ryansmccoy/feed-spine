"""Query plan analysis and index recommendation utilities.

Extracted from :mod:`feedspine.storage.optimization` for single-responsibility.

Classes
-------
QueryPlan
    Parsed query execution plan.
IndexRecommendation
    Index recommendation based on query patterns.

Functions
---------
analyze_query_plan
    Parse EXPLAIN ANALYZE output into QueryPlan.
recommend_indexes_for_queries
    Analyze query patterns and recommend indexes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
            plan.warnings.append(f"Row estimate off by {ratio:.1f}x - consider running ANALYZE")

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
                recommendations.append(
                    IndexRecommendation(
                        table=table,
                        columns=[f"(content->>'{field}')"],
                        index_type="btree",
                        reason=f"Speed up queries filtering by content.{field}",
                        create_sql=f"CREATE INDEX {idx_name} ON {schema}.{table} ((content->>'{field}'))",
                        estimated_benefit=10.0,
                    )
                )

        # Check for time range queries
        if "captured_at" in query_lower and (">" in query or "<" in query):
            recommendations.append(
                IndexRecommendation(
                    table=table,
                    columns=["captured_at"],
                    index_type="brin",
                    reason="BRIN index for time-range queries (very small)",
                    create_sql=f"CREATE INDEX ix_{table}_captured_brin ON {schema}.{table} USING BRIN (captured_at)",
                    estimated_benefit=5.0,
                )
            )

    return recommendations
