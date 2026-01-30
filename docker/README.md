# FeedSpine Docker Infrastructure

Quick database setup for development and production.

## Quick Start

```bash
# Start PostgreSQL (development)
docker compose up -d postgres

# Or start everything
docker compose up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| **postgres** | 5432 | Standard PostgreSQL 16 |
| **timescale** | 5433 | TimescaleDB (time-series optimized) |
| **pgbouncer** | 6432 | Connection pooling |
| **redis** | 6379 | Caching layer |
| **adminer** | 8080 | Database admin UI (dev only) |

## Connection Strings

```python
# PostgreSQL
"postgresql://feedspine:feedspine@localhost:5432/feedspine"

# TimescaleDB
"postgresql://feedspine:feedspine@localhost:5433/feedspine"

# Through PgBouncer (high concurrency)
"postgresql://feedspine:feedspine@localhost:6432/feedspine"
```

## Data Directory

By default, data is stored in `./data/<service>/`. 

To use a different location:

```bash
# Set environment variable
export FEEDSPINE_DATA_DIR=/path/to/your/data

# Or use .env file
cp .env.example .env
# Edit FEEDSPINE_DATA_DIR in .env
```

## Usage with FeedSpine

### Development (SQLite)

```python
from feedspine.storage import create_storage

storage = create_storage("sqlite:///./data/feeds.db")
await storage.initialize()
```

### Production (PostgreSQL)

```python
from feedspine.storage import create_storage

storage = create_storage(
    "postgresql://feedspine:feedspine@localhost:5432/feedspine",
    pool_size=20,
)
await storage.initialize()
```

### Time-Series Data (TimescaleDB)

Best for observations, events, and time-partitioned data:

```python
storage = create_storage(
    "postgresql://feedspine:feedspine@localhost:5433/feedspine",
    use_timescale=True,
)
await storage.initialize()
```

### High Concurrency (PgBouncer)

```python
storage = create_storage(
    "postgresql://feedspine:feedspine@localhost:6432/feedspine",
    pool_size=0,  # Let PgBouncer handle pooling
)
```

### Environment Variables

```bash
export FEEDSPINE_DATABASE_URL=postgresql://feedspine:feedspine@localhost:5432/feedspine
export FEEDSPINE_ENV=production
```

```python
from feedspine.storage import storage_from_env

storage = storage_from_env()
```

## Scaling Guide

### Small Datasets (< 1M records)
- Standard PostgreSQL
- Default configuration
- Single instance

### Medium Datasets (1M - 100M records)
- Enable connection pooling (PgBouncer)
- Add indexes for common queries
- Consider TimescaleDB for time-series

### Large Datasets (100M+ records)
- TimescaleDB with compression (10x storage savings)
- Partitioning by month
- Read replicas for analytics
- Materialized views for aggregations

## Maintenance

### Backup

```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U feedspine feedspine > backup.sql

# Restore
docker compose exec -T postgres psql -U feedspine feedspine < backup.sql
```

### Vacuum/Analyze

```bash
docker compose exec postgres psql -U feedspine -c "VACUUM ANALYZE feedspine.records;"
```

### View Logs

```bash
docker compose logs -f postgres
```

## Development Tools

### Adminer (Database UI)

```bash
# Start with dev profile
docker compose --profile dev up -d

# Open http://localhost:8080
# Server: postgres
# Username: feedspine
# Password: feedspine
# Database: feedspine
```

### psql CLI

```bash
docker compose exec postgres psql -U feedspine feedspine
```

## Configuration

See `.env.example` for all configuration options:

```bash
# Database passwords
POSTGRES_PASSWORD=feedspine

# Port mappings
POSTGRES_PORT=5432
TIMESCALE_PORT=5433
PGBOUNCER_PORT=6432
REDIS_PORT=6379
ADMINER_PORT=8080

# Data directory
FEEDSPINE_DATA_DIR=./data
```

## Troubleshooting

### Port Conflicts

Change ports in `.env`:
```bash
POSTGRES_PORT=5433
```

### Permission Issues

On Linux, ensure data directory is writable:
```bash
sudo chown -R 999:999 ./data/postgres
```

### Connection Refused

Check if service is healthy:
```bash
docker compose ps
docker compose logs postgres
```
