# FeedSpine Event System

> Decoupled, event-driven architecture for reactive applications.

**Location**: `feedspine/docs/design/improvements/`  
**Priority**: Medium-High (9/10 long-term value)  
**Complexity**: High

---

## Overview

Enable reactive, observable applications through a publish/subscribe event system.

## Current State

```python
# Current: Synchronous, opaque
result = await spine.collect()
# No visibility into what happened
```

**Problems:**
- No intermediate visibility
- Can't react to events
- Tight coupling
- Hard to extend behavior

---

## Vision

```python
# Event-driven with full observability
@spine.events.on(RecordDiscovered)
async def handle_new_record(event):
    if event.content.get("priority") == "high":
        await send_alert(event)

@spine.events.on(CollectionFailed)
async def handle_failure(event):
    await page_oncall(event.error)

# Run collection (events fire automatically)
await spine.collect()
```

---

## Implementation

### Part A: Event Definitions

```python
# feedspine/events/base.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from enum import Enum
import uuid

class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

@dataclass
class Event:
    """Base class for all events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    priority: EventPriority = EventPriority.NORMAL
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# feedspine/events/collection.py

@dataclass
class CollectionStarted(Event):
    """Emitted when collection begins."""
    adapter_count: int = 0
    estimated_records: int = 0

@dataclass
class CollectionProgress(Event):
    """Periodic progress update."""
    records_processed: int = 0
    records_new: int = 0
    records_duplicate: int = 0
    bytes_downloaded: int = 0

@dataclass
class CollectionCompleted(Event):
    """Collection finished successfully."""
    total_new: int = 0
    total_duplicates: int = 0
    duration_seconds: float = 0.0

@dataclass
class CollectionFailed(Event):
    """Collection failed."""
    error: Exception | None = None
    error_message: str = ""
    priority: EventPriority = EventPriority.HIGH


# feedspine/events/records.py

@dataclass
class RecordDiscovered(Event):
    """New record found."""
    natural_key: str = ""
    content: dict = field(default_factory=dict)

@dataclass
class RecordDuplicate(Event):
    """Duplicate detected."""
    natural_key: str = ""


# feedspine/events/adapters.py

@dataclass
class AdapterStarted(Event):
    """Adapter began fetching."""
    adapter_name: str = ""

@dataclass
class AdapterCompleted(Event):
    """Adapter finished."""
    adapter_name: str = ""
    records_fetched: int = 0

@dataclass
class AdapterFailed(Event):
    """Adapter failed."""
    adapter_name: str = ""
    error: Exception | None = None
    priority: EventPriority = EventPriority.HIGH
```

### Part B: Event Bus

```python
# feedspine/events/bus.py

from typing import Callable, Awaitable, Type, TypeVar
from collections import defaultdict
import asyncio
import logging

E = TypeVar("E", bound=Event)

class EventBus:
    """Async event bus for decoupled communication."""
    
    def __init__(self):
        self._handlers: dict[Type[Event], list[Callable]] = defaultdict(list)
        self._global_handlers: list[Callable] = []
        self._logger = logging.getLogger(__name__)
    
    def on(
        self,
        event_type: Type[E],
    ) -> Callable[[Callable[[E], Awaitable[None]]], Callable[[E], Awaitable[None]]]:
        """Decorator to subscribe to an event type."""
        def decorator(handler: Callable[[E], Awaitable[None]]):
            self._handlers[event_type].append(handler)
            return handler
        return decorator
    
    def subscribe(
        self,
        event_type: Type[E],
        handler: Callable[[E], Awaitable[None]],
    ) -> Callable[[], None]:
        """Subscribe to event type. Returns unsubscribe function."""
        self._handlers[event_type].append(handler)
        return lambda: self._handlers[event_type].remove(handler)
    
    def subscribe_all(
        self,
        handler: Callable[[Event], Awaitable[None]],
    ) -> Callable[[], None]:
        """Subscribe to all events."""
        self._global_handlers.append(handler)
        return lambda: self._global_handlers.remove(handler)
    
    async def publish(self, event: Event) -> None:
        """Publish event to subscribers."""
        handlers = self._global_handlers + self._handlers.get(type(event), [])
        
        tasks = [
            asyncio.create_task(self._safe_call(h, event))
            for h in handlers
        ]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_call(self, handler, event):
        try:
            await handler(event)
        except Exception as e:
            self._logger.error(f"Handler error: {e}")


class EventEmitter:
    """Mixin for classes that emit events."""
    
    def __init__(self, bus: EventBus | None = None):
        self._event_bus = bus or EventBus()
    
    async def emit(self, event: Event) -> None:
        await self._event_bus.publish(event)
    
    @property
    def events(self) -> EventBus:
        return self._event_bus
```

