"""Storage backend implementations."""

from feedspine.storage.memory import MemoryStorage

__all__ = ["MemoryStorage"]

# Optional: DuckDB storage (requires duckdb)
try:
    from feedspine.storage.duckdb import DuckDBStorage as _DuckDBStorage

    DuckDBStorage = _DuckDBStorage
    __all__.append("DuckDBStorage")
except ImportError:
    DuckDBStorage = None  # type: ignore[misc,assignment]
