# Development Setup

Set up your development environment for contributing to FeedSpine.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git

## Quick Setup

```bash
# Clone the repository
git clone https://github.com/ryansmccoy/feedspine.git
cd feedspine

# Create virtual environment and install dependencies
uv sync

# Verify installation
uv run pytest
```

## Development Dependencies

The project includes several development tools:

| Tool | Purpose |
|------|---------|
| pytest | Testing |
| pytest-asyncio | Async test support |
| pytest-cov | Coverage reporting |
| ruff | Linting and formatting |
| mypy | Type checking |
| pre-commit | Git hooks |
| interrogate | Docstring coverage |
| mkdocs | Documentation |

## Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=feedspine

# Specific test file
uv run pytest tests/unit/storage/test_memory.py

# Run doctests
uv run pytest --doctest-modules src/
```

## Code Quality

```bash
# Lint and format
uv run ruff check src tests
uv run ruff format src tests

# Type checking
uv run mypy src

# Docstring coverage
uv run interrogate -v src/
```

## Pre-commit Hooks

Install hooks to run checks before each commit:

```bash
uv run pre-commit install
```

## Building Documentation

```bash
# Serve locally with hot reload
uv run mkdocs serve

# Build static site
uv run mkdocs build
```

## Project Structure

```
feedspine/
├── src/feedspine/        # Source code
│   ├── models/           # Pydantic data models
│   ├── protocols/        # Protocol definitions
│   ├── storage/          # Storage implementations
│   └── ...
├── tests/                # Tests (mirror src structure)
│   └── unit/
│       ├── models/
│       └── storage/
├── docs/                 # Documentation
└── scripts/              # Build scripts
```

## See Also

- [Documentation Guide](../DOCUMENTATION_GUIDE.md)
