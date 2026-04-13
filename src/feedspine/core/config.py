"""FeedSpine configuration.

Application settings loaded from environment variables with ``FEEDSPINE_`` prefix.
Provides typed configuration with Pydantic validation.

Example:
    >>> from feedspine.core.config import get_settings
    >>> settings = get_settings()
    >>> settings.log_level
    'INFO'
    >>> settings.storage
    'memory'
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from spine.core.settings import SpineBaseSettings

    _SETTINGS_BASE = SpineBaseSettings
except ImportError:
    _SETTINGS_BASE = BaseSettings  # type: ignore[assignment]

if TYPE_CHECKING:
    from feedspine.core.storage_config import StorageConfig
    from feedspine.utils.retry import RetryConfig


class FeedSpineSettings(_SETTINGS_BASE):  # type: ignore[misc]
    """Unified FeedSpine settings.

    Loads from environment variables with FEEDSPINE_ prefix.
    Extends SpineBaseSettings for shared host/port/debug/log_level/data_dir.
    """

    model_config = SettingsConfigDict(
        env_prefix="FEEDSPINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Override SpineBaseSettings defaults
    port: int = 11300
    log_format: str = Field(default="json", description="Log format: json or console")
    otel_service_name: str = Field(default="feed-spine", description="Service name for OpenTelemetry")

    # Storage
    storage: str = Field(default="memory", description="Storage backend type (memory, sqlite, duckdb, postgresql)")
    storage_connection: str = Field(default="", description="Storage connection string")
    storage_path: Path = Field(default=Path("./data"), description="Path for file-based storage")

    # Database URLs (optional)
    database_url: str | None = Field(default=None, description="Database connection URL")
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # External service URLs
    capture_spine_url: str = Field(
        default="http://localhost:8200",
        description="Capture-spine API endpoint URL",
    )

    # Collection
    default_batch_size: int = Field(default=100, ge=1, le=10000)
    request_timeout: float = Field(default=30.0, ge=1.0)
    adapter_timeout: float = Field(default=30.0, ge=1.0, description="HTTP timeout for feed adapters")
    rate_limit_delay: float = Field(default=0.1, ge=0.0, description="Delay between requests")
    rate_limit_default: float = Field(default=10.0, ge=0.1, description="Default requests/sec rate limit")

    # Retry
    max_retries: int = Field(default=3, ge=1, description="Maximum retry attempts")
    retry_base_delay: float = Field(default=1.0, ge=0.1, description="Initial retry delay in seconds")
    retry_max_delay: float = Field(default=60.0, ge=1.0, description="Maximum retry delay in seconds")
    retry_exponential_base: float = Field(default=2.0, ge=1.1, description="Exponential backoff multiplier")

    # Storage pool (used by SQLAlchemy backend)
    storage_pool_size: int = Field(default=5, ge=1, description="Connection pool size")
    storage_max_overflow: int = Field(default=10, ge=0, description="Extra connections beyond pool_size")
    storage_pool_timeout: int = Field(default=30, ge=1, description="Pool connection timeout in seconds")
    storage_pool_recycle: int = Field(default=1800, ge=60, description="Recycle connections after N seconds")

    # API Authentication
    api_key: str | None = Field(default=None, description="API key for authentication")
    require_auth: bool = Field(default=False, description="Require authentication for API")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3010,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins.",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into list."""
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def get_retry_config(self) -> RetryConfig:
        """Build a RetryConfig from settings."""
        from feedspine.utils.retry import RetryConfig as _RetryConfig

        return _RetryConfig(
            max_attempts=self.max_retries,
            base_delay=self.retry_base_delay,
            max_delay=self.retry_max_delay,
            exponential_base=self.retry_exponential_base,
        )

    def get_storage_config(self) -> StorageConfig:
        """Build a StorageConfig from settings."""
        from feedspine.core.storage_config import StorageConfig as _StorageConfig

        return _StorageConfig(
            pool_size=self.storage_pool_size,
            max_overflow=self.storage_max_overflow,
            pool_timeout=self.storage_pool_timeout,
            pool_recycle=self.storage_pool_recycle,
            batch_size=self.default_batch_size,
        )


# Backwards-compatible alias
Settings = FeedSpineSettings


@lru_cache(maxsize=1)
def get_settings() -> FeedSpineSettings:
    """Get cached settings singleton."""
    return FeedSpineSettings()
