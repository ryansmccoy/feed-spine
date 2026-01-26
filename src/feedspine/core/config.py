"""FeedSpine configuration.

Application settings loaded from environment variables with FEEDSPINE_ prefix.

Example:
    >>> from feedspine.core.config import get_settings
    >>> settings = get_settings(log_level="DEBUG")
    >>> settings.log_level
    'DEBUG'
    >>> settings.storage_backend
    'memory'
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Loads from environment variables with FEEDSPINE_ prefix.

    Example:
        >>> from feedspine.core.config import Settings
        >>> s = Settings(database_url="sqlite:///test.db")
        >>> s.database_url
        'sqlite:///test.db'
        >>> s.default_batch_size
        100
    """

    model_config = SettingsConfigDict(
        env_prefix="FEEDSPINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage
    storage_backend: str = Field(default="memory", description="Storage backend type")
    storage_path: Path = Field(default=Path("./data"), description="Path for file-based storage")

    # Database URLs (optional)
    database_url: str | None = Field(default=None, description="Database connection URL")
    redis_url: str | None = Field(default=None, description="Redis connection URL")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or console")

    # Collection
    default_batch_size: int = Field(default=100, ge=1, le=10000)
    request_timeout: float = Field(default=30.0, ge=1.0)
    rate_limit_delay: float = Field(default=0.1, ge=0.0, description="Delay between requests")


def get_settings(**overrides: Any) -> Settings:
    """Get settings with optional overrides.

    Example:
        >>> from feedspine.core.config import get_settings
        >>> s = get_settings(rate_limit_delay=0.5)
        >>> s.rate_limit_delay
        0.5
    """
    return Settings(**overrides)
