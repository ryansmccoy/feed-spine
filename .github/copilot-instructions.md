# GitHub Copilot Instructions for FeedSpine

This file provides context to GitHub Copilot for generating consistent, high-quality code.

## Project Overview

FeedSpine is a **storage-agnostic, executor-agnostic feed capture framework** built with:
- Python 3.11+
- Pydantic 2.x for data models
- Protocol-based design for all extension points
- Async-first architecture
- Medallion architecture (Bronze → Silver → Gold)

## Code Style

### Type Annotations
- **Always** use full type annotations on all functions and methods
- Use `from __future__ import annotations` at the top of every file
- Use `| None` syntax instead of `Optional[T]`
- Use `list[T]` instead of `List[T]` (Python 3.11+ style)

```python
# ✅ Correct
async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:

# ❌ Wrong
async def get(self, record_id, layer=None):
```

### Async Consistency
- All protocol methods are `async`
- All implementations must be `async`
- Use `asyncio` for concurrency, not threading

### Docstrings
Use **Google-style docstrings** with runnable examples (doctests):

```python
async def store(self, record: Record) -> None:
    """Store a record at its specified layer.

    Records are indexed by both ID and natural key for efficient lookup.
    Storing a record with an existing ID will overwrite the previous record.

    Args:
        record: The record to store. Must have valid id and natural_key.

    Raises:
        StorageError: If the storage operation fails.

    Example:
        >>> import asyncio
        >>> from feedspine.storage.memory import MemoryStorage
        >>> from feedspine.models.record import Record, RecordCandidate
        >>> from feedspine.models.base import Metadata
        >>> from datetime import datetime, timezone
        >>>
        >>> async def example():
        ...     storage = MemoryStorage()
        ...     await storage.initialize()
        ...     candidate = RecordCandidate(
        ...         natural_key="test-key",
        ...         published_at=datetime.now(timezone.utc),
        ...         content={"title": "Test"},
        ...         metadata=Metadata(source="test"),
        ...     )
        ...     record = Record.from_candidate(candidate, record_id="r1")
        ...     await storage.store(record)
        ...     exists = await storage.exists("r1")
        ...     await storage.close()
        ...     return exists
        >>>
        >>> asyncio.run(example())
        True

    See Also:
        - :meth:`get`: Retrieve stored records
        - :meth:`delete`: Remove records
    """
```

**Docstring Requirements:**
- All public functions/methods MUST have docstrings
- Public API MUST include `Example:` section with runnable doctests
- Use `Args:`, `Returns:`, `Raises:` sections as needed
- Add `See Also:` for related functions/classes
- Run `uv run pytest --doctest-modules src/` to verify examples

### Imports
Order: stdlib → third-party → local, alphabetically within each group:

```python
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from feedspine.models import Record
from feedspine.protocols import StorageBackend

if TYPE_CHECKING:
    from feedspine.models import Layer
```

## Directory Structure

### Source mirrors tests exactly:
```
src/feedspine/storage/memory.py  →  tests/unit/storage/test_memory.py
src/feedspine/search/vector/chroma.py  →  tests/unit/search/vector/test_chroma.py
```

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Protocol | `<Concept>Backend` | `StorageBackend`, `CacheBackend` |
| Implementation | `<Backend><Concept>` | `MemoryStorage`, `RedisCache` |
| Model | `PascalCase` | `Record`, `RecordCandidate` |
| Exception | `<Name>Error` | `StorageError`, `ValidationError` |
| Test class | `Test<Class><Aspect>` | `TestMemoryStorageBasic` |
| Test method | `test_<what>_<condition>` | `test_store_duplicate_returns_false` |

## Key Patterns

### Protocol Implementation
```python
from feedspine.protocols.storage import StorageBackend

class MemoryStorage(StorageBackend):
    """In-memory storage for testing."""
    
    def __init__(self) -> None:
        self._records: dict[str, Record] = {}
        self._initialized = False
    
    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
    
    async def close(self) -> None:
        self._records.clear()
        self._initialized = False
```

### Pydantic Models
```python
from pydantic import BaseModel, Field, ConfigDict

class Record(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )
    
    id: str = Field(..., description="Unique identifier")
    natural_key: str = Field(..., min_length=1)
```

### Error Handling
```python
from feedspine.core.exceptions import StorageError

async def store(self, record: Record) -> None:
    try:
        # operation
    except SomeError as e:
        raise StorageError(f"Failed to store {record.id}") from e
```

## Testing Patterns

### Test Structure
```python
"""Tests for feedspine.storage.memory."""

import pytest
from feedspine.storage.memory import MemoryStorage

@pytest.fixture
async def storage():
    s = MemoryStorage()
    await s.initialize()
    yield s
    await s.close()

class TestMemoryStorageBasic:
    async def test_store_and_get(self, storage: MemoryStorage) -> None:
        """Store and retrieve works."""
        ...
```

### Protocol Compliance Tests
All implementations of a protocol should pass the same compliance tests.

## Files to Reference

When generating code, reference these files for patterns:
- `src/feedspine/models/record.py` - Pydantic model patterns
- `src/feedspine/protocols/storage.py` - Protocol definition pattern
- `src/feedspine/storage/memory.py` - Implementation pattern
- `tests/unit/storage/test_memory.py` - Test pattern
