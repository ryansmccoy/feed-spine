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

Direct Backend Usage:
    >>> from feedspine.storage import SQLiteStorage
    >>> storage = SQLiteStorage("feeds.db")
    >>> await storage.initialize()

Docker PostgreSQL:
    # Start database
    cd feedspine/docker && docker compose up -d postgres
    
    # Connect
    storage = create_storage("postgresql://feedspine:feedspine@localhost:5432/feedspine")

Environment Variables:
    export FEEDSPINE_DATABASE_URL=postgresql://localhost/feedspine
    storage = storage_from_env()
"""

from feedspine.storage.memory import MemoryStorage

__all__ = ["MemoryStorage"]

# Storage factory (always available)
try:
    from feedspine.storage.factory import (
        create_storage,
        storage_from_env,
        StorageOptions,
        StorageEnvironment,
        detect_storage_type,
        get_docker_connection_string,
    )
    __all__.extend([
        "create_storage",
        "storage_from_env", 
        "StorageOptions",
        "StorageEnvironment",
        "detect_storage_type",
        "get_docker_connection_string",
    ])
except ImportError:
    create_storage = None  # type: ignore[misc,assignment]
    storage_from_env = None  # type: ignore[misc,assignment]
    StorageOptions = None  # type: ignore[misc,assignment]

# SQLite storage (stdlib - always available)
try:
    from feedspine.storage.sqlite import SQLiteStorage as _SQLiteStorage
    SQLiteStorage = _SQLiteStorage
    __all__.append("SQLiteStorage")
except ImportError:
    SQLiteStorage = None  # type: ignore[misc,assignment]

# PostgreSQL storage (requires asyncpg) - low-level async
try:
    from feedspine.storage.postgres import PostgresStorage as _PostgresStorage
    PostgresStorage = _PostgresStorage
    __all__.append("PostgresStorage")
except ImportError:
    PostgresStorage = None  # type: ignore[misc,assignment]

# SQLAlchemy storage (requires sqlalchemy) - production PostgreSQL
try:
    from feedspine.storage.sqlalchemy_storage import (
        SQLAlchemyStorage as _SQLAlchemyStorage,
        StorageConfig,
    )
    SQLAlchemyStorage = _SQLAlchemyStorage
    __all__.extend(["SQLAlchemyStorage", "StorageConfig"])
except ImportError:
    SQLAlchemyStorage = None  # type: ignore[misc,assignment]
    StorageConfig = None  # type: ignore[misc,assignment]

# DuckDB storage (requires duckdb) - analytics
try:
    from feedspine.storage.duckdb import DuckDBStorage as _DuckDBStorage
    DuckDBStorage = _DuckDBStorage
    __all__.append("DuckDBStorage")
except ImportError:
    DuckDBStorage = None  # type: ignore[misc,assignment]

# Query optimization utilities
try:
    from feedspine.storage.optimization import (
        Cursor,
        Page,
        paginate_with_cursor,
        BatchConfig,
        batch_iterator,
        process_in_batches,
        TimePartition,
        generate_monthly_partitions,
        generate_partition_sql,
        QueryPlan,
        analyze_query_plan,
        IndexRecommendation,
        recommend_indexes_for_queries,
        get_scaling_recommendations,
        SCALING_STRATEGIES,
    )
    __all__.extend([
        "Cursor",
        "Page", 
        "paginate_with_cursor",
        "BatchConfig",
        "batch_iterator",
        "process_in_batches",
        "TimePartition",
        "generate_monthly_partitions",
        "get_scaling_recommendations",
    ])
except ImportError:
    pass

# SQLAlchemy models (requires sqlalchemy)
try:
    from feedspine.storage.models import (
        Base,
        RecordModel,
        SightingModel,
        FeedRunModel,
        RecordVersionModel,
        MetadataModel,
        create_all_tables,
        create_partitioned_records_table,
        create_partition,
        create_timescale_hypertable,
    )
    __all__.extend([
        "Base",
        "RecordModel",
        "create_all_tables",
        "create_partition",
        "create_timescale_hypertable",
    ])
except ImportError:
    pass
# Data type configurations
try:
    from feedspine.storage.data_types import (
        DataType,
        DataTypeConfig,
        DATA_TYPE_CONFIGS,
        get_config_for_type,
        get_storage_recommendations,
    )
    __all__.extend([
        "DataType",
        "DataTypeConfig",
        "DATA_TYPE_CONFIGS",
        "get_config_for_type",
        "get_storage_recommendations",
    ])
except ImportError:
    pass

# Observation storage (specialized for financial observations)
try:
    from feedspine.storage.observation_storage import ObservationStorage
    __all__.append("ObservationStorage")
except ImportError:
    ObservationStorage = None  # type: ignore[misc,assignment]