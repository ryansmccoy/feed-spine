# FeedSpine Core Improvements

> Tactical improvements for FeedSpine's reliability and observability.

**Location**: `feedspine/docs/design/improvements/`  
**Related**: [py-sec-edgar improvements](../../../../py_sec_edgar/docs/architecture/improvements/README.md)

---

## 1. Progress Reporting Protocol

**Impact: 10/10** | **Effort: Medium**

### Problem

No standard way for adapters to report progress during long-running operations.

### Solution

Define a `ProgressReporter` protocol that consumers can implement:

```python
# feedspine/protocols/progress.py

from typing import Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Enum

class ProgressStage(Enum):
    INITIALIZING = "initializing"
    FETCHING = "fetching"
    PARSING = "parsing"
    STORING = "storing"
    COMPLETE = "complete"

@dataclass
class ProgressEvent:
    """Standard progress event structure."""
    stage: ProgressStage
    source: str
    current: int
    total: int
    message: str
    bytes_processed: int = 0
    records_processed: int = 0
    elapsed_seconds: float = 0.0
    
    @property
    def percentage(self) -> float:
        return (self.current / self.total * 100) if self.total > 0 else 0.0

@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for progress reporting implementations."""
    
    def report(self, event: ProgressEvent) -> None:
        """Report a progress event."""
        ...
```

### Integration Points

1. `FeedSpine.collect()` accepts optional `progress: ProgressReporter`
2. Adapters receive progress reporter via `fetch(progress=...)`
3. Default no-op implementation for backward compatibility

### Implementation Checklist

- [ ] Define `ProgressEvent` dataclass
- [ ] Define `ProgressReporter` protocol
- [ ] Add `progress` parameter to `FeedSpine.collect()`
- [ ] Pass progress to adapters during fetch
- [ ] Add `NullProgressReporter` default implementation
- [ ] Document protocol in API docs

---

## 2. Retry Utilities

**Impact: 9/10** | **Effort: Medium**

### Problem

No standard retry/backoff utilities for adapters to use.

### Solution

Provide reusable retry primitives:

```python
# feedspine/utils/retry.py

from dataclasses import dataclass
from typing import TypeVar, Callable, Awaitable
import asyncio
import random

T = TypeVar("T")

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on: tuple[type[Exception], ...] = (Exception,)

class RetryExhausted(Exception):
    """All retry attempts failed."""
    def __init__(self, last_error: Exception, attempts: int):
        self.last_error = last_error
        self.attempts = attempts

async def with_retry(
    func: Callable[[], Awaitable[T]],
    config: RetryConfig = RetryConfig(),
    on_retry: Callable[[Exception, int, float], None] | None = None,
) -> T:
    """Execute async function with retry logic."""
    last_error: Exception | None = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func()
        except config.retry_on as e:
            last_error = e
            
            if attempt == config.max_attempts:
                raise RetryExhausted(e, attempt) from e
            
            delay = min(
                config.base_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay,
            )
            
            if config.jitter:
                delay *= (0.5 + random.random())
            
            if on_retry:
                on_retry(e, attempt, delay)
            
            await asyncio.sleep(delay)
    
    raise RetryExhausted(last_error or Exception("Unknown"), config.max_attempts)
```

### Implementation Checklist

- [ ] Create `RetryConfig` dataclass
- [ ] Implement `with_retry()` function
- [ ] Create `retry` decorator
- [ ] Add to `feedspine.utils` public API
- [ ] Document usage patterns

---

## 3. Metrics Interface

**Impact: 8/10** | **Effort: Medium**

### Problem

No standard way to collect operational metrics.

### Solution

Define a `MetricsBackend` protocol:

```python
# feedspine/protocols/metrics.py

from typing import Protocol

class MetricsBackend(Protocol):
    """Protocol for metrics backends."""
    
    def counter(self, name: str, value: int = 1, tags: dict[str, str] | None = None) -> None:
        ...
    
    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        ...
    
    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        ...


class NullMetrics:
    """No-op metrics implementation."""
    def counter(self, *args, **kwargs): pass
    def gauge(self, *args, **kwargs): pass
    def histogram(self, *args, **kwargs): pass


class InMemoryMetrics:
    """In-memory metrics for testing."""
    def __init__(self):
        self.counters: dict[str, int] = {}
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = {}
    
    # ... implementation ...
```

### Predefined Metrics

```python
# Standard metric names
METRICS = {
    "feedspine_records_processed_total": "Total records processed",
    "feedspine_records_new_total": "New records inserted",
    "feedspine_records_duplicate_total": "Duplicate records skipped",
    "feedspine_fetch_duration_seconds": "Time to fetch from adapter",
    "feedspine_bytes_downloaded_total": "Bytes downloaded",
    "feedspine_errors_total": "Errors encountered",
}
```

### Implementation Checklist

- [ ] Define `MetricsBackend` protocol
- [ ] Create `NullMetrics` default
- [ ] Create `InMemoryMetrics` for testing
- [ ] Add metrics parameter to `FeedSpine`
- [ ] Instrument key operations
- [ ] Document metric names

---

## 4. Tight Coupling Fix

**Impact: 6/10** | **Effort: Low**

### Problem

```python
# Current: Direct access to internal dict
self.spine._feeds.pop(adapter.name, None)  # Bad!
```

### Solution

Add proper API methods:

```python
# feedspine/core/feedspine.py

class FeedSpine:
    def unregister_feed(self, name: str) -> bool:
        """Remove a registered feed adapter."""
        if name in self._feeds:
            del self._feeds[name]
            return True
        return False
    
    def clear_feeds(self) -> None:
        """Remove all registered feeds."""
        self._feeds.clear()
    
    @property
    def registered_feeds(self) -> list[str]:
        """Get list of registered feed names."""
        return list(self._feeds.keys())
```

### Implementation Checklist

- [ ] Add `unregister_feed()` method
- [ ] Add `clear_feeds()` method
- [ ] Add `registered_feeds` property
- [ ] Update documentation
- [ ] Deprecate direct `_feeds` access

---

## Summary

| Improvement | Files to Modify | New Files |
|-------------|-----------------|-----------|
| Progress Protocol | `core/feedspine.py` | `protocols/progress.py` |
| Retry Utilities | - | `utils/retry.py` |
| Metrics Interface | `core/feedspine.py` | `protocols/metrics.py` |
| Coupling Fix | `core/feedspine.py` | - |

---

*See also: [Plugin Architecture](PLUGIN_ARCHITECTURE.md) | [Streaming Pipeline](STREAMING_PIPELINE.md)*
