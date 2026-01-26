# Changelog

All notable changes to FeedSpine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-01-24

### Added

#### Core Framework
- `FeedSpine` orchestrator class for coordinating feed collection
- `Pipeline` class for stage-based feed processing with deduplication
- Protocol-based architecture with 8 extension points:
  - `StorageBackend` - Record persistence
  - `SearchBackend` - Full-text and semantic search
  - `CacheBackend` - Key-value caching
  - `BlobStorage` - Large file storage
  - `MessageQueue` - Pub/sub messaging
  - `Notifier` - Alert notifications
  - `Executor` - Task execution
  - `FeedAdapter` - Feed parsing

#### Models
- `Layer` enum for medallion architecture (Bronze → Silver → Gold)
- `Record` and `RecordCandidate` for data representation
- `Sighting` for tracking when records are first seen
- `Task` and `TaskResult` for executor communication
- `Metadata` for source attribution

#### Storage Backends
- `MemoryStorage` - In-memory storage for testing
- `DuckDBStorage` - Embedded analytics database (requires `feedspine[duckdb]`)

#### Search Backends
- `MemorySearch` - Linear search for testing
- `ElasticsearchSearch` - Full-text search (requires `feedspine[elasticsearch]`)

#### Feed Adapters
- `RSSFeedAdapter` - RSS/Atom feed parsing
- `JSONFeedAdapter` - JSON API responses
- `BaseFeedAdapter` - Base class for custom adapters

#### Other Components
- `MemoryCache` - In-memory cache with TTL
- `MemoryQueue` - In-memory message queue
- `FilesystemBlob` - Local file blob storage
- `ConsoleNotifier` - Console output notifications
- `SyncExecutor` - Synchronous task execution
- `MemoryScheduler` - Cron-based scheduling

#### Infrastructure
- CLI via Typer (`feedspine` command)
- FastAPI integration (requires `feedspine[api]`)
- Docker Compose configuration
- Kubernetes manifests (Kustomize)

#### Documentation
- MkDocs documentation with Material theme
- Getting started guide
- Architecture concepts
- How-to guides for custom backends
- Industry-specific examples

### Notes

This is the initial public release of FeedSpine. The API should be considered
unstable until v1.0.0. Breaking changes may occur in 0.x releases.

[Unreleased]: https://github.com/ryansmccoy/feedspine/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ryansmccoy/feedspine/releases/tag/v0.1.0
