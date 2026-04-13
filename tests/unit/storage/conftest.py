"""Storage-layer test fixtures."""

from __future__ import annotations

import pytest

from feedspine.storage.memory import MemoryStorage


@pytest.fixture
def memory_storage() -> MemoryStorage:
    """Fresh in-memory storage for testing."""
    return MemoryStorage()
