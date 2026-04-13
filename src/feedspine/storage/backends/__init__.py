"""Refactored storage backends for FeedSpine.

This package contains the refactored storage backend implementations
that use shared components to eliminate code duplication.

Backends:
    sqlite: SQLite storage (zero-config, embedded)
    postgres: PostgreSQL storage (production-grade)
    duckdb: DuckDB storage (analytics-focused)
    sqlalchemy: SQLAlchemy-based storage (ORM flexibility)
    memory: In-memory storage (testing)
"""

__all__: list[str] = []

# SQLite storage (stdlib - always available)
from feedspine.storage.backends.sqlite import SQLiteStorage

__all__.append("SQLiteStorage")

# PostgreSQL storage (requires asyncpg)
try:
    from feedspine.storage.backends.postgres import PostgresStorage

    __all__.append("PostgresStorage")
except ImportError:
    PostgresStorage = None  # type: ignore[misc,assignment]

# DuckDB storage (requires duckdb)
try:
    from feedspine.storage.backends.duckdb import DuckDBStorage

    __all__.append("DuckDBStorage")
except ImportError:
    DuckDBStorage = None  # type: ignore[misc,assignment]
