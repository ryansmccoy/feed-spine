"""Storage backend implementations.

All storage backends auto-create their schema on initialize().
Just pass a connection/path and call initialize() - no manual setup needed.

Quick Start:
    # Easiest - auto-detect backend from connection string
    from feedspine.storage import create_storage

    storage = create_storage("sqlite:///feeds.db")      # SQLite
    storage = create_storage("postgresql://localhost/db")  # PostgreSQL
    storage = create_storage("memory://")                # In-memory

    await storage.initialize()  # Auto-creates schema

Repository Pattern (spine-core style):
    >>> import sqlite3
    >>> from feedspine.storage import FeedRepository, SQLiteDialect
    >>> conn = sqlite3.connect(":memory:")
    >>> conn.row_factory = sqlite3.Row
    >>> repo = FeedRepository(conn, SQLiteDialect())
    >>> repo.ensure_schema()

    Or with SQLAlchemy:
    >>> from sqlalchemy.orm import Session
    >>> from feedspine.storage import FeedRepository, PostgreSQLDialect
    >>> repo = FeedRepository.from_session(session, PostgreSQLDialect())

Direct Backend Usage:
    >>> from feedspine.storage import SQLiteStorage
    >>> storage = SQLiteStorage("feeds.db")
    >>> await storage.initialize()

Docker PostgreSQL:
    # Start database
    cd feedspine/docker && docker compose up -d postgres

    # Connect
    storage = create_storage("postgresql://user:password@localhost:5432/feedspine")

Environment Variables:
    export FEEDSPINE_DATABASE_URL=postgresql://localhost/feedspine
    storage = storage_from_env()
"""

# Dialect + Repository (always available — no external deps)
from feedspine.storage.dialect import (
    Dialect,
    PostgreSQLDialect,
    SQLiteDialect,
    get_dialect,
)
from feedspine.storage.feed_repository import FeedRepository
from feedspine.storage.memory import MemoryStorage
from feedspine.storage.repository import (
    BaseRepository,
    Connection,
    SAConnectionBridge,
)
from feedspine.storage.repository_backend import RepositoryStorageBackend

__all__ = [
    "MemoryStorage",
    # Dialect
    "Dialect",
    "SQLiteDialect",
    "PostgreSQLDialect",
    "get_dialect",
    # Repository
    "BaseRepository",
    "Connection",
    "SAConnectionBridge",
    "FeedRepository",
    "RepositoryStorageBackend",
]

# Storage factory (always available)
try:
    from feedspine.storage.factory import (
        StorageEnvironment,
        StorageOptions,
        create_storage,
        detect_storage_type,
        get_docker_connection_string,
        storage_from_env,
    )

    __all__.extend(
        [
            "create_storage",
            "storage_from_env",
            "StorageOptions",
            "StorageEnvironment",
            "detect_storage_type",
            "get_docker_connection_string",
        ]
    )
except ImportError:
    create_storage = None  # type: ignore[misc,assignment]
    storage_from_env = None  # type: ignore[misc,assignment]
    StorageOptions = None  # type: ignore[misc,assignment]

# SQLite storage (stdlib - always available)
try:
    from feedspine.storage.backends.sqlite import SQLiteStorage as _SQLiteStorage

    SQLiteStorage = _SQLiteStorage
    __all__.append("SQLiteStorage")
except ImportError:
    SQLiteStorage = None  # type: ignore[misc,assignment]

# PostgreSQL storage (requires asyncpg) - uses shared components
try:
    from feedspine.storage.backends.postgres import PostgresStorage as _PostgresStorage

    PostgresStorage = _PostgresStorage
    __all__.append("PostgresStorage")
except ImportError:
    PostgresStorage = None  # type: ignore[misc,assignment]

# StorageConfig (always available)
from feedspine.core.storage_config import StorageConfig

__all__.append("StorageConfig")

# DuckDB storage (requires duckdb) - uses shared components
try:
    from feedspine.storage.backends.duckdb import DuckDBStorage as _DuckDBStorage

    DuckDBStorage = _DuckDBStorage
    __all__.append("DuckDBStorage")
except ImportError:
    DuckDBStorage = None  # type: ignore[misc,assignment]

# Query optimization utilities
try:
    from feedspine.storage.optimization import (
        SCALING_STRATEGIES,
        BatchConfig,
        Cursor,
        IndexRecommendation,
        Page,
        QueryPlan,
        TimePartition,
        analyze_query_plan,
        batch_iterator,
        generate_monthly_partitions,
        generate_partition_sql,
        get_scaling_recommendations,
        paginate_with_cursor,
        process_in_batches,
        recommend_indexes_for_queries,
    )

    __all__.extend(
        [
            "Cursor",
            "Page",
            "paginate_with_cursor",
            "BatchConfig",
            "batch_iterator",
            "process_in_batches",
            "TimePartition",
            "generate_monthly_partitions",
            "get_scaling_recommendations",
        ]
    )
except ImportError:
    pass

# SQLAlchemy models (requires sqlalchemy)
try:
    from feedspine.storage.models import (
        Base,
        FeedRunModel,
        MetadataModel,
        RecordModel,
        RecordVersionModel,
        SightingModel,
        create_all_tables,
        create_partition,
        create_partitioned_records_table,
        create_timescale_hypertable,
    )

    __all__.extend(
        [
            "Base",
            "RecordModel",
            "create_all_tables",
            "create_partition",
            "create_timescale_hypertable",
        ]
    )
except ImportError:
    pass
# Data type configurations
try:
    from feedspine.storage.data_types import (
        DATA_TYPE_CONFIGS,
        DataType,
        DataTypeConfig,
        get_config,
        get_storage_recommendations,
    )

    __all__.extend(
        [
            "DataType",
            "DataTypeConfig",
            "DATA_TYPE_CONFIGS",
            "get_config",
            "get_storage_recommendations",
        ]
    )
except ImportError:
    pass

# Observation storage (specialized for financial observations)
try:
    from feedspine.storage.observations import ObservationStorage

    __all__.append("ObservationStorage")
except ImportError:
    ObservationStorage = None  # type: ignore[misc,assignment]
