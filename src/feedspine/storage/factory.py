"""
Storage Factory - Easy storage backend configuration.

Provides a simple interface to configure and create storage backends
with sensible defaults for different deployment scenarios.

Usage:
    from feedspine.storage import create_storage
    
    # Local development (SQLite)
    storage = create_storage("sqlite:///data/feedspine.db")
    
    # Docker PostgreSQL
    storage = create_storage("postgresql://feedspine:feedspine@localhost:5432/feedspine")
    
    # Production with TimescaleDB
    storage = create_storage(
        "postgresql://user:pass@timescale:5432/feedspine",
        use_timescale=True,
        pool_size=20,
    )
    
    # Memory (for testing)
    storage = create_storage("memory://")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

StorageType = Literal["memory", "sqlite", "duckdb", "postgresql", "timescale"]


@dataclass
class StorageOptions:
    """
    Universal storage configuration options.
    
    Works across all backends with sensible defaults.
    
    Attributes:
        # Connection
        pool_size: Connection pool size (0 = no pooling)
        max_overflow: Extra connections beyond pool_size
        connect_timeout: Connection timeout in seconds
        
        # Performance
        batch_size: Records per batch insert
        page_size: Default pagination size
        
        # Features
        auto_migrate: Auto-create/update schema
        use_timescale: Enable TimescaleDB features
        enable_versioning: Track record versions
        
        # Data directory
        data_dir: Base directory for file-based storage
        
        # Logging
        echo_sql: Log SQL statements
        log_slow_queries_ms: Log queries slower than this
    """
    
    # Connection
    pool_size: int = 5
    max_overflow: int = 10
    connect_timeout: int = 30
    
    # Performance
    batch_size: int = 1000
    page_size: int = 100
    
    # Features
    auto_migrate: bool = True
    use_timescale: bool = False
    enable_versioning: bool = True
    
    # Data directory
    data_dir: str | None = None
    
    # Logging
    echo_sql: bool = False
    log_slow_queries_ms: int = 1000
    
    @classmethod
    def for_development(cls) -> "StorageOptions":
        """Development settings: verbose, small pools."""
        return cls(
            pool_size=2,
            batch_size=100,
            echo_sql=True,
            log_slow_queries_ms=100,
        )
    
    @classmethod
    def for_production(cls) -> "StorageOptions":
        """Production settings: larger pools, optimized."""
        return cls(
            pool_size=20,
            max_overflow=30,
            batch_size=5000,
            echo_sql=False,
            log_slow_queries_ms=5000,
        )
    
    @classmethod
    def for_testing(cls) -> "StorageOptions":
        """Test settings: in-memory, no persistence."""
        return cls(
            pool_size=1,
            batch_size=10,
            auto_migrate=True,
            enable_versioning=False,
        )


def detect_storage_type(connection_string: str) -> StorageType:
    """Detect storage type from connection string."""
    if connection_string.startswith("memory://") or connection_string == ":memory:":
        return "memory"
    
    if connection_string.startswith("sqlite://") or connection_string.endswith(".db"):
        return "sqlite"
    
    if connection_string.startswith("duckdb://") or connection_string.endswith(".duckdb"):
        return "duckdb"
    
    if connection_string.startswith(("postgresql://", "postgres://")):
        return "postgresql"
    
    # Default to SQLite for file paths
    return "sqlite"


def create_storage(
    connection_string: str | None = None,
    storage_type: StorageType | None = None,
    options: StorageOptions | None = None,
    **kwargs: Any,
) -> Any:
    """
    Create storage backend from connection string.
    
    Auto-detects backend type from connection string format.
    
    Args:
        connection_string: Database connection string or file path
            - "memory://" -> MemoryStorage
            - "sqlite:///path/to/db.db" -> SQLiteStorage
            - "duckdb:///path/to/db.duckdb" -> DuckDBStorage
            - "postgresql://user:pass@host/db" -> SQLAlchemyStorage
        storage_type: Override auto-detection
        options: StorageOptions instance
        **kwargs: Override specific options
        
    Returns:
        Configured storage backend instance
        
    Examples:
        # Auto-detect SQLite
        storage = create_storage("./data/feeds.db")
        
        # Explicit PostgreSQL
        storage = create_storage(
            "postgresql://localhost/feedspine",
            pool_size=20,
            use_timescale=True,
        )
        
        # Memory storage for testing
        storage = create_storage("memory://")
        
        # From environment
        storage = create_storage()  # Uses FEEDSPINE_DATABASE_URL
    """
    # Get connection string from environment if not provided
    if connection_string is None:
        connection_string = os.environ.get(
            "FEEDSPINE_DATABASE_URL",
            os.environ.get("DATABASE_URL", "memory://")
        )
    
    # Merge options
    if options is None:
        options = StorageOptions(**kwargs)
    else:
        # Override with kwargs
        for key, value in kwargs.items():
            if hasattr(options, key):
                setattr(options, key, value)
    
    # Detect storage type
    if storage_type is None:
        storage_type = detect_storage_type(connection_string)
    
    # Create appropriate backend
    if storage_type == "memory":
        from feedspine.storage.memory import MemoryStorage
        return MemoryStorage()
    
    elif storage_type == "sqlite":
        from feedspine.storage.sqlite import SQLiteStorage
        
        # Extract path from connection string
        if connection_string.startswith("sqlite:///"):
            db_path = connection_string[10:]
        else:
            db_path = connection_string
        
        # Apply data_dir if specified
        if options.data_dir and not os.path.isabs(db_path):
            db_path = os.path.join(options.data_dir, db_path)
        
        return SQLiteStorage(db_path)
    
    elif storage_type == "duckdb":
        from feedspine.storage.duckdb import DuckDBStorage
        
        # Extract path from connection string
        if connection_string.startswith("duckdb:///"):
            db_path = connection_string[10:]
        else:
            db_path = connection_string
        
        # Apply data_dir if specified
        if options.data_dir and not os.path.isabs(db_path):
            db_path = os.path.join(options.data_dir, db_path)
        
        return DuckDBStorage(db_path)
    
    elif storage_type in ("postgresql", "timescale"):
        from feedspine.storage.sqlalchemy_storage import SQLAlchemyStorage, StorageConfig
        
        config = StorageConfig(
            pool_size=options.pool_size,
            max_overflow=options.max_overflow,
            batch_size=options.batch_size,
            echo=options.echo_sql,
            use_timescale=options.use_timescale or storage_type == "timescale",
        )
        
        return SQLAlchemyStorage(connection_string, config=config)
    
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


# =============================================================================
# Environment-based Configuration
# =============================================================================


@dataclass
class StorageEnvironment:
    """
    Storage configuration from environment variables.
    
    Environment Variables:
        FEEDSPINE_DATABASE_URL: Primary database connection
        FEEDSPINE_DATA_DIR: Data directory for file storage
        FEEDSPINE_POOL_SIZE: Connection pool size
        FEEDSPINE_USE_TIMESCALE: Enable TimescaleDB (true/false)
        FEEDSPINE_BATCH_SIZE: Batch size for bulk operations
        FEEDSPINE_ENV: Environment (development/production/test)
    """
    
    database_url: str = field(default_factory=lambda: os.environ.get(
        "FEEDSPINE_DATABASE_URL",
        os.environ.get("DATABASE_URL", "memory://")
    ))
    data_dir: str = field(default_factory=lambda: os.environ.get(
        "FEEDSPINE_DATA_DIR", "./data"
    ))
    pool_size: int = field(default_factory=lambda: int(os.environ.get(
        "FEEDSPINE_POOL_SIZE", "5"
    )))
    use_timescale: bool = field(default_factory=lambda: os.environ.get(
        "FEEDSPINE_USE_TIMESCALE", "false"
    ).lower() == "true")
    batch_size: int = field(default_factory=lambda: int(os.environ.get(
        "FEEDSPINE_BATCH_SIZE", "1000"
    )))
    env: str = field(default_factory=lambda: os.environ.get(
        "FEEDSPINE_ENV", "development"
    ))
    
    def create_storage(self) -> Any:
        """Create storage from environment configuration."""
        if self.env == "production":
            options = StorageOptions.for_production()
        elif self.env == "test":
            options = StorageOptions.for_testing()
        else:
            options = StorageOptions.for_development()
        
        # Override with environment values
        options.data_dir = self.data_dir
        options.pool_size = self.pool_size
        options.use_timescale = self.use_timescale
        options.batch_size = self.batch_size
        
        return create_storage(self.database_url, options=options)


def storage_from_env() -> Any:
    """
    Create storage from environment variables.
    
    Shorthand for StorageEnvironment().create_storage()
    """
    return StorageEnvironment().create_storage()


# =============================================================================
# Docker/Compose Helpers
# =============================================================================


def get_docker_connection_string(
    service: str = "postgres",
    host: str | None = None,
    port: int | None = None,
    database: str = "feedspine",
    user: str = "feedspine",
    password: str = "feedspine",
) -> str:
    """
    Build connection string for Docker Compose services.
    
    Args:
        service: Service name from docker-compose.yml
        host: Override host (default: localhost)
        port: Override port (default: service-specific)
        database: Database name
        user: Database user
        password: Database password
        
    Returns:
        PostgreSQL connection string
    """
    # Default ports for each service
    default_ports = {
        "postgres": 5432,
        "timescale": 5433,
        "pgbouncer": 6432,
    }
    
    host = host or "localhost"
    port = port or default_ports.get(service, 5432)
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# =============================================================================
# Quick Start Examples
# =============================================================================


QUICK_START = """
# FeedSpine Storage Quick Start

