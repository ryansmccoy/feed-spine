---
title: "Guardrails"
type: specification
status: active
tags: [feed-spine, testing, python]
created: 2026-02-22
updated: 2026-04-12
---
# FeedSpine Development Guardrails

> Enforced standards for code, documentation, and testing.

This document defines the **must-follow** rules for all FeedSpine development.

---

## Table of Contents

1. [Ecosystem Collaboration](#ecosystem-collaboration)
2. [Code Standards](#code-standards)
3. [Documentation Standards](#documentation-standards)
4. [Testing Standards](#testing-standards)
5. [Protocol Design](#protocol-design)

---

## Ecosystem Collaboration

### Three-Package Ecosystem

FeedSpine is part of a tightly integrated ecosystem:

```
FeedSpine (ingestion) ←→ EntitySpine (identity) ←→ py-sec-edgar (application)
```

**Cross-package changes are ENCOURAGED when they improve integration.**

### When to Modify Other Packages

| Scenario | Action |
|----------|--------|
| FeedSpine record needs entity resolution | ✅ Coordinate with EntitySpine |
| py-sec-edgar needs new adapter | ✅ Add adapter to FeedSpine |
| Storage protocol change affects EntitySpine | ✅ Update both packages |

---

## Code Standards

### Async-First Design

All I/O operations MUST be async:

```python
# ✅ Correct - async
async def fetch_feed(url: str) -> list[Record]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return parse(response.text)

# ❌ Wrong - blocking
def fetch_feed(url: str) -> list[Record]:
    response = requests.get(url)  # Blocks event loop
    return parse(response.text)
```

### Type Hints Required

All public functions MUST have complete type hints:

```python
# ✅ Correct
async def save(
    self,
    record: FeedRecord,
    *,
    layer: Layer = Layer.BRONZE
) -> str:
    ...

# ❌ Wrong
async def save(self, record, tier=None):  # No types
    ...
```

### Docstrings Required (Google Style)

```python
async def collect(
    self,
    feeds: list[str] | None = None,
    *,
    max_concurrent: int = 5
) -> CollectionResult:
    """Collect records from registered feeds.

    Args:
        feeds: Specific feeds to collect from. If None, collects from all.
        max_concurrent: Maximum concurrent feed fetches.

    Returns:
        CollectionResult with statistics and any errors.

    Raises:
        FeedSpineError: If collection fails catastrophically.

    Examples:
        >>> async with FeedSpine(storage) as spine:
        ...     result = await spine.collect()
        ...     print(result.total_new)
    """
```

---

## Documentation Standards

### Required Files

Every release must have:

- [ ] Updated `CHANGELOG.md` with all changes
- [ ] Updated `FEATURES.md` for new features
- [ ] Docstrings for all new public APIs
- [ ] Updated `TODO.md` if work items change

### Code Examples Must Work

```python
# ✅ Every example in docs must be runnable
>>> from feedspine import create_feed_spine, MemoryStorage
>>> storage = MemoryStorage()
>>> app = create_feed_spine(storage)
>>> # This must actually work!
```

---

## Testing Standards

### Minimum Coverage: 80%

```bash
pytest --cov=feedspine --cov-fail-under=80
```

### Test Categories

| Category | Location | Purpose |
|----------|----------|---------|
| Unit | `tests/unit/` | Isolated component tests |
| Integration | `tests/integration/` | Cross-component tests |
| Adapters | `tests/adapters/` | Feed adapter tests |
| Storage | `tests/storage/` | Storage backend tests |

### Fixture Patterns

```python
# Use fixtures, not repeated setup
@pytest.fixture
def memory_storage():
    return MemoryStorage()

@pytest.fixture
async def app(memory_storage):
    return create_feed_spine(memory_storage)
```

### Async Test Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_collect_returns_results(app):
    """Collection returns CollectionResult."""
    result = await app.collect()
    
    assert isinstance(result, CollectionResult)
    assert result.total_processed >= 0
```

---

## Protocol Design

### All Components Use Protocols

```python
from typing import Protocol

class FeedAdapterProtocol(Protocol):
    """All feed adapters must implement this."""
    
    name: str
    
    async def fetch(self) -> list[RawRecord]: ...
    async def parse(self, raw: bytes) -> list[FeedRecord]: ...

class StorageProtocol(Protocol):
    """All storage backends must implement this."""
    
    async def save(self, record: FeedRecord) -> str: ...
    async def get(self, key: str) -> FeedRecord | None: ...
    async def exists(self, key: str) -> bool: ...
```

### Protocol Checklist

When adding a new component type:

- [ ] Define protocol in `protocols/`
- [ ] Create at least 2 implementations
- [ ] Add protocol tests that work with any implementation
- [ ] Document in `concepts/protocols.md`

---

## CI Enforcement

These standards are enforced via GitHub Actions:

```yaml
# .github/workflows/ci.yml
- name: Type Check
  run: mypy feedspine/ --strict

- name: Lint
  run: ruff check feedspine/

- name: Format Check
  run: ruff format --check feedspine/

- name: Tests
  run: pytest --cov=feedspine --cov-fail-under=80

- name: Docs Build
  run: mkdocs build --strict
```

---

## Quick Reference

| Rule | Enforcement |
|------|-------------|
| Async I/O | Code review |
| Type hints | mypy --strict |
| Docstrings | pydocstyle |
| 80% coverage | pytest --cov-fail-under |
| Protocol-based | Code review |
| Examples work | doctest |

---

*These guardrails ensure FeedSpine remains maintainable, testable, and well-documented.*
