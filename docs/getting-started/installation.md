# Installation

## Requirements

- Python 3.11 or higher
- pip or uv package manager

## Basic Installation

=== "pip"

    ```bash
    pip install feedspine
    ```

=== "uv"

    ```bash
    uv add feedspine
    ```

=== "poetry"

    ```bash
    poetry add feedspine
    ```

## Installation with Extras

FeedSpine uses optional dependencies to keep the core lightweight. Install only what you need:

### Storage Backends

```bash
# PostgreSQL
pip install feedspine[postgres]

# SQLite (async)
pip install feedspine[sqlite]

# DuckDB (embedded analytics)
pip install feedspine[duckdb]

# Redis
pip install feedspine[redis]

# MongoDB
pip install feedspine[mongo]

# All storage backends
pip install feedspine[storage-all]
```

### Search Backends

```bash
# Elasticsearch
pip install feedspine[elasticsearch]

# Meilisearch
pip install feedspine[meilisearch]
```

### Vector Search

```bash
# ChromaDB
pip install feedspine[chroma]

# Qdrant
pip install feedspine[qdrant]
```

### Queue Backends

```bash
# RabbitMQ
pip install feedspine[rabbitmq]

# Kafka
pip install feedspine[kafka]
```

### Executors

```bash
# Celery
pip install feedspine[celery]

# Prefect
pip install feedspine[prefect]
```

### Everything

```bash
pip install feedspine[all]
```

## Development Installation

For contributing to FeedSpine:

```bash
# Clone the repository
git clone https://github.com/ryansmccoy/feedspine.git
cd feedspine

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e ".[dev,docs]"
```

## Verify Installation

```python
>>> import feedspine
>>> feedspine.__version__
'0.1.0'
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Build your first feed collector
- [Tutorials](../tutorials/first-feed.md) - Step-by-step learning
