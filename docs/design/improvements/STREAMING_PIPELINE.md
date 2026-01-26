# FeedSpine Streaming Pipeline

> Memory-efficient streaming with backpressure and composable pipelines.

**Location**: `feedspine/docs/design/improvements/`  
**Priority**: High (9/10 long-term value)  
**Complexity**: High

---

## Overview

Replace batch processing with true streaming for handling massive datasets.

## Current State

```python
# Current: Full materialization in memory
async def collect(self) -> CollectionResult:
    for adapter in self._feeds.values():
        async for candidate in adapter.fetch():
            # Each candidate held in memory until stored
            await self.storage.insert(candidate)
```

**Problems:**
- Memory grows with data size
- No backpressure when storage is slow
- Can't process while downloading
- No parallel stream processing

---

## Vision

```python
# True streaming
async for record in spine.collect_stream():
    process(record)  # Constant memory usage

# Parallel collection
async for record in spine.collect_parallel(max_concurrent=4):
    process(record)

# Composable pipelines
await (
    spine.pipeline()
    .filter(lambda r: r.content.get("type") == "important")
    .batch(100)
    .tap(save_batch)
    .drain()
)
```

---

## Implementation

### Part A: Stream Primitives

```python
# feedspine/streaming/primitives.py

from typing import TypeVar, AsyncIterator, Callable, Awaitable
import asyncio

T = TypeVar("T")
U = TypeVar("U")

class AsyncBuffer:
    """Bounded async buffer with backpressure."""
    
    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._done = False
    
    async def put(self, item: T) -> None:
        """Add item, blocks if buffer is full (backpressure)."""
        await self._queue.put(item)
    
    async def get(self) -> T | None:
        """Get item, returns None when done."""
        if self._done and self._queue.empty():
            return None
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None if self._done else await self.get()
    
    def mark_done(self) -> None:
        self._done = True
    
    async def __aiter__(self) -> AsyncIterator[T]:
        while True:
            item = await self.get()
            if item is None:
                break
            yield item


async def amap(
    source: AsyncIterator[T],
    func: Callable[[T], Awaitable[U]],
) -> AsyncIterator[U]:
    """Async map over iterator."""
    async for item in source:
        yield await func(item)


async def afilter(
    source: AsyncIterator[T],
    predicate: Callable[[T], Awaitable[bool]],
) -> AsyncIterator[T]:
    """Async filter over iterator."""
    async for item in source:
        if await predicate(item):
            yield item


async def abatch(
    source: AsyncIterator[T],
    size: int,
) -> AsyncIterator[list[T]]:
    """Batch items into chunks."""
    batch: list[T] = []
    async for item in source:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


async def amerge(
    *sources: AsyncIterator[T],
    buffer_size: int = 100,
) -> AsyncIterator[T]:
    """Merge multiple async iterators concurrently."""
    buffer = AsyncBuffer(maxsize=buffer_size)
    active = set()
    
    async def drain(source: AsyncIterator[T]) -> None:
        try:
            async for item in source:
                await buffer.put(item)
        finally:
            pass
    
    for source in sources:
        task = asyncio.create_task(drain(source))
        active.add(task)
        task.add_done_callback(active.discard)
    
    try:
        while active or not buffer._queue.empty():
            item = await buffer.get()
            if item is not None:
                yield item
    finally:
        for task in active:
            task.cancel()
        buffer.mark_done()
```

### Part B: Pipeline Builder

