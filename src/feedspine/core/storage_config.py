"""Storage configuration data holder.

Provides :class:`StorageConfig` with sensible defaults for connection
pooling, batching, and schema management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feedspine.core.config import FeedSpineSettings


class StorageConfig:
    """Storage configuration with sensible defaults.

    Attributes:
        pool_size: Connection pool size (default: 5)
        max_overflow: Extra connections allowed (default: 10)
        pool_timeout: Seconds to wait for connection (default: 30)
        pool_recycle: Recycle connections after N seconds (default: 1800)
        batch_size: Records per batch insert (default: 1000)
        echo: Log SQL statements (default: False)
        schema: Database schema name (default: feedspine)
    """

    def __init__(
        self,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        batch_size: int = 1000,
        echo: bool = False,
        schema: str = "feedspine",
        use_timescale: bool = False,
    ):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.batch_size = batch_size
        self.echo = echo
        self.schema = schema
        self.use_timescale = use_timescale

    @classmethod
    def from_settings(cls, settings: FeedSpineSettings | None = None) -> StorageConfig:
        """Create a StorageConfig from FeedSpineSettings.

        Args:
            settings: Settings instance. If None, uses ``get_settings()``.
        """
        if settings is None:
            from feedspine.core.config import get_settings

            settings = get_settings()
        return settings.get_storage_config()
