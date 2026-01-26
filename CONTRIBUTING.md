# Contributing to FeedSpine

Thank you for contributing! This guide ensures consistency across the codebase.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/ryansmccoy/feedspine
cd feedspine

# Install with uv (recommended)
uv sync --all-extras

# Run checks
uv run ruff check src tests
uv run mypy src
uv run pytest
```

## Code Organization

### Directory Structure

Source code and tests **must mirror each other**:

```
src/feedspine/storage/memory.py    →  tests/unit/storage/test_memory.py
src/feedspine/search/sqlite_fts.py →  tests/unit/search/test_sqlite_fts.py
src/feedspine/search/vector/chroma.py → tests/unit/search/vector/test_chroma.py
```

### Module Organization

| Directory | Purpose | Examples |
|-----------|---------|----------|
| `core/` | Framework internals | config, exceptions, logging |
| `models/` | Pydantic data models | Record, Sighting, Task |
| `protocols/` | Abstract interfaces | StorageBackend, SearchBackend |
| `storage/` | Storage implementations | MemoryStorage, PostgresStorage |
| `search/` | Search implementations | SQLiteFTS, ElasticsearchSearch |
| `cache/` | Cache implementations | MemoryCache, RedisCache |
| `executors/` | Executor implementations | SyncExecutor, CeleryExecutor |
| `pipeline/` | Streaming pipeline | Stage, Pipeline, built-in stages |
| `workflow/` | DAG workflows | Workflow, Task, adapters |
| `reader/` | Query interface | CLI, API, ReaderService |

## Naming Conventions

### Files

| Type | Pattern | Example |
|------|---------|---------|
| Module | `snake_case.py` | `memory_storage.py` |
| Test | `test_<module>.py` | `test_memory_storage.py` |
| Protocol | `<concept>.py` | `storage.py`, `search.py` |

### Classes

| Type | Pattern | Example |
|------|---------|---------|
| Protocol | `<Concept>Backend` | `StorageBackend`, `CacheBackend` |
| Implementation | `<Backend><Concept>` | `MemoryStorage`, `RedisCache` |
| Model | `PascalCase` | `Record`, `RecordCandidate` |
| Exception | `<Name>Error` | `StorageError`, `ValidationError` |

### Functions & Tests

| Type | Pattern | Example |
|------|---------|---------|
| Public method | `snake_case` | `get_record()`, `store()` |
| Private method | `_snake_case` | `_validate()` |
| Test class | `Test<Class><Aspect>` | `TestMemoryStorageBasic` |
| Test method | `test_<what>_<condition>` | `test_store_duplicate_returns_false` |

## Code Style

### Type Annotations (Required)

```python
# ✅ Correct
from __future__ import annotations

async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
    ...

# ❌ Wrong - missing annotations
async def get(self, record_id, layer=None):
    ...
```

### Import Order

```python
"""Module docstring."""

from __future__ import annotations

# 1. Standard library
import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

# 2. Third-party
from pydantic import BaseModel, Field

# 3. Local
from feedspine.core.exceptions import StorageError
from feedspine.models import Record

# 4. Type-checking only
if TYPE_CHECKING:
    from feedspine.models import Layer
```

### Docstrings (NumPy Style)

```python
async def store(self, record: Record) -> None:
    """
    Store a record at its specified layer.

    Parameters
    ----------
    record : Record
        The record to store.

    Raises
    ------
    StorageError
        If the storage operation fails.

    Examples
    --------
    >>> await storage.store(record)
    """
```

### Error Handling

```python
# ✅ Correct - specific exception with context
from feedspine.core.exceptions import StorageError

async def store(self, record: Record) -> None:
    try:
        await self._conn.execute(...)
    except DatabaseError as e:
        raise StorageError(f"Failed to store record {record.id}") from e

# ❌ Wrong - bare except, generic exception
try:
    ...
except:
    raise Exception("Failed")
```

## Testing

### Test File Structure

```python
"""Tests for feedspine.storage.memory."""

from __future__ import annotations

import pytest
from feedspine.storage.memory import MemoryStorage
from feedspine.models import Record


# === FIXTURES ===

@pytest.fixture
async def storage() -> MemoryStorage:
    """Fresh storage instance."""
    s = MemoryStorage()
    await s.initialize()
    yield s
    await s.close()


# === TEST CLASSES ===

class TestMemoryStorageBasic:
    """Basic CRUD operations."""

    async def test_store_and_get(self, storage: MemoryStorage) -> None:
        """Can store and retrieve a record."""
        record = make_record()
        await storage.store(record)
        result = await storage.get(record.id)
        assert result == record

    async def test_get_nonexistent_returns_none(self, storage: MemoryStorage) -> None:
        """Getting nonexistent record returns None."""
        result = await storage.get("does-not-exist")
        assert result is None


class TestMemoryStorageEdgeCases:
    """Edge cases and error handling."""

    async def test_store_empty_content(self, storage: MemoryStorage) -> None:
        """Can store record with empty content."""
        ...
```

### Protocol Compliance Tests

All implementations of a protocol should be tested together:

```python
# tests/unit/protocols/test_storage_protocol.py

IMPLEMENTATIONS = [
    pytest.param("memory", id="memory"),
    pytest.param("sqlite", id="sqlite"),
    pytest.param("postgres", marks=pytest.mark.postgres, id="postgres"),
]

@pytest.fixture(params=IMPLEMENTATIONS)
async def storage(request) -> StorageBackend:
    impl = request.param
    backend = create_backend(impl)
    await backend.initialize()
    yield backend
    await backend.close()

class TestStorageProtocolCompliance:
    """All StorageBackend implementations must pass these."""

    async def test_store_and_get(self, storage: StorageBackend) -> None:
        ...
```

## Pull Request Checklist

Before submitting:

- [ ] Code follows naming conventions
- [ ] All functions have type annotations
- [ ] All public functions have docstrings
- [ ] Tests mirror source structure
- [ ] `uv run ruff check src tests` passes
- [ ] `uv run mypy src` passes
- [ ] `uv run pytest` passes
- [ ] Coverage not decreased

## Coverage Requirements

| Module | Minimum |
|--------|---------|
| models/ | 95% |
| protocols/ | 90% |
| storage/ | 85% |
| Overall | 85% |

Run coverage:
```bash
uv run pytest --cov=feedspine --cov-report=term-missing
```