```python
# feedspine/streaming/pipeline.py

from dataclasses import dataclass
from typing import TypeVar, Generic, AsyncIterator, Callable, Awaitable

T = TypeVar("T")
U = TypeVar("U")

class Pipeline(Generic[T]):
    """Composable async pipeline builder."""
    
    def __init__(self, source: AsyncIterator[T]):
        self._source = source
        self._transforms: list[Callable] = []
    
    def map(
        self,
        func: Callable[[T], Awaitable[U]],
    ) -> "Pipeline[U]":
        """Add map transformation."""
        self._transforms.append(lambda s: amap(s, func))
        return self  # type: ignore
    
    def filter(
        self,
        predicate: Callable[[T], Awaitable[bool]],
    ) -> "Pipeline[T]":
        """Add filter transformation."""
        self._transforms.append(lambda s: afilter(s, predicate))
        return self
    
    def batch(self, size: int) -> "Pipeline[list[T]]":
        """Batch items into chunks."""
        self._transforms.append(lambda s: abatch(s, size))
        return self  # type: ignore
    
    def tap(
        self,
        func: Callable[[T], Awaitable[None]],
    ) -> "Pipeline[T]":
        """Side effect without transformation."""
        async def tap_transform(source):
            async for item in source:
                await func(item)
                yield item
        self._transforms.append(tap_transform)
        return self
    
    async def __aiter__(self) -> AsyncIterator[T]:
        """Execute pipeline."""
        current = self._source
        for transform in self._transforms:
            current = transform(current)
        async for item in current:
            yield item
    
    async def collect(self) -> list[T]:
        """Collect all results."""
        return [item async for item in self]
    
    async def count(self) -> int:
        """Count items."""
        count = 0
        async for _ in self:
            count += 1
        return count
    
    async def drain(self) -> None:
        """Execute, discarding results."""
        async for _ in self:
            pass
```

### Part C: Streaming FeedSpine Methods

```python
# feedspine/core/feedspine.py

class FeedSpine:
    async def collect_stream(self) -> AsyncIterator[Record]:
        """Stream records as collected (constant memory)."""
        for adapter in self._feeds.values():
            await adapter.initialize()
            try:
                async for candidate in adapter.fetch():
                    if not await self._is_duplicate(candidate):
                        record = await self.storage.insert(candidate)
                        yield record
            finally:
                await adapter.close()
    
    async def collect_parallel(
        self,
        max_concurrent: int = 4,
    ) -> AsyncIterator[Record]:
        """Collect from adapters in parallel."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_fetch(adapter):
            async with semaphore:
                await adapter.initialize()
                try:
                    async for candidate in adapter.fetch():
                        yield candidate
                finally:
                    await adapter.close()
        
        streams = [bounded_fetch(a) for a in self._feeds.values()]
        
        async for candidate in amerge(*streams):
            if not await self._is_duplicate(candidate):
                yield await self.storage.insert(candidate)
    
    def pipeline(self) -> Pipeline[RecordCandidate]:
        """Create pipeline for custom processing."""
        async def source():
            for adapter in self._feeds.values():
                await adapter.initialize()
                async for candidate in adapter.fetch():
                    yield candidate
                await adapter.close()
        return Pipeline(source())
```

---

## Usage Examples

```python
# Simple streaming
async for record in spine.collect_stream():
    print(record.natural_key)

# Parallel with concurrency limit
async for record in spine.collect_parallel(max_concurrent=4):
    await process(record)

# Custom pipeline
count = await (
    spine.pipeline()
    .filter(async_is_important)
    .map(enrich)
    .batch(100)
    .tap(save_batch)
    .count()
)
```

---

## Benefits

| Benefit | Description |
|---------|-------------|
| **Memory** | Constant usage regardless of data size |
| **Backpressure** | Slow consumers pause fast producers |
| **Parallelism** | Multiple adapters run concurrently |
| **Composability** | Build complex flows from simple parts |
| **Real-time** | Process data as it arrives |

---

## Implementation Checklist

- [ ] Create `feedspine/streaming/` package
- [ ] Implement `AsyncBuffer` with backpressure
- [ ] Implement stream primitives (`amap`, `afilter`, `abatch`, `amerge`)
- [ ] Implement `Pipeline` builder
- [ ] Add `collect_stream()` to FeedSpine
- [ ] Add `collect_parallel()` to FeedSpine
- [ ] Add `pipeline()` factory method
- [ ] Add comprehensive tests
- [ ] Document usage patterns

---

*See also: [Core Improvements](CORE_IMPROVEMENTS.md) | [Event System](EVENT_SYSTEM.md)*
