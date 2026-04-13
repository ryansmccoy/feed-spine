"""Shared components for FeedSpine storage backends.

This package contains reusable code that eliminates duplication across
storage backends (SQLite, PostgreSQL, DuckDB, SQLAlchemy).

Components:
    query_builders: SQL query building with backend-specific extensions
    converters: Row ↔ domain model conversions
    validators: Input validation helpers
"""

from feedspine.storage.shared.converters import (
    json_serial,
    parse_datetime,
    record_to_row,
    row_to_record,
    row_to_sighting,
    serialize_datetime,
    sighting_to_row,
)
from feedspine.storage.shared.query_builders import (
    DuckDBQueryBuilder,
    PostgresQueryBuilder,
    QueryBuilder,
    SQLiteQueryBuilder,
)
from feedspine.storage.shared.validators import (
    sanitize_order_by,
    validate_layer,
    validate_natural_key,
    validate_record,
    validate_sighting,
)

__all__ = [
    # Converters
    "row_to_record",
    "record_to_row",
    "row_to_sighting",
    "sighting_to_row",
    "parse_datetime",
    "serialize_datetime",
    "json_serial",
    # Query builders
    "QueryBuilder",
    "SQLiteQueryBuilder",
    "PostgresQueryBuilder",
    "DuckDBQueryBuilder",
    # Validators
    "validate_record",
    "validate_sighting",
    "validate_layer",
    "validate_natural_key",
    "sanitize_order_by",
]
