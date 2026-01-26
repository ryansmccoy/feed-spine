# FeedSpine Documentation Guide

> Best practices for creating maintainable, auto-generated documentation with runnable examples.

## Table of Contents

1. [Docstring Format](#docstring-format)
2. [Runnable Examples (Doctests)](#runnable-examples-doctests)
3. [Cross-References and Linking](#cross-references-and-linking)
4. [Documentation Generator Choice](#documentation-generator-choice)
5. [Hosting Options](#hosting-options)
6. [Documentation Structure](#documentation-structure)
7. [Maintenance Practices](#maintenance-practices)
8. [Implementation Checklist](#implementation-checklist)

---

## Docstring Format

### Recommended: Google Style

We use **Google-style docstrings** because they are:
- Human-readable without rendering
- Well-supported by Sphinx, MkDocs, and IDE tooltips
- Concise yet comprehensive

```python
def promote(
    self,
    target_layer: Layer,
    enrichments: dict[str, Any] | None = None,
) -> "Record":
    """Promote a record to a higher layer in the data pipeline.

    Records flow through layers: BRONZE → SILVER → GOLD. Each promotion
    represents increased data quality and enrichment.

    Args:
        target_layer: The layer to promote to. Must be higher than current.
        enrichments: Optional data to merge into content during promotion.
            Keys are field names, values are the enriched data.

    Returns:
        A new Record instance at the target layer with updated timestamps.

    Raises:
        ValueError: If target_layer is not higher than current layer.
        ValueError: If target_layer equals current layer.

    Example:
        >>> from feedspine.models.record import Record, RecordCandidate
        >>> from feedspine.models.base import Layer, Metadata
        >>> from datetime import datetime, timezone
        >>> candidate = RecordCandidate(
        ...     natural_key="example-key",
        ...     published_at=datetime.now(timezone.utc),
        ...     content={"title": "Example"},
        ...     metadata=Metadata(source="test"),
        ... )
        >>> bronze = Record.from_candidate(candidate, record_id="rec-001")
        >>> silver = bronze.promote(Layer.SILVER, {"verified": True})
        >>> silver.layer
        <Layer.SILVER: 'silver'>
        >>> silver.content["verified"]
        True

    See Also:
        - :class:`Layer`: Available data quality layers
        - :meth:`from_candidate`: Create initial BRONZE record

    Note:
        Promotion is immutable - returns a new Record, original unchanged.
    """
```

### Docstring Sections Reference

| Section | Purpose | When to Use |
|---------|---------|-------------|
| **Summary** | One-line description | Always (first line) |
| **Extended Description** | Detailed explanation | Complex functions |
| **Args** | Parameter documentation | Functions with params |
| **Returns** | Return value description | Non-None returns |
| **Yields** | Generator yield description | Generators/async generators |
| **Raises** | Exceptions that may be raised | When exceptions possible |
| **Example** | Runnable code examples | Public API (required) |
| **See Also** | Related functions/classes | When helpful |
| **Note** | Important caveats | Edge cases, gotchas |
| **Warning** | Critical information | Breaking changes, dangers |
| **Todo** | Future improvements | Development notes |

### Class Docstrings

```python
class MemoryStorage:
    """In-memory storage backend for testing and development.

    Implements the :class:`StorageBackend` protocol using Python dictionaries.
    Data is lost when the process exits. Thread-safe for single-process
    async usage.

    Attributes:
        _records: Layer-partitioned record storage.
        _key_index: Natural key to record ID mapping.
        _sightings: Sighting history by natural key.

    Example:
        >>> import asyncio
        >>> from feedspine.storage.memory import MemoryStorage
        >>> async def example():
        ...     storage = MemoryStorage()
        ...     await storage.initialize()
        ...     count = await storage.count()
        ...     await storage.close()
        ...     return count
        >>> asyncio.run(example())
        0

    See Also:
        - :class:`StorageBackend`: Protocol this implements
        - :class:`SQLiteStorage`: Persistent alternative (coming soon)

    Note:
        Best for: testing, development, small datasets (<10k records).
        Not for: production, persistence, large datasets.
    """
```

### Module Docstrings

```python
"""In-memory storage backend for testing.

This module provides :class:`MemoryStorage`, a reference implementation
of the :class:`~feedspine.protocols.storage.StorageBackend` protocol.

Example:
    Basic usage::

        from feedspine.storage.memory import MemoryStorage

        async def main():
            storage = MemoryStorage()
            await storage.initialize()
            # ... use storage ...
            await storage.close()

Typical usage patterns:

    1. **Testing**: Fast, isolated storage for unit tests
    2. **Development**: Quick iteration without database setup
    3. **Reference**: Example for implementing other backends

See Also:
    - :mod:`feedspine.protocols.storage`: StorageBackend protocol
    - :mod:`feedspine.storage.sqlite`: Persistent storage (planned)
"""
```

---

## Runnable Examples (Doctests)

### Why Doctests?

1. **Always Up-to-Date**: Tests fail if examples break
2. **Documentation as Tests**: Examples are verified on every CI run
3. **User Confidence**: "This code actually works"

### Writing Good Doctests

```python
def get_by_natural_key(self, natural_key: str) -> Record | None:
    """Retrieve a record by its natural key.

    Natural keys are normalized (lowercase, stripped) before lookup.

    Args:
        natural_key: The unique business identifier for the record.

    Returns:
        The Record if found, None otherwise.

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
        ...
        ...     # Create and store a record
        ...     candidate = RecordCandidate(
        ...         natural_key="SEC-AAPL-10K-2024",
        ...         published_at=datetime.now(timezone.utc),
        ...         content={"form": "10-K"},
        ...         metadata=Metadata(source="sec-edgar"),
        ...     )
        ...     record = Record.from_candidate(candidate, record_id="r1")
        ...     await storage.store(record)
        ...
        ...     # Retrieve by natural key (case-insensitive)
        ...     found = await storage.get_by_natural_key("sec-aapl-10k-2024")
        ...     not_found = await storage.get_by_natural_key("nonexistent")
        ...
        ...     await storage.close()
        ...     return found is not None, not_found is None
        >>>
        >>> asyncio.run(example())
        (True, True)
    """
```

### Doctest Best Practices

```python
# ✅ GOOD: Self-contained, deterministic output
"""
Example:
    >>> 2 + 2
    4
    >>> sorted([3, 1, 2])
    [1, 2, 3]
"""

# ✅ GOOD: Use ... for async patterns
"""
Example:
    >>> import asyncio
    >>> async def example():
    ...     return "hello"
    >>> asyncio.run(example())
    'hello'
"""

# ✅ GOOD: Use ellipsis for variable output
"""
Example:
    >>> import uuid
    >>> str(uuid.uuid4())  # doctest: +ELLIPSIS
    '...-...-...-...-...'
"""

# ✅ GOOD: Skip platform-specific tests
"""
Example:
    >>> import sys
    >>> sys.platform  # doctest: +SKIP
    'win32'
"""

# ❌ BAD: Non-deterministic output
"""
Example:
    >>> datetime.now()  # Changes every run!
    datetime.datetime(2024, 1, 15, 10, 30, 45)
"""

# ❌ BAD: Depends on external state
"""
Example:
    >>> fetch_from_api()  # Network call!
    {'status': 'ok'}
"""
```

### Running Doctests

```bash
# Run all doctests
uv run pytest --doctest-modules src/

# Run doctests for specific module
uv run pytest --doctest-modules src/feedspine/models/record.py

# Include doctests in coverage
uv run pytest --doctest-modules --cov=feedspine src/
```

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "--doctest-modules"
doctest_optionflags = [
    "NORMALIZE_WHITESPACE",
    "ELLIPSIS",
]
```

---

## Cross-References and Linking

### Sphinx Cross-Reference Syntax

Use these in docstrings for auto-linking in generated docs:

```python
"""
See Also:
    - :class:`Layer`: The Layer enum
    - :meth:`Record.promote`: Promote to higher layer
    - :func:`feedspine.utils.normalize_key`: Key normalization
    - :mod:`feedspine.protocols`: All protocol definitions
    - :attr:`Record.natural_key`: The record's business key
    - :exc:`ValueError`: Raised on invalid input
    - :data:`DEFAULT_TIMEOUT`: Module constant

External links:
    - `SEC EDGAR <https://www.sec.gov/edgar>`_
    - `Pydantic docs <https://docs.pydantic.dev/>`_
"""
```

### Intersphinx (Link to External Docs)

Links to Python stdlib, Pydantic, etc. are automatic with intersphinx:

```python
"""
Args:
    data: A :class:`dict` mapping strings to values.
    model: A :class:`pydantic.BaseModel` subclass.
    
Returns:
    An :class:`asyncio.Task` that resolves to the result.
"""
```

---

## Documentation Generator Choice

### Recommendation: **MkDocs + mkdocstrings**

| Feature | MkDocs | Sphinx |
|---------|--------|--------|
| **Config format** | YAML (simple) | Python (complex) |
| **Markdown support** | Native | Requires MyST |
| **Google docstrings** | ✅ mkdocstrings | ✅ napoleon |
| **Live reload** | ✅ Built-in | ❌ Needs plugin |
| **Modern themes** | Material theme | Read the Docs theme |
| **Learning curve** | Low | Medium-High |
| **Ecosystem** | Growing | Mature |

### MkDocs Setup

```bash
# Install dependencies
uv add --group docs mkdocs mkdocs-material mkdocstrings[python] mkdocs-gen-files mkdocs-literate-nav

# Project structure
docs/
├── index.md              # Home page
├── getting-started.md    # Quick start guide
├── tutorials/            # Step-by-step tutorials
│   └── first-feed.md
├── how-to/              # Task-oriented guides
│   └── custom-storage.md
├── concepts/            # Explanations
│   └── layer-system.md
├── reference/           # Auto-generated API docs
│   └── (generated)
└── DOCUMENTATION_GUIDE.md  # This file

mkdocs.yml               # MkDocs configuration
```

### mkdocs.yml Configuration

```yaml
site_name: FeedSpine
site_description: Generic feed capture framework
site_url: https://feedspine.readthedocs.io/
repo_url: https://github.com/yourorg/feedspine
repo_name: feedspine

theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - search.suggest
    - content.code.copy
    - content.code.annotate
  palette:
    - scheme: default
      primary: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            show_category_heading: true
            members_order: source
            separate_signature: true
            show_signature_annotations: true
  - gen-files:
      scripts:
        - scripts/gen_ref_pages.py
  - literate-nav:
      nav_file: SUMMARY.md

nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Tutorials:
    - Your First Feed: tutorials/first-feed.md
  - How-To Guides:
    - Custom Storage Backend: how-to/custom-storage.md
  - Concepts:
    - The Layer System: concepts/layer-system.md
  - API Reference: reference/

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - admonition
  - pymdownx.details
  - attr_list
  - md_in_html
  - toc:
      permalink: true

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/yourorg/feedspine
```

### Auto-Generate API Reference

Create `scripts/gen_ref_pages.py`:

```python
"""Generate API reference pages automatically."""
from pathlib import Path
import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

src = Path("src/feedspine")

for path in sorted(src.rglob("*.py")):
    if path.name.startswith("_"):
        continue
    
    module_path = path.relative_to("src").with_suffix("")
    doc_path = path.relative_to("src").with_suffix(".md")
    full_doc_path = Path("reference", doc_path)
    
    parts = tuple(module_path.parts)
    
    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")
    
    nav[parts] = doc_path.as_posix()
    
    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        identifier = ".".join(parts)
        print(f"::: {identifier}", file=fd)
    
    mkdocs_gen_files.set_edit_path(full_doc_path, path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
```

---

## Hosting Options

### Recommendation: **Read the Docs**

| Feature | Read the Docs | GitHub Pages |
|---------|---------------|--------------|
| **Cost** | Free (open source) | Free |
| **Versioning** | ✅ Built-in | ❌ Manual |
| **PR previews** | ✅ Automatic | ❌ Needs Actions |
| **Search** | ✅ Built-in | ✅ With plugin |
| **Custom domain** | ✅ Easy | ✅ Easy |
| **Private repos** | Paid | Free with Actions |
| **PDF export** | ✅ Built-in | ❌ Manual |

### Read the Docs Setup

1. Create `.readthedocs.yaml`:

```yaml
version: 2

build:
  os: ubuntu-22.04
  tools:
    python: "3.12"

mkdocs:
  configuration: mkdocs.yml

python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs
```

2. Add docs dependencies to `pyproject.toml`:

```toml
[project.optional-dependencies]
docs = [
    "mkdocs>=1.5",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.24",
    "mkdocs-gen-files>=0.5",
    "mkdocs-literate-nav>=0.6",
]
```

3. Connect repository at [readthedocs.org](https://readthedocs.org/)

### GitHub Pages Alternative

Add `.github/workflows/docs.yml`:

```yaml
name: Deploy Docs

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --group docs
      - run: uv run mkdocs build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/deploy-pages@v4
        id: deployment
```

---

## Documentation Structure

### Diátaxis Framework

Organize docs into four quadrants:

```
                    PRACTICAL                     THEORETICAL
              ┌─────────────────────────────┬─────────────────────────────┐
              │                             │                             │
   LEARNING   │        TUTORIALS            │        EXPLANATIONS         │
              │                             │                             │
              │   "Learning-oriented"       │   "Understanding-oriented"  │
              │   Step-by-step lessons      │   Conceptual discussions    │
              │   For newcomers             │   Background & context      │
              │                             │                             │
              ├─────────────────────────────┼─────────────────────────────┤
              │                             │                             │
   WORKING    │        HOW-TO GUIDES        │        REFERENCE            │
              │                             │                             │
              │   "Task-oriented"           │   "Information-oriented"    │
              │   Problem-solving           │   Technical descriptions    │
              │   For practitioners         │   API documentation         │
              │                             │                             │
              └─────────────────────────────┴─────────────────────────────┘
```

### Content Guidelines

#### Tutorials (docs/tutorials/)
- **Goal**: Help users *learn*
- **Approach**: Step-by-step, hand-holding
- **Example**: "Build Your First SEC Filing Collector"

```markdown
# Your First Feed

In this tutorial, you'll build a complete feed collector that:
- Connects to a data source
- Captures new records
- Stores them for later processing

## Prerequisites

Before starting, ensure you have:
- Python 3.11+
- FeedSpine installed (`pip install feedspine`)

## Step 1: Create a Feed Definition

Let's start by defining what data we want to capture...
```

#### How-To Guides (docs/how-to/)
- **Goal**: Help users *accomplish tasks*
- **Approach**: Focused, practical
- **Example**: "How to Implement a Custom Storage Backend"

```markdown
# Implement a Custom Storage Backend

This guide shows how to create a PostgreSQL storage backend.

## Requirements

You need:
- A running PostgreSQL instance
- `asyncpg` library installed

## Implementation

### 1. Create the class

```python
class PostgresStorage:
    """PostgreSQL storage backend."""
    
    async def initialize(self) -> None:
        ...
```

### 2. Implement required methods
...
```

#### Explanations (docs/concepts/)
- **Goal**: Help users *understand*
- **Approach**: Discursive, contextual
- **Example**: "The Bronze-Silver-Gold Layer System"

```markdown
# The Layer System

FeedSpine uses a three-layer data quality model inspired by
medallion architecture.

## Why Layers?

Raw data from feeds is often messy...

## Layer Definitions

### Bronze Layer
The bronze layer contains raw, unprocessed data exactly as captured...
```

#### Reference (docs/reference/)
- **Goal**: Provide *accurate information*
- **Approach**: Austere, comprehensive
- **Generated from**: Docstrings (automatic)

---

## Maintenance Practices

### Documentation as Code

```yaml
# .github/workflows/ci.yml
- name: Check docs build
  run: uv run mkdocs build --strict

- name: Run doctests  
  run: uv run pytest --doctest-modules src/

- name: Check doc coverage
  run: uv run interrogate -v src/ --fail-under 80
```

### Doc Coverage with interrogate

```bash
uv add --group dev interrogate
uv run interrogate -v src/feedspine/
```

Add to `pyproject.toml`:

```toml
[tool.interrogate]
ignore-init-method = true
ignore-init-module = true
ignore-magic = true
ignore-semiprivate = true
ignore-private = true
ignore-property-decorators = true
ignore-module = false
ignore-nested-functions = true
ignore-nested-classes = true
fail-under = 80
verbose = 1
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/econchick/interrogate
  rev: 1.7.0
  hooks:
    - id: interrogate
      args: [--fail-under=80, src/]
```

### Review Checklist

When reviewing PRs, check:

- [ ] New public functions have docstrings
- [ ] Docstrings include Examples section
- [ ] Examples are runnable (doctests pass)
- [ ] Complex functions have Args/Returns/Raises
- [ ] Cross-references use proper syntax
- [ ] No broken links in docs

### Versioned Documentation

Read the Docs automatically versions docs by:
- Git tags (releases)
- Branches (latest, stable)

```yaml
# .readthedocs.yaml
version: 2
build:
  os: ubuntu-22.04
  tools:
    python: "3.12"

# Versions configured in RTD dashboard
```

---

## Implementation Checklist

### Phase 1: Foundation (Do Now)
- [ ] Add `interrogate` for doc coverage
- [ ] Update existing docstrings to Google style
- [ ] Add Examples to all public API functions
- [ ] Run doctests in CI

### Phase 2: Generator Setup
- [ ] Install MkDocs + mkdocstrings
- [ ] Create `mkdocs.yml` configuration
- [ ] Add auto-generation script
- [ ] Create initial docs structure

### Phase 3: Content
- [ ] Write `docs/index.md` (home page)
- [ ] Write `docs/getting-started.md`
- [ ] Create first tutorial
- [ ] Create first how-to guide

### Phase 4: Hosting
- [ ] Set up Read the Docs account
- [ ] Add `.readthedocs.yaml`
- [ ] Connect repository
- [ ] Configure custom domain (optional)

### Phase 5: Maintenance
- [ ] Add doc build to CI
- [ ] Add doctest to CI
- [ ] Add interrogate to pre-commit
- [ ] Document the documentation process

---

## Quick Reference Card

```python
"""One-line summary (imperative mood, <80 chars).

Extended description if needed. Can span multiple paragraphs.
Use reStructuredText formatting for emphasis and code.

Args:
    param1: Description of first parameter.
    param2: Description with type info if not in signature.
        Can wrap to multiple lines with indentation.

Returns:
    Description of return value. Include type if complex.

Raises:
    ValueError: When param1 is invalid.
    TypeError: When param2 has wrong type.

Example:
    >>> function_name("input")
    'expected output'

    Multiple examples are fine::

        >>> function_name("another")
        'another output'

See Also:
    - :func:`related_function`: Brief description
    - :class:`RelatedClass`: Brief description

Note:
    Important caveat or edge case information.

Warning:
    Critical information about dangerous behavior.

.. versionadded:: 0.2.0
.. versionchanged:: 0.3.0
   Description of what changed.
.. deprecated:: 0.4.0
   Use :func:`new_function` instead.
"""
```

---

## Resources

- [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [MkDocs Documentation](https://www.mkdocs.org/)
- [mkdocstrings](https://mkdocstrings.github.io/)
- [Diátaxis Framework](https://diataxis.fr/)
- [Read the Docs Tutorial](https://docs.readthedocs.io/en/stable/tutorial/)
- [interrogate - Doc Coverage](https://interrogate.readthedocs.io/)
