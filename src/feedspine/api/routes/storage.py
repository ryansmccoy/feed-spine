"""Storage API routes for FeedSpine.

Provides storage backend status and management endpoints:
- Storage status (type, record counts, health)
- Available storage backends list
"""

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from feedspine.api.models import StorageHealthResponse

router = APIRouter(prefix="/api/v1/storage", tags=["storage"])


# =============================================================================
# Models
# =============================================================================


class StorageStatus(BaseModel):
    """Storage backend status."""

    backend_type: str = Field(description="Storage backend class name")
    backend_name: str = Field(description="Storage backend display name")
    is_connected: bool = Field(description="Whether storage is initialized")
    total_records: int = Field(description="Total record count")
    supports_versioning: bool = Field(description="Whether versioning is supported")
    supports_feed_runs: bool = Field(description="Whether feed run tracking is supported")
    supports_observations: bool = Field(description="Whether observations are supported")
    connection_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Connection details (redacted)",
    )


class BackendInfo(BaseModel):
    """Storage backend information."""

    name: str = Field(description="Backend identifier")
    display_name: str = Field(description="Human-readable name")
    description: str = Field(description="Backend description")
    is_available: bool = Field(description="Whether backend dependencies are installed")
    requires_connection: bool = Field(description="Whether connection string is required")
    supports_versioning: bool = Field(description="Whether versioning is supported")
    supports_timeseries: bool = Field(description="Whether time-series features are supported")


class AvailableBackends(BaseModel):
    """List of available storage backends."""

    backends: list[BackendInfo] = Field(description="Available storage backends")
    current_backend: str = Field(description="Currently active backend type")


# =============================================================================
# Backend Registry Helpers
# =============================================================================


def _check_duckdb_available() -> bool:
    """Check if DuckDB is available."""
    try:
        import duckdb  # noqa: F401

        return True
    except ImportError:
        return False


def _check_postgres_available() -> bool:
    """Check if PostgreSQL drivers are available."""
    try:
        import asyncpg  # noqa: F401

        return True
    except ImportError:
        try:
            import psycopg2  # noqa: F401

            return True
        except ImportError:
            return False


def _get_backend_registry() -> list[BackendInfo]:
    """Get storage backend registry with live availability checks."""
    return [
        BackendInfo(
            name="memory",
            display_name="Memory Storage",
            description="In-memory storage for testing and development. Data is lost on restart.",
            is_available=True,
            requires_connection=False,
            supports_versioning=False,
            supports_timeseries=False,
        ),
        BackendInfo(
            name="sqlite",
            display_name="SQLite Storage",
            description="File-based SQLite database. Good for single-user deployments.",
            is_available=True,
            requires_connection=False,
            supports_versioning=True,
            supports_timeseries=False,
        ),
        BackendInfo(
            name="duckdb",
            display_name="DuckDB Storage",
            description="Columnar analytics database. Excellent for analytics and Parquet export.",
            is_available=_check_duckdb_available(),
            requires_connection=False,
            supports_versioning=True,
            supports_timeseries=False,
        ),
        BackendInfo(
            name="postgresql",
            display_name="PostgreSQL Storage",
            description="Production-grade relational database with full feature support.",
            is_available=_check_postgres_available(),
            requires_connection=True,
            supports_versioning=True,
            supports_timeseries=False,
        ),
        BackendInfo(
            name="timescale",
            display_name="TimescaleDB Storage",
            description="Time-series optimized PostgreSQL. Best for high-frequency feeds.",
            is_available=_check_postgres_available(),
            requires_connection=True,
            supports_versioning=True,
            supports_timeseries=True,
        ),
    ]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=StorageStatus)
async def get_storage_status(request: Request) -> StorageStatus:
    """Get current storage backend status.

    Returns information about the active storage backend including:
    - Backend type and name
    - Connection status
    - Record counts
    - Supported features
    """
    storage = request.app.state.storage

    # Determine backend name from class
    backend_type = type(storage).__name__
    backend_name = backend_type.replace("Storage", "").replace("Backend", "")

    # Check supported features
    supports_versioning = hasattr(storage, "get_versions") or hasattr(storage, "get_record_versions")
    supports_feed_runs = hasattr(storage, "get_feed_runs") or hasattr(storage, "list_feed_runs")
    supports_observations = hasattr(storage, "store_observation") or hasattr(storage, "list_observations")

    # Get record count
    try:
        total_records = await storage.count()
        is_connected = True
    except Exception:
        total_records = 0
        is_connected = False

    # Build redacted connection info
    connection_info: dict[str, Any] = {}
    if hasattr(storage, "connection_string"):
        conn = storage.connection_string
        if isinstance(conn, str) and "://" in conn:
            # Redact password from connection string
            parts = conn.split("://", 1)
            if len(parts) == 2 and "@" in parts[1]:
                # Has credentials
                connection_info["protocol"] = parts[0]
                host_part = parts[1].split("@", 1)[-1]
                connection_info["host"] = host_part.split("/")[0] if "/" in host_part else host_part
            else:
                connection_info["protocol"] = parts[0]
    elif hasattr(storage, "db_path"):
        connection_info["path"] = str(storage.db_path)

    return StorageStatus(
        backend_type=backend_type,
        backend_name=backend_name,
        is_connected=is_connected,
        total_records=total_records,
        supports_versioning=supports_versioning,
        supports_feed_runs=supports_feed_runs,
        supports_observations=supports_observations,
        connection_info=connection_info,
    )


@router.get("/backends", response_model=AvailableBackends)
async def get_available_backends(request: Request) -> AvailableBackends:
    """List available storage backends.

    Returns all storage backends that can be used, along with their
    capabilities and whether required dependencies are installed.
    """
    storage = request.app.state.storage
    current_backend = type(storage).__name__.lower().replace("storage", "").replace("backend", "")

    # Map common class names to backend identifiers
    backend_mapping = {
        "memory": "memory",
        "sqlite": "sqlite",
        "sqliterepo": "sqlite",
        "duckdb": "duckdb",
        "postgres": "postgresql",
        "postgresql": "postgresql",
        "asyncpg": "postgresql",
        "timescale": "timescale",
        "timescaledb": "timescale",
    }
    current = backend_mapping.get(current_backend, current_backend)

    return AvailableBackends(
        backends=_get_backend_registry(),
        current_backend=current,
    )


@router.get("/health", response_model=StorageHealthResponse)
async def storage_health(request: Request) -> StorageHealthResponse:
    """Quick storage health check.

    Returns a simple health status for the storage backend.
    """
    storage = request.app.state.storage

    try:
        count = await storage.count()
        return {
            "status": "healthy",
            "backend": type(storage).__name__,
            "record_count": count,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "backend": type(storage).__name__,
            "error": str(e),
        }
