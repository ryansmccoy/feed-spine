# Design Documents

This section contains the foundational design documents for FeedSpine.

## Core Design

- [Manifesto](manifesto.md) - The vision and principles behind FeedSpine
- [Framework Design](framework-design.md) - Detailed framework architecture
- [Python Architecture](python-architecture.md) - Package structure and protocols
- [Implementation Roadmap](implementation-roadmap.md) - Phased development plan

## Key Concepts

FeedSpine is built on these core principles:

1. **Storage Agnostic** - DuckDB, PostgreSQL, SQLite, Redis, MongoDB, filesystem
2. **Executor Agnostic** - Sync, AsyncIO, Celery, Prefect, Dagster, Airflow
3. **Protocol-based** - Swap any component without code changes
4. **Medallion Architecture** - Bronze → Silver → Gold data layers
5. **Multi-feed Deduplication** - Natural key-based with sighting history
