"""Feed Composition Pattern - Modern alternative to Builder.

This module provides a clean, Pythonic interface for configuring and running
feed collection pipelines without the verbosity of the builder pattern.

The core idea combines:
- Dataclass for configuration (type-safe, IDE-friendly)
- Context manager for lifecycle (Pythonic resource management)
- Functional operators for transformations (composable, testable)

Example:
    >>> import asyncio
    >>> from feedspine.composition import Feed
    >>> from feedspine.storage.memory import MemoryStorage

    Simple usage with context manager:

    >>> async def example():
    ...     from feedspine.composition.testing import MockAdapter
    ...     adapter = MockAdapter(records=[])
    ...     storage = MemoryStorage()
    ...     async with Feed(adapter=adapter, storage=storage) as feed:
    ...         result = await feed.collect()
    ...         print(f"Collected {result.total_processed} records")
    >>> asyncio.run(example())
    Collected 0 records
"""

from __future__ import annotations

from feedspine.composition.config import FeedConfig
from feedspine.composition.feed import Feed, collect
from feedspine.composition.preset import Preset

__all__ = [
    "Feed",
    "FeedConfig",
    "Preset",
    "collect",
]
