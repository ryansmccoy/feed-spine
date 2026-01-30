# Changelog - FeedSpine

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **entityspine Integration** - Storage backends now support entityspine domain models
  - Records can be linked to Entity, Security, Listing via `entity_id` field
  - `resolve_entity()` helper in storage for cross-referencing
  - Why: Enables entity-centric queries across all captured content
  
- **Enhanced Record Model** - Extended `Record` with provenance fields
  - `captured_at`, `source_system`, `source_id` for lineage tracking
  - `content_hash` for deduplication across sources
  - Why: Supports Bronze/Silver/Gold medallion architecture with full audit trail

- **Storage Protocol Extensions** - New storage capabilities
  - `get_by_entity()` - Retrieve all records for an entity
  - `get_by_source()` - Filter by source system
  - `count_by_type()` - Analytics over record types
  - Why: Enables capture-spine and trading-desktop to query by entity context

- **Enricher Framework** - Extensible content enrichment
  - `Enricher` protocol for pluggable enrichment
  - `EntityResolver` enricher for automatic entity linking
  - Why: Automates entity resolution during ingestion

- **Feature Documentation** - Comprehensive feature planning docs
  - `docs/features/` - 8K release capture, earnings intelligence, chat ingestion
  - Integration guides for capture-spine and trading-desktop
  - Why: Documents planned 1.0.0 release features

### Changed
- Standardized CI/CD workflows with uv
- Improved test coverage for storage backends

---

## [0.1.0] - 2026-01-15

### Added
- Core `FeedSpine` orchestration class
- `Pipeline` and `PipelineStats` for data flow management
- Protocol-based storage backends (`MemoryStorage`, `DuckDBStorage`)
- Feed adapters (`RSSFeedAdapter`, `JSONFeedAdapter`)
- Checkpoint/resume support for long-running jobs
- Progress reporting with callbacks
- Content schema registry for typed records
- Medallion architecture (Bronze → Silver → Gold layers)
- Automatic natural key deduplication
- Complete sighting history tracking

### Infrastructure
- mkdocs documentation setup
- GitHub Actions CI pipeline
- Docker support

---

## Ecosystem Impact

### Why FeedSpine + entityspine?

| Before | After |
|--------|-------|
| Records stored without entity context | Records linked to canonical entities |
| Duplicate content across sources | Content-hash deduplication |
| No audit trail | Full provenance tracking |
| Source-specific queries | Entity-centric queries |

### What This Enables

1. **capture-spine** can query "all news about Apple Inc." regardless of source
2. **trading-desktop** can show entity context on any content
3. **Compliance** can trace any data back to source and capture time

---

*For feature highlights, see [FEATURES.md](FEATURES.md).*