## 1. Local Development (SQLite)

```python
from feedspine.storage import create_storage

# Auto-creates database file and schema
storage = create_storage("sqlite:///./data/feeds.db")
await storage.initialize()
```

## 2. Docker PostgreSQL

Start the database:
```bash
cd feedspine/docker
docker compose up -d postgres
```

Connect:
```python
storage = create_storage("postgresql://feedspine:feedspine@localhost:5432/feedspine")
await storage.initialize()
```

## 3. TimescaleDB (Time-Series Optimized)

```bash
cd feedspine/docker
docker compose up -d timescale
```

```python
storage = create_storage(
    "postgresql://feedspine:feedspine@localhost:5433/feedspine",
    use_timescale=True,
)
await storage.initialize()
```

## 4. Production with PgBouncer

```python
storage = create_storage(
    "postgresql://feedspine:feedspine@localhost:6432/feedspine",
    pool_size=0,  # Let PgBouncer handle pooling
)
```

## 5. From Environment Variables

```bash
export FEEDSPINE_DATABASE_URL=postgresql://prod-db:5432/feedspine
export FEEDSPINE_ENV=production
export FEEDSPINE_USE_TIMESCALE=true
```

```python
from feedspine.storage import storage_from_env

storage = storage_from_env()
```

## 6. Custom Data Directory

Mount your data wherever you want:
```bash
export FEEDSPINE_DATA_DIR=/mnt/ssd/feedspine
docker compose up -d
```

Or in code:
```python
storage = create_storage(
    "sqlite:///feeds.db",
    data_dir="/mnt/ssd/feedspine",
)
```
"""
