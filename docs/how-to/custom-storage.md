# Implement a Custom Storage Backend

This guide shows you how to implement a custom storage backend that integrates
with your existing infrastructure.

## Overview

All storage backends implement the `StorageBackend` protocol. This ensures
consistent behavior across different implementations.

## The StorageBackend Protocol

```python
from typing import Protocol, AsyncIterator
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting
from feedspine.models.base import Layer

class StorageBackend(Protocol):
    """Protocol for storage implementations."""
    
    async def initialize(self) -> None:
        """Initialize the storage connection."""
        ...
    
    async def close(self) -> None:
        """Close the storage connection."""
        ...
    
    async def store(self, record: Record) -> None:
        """Store a record."""
        ...
    
    async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
        """Get a record by ID."""
        ...
    
    async def get_by_natural_key(self, natural_key: str) -> Record | None:
        """Get a record by natural key."""
        ...
    
    async def exists(self, record_id: str, layer: Layer | None = None) -> bool:
        """Check if a record exists."""
        ...
    
    async def exists_by_natural_key(self, natural_key: str) -> bool:
        """Check if a natural key exists."""
        ...
    
    async def delete(self, record_id: str, layer: Layer | None = None) -> bool:
        """Delete a record."""
        ...
    
    async def query(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AsyncIterator[Record]:
        """Query records."""
        ...
    
    async def count(
        self,
        layer: Layer | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records."""
        ...
    
    async def record_sighting(self, sighting: Sighting) -> bool:
        """Record a sighting. Returns True if first time seen."""
        ...
    
    async def get_sightings(self, natural_key: str) -> list[Sighting]:
        """Get sighting history for a natural key."""
        ...
```

## Step-by-Step Implementation

### 1. Create the Class Structure

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator

from feedspine.models.base import Layer
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting

if TYPE_CHECKING:
    import asyncpg


class PostgresStorage:
    """PostgreSQL storage backend using asyncpg."""
    
    def __init__(self, connection_string: str) -> None:
        self._dsn = connection_string
        self._pool: asyncpg.Pool | None = None
```

### 2. Implement Lifecycle Methods

```python
async def initialize(self) -> None:
    """Create connection pool and ensure schema exists."""
    import asyncpg
    
    self._pool = await asyncpg.create_pool(self._dsn)
    await self._ensure_schema()

async def close(self) -> None:
    """Close the connection pool."""
    if self._pool:
        await self._pool.close()
        self._pool = None

async def _ensure_schema(self) -> None:
    """Create tables if they don't exist."""
    async with self._pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY,
                natural_key TEXT NOT NULL,
                layer TEXT NOT NULL,
                content JSONB NOT NULL,
                metadata JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_records_natural_key 
                ON records(natural_key);
            CREATE INDEX IF NOT EXISTS idx_records_layer 
                ON records(layer);
        """)
```

### 3. Implement CRUD Operations

```python
async def store(self, record: Record) -> None:
    """Store or update a record."""
    async with self._pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO records (id, natural_key, layer, content, metadata, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                content = $4,
                metadata = $5,
                layer = $3,
                updated_at = $7
        """, record.id, record.natural_key, record.layer.value,
             record.content, record.metadata.model_dump(),
             record.created_at, record.updated_at)

async def get(self, record_id: str, layer: Layer | None = None) -> Record | None:
    """Retrieve a record by ID."""
    query = "SELECT * FROM records WHERE id = $1"
    params = [record_id]
    
    if layer:
        query += " AND layer = $2"
        params.append(layer.value)
    
    async with self._pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        if row:
            return self._row_to_record(row)
        return None
```

### 4. Implement Query Methods

```python
async def query(
    self,
    layer: Layer | None = None,
    filters: dict[str, Any] | None = None,
    order_by: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AsyncIterator[Record]:
    """Query records with filters and pagination."""
    query = "SELECT * FROM records WHERE 1=1"
    params = []
    param_idx = 1
    
    if layer:
        query += f" AND layer = ${param_idx}"
        params.append(layer.value)
        param_idx += 1
    
    # Add more filter handling as needed
    
    if order_by:
        # Validate order_by to prevent SQL injection
        direction = "DESC" if order_by.startswith("-") else "ASC"
        field = order_by.lstrip("-")
        if field in ("created_at", "updated_at", "natural_key"):
            query += f" ORDER BY {field} {direction}"
    
    query += f" LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])
    
    async with self._pool.acquire() as conn:
        async for row in conn.cursor(query, *params):
            yield self._row_to_record(row)
```

## Testing Your Implementation

Use the existing test patterns from `tests/unit/storage/test_memory.py`:

```python
"""Tests for PostgresStorage."""
import pytest
from feedspine.storage.postgres import PostgresStorage

@pytest.fixture
async def storage():
    """Create test storage instance."""
    s = PostgresStorage("postgresql://test:test@localhost/test")
    await s.initialize()
    yield s
    # Clean up test data
    await s._pool.execute("DELETE FROM records")
    await s.close()

class TestPostgresStorageBasic:
    async def test_store_and_get(self, storage):
        record = make_record("test-key")
        await storage.store(record)
        retrieved = await storage.get(record.id)
        assert retrieved is not None
        assert retrieved.id == record.id
```

## Best Practices

1. **Connection Pooling**: Always use connection pools for production
2. **Transactions**: Use transactions for multi-step operations
3. **Indexes**: Add indexes for frequently queried fields
4. **Error Handling**: Wrap database errors in `StorageError`
5. **Testing**: Test against a real database, not mocks

## See Also

- [StorageBackend Protocol](../reference/feedspine/protocols/storage.md)
- [MemoryStorage Implementation](../reference/feedspine/storage/memory.md)
- [Layer System](../concepts/layers.md)
