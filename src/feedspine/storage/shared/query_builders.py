"""Shared query building logic for FeedSpine storage backends.

This module provides a base QueryBuilder class with common SQL logic,
plus backend-specific subclasses that handle dialect differences:
- SQLiteQueryBuilder: json_extract, INSERT OR IGNORE
- PostgresQueryBuilder: JSONB operators, ON CONFLICT
- DuckDBQueryBuilder: JSON path, analytical functions

By extracting query building, we eliminate ~200 lines of duplication
per backend (~800 lines total).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# Valid SQL identifier pattern — letters, digits, underscores only
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Valid JSON path segment — alphanumeric + underscores + hyphens
_SAFE_JSON_PATH_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_\-]*(\.[a-zA-Z_][a-zA-Z0-9_\-]*)*$")


def _validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate a SQL identifier (table, column, schema name).

    Raises:
        ValueError: If the identifier contains unsafe characters.
    """
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL {label}: {name!r}")
    return name


def _validate_json_path(path: str) -> str:
    """Validate a JSON path segment for use in SQL queries.

    Raises:
        ValueError: If the path contains unsafe characters.
    """
    if not _SAFE_JSON_PATH_RE.match(path):
        raise ValueError(f"Invalid JSON path: {path!r}")
    return path


class QueryBuilder:
    """Base query builder with common SQL logic.

    Subclasses override for backend-specific features (JSONB, FTS, etc.).

    This class is designed to be stateless - all state is passed as arguments.
    """

    # SQL dialect placeholder style
    PLACEHOLDER = "?"

    def build_time_range_filter(
        self,
        start_time: datetime | None,
        end_time: datetime | None,
        time_column: str = "captured_at",
    ) -> tuple[str, list[Any]]:
        """Build time range filter clause.

        Args:
            start_time: Start of range (inclusive)
            end_time: End of range (exclusive)
            time_column: Column name for filtering

        Returns:
            Tuple of (WHERE clause, parameters list)
        """
        conditions = []
        params = []

        if start_time:
            conditions.append(f"{time_column} >= {self.PLACEHOLDER}")
            params.append(start_time)

        if end_time:
            conditions.append(f"{time_column} < {self.PLACEHOLDER}")
            params.append(end_time)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    def build_layer_filter(
        self,
        layer: str | None,
        layer_column: str = "layer",
    ) -> tuple[str, list[Any]]:
        """Build layer filter clause.

        Args:
            layer: Layer value (e.g., 'bronze', 'silver', 'gold')
            layer_column: Column name for filtering

        Returns:
            Tuple of (WHERE clause, parameters list)
        """
        if not layer:
            return "1=1", []
        return f"{layer_column} = {self.PLACEHOLDER}", [layer]

    def build_content_filter(
        self,
        filters: dict[str, Any] | None,
        content_column: str = "content",
    ) -> tuple[str, list[Any]]:
        """Build content/JSON filter clause.

        Override in subclasses for backend-specific JSON handling.

        Args:
            filters: Key-value pairs to filter on
            content_column: JSON column name

        Returns:
            Tuple of (WHERE clause, parameters list)
        """
        if not filters:
            return "1=1", []

        conditions = []
        params = []

        for key, value in filters.items():
            # Default: no JSON extraction (subclass should override)
            _validate_identifier(key, "filter column")
            conditions.append(f"{key} = {self.PLACEHOLDER}")
            params.append(value)

        return " AND ".join(conditions), params

    def build_order_by(
        self,
        order_by: str | None,
        default: str = "captured_at DESC",
    ) -> str:
        """Build ORDER BY clause.

        Args:
            order_by: Field to sort by (prefix with - for descending)
            default: Default ordering if none specified

        Returns:
            ORDER BY clause (without 'ORDER BY' prefix)

        Raises:
            ValueError: If order_by contains unsafe characters.
        """
        if not order_by:
            return default

        is_desc = order_by.startswith("-")
        column = order_by[1:] if is_desc else order_by

        # Allow dotted JSON paths (e.g. content.title) but validate each part
        for part in column.split("."):
            if not _SAFE_IDENTIFIER_RE.match(part):
                raise ValueError(f"Invalid order_by column: {order_by!r}")

        direction = "DESC" if is_desc else "ASC"
        return f"{column} {direction}"

    def build_limit_offset(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> str:
        """Build LIMIT/OFFSET clause.

        Args:
            limit: Maximum rows to return
            offset: Number of rows to skip

        Returns:
            LIMIT/OFFSET clause
        """
        clause = ""
        if limit:
            clause += f" LIMIT {int(limit)}"
        if offset:
            clause += f" OFFSET {int(offset)}"
        return clause

    def build_select_query(
        self,
        table: str,
        layer: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[str, list[Any]]:
        """Build complete SELECT query.

        Args:
            table: Table name
            layer: Optional layer filter
            filters: Optional content filters
            order_by: Optional ordering
            limit: Optional row limit
            offset: Optional row offset

        Returns:
            Tuple of (complete SQL query, parameters list)
        """
        _validate_identifier(table, "table")
        params: list[Any] = []
        conditions = ["1=1"]

        # Layer filter
        layer_clause, layer_params = self.build_layer_filter(layer)
        if layer_clause != "1=1":
            conditions.append(layer_clause)
            params.extend(layer_params)

        # Content filter
        content_clause, content_params = self.build_content_filter(filters)
        if content_clause != "1=1":
            conditions.append(content_clause)
            params.extend(content_params)

        # Build query
        sql = f"SELECT * FROM {table} WHERE {' AND '.join(conditions)}"
        sql += f" ORDER BY {self.build_order_by(order_by)}"
        sql += self.build_limit_offset(limit, offset)

        return sql, params

    def build_count_query(
        self,
        table: str,
        layer: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> tuple[str, list[Any]]:
        """Build COUNT query.

        Args:
            table: Table name
            layer: Optional layer filter
            filters: Optional content filters

        Returns:
            Tuple of (SQL query, parameters list)
        """
        _validate_identifier(table, "table")
        params: list[Any] = []
        conditions = ["1=1"]

        # Layer filter
        layer_clause, layer_params = self.build_layer_filter(layer)
        if layer_clause != "1=1":
            conditions.append(layer_clause)
            params.extend(layer_params)

        # Content filter
        content_clause, content_params = self.build_content_filter(filters)
        if content_clause != "1=1":
            conditions.append(content_clause)
            params.extend(content_params)

        sql = f"SELECT COUNT(*) FROM {table} WHERE {' AND '.join(conditions)}"
        return sql, params


class SQLiteQueryBuilder(QueryBuilder):
    """SQLite-specific query builder.

    Features:
    - json_extract() for JSON field access
    - INSERT OR IGNORE/REPLACE for upserts
    """

    def build_content_filter(
        self,
        filters: dict[str, Any] | None,
        content_column: str = "content",
    ) -> tuple[str, list[Any]]:
        """Build JSON content filter using SQLite's json_extract().

        Example:
            filters={"title": "Hello"}
            → "json_extract(content, '$.title') = ?"
        """
        if not filters:
            return "1=1", []

        conditions = []
        params = []

        for key, value in filters.items():
            if key.startswith("content."):
                # JSON field query
                json_path = key.replace("content.", "")
                _validate_json_path(json_path)
                conditions.append(f"json_extract({content_column}, '$.{json_path}') = {self.PLACEHOLDER}")
            elif "." in key:
                # Assume JSON path
                _validate_json_path(key)
                conditions.append(f"json_extract({content_column}, '$.{key}') = {self.PLACEHOLDER}")
            else:
                # Direct column
                _validate_identifier(key, "filter column")
                conditions.append(f"{key} = {self.PLACEHOLDER}")
            params.append(value)

        return " AND ".join(conditions), params

    def build_upsert_sql(
        self,
        table: str,
        columns: list[str],
        conflict_column: str = "natural_key",
        update_columns: list[str] | None = None,
    ) -> str:
        """Build SQLite INSERT OR REPLACE statement.

        Args:
            table: Table name
            columns: Column names for INSERT
            conflict_column: Column to detect conflicts on (unused for SQLite)
            update_columns: Columns to update on conflict (unused for SQLite)

        Returns:
            INSERT OR REPLACE SQL template
        """
        placeholders = ", ".join([self.PLACEHOLDER] * len(columns))
        return f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

    def build_insert_ignore_sql(
        self,
        table: str,
        columns: list[str],
    ) -> str:
        """Build SQLite INSERT OR IGNORE statement."""
        placeholders = ", ".join([self.PLACEHOLDER] * len(columns))
        return f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"


class PostgresQueryBuilder(QueryBuilder):
    """Postgres-specific query builder.

    Features:
    - $1, $2 placeholder style
    - JSONB operators (@>, ->>, etc.)
    - ON CONFLICT for upserts
    - Full-text search support
    """

    PLACEHOLDER = "$"  # Will be expanded to $1, $2, etc.

    def _numbered_placeholder(self, index: int) -> str:
        """Get numbered placeholder ($1, $2, etc.)."""
        return f"${index}"

    def build_content_filter(
        self,
        filters: dict[str, Any] | None,
        content_column: str = "content",
        start_index: int = 1,
    ) -> tuple[str, list[Any], int]:
        """Build JSONB content filter using Postgres operators.

        Args:
            filters: Key-value pairs to filter on
            content_column: JSONB column name
            start_index: Starting parameter index

        Returns:
            Tuple of (WHERE clause, parameters list, next parameter index)
        """
        if not filters:
            return "1=1", [], start_index

        conditions = []
        params = []
        idx = start_index

        for key, value in filters.items():
            if key.startswith("content."):
                # JSON field query using ->>
                json_path = key.replace("content.", "")
                _validate_json_path(json_path)
                conditions.append(f"{content_column}->>'{json_path}' = ${idx}")
            elif "." in key:
                # Assume JSON path
                _validate_json_path(key)
                conditions.append(f"{content_column}->>'{key}' = ${idx}")
            else:
                # Direct column
                _validate_identifier(key, "filter column")
                conditions.append(f"{key} = ${idx}")
            params.append(str(value))
            idx += 1

        return " AND ".join(conditions), params, idx

    def build_jsonb_containment_filter(
        self,
        dimensions: dict[str, str],
        jsonb_column: str = "content",
        param_index: int = 1,
    ) -> tuple[str, dict[str, Any], int]:
        """Build Postgres JSONB containment filter (@>).

        Example:
            dimensions={'service': 'api', 'env': 'prod'}
            → "content @> $1"
            → params = '{"service":"api","env":"prod"}'
        """
        if not dimensions:
            return "1=1", {}, param_index

        import json

        return (
            f"{jsonb_column} @> ${param_index}",
            {"dim_filter": json.dumps(dimensions)},
            param_index + 1,
        )

    def build_fulltext_search(
        self,
        search_query: str,
        fts_column: str = "fts_vector",
        param_index: int = 1,
    ) -> tuple[str, dict[str, str], int]:
        """Build Postgres full-text search clause.

        Args:
            search_query: Search text
            fts_column: Full-text search vector column
            param_index: Parameter index

        Returns:
            Tuple of (WHERE clause, parameters dict, next index)
        """
        return (
            f"{fts_column} @@ plainto_tsquery(${param_index})",
            {"search_query": search_query},
            param_index + 1,
        )

    def build_upsert_sql(
        self,
        table: str,
        schema: str,
        columns: list[str],
        conflict_column: str = "natural_key",
        update_columns: list[str] | None = None,
    ) -> str:
        """Build Postgres INSERT ... ON CONFLICT statement.

        Args:
            table: Table name
            schema: Schema name
            columns: Column names for INSERT
            conflict_column: Column to detect conflicts on
            update_columns: Columns to update on conflict

        Returns:
            INSERT ... ON CONFLICT SQL template
        """
        placeholders = ", ".join([f"${i + 1}" for i in range(len(columns))])
        sql = f"INSERT INTO {schema}.{table} ({', '.join(columns)}) VALUES ({placeholders})"

        if update_columns:
            updates = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            sql += f" ON CONFLICT ({conflict_column}) DO UPDATE SET {updates}"
        else:
            sql += f" ON CONFLICT ({conflict_column}) DO NOTHING"

        return sql


class DuckDBQueryBuilder(QueryBuilder):
    """DuckDB-specific query builder.

    Features:
    - JSON path operators
    - INSERT OR IGNORE/REPLACE
    - Analytical window functions
    - Parquet export support
    """

    def build_content_filter(
        self,
        filters: dict[str, Any] | None,
        content_column: str = "content",
    ) -> tuple[str, list[Any]]:
        """Build JSON content filter using DuckDB's ->> operator.

        Example:
            filters={"title": "Hello"}
            → "content->>'title' = ?"
        """
        if not filters:
            return "1=1", []

        conditions = []
        params = []

        for key, value in filters.items():
            if key.startswith("content."):
                json_path = key.replace("content.", "")
                _validate_json_path(json_path)
                conditions.append(f"{content_column}->>'{json_path}' = {self.PLACEHOLDER}")
            else:
                _validate_json_path(key)
                conditions.append(f"{content_column}->>'{key}' = {self.PLACEHOLDER}")
            params.append(str(value))

        return " AND ".join(conditions), params

    def build_window_function(
        self,
        window_type: str,
        value_column: str,
        partition_by: list[str] | None = None,
        order_by: str = "captured_at",
    ) -> str:
        """Build DuckDB window function for analytics.

        Example:
            window_type='AVG', value_column='value', partition_by=['layer']
            → "AVG(value) OVER (PARTITION BY layer ORDER BY captured_at)"

        Raises:
            ValueError: If any identifier contains unsafe characters.
        """
        # Validate all identifiers to prevent SQL injection
        for ident in [window_type, value_column, order_by]:
            if not _SAFE_IDENTIFIER_RE.match(ident):
                raise ValueError(f"Invalid SQL identifier: {ident!r}")
        if partition_by:
            for col in partition_by:
                if not _SAFE_IDENTIFIER_RE.match(col):
                    raise ValueError(f"Invalid partition column: {col!r}")
            partition = f"PARTITION BY {', '.join(partition_by)} "
        else:
            partition = ""

        return f"{window_type}({value_column}) OVER ({partition}ORDER BY {order_by})"

    def build_approx_percentile(
        self,
        value_column: str,
        percentile: float,
        group_by: list[str] | None = None,
    ) -> str:
        """Build DuckDB approximate percentile aggregation.

        Args:
            value_column: Column to calculate percentile on
            percentile: Percentile value (0.0 to 1.0)
            group_by: Optional grouping columns

        Returns:
            SQL aggregation expression
        """
        group_clause = ""
        if group_by:
            group_clause = f" GROUP BY {', '.join(group_by)}"

        return f"approx_quantile({value_column}, {percentile}){group_clause}"

    def build_parquet_export(
        self,
        query: str,
        output_path: str,
    ) -> str:
        """Build DuckDB COPY ... TO PARQUET statement.

        Args:
            query: SELECT query to export
            output_path: Output file path

        Returns:
            COPY TO PARQUET SQL statement
        """
        return f"COPY ({query}) TO '{output_path}' (FORMAT PARQUET)"

    def build_upsert_sql(
        self,
        table: str,
        columns: list[str],
        on_conflict: str = "replace",
    ) -> str:
        """Build DuckDB INSERT OR REPLACE/IGNORE statement.

        Args:
            table: Table name
            columns: Column names for INSERT
            on_conflict: 'replace', 'ignore', or 'error'

        Returns:
            INSERT SQL template
        """
        placeholders = ", ".join([self.PLACEHOLDER] * len(columns))

        if on_conflict == "replace":
            return f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        elif on_conflict == "ignore":
            return f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        else:
            return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
