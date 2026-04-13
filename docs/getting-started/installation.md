---
title: "Installation"
type: guide
status: active
tags: [feed-spine, python]
created: 2026-02-22
updated: 2026-04-12
---
# Installation

## Requirements

- Python 3.12 or higher
- uv package manager (recommended) or pip

## Basic Installation

```bash
# Recommended
uv add feedspine

# Or with pip
pip install feedspine
```

## Installation with Extras

FeedSpine uses optional dependencies to keep the core lightweight. Install only what you need:

### Storage Backends

```bash
# SQLAlchemy (async) + Alembic migrations
uv add "feedspine[sqlalchemy]"

# PostgreSQL
uv add "feedspine[postgres]"

# DuckDB (embedded analytics)
uv add "feedspine[duckdb]"

# Redis cache
uv add "feedspine[redis]"

# All storage backends
uv add "feedspine[storage-all]"
```

### Search Backends

```bash
# Elasticsearch
uv add "feedspine[elasticsearch]"
```

### Entity Resolution

```bash
# Entity-spine integration
uv add "feedspine[entity]"
```

### API Server

```bash
# FastAPI + Uvicorn
uv add "feedspine[api]"
```

### Everything

```bash
uv add "feedspine[all]"
```

## Development Installation

For contributing to FeedSpine:

```bash
# Clone the repository
git clone https://github.com/ryansmccoy/feed-spine.git
cd feed-spine

# Install with uv (recommended)
uv sync
```

## Verify Installation

```python
>>> import feedspine
>>> feedspine.__version__
'0.3.0'
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Build your first feed collector
- [Tutorials](../tutorials/first-feed.md) - Step-by-step learning
