# FeedSpine Plugin Architecture

> Extensible adapter registration and discovery system.

**Location**: `feedspine/docs/design/improvements/`  
**Priority**: High (10/10 long-term value)  
**Complexity**: Medium

---

## Overview

Enable third-party packages to register adapters without modifying FeedSpine core.

## Current State

```python
# Currently: Direct import and instantiation
from some_package.adapters import MyAdapter

adapter = MyAdapter(...)
spine.register_feed(adapter)
```

**Problems:**
- No discoverability
- Manual adapter management
- No standard configuration pattern
- Hard to test

## Vision

```python
# Future: Auto-discovery and creation
from feedspine import FeedSpine

spine = FeedSpine(storage=storage)
print(spine.available_adapters)
# ['sec.quarterly', 'sec.daily', 'sec.rss', 'twitter.stream', ...]

# Create by name with config
adapter = spine.create_adapter("sec.quarterly", year=2025, quarter=1)
```

---

## Implementation

### Part A: Adapter Registry

```python
# feedspine/plugins/registry.py

from typing import Type, Callable, Any
from importlib.metadata import entry_points
import logging

logger = logging.getLogger(__name__)

class AdapterRegistry:
    """Global registry for feed adapters."""
    
    _instance: "AdapterRegistry | None" = None
    
    def __init__(self):
        self._adapters: dict[str, Type] = {}
        self._factories: dict[str, Callable[..., Any]] = {}
        self._loaded_entry_points = False
    
    @classmethod
    def instance(cls) -> "AdapterRegistry":
        """Get singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(
        self,
        name: str,
        adapter_class: Type | None = None,
    ) -> Callable | None:
        """Register an adapter class.
        
        Can be used as a decorator:
            @registry.register("my_adapter")
            class MyAdapter: ...
        
        Or called directly:
            registry.register("my_adapter", MyAdapter)
        """
        def decorator(cls: Type) -> Type:
            self._adapters[name] = cls
            logger.debug(f"Registered adapter: {name}")
            return cls
        
        if adapter_class is not None:
            self._adapters[name] = adapter_class
            return None
        
        return decorator
    
    def _load_entry_points(self) -> None:
        """Load adapters from package entry points."""
        if self._loaded_entry_points:
            return
        
        self._loaded_entry_points = True
        
        try:
            eps = entry_points(group="feedspine.adapters")
            for ep in eps:
                try:
                    adapter_class = ep.load()
                    self.register(ep.name, adapter_class=adapter_class)
                    logger.info(f"Loaded adapter: {ep.name}")
                except Exception as e:
                    logger.warning(f"Failed to load {ep.name}: {e}")
        except Exception:
            pass  # No entry points
    
    def get(self, name: str) -> Type | None:
        """Get adapter class by name."""
        self._load_entry_points()
        return self._adapters.get(name)
    
    def create(self, name: str, **kwargs) -> Any:
        """Create adapter instance by name."""
        self._load_entry_points()
        
        adapter_class = self._adapters.get(name)
        if adapter_class is None:
            raise KeyError(f"Unknown adapter: {name}. Available: {self.available}")
        
        return adapter_class(**kwargs)
    
    @property
    def available(self) -> list[str]:
        """List available adapter names."""
        self._load_entry_points()
        return sorted(self._adapters.keys())


# Global instance
registry = AdapterRegistry.instance()

# Convenience decorator
def adapter(name: str):
    """Decorator to register a feed adapter."""
    return registry.register(name)
```

### Part B: FeedSpine Integration

```python
# feedspine/core/feedspine.py

from feedspine.plugins.registry import registry, AdapterRegistry

class FeedSpine:
    def __init__(
        self,
        storage: StorageBackend,
        registry: AdapterRegistry | None = None,
    ):
        self.storage = storage
        self._registry = registry or AdapterRegistry.instance()
        self._feeds: dict[str, FeedAdapter] = {}
    
    @property
    def available_adapters(self) -> list[str]:
        """List all registered adapter types."""
        return self._registry.available
    
    def create_adapter(self, name: str, **kwargs) -> FeedAdapter:
        """Create an adapter by registered name."""
        return self._registry.create(name, **kwargs)
    
    def register_by_name(
        self,
        adapter_name: str,
        instance_name: str | None = None,
        **kwargs,
    ) -> FeedAdapter:
        """Create and register an adapter in one call."""
        adapter = self.create_adapter(adapter_name, **kwargs)
        feed_name = instance_name or f"{adapter_name}_{id(adapter)}"
        self.register_feed(adapter, name=feed_name)
        return adapter
```

### Part C: Entry Points (for third-party packages)

```toml
# In a third-party package's pyproject.toml

[project.entry-points."feedspine.adapters"]
"mycompany.feed" = "mypackage.adapters:MyFeedAdapter"
"mycompany.stream" = "mypackage.adapters:MyStreamAdapter"
```

---

## Usage Patterns

### Pattern 1: Decorator Registration

```python
from feedspine.plugins import adapter

@adapter("my.custom.feed")
class MyCustomAdapter:
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
    
    async def fetch(self):
        ...
```

### Pattern 2: Explicit Registration

```python
from feedspine.plugins import registry

class LegacyAdapter:
    ...

registry.register("legacy.feed", LegacyAdapter)
```

### Pattern 3: Entry Point Discovery

```python
# Automatically discovered from installed packages
spine = FeedSpine(storage=storage)
print(spine.available_adapters)
# Includes adapters from all installed packages
```

### Pattern 4: Testing with Mock Registry

```python
def test_collection():
    test_registry = AdapterRegistry()
    test_registry.register("test.adapter", MockAdapter)
    
    spine = FeedSpine(storage=storage, registry=test_registry)
    adapter = spine.create_adapter("test.adapter")
```

---

## Benefits

| Benefit | Description |
|---------|-------------|
| **Extensibility** | Add adapters without modifying FeedSpine |
| **Discoverability** | `available_adapters` shows all options |
| **Testability** | Inject mock registries for testing |
| **Decoupling** | FeedSpine doesn't import adapter packages |
| **Standards** | Uses Python entry points (PEP 621) |

---

## Implementation Checklist

- [ ] Create `feedspine/plugins/` package
- [ ] Implement `AdapterRegistry` class
- [ ] Add `adapter` decorator
- [ ] Integrate registry into `FeedSpine`
- [ ] Add `available_adapters` property
- [ ] Add `create_adapter()` method
- [ ] Add `register_by_name()` convenience method
- [ ] Document entry points specification
- [ ] Add migration guide for existing code

---

*See also: [Core Improvements](CORE_IMPROVEMENTS.md) | [Streaming Pipeline](STREAMING_PIPELINE.md)*
