---
title: "Project Structure"
type: reference
status: active
tags: [feedspine]
created: 2026-01-15
updated: 2026-06-15
---
# Ideal Python Project Structure

> **Purpose:** Reference guide for standardized project layout
> **Applies To:** All spine ecosystem projects
> **Version:** 1.0
> **Created:** February 1, 2026

---

## 📁 Root Directory Structure

```
project-name/
├── .github/                    # GitHub-specific configuration
│   ├── workflows/              # CI/CD pipelines
│   │   ├── ci.yml              # Main CI (lint, test, build)
│   │   ├── release.yml         # PyPI publishing
│   │   └── docs.yml            # Documentation deployment
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
│
├── docs/                       # Documentation (MkDocs source)
│   └── (see detailed structure below)
│
├── examples/                   # Runnable example scripts
│   ├── basic_usage.py
│   ├── advanced_features.py
│   └── README.md
│
├── scripts/                    # Development/maintenance scripts
│   ├── audit.py                # Code quality audit
│   ├── benchmark.py            # Performance benchmarks
│   └── generate_docs.py        # API doc generation
│
├── src/                        # Source code (src layout)
│   └── package_name/
│       └── (see detailed structure below)
│
├── tests/                      # Test suite
│   └── (see detailed structure below)
│
├── .editorconfig               # Editor configuration
├── .gitignore                  # Git ignore patterns
├── .pre-commit-config.yaml     # Pre-commit hooks
├── .python-version             # Python version (pyenv)
├── CHANGELOG.md                # Version history
├── LICENSE                     # License file
├── Makefile                    # Common commands
├── justfile                    # Just task runner (alternative to Make)
├── mkdocs.yml                  # MkDocs configuration
├── pyproject.toml              # Project metadata & tools config
├── pytest.ini                  # Pytest configuration (if not in pyproject.toml)
├── README.md                   # Project overview
└── requirements/               # Pinned dependencies (optional)
    ├── base.txt                # Core dependencies
    ├── dev.txt                 # Development dependencies
    └── docs.txt                # Documentation dependencies
```

---

## 📚 Ideal `docs/` Structure

```
docs/
├── index.md                    # Landing page (required for MkDocs)
├── CHANGELOG.md                # Symlink or copy from root
├── FEATURES.md                 # Feature overview
│
├── getting-started/            # 🚀 Quick start guides
│   ├── installation.md         # How to install
│   ├── quickstart.md           # 5-minute tutorial
│   └── configuration.md        # Configuration options
│
├── tutorials/                  # 📖 Step-by-step learning
│   ├── first-steps.md          # Beginner tutorial
│   ├── intermediate.md         # Building on basics
│   └── advanced.md             # Complex scenarios
│
├── how-to/                     # 🔧 Task-oriented guides
│   ├── custom-storage.md       # How to implement X
│   ├── custom-adapter.md       # How to extend Y
│   └── deployment.md           # How to deploy
│
├── concepts/                   # 💡 Explanation of key concepts
│   ├── architecture.md         # System architecture
│   ├── protocols.md            # Protocol pattern explanation
│   └── data-model.md           # Core data model
│
├── reference/                  # 📋 API reference (auto-generated)
│   ├── api/                    # Module documentation
│   │   ├── models.md
│   │   ├── storage.md
│   │   └── ...
│   ├── cli.md                  # CLI command reference
│   └── configuration.md        # Config schema reference
│
├── design/                     # 🏗️ Architecture decisions
│   ├── architecture.md         # High-level design
│   ├── patterns.md             # Design patterns used
│   ├── decisions/              # Architecture Decision Records (ADRs)
│   │   ├── 001-storage-protocol.md
│   │   └── 002-pydantic-models.md
│   └── roadmap.md              # Future plans
│
├── contributing/               # 👥 Contributor guides
│   ├── setup.md                # Development setup
│   ├── code-style.md           # Coding standards
│   ├── testing.md              # How to write tests
│   └── releasing.md            # Release process
│
├── release/                    # 📦 Release documentation
│   ├── checklist.md            # Pre-release checklist
│   ├── audit.md                # Release audit template
│   └── history.md              # Detailed release notes
│
├── prompts/                    # 🤖 AI/LLM prompts (if applicable)
│   └── ...
│
├── archive/                    # 📁 Historical/completed docs
│   └── ...
│
└── stylesheets/                # 🎨 MkDocs custom CSS
    └── extra.css
```

### Documentation Principles

| Folder | Question It Answers | Audience |
|--------|---------------------|----------|
| `getting-started/` | "How do I get this running?" | New users |
| `tutorials/` | "How do I learn this step-by-step?" | Learning users |
| `how-to/` | "How do I accomplish X?" | Working users |
| `concepts/` | "Why does this work this way?" | Understanding users |
| `reference/` | "What exactly does X do?" | All users |
| `design/` | "How is this built?" | Contributors |
| `contributing/` | "How do I contribute?" | Contributors |

