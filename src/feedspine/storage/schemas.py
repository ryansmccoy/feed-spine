"""Database schema definitions for FeedSpine.

This module contains the DDL (Data Definition Language) statements for both
SQLite and PostgreSQL backends. These schemas define the structure of:

- records: Main feed record storage with medallion layering
- sightings: Tracking when/where records were seen
- feed_runs: Collection run history and metrics
- record_versions: Version history for records
- feed_configs: Feed configuration storage
- observations: Domain-specific observations
- _feedspine_meta: Internal metadata storage

Usage:
    from feedspine.storage.schemas import SQLITE_SCHEMA, POSTGRES_SCHEMA

    # In FeedRepository.ensure_schema():
    schema = POSTGRES_SCHEMA if dialect.name == "postgresql" else SQLITE_SCHEMA
    for statement in schema.split(";"):
        ...
"""

SQLITE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY,
        natural_key TEXT NOT NULL UNIQUE,
        layer TEXT NOT NULL DEFAULT 'bronze',
        content TEXT NOT NULL,
        metadata TEXT,
        published_at TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        version INTEGER NOT NULL DEFAULT 1,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        seen_count INTEGER NOT NULL DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_records_layer ON records(layer);
    CREATE INDEX IF NOT EXISTS idx_records_published ON records(published_at);
    CREATE INDEX IF NOT EXISTS idx_records_captured ON records(captured_at);
    CREATE INDEX IF NOT EXISTS idx_records_natural_key ON records(natural_key);

    CREATE TABLE IF NOT EXISTS sightings (
        id TEXT PRIMARY KEY,
        natural_key TEXT NOT NULL,
        record_id TEXT,
        source TEXT NOT NULL,
        seen_at TEXT NOT NULL,
        is_new INTEGER NOT NULL DEFAULT 1,
        raw_data_hash TEXT,
        metadata TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_sightings_key ON sightings(natural_key);
    CREATE INDEX IF NOT EXISTS idx_sightings_source ON sightings(source);
    CREATE INDEX IF NOT EXISTS idx_sightings_seen ON sightings(seen_at);

    CREATE TABLE IF NOT EXISTS feed_runs (
        run_id TEXT PRIMARY KEY,
        feed_name TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        records_fetched INTEGER DEFAULT 0,
        records_new INTEGER DEFAULT 0,
        records_updated INTEGER DEFAULT 0,
        records_unchanged INTEGER DEFAULT 0,
        error_message TEXT,
        metadata TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_feed_runs_feed ON feed_runs(feed_name);

    CREATE TABLE IF NOT EXISTS record_versions (
        id TEXT PRIMARY KEY,
        record_key TEXT NOT NULL,
        version INTEGER NOT NULL,
        content TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        source TEXT NOT NULL,
        change_type TEXT NOT NULL,
        change_reason TEXT,
        parent_version INTEGER,
        metadata TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_versions_key ON record_versions(record_key);

    CREATE TABLE IF NOT EXISTS _feedspine_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS feed_configs (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        adapter_type TEXT NOT NULL,
        url TEXT,
        path TEXT,
        schedule TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        config TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_run_at TEXT,
        last_run_status TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_feed_configs_adapter ON feed_configs(adapter_type);
    CREATE INDEX IF NOT EXISTS idx_feed_configs_enabled ON feed_configs(enabled);

    CREATE TABLE IF NOT EXISTS observations (
        id TEXT PRIMARY KEY,
        observation_type TEXT NOT NULL,
        source TEXT NOT NULL,
        fingerprint TEXT NOT NULL UNIQUE,
        data TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_observations_type ON observations(observation_type);
    CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source);
    CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at);
    CREATE INDEX IF NOT EXISTS idx_observations_fingerprint ON observations(fingerprint);
"""

POSTGRES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY,
        natural_key TEXT NOT NULL UNIQUE,
        layer TEXT NOT NULL DEFAULT 'bronze',
        content JSONB NOT NULL,
        metadata JSONB,
        published_at TIMESTAMPTZ NOT NULL,
        captured_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        version INTEGER NOT NULL DEFAULT 1,
        first_seen_at TIMESTAMPTZ NOT NULL,
        last_seen_at TIMESTAMPTZ NOT NULL,
        seen_count INTEGER NOT NULL DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_records_layer ON records(layer);
    CREATE INDEX IF NOT EXISTS idx_records_published ON records(published_at);
    CREATE INDEX IF NOT EXISTS idx_records_captured ON records(captured_at);
    CREATE INDEX IF NOT EXISTS idx_records_natural_key ON records(natural_key);

    CREATE TABLE IF NOT EXISTS sightings (
        id TEXT PRIMARY KEY,
        natural_key TEXT NOT NULL,
        record_id TEXT,
        source TEXT NOT NULL,
        seen_at TIMESTAMPTZ NOT NULL,
        is_new BOOLEAN NOT NULL DEFAULT TRUE,
        raw_data_hash TEXT,
        metadata JSONB
    );

    CREATE INDEX IF NOT EXISTS idx_sightings_key ON sightings(natural_key);
    CREATE INDEX IF NOT EXISTS idx_sightings_source ON sightings(source);
    CREATE INDEX IF NOT EXISTS idx_sightings_seen ON sightings(seen_at);

    CREATE TABLE IF NOT EXISTS feed_runs (
        run_id TEXT PRIMARY KEY,
        feed_name TEXT NOT NULL,
        started_at TIMESTAMPTZ NOT NULL,
        completed_at TIMESTAMPTZ,
        status TEXT NOT NULL DEFAULT 'running',
        records_fetched INTEGER DEFAULT 0,
        records_new INTEGER DEFAULT 0,
        records_updated INTEGER DEFAULT 0,
        records_unchanged INTEGER DEFAULT 0,
        error_message TEXT,
        metadata JSONB
    );

    CREATE INDEX IF NOT EXISTS idx_feed_runs_feed ON feed_runs(feed_name);

    CREATE TABLE IF NOT EXISTS record_versions (
        id TEXT PRIMARY KEY,
        record_key TEXT NOT NULL,
        version INTEGER NOT NULL,
        content JSONB NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        source TEXT NOT NULL,
        change_type TEXT NOT NULL,
        change_reason TEXT,
        parent_version INTEGER,
        metadata JSONB
    );

    CREATE INDEX IF NOT EXISTS idx_versions_key ON record_versions(record_key);

    CREATE TABLE IF NOT EXISTS _feedspine_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS feed_configs (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        adapter_type TEXT NOT NULL,
        url TEXT,
        path TEXT,
        schedule TEXT,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        config JSONB,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        last_run_at TIMESTAMPTZ,
        last_run_status TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_feed_configs_adapter ON feed_configs(adapter_type);
    CREATE INDEX IF NOT EXISTS idx_feed_configs_enabled ON feed_configs(enabled);

    CREATE TABLE IF NOT EXISTS observations (
        id TEXT PRIMARY KEY,
        observation_type TEXT NOT NULL,
        source TEXT NOT NULL,
        fingerprint TEXT NOT NULL UNIQUE,
        data JSONB NOT NULL,
        metadata JSONB,
        created_at TIMESTAMPTZ NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_observations_type ON observations(observation_type);
    CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source);
    CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at);
    CREATE INDEX IF NOT EXISTS idx_observations_fingerprint ON observations(fingerprint);
"""

__all__ = ["SQLITE_SCHEMA", "POSTGRES_SCHEMA"]
