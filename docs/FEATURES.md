# Feature History - FeedSpine

<!-- Auto-generated from commits. Run `make todos` or edit manually for major features. -->

> Track new features as they're added. Newest first.

---

## 2026-01-15 - Checkpoint/Resume Support (v0.1.0)

- Add `Checkpoint`, `CheckpointManager`, `CheckpointStore`
- `FileCheckpointStore` and `MemoryCheckpointStore` implementations
- Resume long-running collections from last checkpoint

## 2026-01-12 - Progress Reporting Protocol

- Add `ProgressReporter` protocol
- `CallbackProgressReporter`, `NullProgressReporter`
- `ProgressEvent` and `ProgressStage` enums

## 2026-01-10 - Content Schema Registry

- Add `ContentSchema`, `TypedRecord`
- `register_content_schema`, `get_content_schema`
- Type-safe record handling

## 2026-01-08 - Core Pipeline Architecture

- `Pipeline` and `PipelineStats` for orchestration
- `FeedSpine` main class with context manager support
- Medallion architecture (Bronze → Silver → Gold)

## 2026-01-05 - Storage Backends

- `MemoryStorage` for development
- `DuckDBStorage` for analytics (optional)
- Protocol-based design for swappable backends

## 2026-01-01 - Feed Adapters

- `BaseFeedAdapter`, `RSSFeedAdapter`, `JSONFeedAdapter`
- Natural key deduplication
- Sighting history tracking

---

*This file documents major feature additions. For detailed changes, see [CHANGELOG.md](CHANGELOG.md).*