---

## 🧪 Ideal `tests/` Structure

```
tests/
├── conftest.py                 # Shared fixtures
├── pytest.ini                  # Test configuration (if not in pyproject.toml)
│
├── unit/                       # 🔬 Unit tests (fast, isolated)
│   ├── conftest.py             # Unit test fixtures
│   ├── models/
│   │   ├── test_base.py
│   │   ├── test_record.py
│   │   └── ...
│   ├── storage/
│   │   ├── test_memory.py
│   │   ├── test_sqlite.py
│   │   └── ...
│   └── services/
│       └── ...
│
├── integration/                # 🔗 Integration tests (real dependencies)
│   ├── conftest.py             # Integration fixtures (DB setup, etc.)
│   ├── test_database.py
│   ├── test_elasticsearch.py
│   └── test_api.py
│
├── e2e/                        # 🌐 End-to-end tests (full system)
│   ├── conftest.py
│   └── test_workflows.py
│
├── performance/                # ⚡ Performance/benchmark tests
│   ├── conftest.py
│   ├── test_bulk_insert.py
│   └── test_search_latency.py
│
├── fixtures/                   # 📦 Test data and fixtures
│   ├── data/
│   │   ├── sample.json
│   │   └── sample.csv
│   └── factories.py            # Test object factories
│
└── smoke/                      # 💨 Quick sanity checks
    └── test_imports.py
```

### Test Organization Principles

| Folder | Characteristics | When to Run |
|--------|-----------------|-------------|
| `unit/` | Fast (<1s), no I/O, mocked deps | Every commit |
| `integration/` | Medium speed, real DB/services | Every PR |
| `e2e/` | Slow, full system | Pre-release |
| `performance/` | Benchmarks, may be slow | On demand |
| `smoke/` | Quick sanity checks | CI first step |

### Naming Conventions

```python
# File naming
test_<module_name>.py           # Test file
conftest.py                     # Fixtures

# Function naming
def test_<what>_<when>_<expected>():
    """Test <what> when <condition> should <expected>."""
    pass

# Examples:
def test_record_creation_with_valid_data_succeeds(): ...
def test_record_creation_with_missing_key_raises_error(): ...
def test_search_with_empty_query_returns_all(): ...
```

---

## 📦 Ideal `src/package_name/` Structure

```
src/
└── package_name/
    ├── __init__.py             # Package exports, version
    ├── py.typed                 # PEP 561 marker
    │
    ├── core/                   # 🎯 Core abstractions
    │   ├── __init__.py
    │   ├── config.py           # Configuration (pydantic-settings)
    │   ├── exceptions.py       # Custom exceptions
    │   └── types.py            # Type aliases, protocols
    │
    ├── models/                 # 📊 Pydantic models
    │   ├── __init__.py
    │   ├── base.py             # Base model class
    │   ├── record.py           # Domain models
    │   └── ...
    │
    ├── protocols/              # 🔌 Interface definitions (typing.Protocol)
    │   ├── __init__.py
    │   ├── storage.py          # StorageBackend protocol
    │   ├── search.py           # SearchBackend protocol
    │   └── ...
    │
    ├── storage/                # 💾 Storage implementations
    │   ├── __init__.py
    │   ├── memory.py           # In-memory (testing)
    │   ├── sqlite.py           # SQLite
    │   └── postgres.py         # PostgreSQL
    │
    ├── services/               # ⚙️ Business logic
    │   ├── __init__.py
    │   └── ...
    │
    ├── api/                    # 🌐 API layer (if applicable)
    │   ├── __init__.py
    │   ├── routers/
    │   └── schemas.py
    │
    ├── cli/                    # 💻 CLI commands (Typer/Click)
    │   ├── __init__.py
    │   ├── main.py             # CLI entry point
    │   └── commands/
    │
    └── _internal/              # 🔒 Private implementation details
        └── ...
```

### Module Organization Principles

| Folder | Contents | Import Pattern |
|--------|----------|----------------|
| `core/` | Config, exceptions, base types | `from pkg.core import Config` |
| `models/` | Pydantic data models | `from pkg.models import Record` |
| `protocols/` | Abstract interfaces | `from pkg.protocols import StorageBackend` |
| `storage/` | Protocol implementations | `from pkg.storage import SQLiteStorage` |
| `services/` | Business logic | `from pkg.services import RecordService` |
| `api/` | HTTP/REST layer | Internal to API |
| `cli/` | CLI commands | Entry point only |

---

## 📝 Essential Configuration Files

### `pyproject.toml` (Complete Example)