### Part C: FeedSpine Integration

```python
# feedspine/core/feedspine.py

class FeedSpine(EventEmitter):
    def __init__(self, storage, event_bus: EventBus | None = None):
        super().__init__(bus=event_bus)
        self.storage = storage
        self._feeds = {}
    
    async def collect(self) -> CollectionResult:
        start = time.perf_counter()
        
        await self.emit(CollectionStarted(
            adapter_count=len(self._feeds),
        ))
        
        try:
            new_count = 0
            dup_count = 0
            
            for name, adapter in self._feeds.items():
                await self.emit(AdapterStarted(adapter_name=name))
                
                try:
                    async for candidate in adapter.fetch():
                        if await self._is_duplicate(candidate):
                            dup_count += 1
                            await self.emit(RecordDuplicate(
                                natural_key=candidate.natural_key,
                            ))
                        else:
                            await self.storage.insert(candidate)
                            new_count += 1
                            await self.emit(RecordDiscovered(
                                natural_key=candidate.natural_key,
                                content=candidate.content,
                            ))
                    
                    await self.emit(AdapterCompleted(adapter_name=name))
                    
                except Exception as e:
                    await self.emit(AdapterFailed(
                        adapter_name=name,
                        error=e,
                    ))
                    raise
            
            result = CollectionResult(
                total_new=new_count,
                total_duplicates=dup_count,
            )
            
            await self.emit(CollectionCompleted(
                total_new=new_count,
                total_duplicates=dup_count,
                duration_seconds=time.perf_counter() - start,
            ))
            
            return result
            
        except Exception as e:
            await self.emit(CollectionFailed(error=e))
            raise
```

---

## Usage Patterns

### Pattern 1: Decorator Subscription

```python
bus = EventBus()
spine = FeedSpine(storage, event_bus=bus)

@bus.on(RecordDiscovered)
async def log_record(event):
    print(f"New: {event.natural_key}")

@bus.on(CollectionFailed)
async def alert_failure(event):
    await send_alert(event.error)

await spine.collect()
```

### Pattern 2: Programmatic Subscription

```python
def setup_monitoring(spine: FeedSpine):
    unsubscribe = spine.events.subscribe(
        CollectionProgress,
        update_dashboard,
    )
    return unsubscribe
```

### Pattern 3: Event Logging

```python
async def log_all_events(event: Event):
    logger.info(f"{type(event).__name__}: {event}")

spine.events.subscribe_all(log_all_events)
```

### Pattern 4: Event Streaming

```python
async def event_stream(spine: FeedSpine) -> AsyncIterator[Event]:
    queue = asyncio.Queue()
    
    async def handler(event):
        await queue.put(event)
    
    spine.events.subscribe_all(handler)
    
    while True:
        event = await queue.get()
        yield event
```

---

## Benefits

| Benefit | Description |
|---------|-------------|
| **Decoupling** | Components don't know about each other |
| **Extensibility** | Add behaviors without modifying core |
| **Observability** | Full visibility into operations |
| **Reactivity** | Build real-time workflows |
| **Testing** | Capture events to verify behavior |

---

## Implementation Checklist

- [ ] Create `feedspine/events/` package
- [ ] Define base `Event` class
- [ ] Define collection events
- [ ] Define record events
- [ ] Define adapter events
- [ ] Implement `EventBus`
- [ ] Implement `EventEmitter` mixin
- [ ] Integrate into `FeedSpine`
- [ ] Add event streaming helper
- [ ] Document all event types

---

*See also: [Core Improvements](CORE_IMPROVEMENTS.md) | [Streaming Pipeline](STREAMING_PIPELINE.md)*
