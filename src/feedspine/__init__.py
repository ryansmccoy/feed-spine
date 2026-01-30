"""
FeedSpine - Storage-Agnostic Feed Capture Framework.

FeedSpine is a protocol-based framework for building data collection pipelines
with automatic deduplication, sighting history, and medallion architecture.

Key Features:
- Protocol-based design (swap backends without code changes)
- Medallion architecture (Bronze → Silver → Gold)
- Automatic natural key deduplication
- Complete sighting history tracking
- Checkpoint/resume for long-running jobs

Quick Start:
    >>> from feedspine import FeedSpine, MemoryStorage, RSSFeedAdapter
    >>> storage = MemoryStorage()
    >>> async with FeedSpine(storage=storage) as spine:
    ...     spine.register_feed(RSSFeedAdapter(name="news", url="https://..."))
    ...     result = await spine.collect()

Architecture:
    Storage Backends: MemoryStorage, DuckDBStorage
    Feed Adapters: RSSFeedAdapter, JSONFeedAdapter
    Enrichers: PassthroughEnricher, MetadataEnricher
    Search: MemorySearch, ElasticsearchSearch

See Also:
    - https://github.com/ryansmccoy/feed-spine
    - entityspine: Domain models for entity resolution
    - capture-spine: Point-in-time content capture
"""

# Feed adapters
from feedspine.adapter.base import BaseFeedAdapter, FeedAdapter, FeedError
from feedspine.adapter.json import JSONFeedAdapter
from feedspine.adapter.rss import RSSFeedAdapter

# Blob storage backends
from feedspine.blob.filesystem import FilesystemBlob

# Cache backends
from feedspine.cache.memory import MemoryCache

# Core orchestration
from feedspine.core.feedspine import CollectionResult, FeedSpine

# Enrichers
from feedspine.enricher.metadata import MetadataEnricher
from feedspine.enricher.passthrough import PassthroughEnricher

# Executor backends
from feedspine.executor.sync import SyncExecutor
from feedspine.models.base import Layer
from feedspine.models.feed_run import FeedRun, FeedRunStatus
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.sighting import Sighting
from feedspine.models.task import Task, TaskResult, TaskStatus

# Notifier backends
from feedspine.notifier.console import ConsoleNotifier
from feedspine.pipeline import Pipeline, PipelineStats

# Progress reporting
from feedspine.protocols.progress import (
    CallbackProgressReporter,
    NullProgressReporter,
    ProgressEvent,
    ProgressReporter,
    ProgressStage,
)

# Queue backends
from feedspine.queue.memory import MemoryQueue

# Scheduler
from feedspine.scheduler.memory import MemoryScheduler

# Search backends
from feedspine.search.memory import MemorySearch

# Storage backends
from feedspine.storage.memory import MemoryStorage

# Retry utilities
from feedspine.utils.retry import RetryConfig, RetryExhausted, retry, with_retry

# Optional backends (require extra dependencies)
# DuckDB storage (install with: pip install feedspine[duckdb])
try:
    from feedspine.storage.duckdb import DuckDBStorage
except ImportError:
    DuckDBStorage = None  # type: ignore[misc,assignment]

# Elasticsearch search (install with: pip install feedspine[elasticsearch])
try:
    from feedspine.search.elasticsearch import ElasticsearchSearch
except ImportError:
    ElasticsearchSearch = None  # type: ignore[misc,assignment]

# FastAPI integration (install with: pip install feedspine[api])
try:
    from feedspine.api.fastapi import create_app as create_api_app
except ImportError:
    create_api_app = None  # type: ignore[assignment]

# Core resources and checkpoint support
from feedspine.core.checkpoint import (
    Checkpoint,
    CheckpointManager,
    CheckpointStore,
    FileCheckpointStore,
    MemoryCheckpointStore,
)
from feedspine.core.resources import RateLimiter, ResourcePool, Semaphore

# Model extensions
from feedspine.models.content import (
    ContentSchema,
    TypedRecord,
    clear_content_registry,
    get_content_schema,
    register_content_schema,
)
from feedspine.models.converter import (
    ConverterRegistry,
    RecordConverter,
    converter_registry,
)
from feedspine.models.query import Query, QuerySpec

# Enricher protocols
from feedspine.protocols.enricher import (
    BatchEnricher,
    BatchEnrichmentResult,
    EnricherConfig,
    EnrichmentResult,
    EnrichmentStatus,
)

# HTTP utilities (rate limiting, downloads)
from feedspine.http import HttpClient, RateLimiter as HttpRateLimiter
from feedspine.http.client import HttpClientError, RateLimitError, DownloadError

# Metrics collection
from feedspine.metrics import CollectionMetrics, MetricsSummary

# Progress reporter implementations
try:
    from feedspine.reporter import RichProgressReporter, SimpleProgressReporter
except ImportError:
    RichProgressReporter = None  # type: ignore[misc,assignment]
    SimpleProgressReporter = None  # type: ignore[misc,assignment]

# Adapter discovery
from feedspine.discovery import (
    clear_cache as clear_adapter_cache,
    discover_adapters,
    get_adapter,
    list_adapters,
    register_adapter,
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "Layer",
    "Record",
    "RecordCandidate",
    "Sighting",
    "Task",
    "TaskResult",
    "TaskStatus",
    # Feed run tracking
    "FeedRun",
    "FeedRunStatus",
    # Content typing
    "ContentSchema",
    "TypedRecord",
    "register_content_schema",
    "get_content_schema",
    "clear_content_registry",
    # Converter registry
    "ConverterRegistry",
    "RecordConverter",
    "converter_registry",
    # Query builder
    "Query",
    "QuerySpec",
    # Storage
    "MemoryStorage",
    "DuckDBStorage",
    # Cache
    "MemoryCache",
    # Executor
    "SyncExecutor",
    # Queue
    "MemoryQueue",
    # Search
    "MemorySearch",
    "ElasticsearchSearch",
    # Blob
    "FilesystemBlob",
    # Notifier
    "ConsoleNotifier",
    # Pipeline
    "Pipeline",
    "PipelineStats",
    # Progress
    "ProgressReporter",
    "ProgressEvent",
    "ProgressStage",
    "NullProgressReporter",
    "CallbackProgressReporter",
    # Progress reporter implementations
    "RichProgressReporter",
    "SimpleProgressReporter",
    # Retry
    "RetryConfig",
    "RetryExhausted",
    "with_retry",
    "retry",
    # Adapters
    "FeedAdapter",
    "BaseFeedAdapter",
    "FeedError",
    "RSSFeedAdapter",
    "JSONFeedAdapter",
    # Scheduler
    "MemoryScheduler",
    # Enrichers
    "PassthroughEnricher",
    "MetadataEnricher",
    "BatchEnricher",
    "BatchEnrichmentResult",
    "EnricherConfig",
    "EnrichmentResult",
    "EnrichmentStatus",
    # Orchestration
    "FeedSpine",
    "CollectionResult",
    # Resources
    "ResourcePool",
    "RateLimiter",
    "Semaphore",
    # HTTP utilities
    "HttpClient",
    "HttpRateLimiter",
    "HttpClientError",
    "RateLimitError",
    "DownloadError",
    # Metrics
    "CollectionMetrics",
    "MetricsSummary",
    # Checkpointing
    "Checkpoint",
    "CheckpointManager",
    "CheckpointStore",
    "MemoryCheckpointStore",
    "FileCheckpointStore",
    # API
    "create_api_app",
    # Adapter discovery
    "discover_adapters",
    "get_adapter",
    "list_adapters",
    "register_adapter",
    "clear_adapter_cache",
    # Version
    "__version__",
]