```toml
[project]
name = "package-name"
version = "0.1.0"
description = "Short description"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Author Name", email = "author@example.com" }]
keywords = ["keyword1", "keyword2"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Typing :: Typed",
]

dependencies = [
    "pydantic>=2.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.3",
    "mypy>=1.8",
]
docs = [
    "mkdocs>=1.5",
    "mkdocs-material>=9.0",
    "mkdocstrings[python]>=0.24",
]

[project.scripts]
package-name = "package_name.cli:main"

[project.urls]
Homepage = "https://github.com/org/package-name"
Documentation = "https://org.github.io/package-name"
Repository = "https://github.com/org/package-name"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/package_name"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra -q"

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "@overload",
]
```

### `Makefile` (Common Commands)

```makefile
.PHONY: help install test lint format docs serve clean

help:
	@echo "Available commands:"
	@echo "  install    Install package with dev dependencies"
	@echo "  test       Run test suite"
	@echo "  lint       Run linting checks"
	@echo "  format     Format code"
	@echo "  docs       Build documentation"
	@echo "  serve      Serve documentation locally"
	@echo "  clean      Clean build artifacts"

install:
	uv sync

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

docs:
	mkdocs build --strict

serve:
	mkdocs serve --dev-addr 127.0.0.1:8000

clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
```

### `justfile` (Alternative to Make)

```just
# Default recipe
default:
    @just --list

# Install with dev dependencies
install:
    uv sync

# Run all tests
test:
    pytest tests/ -v --cov=src

# Run unit tests only
test-unit:
    pytest tests/unit -v

# Run linting
lint:
    ruff check src/ tests/
    mypy src/

# Format code
format:
    ruff check --fix src/ tests/
    ruff format src/ tests/

# Build documentation
docs:
    mkdocs build --strict

# Serve documentation
serve:
    mkdocs serve --dev-addr 127.0.0.1:8000

# Run pre-commit checks
check:
    pre-commit run --all-files

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info/
    find . -type d -name __pycache__ -exec rm -rf {} +

# Bump version (patch/minor/major)
bump version:
    hatch version {{version}}

# Build package
build:
    hatch build

# Publish to PyPI
publish: build
    hatch publish
```

---

## 🔍 Docstring Standards

### Module Docstring

```python
"""Module short description.

Extended description of what this module does and why.

Example:
    >>> from package import module
    >>> module.function()
    'result'

Attributes:
    MODULE_CONSTANT: Description of module-level constant.

Note:
    Any important notes about the module.
"""
```

### Class Docstring

```python
class MyClass:
    """Short description of the class.

    Extended description with more details about the class purpose,
    behavior, and usage patterns.

    Attributes:
        field_name: Description of the field.
        another_field: Description of another field.

    Example:
        >>> obj = MyClass(field_name="value")
        >>> obj.method()
        'result'

    Note:
        Important notes about class usage.
    """
```

### Function/Method Docstring

```python
def function(
    param1: str,
    param2: int = 10,
    *,
    keyword_only: bool = False,
) -> dict[str, Any]:
    """Short description of function.

    Extended description if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.
        keyword_only: Description. Defaults to False.

    Returns:
        Description of what is returned.

    Raises:
        ValueError: When param1 is empty.
        TypeError: When param2 is not an integer.

    Example:
        >>> function("hello", param2=20)
        {'key': 'value'}

    Note:
        Any important implementation notes.
    """
```

---

## ✅ Pre-Release Checklist

### Code Quality
- [ ] All tests pass (`pytest tests/`)
- [ ] Test coverage > 80% (`pytest --cov`)
- [ ] No linting errors (`ruff check`)
- [ ] No type errors (`mypy src/`)
- [ ] All docstrings present and valid

### Documentation
- [ ] README.md is current
- [ ] CHANGELOG.md updated
- [ ] Docs build without errors (`mkdocs build --strict`)
- [ ] All public API documented
- [ ] Examples run successfully

### Package
- [ ] Version bumped appropriately
- [ ] Dependencies pinned correctly
- [ ] Package builds (`hatch build`)
- [ ] Package installs in clean venv
- [ ] CLI commands work (if applicable)

### Release
- [ ] Git tag created
- [ ] GitHub release drafted
- [ ] PyPI credentials ready
- [ ] Docs deployment configured

---

## 🎯 Summary

| Aspect | Standard |
|--------|----------|
| **Layout** | `src/` layout with `pyproject.toml` |
| **Models** | Pydantic v2 with `FeedSpineModel` base |
| **Protocols** | `typing.Protocol` for interfaces |
| **Testing** | pytest with unit/integration/e2e split |
| **Documentation** | MkDocs Material with Diátaxis structure |
| **Formatting** | Ruff for lint + format |
| **Type Checking** | mypy in strict mode |
| **Task Runner** | Makefile or justfile |
| **CI/CD** | GitHub Actions |

---

*This document should be kept in `docs/contributing/project-structure.md` for each project.*
