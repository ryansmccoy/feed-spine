"""FeedSpine - Storage-Agnostic Feed Capture Framework.

Stability: stable
Tier: full
Since: 0.1.0
Dependencies: duckdb, httpx, pydantic, fastapi
Doc-Types: API_REFERENCE, GUIDE
Tags: feed_collection, medallion, deduplication, pipeline, rss

FeedSpine is a protocol-based framework for building data collection pipelines
with automatic deduplication, sighting history, and medallion architecture.

Quick Start:
    >>> from feedspine import create_feed_spine, MemoryStorage, RSSFeedAdapter
    >>> storage = MemoryStorage()
    >>> app = create_feed_spine(storage)
    >>> app.register_feed(RSSFeedAdapter(name="news", url="https://..."))

Import submodules directly for the full API surface::

    from feedspine.protocols.storage import StorageBackend
    from feedspine.models.record import Record
    from feedspine.ops import OperationContext
"""

__version__ = "0.3.0"

# ── Models ────────────────────────────────────────────────────────────────
from feedspine.adapter.base import BaseFeedAdapter, FeedAdapter, FeedError
from feedspine.adapter.json import JSONFeedAdapter
from feedspine.adapter.rss import RSSFeedAdapter
from feedspine.core.app import FeedSpineApp, create_feed_spine
from feedspine.enricher.metadata import MetadataEnricher
from feedspine.enricher.passthrough import PassthroughEnricher
from feedspine.models.base import Layer
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.sighting import Sighting
from feedspine.pipeline import Pipeline, PipelineStats, ProcessAction, ProcessResult
from feedspine.search.memory import MemorySearch
from feedspine.services.collection import CollectionOutcome, FeedCollectionService
from feedspine.storage.memory import MemoryStorage

# ── Optional backends (require extra dependencies) ────────────────────────
try:
    from feedspine.storage.backends.duckdb import DuckDBStorage
except ImportError:
    DuckDBStorage = None  # type: ignore[misc,assignment]

try:
    from feedspine.search.elasticsearch import ElasticsearchSearch
except ImportError:
    ElasticsearchSearch = None  # type: ignore[misc,assignment]

__all__ = [
    "__version__",
    # Models
    "Layer",
    "Record",
    "RecordCandidate",
    "Sighting",
    # Pipeline
    "Pipeline",
    "PipelineStats",
    "ProcessAction",
    "ProcessResult",
    # Storage
    "MemoryStorage",
    "DuckDBStorage",
    # Search
    "MemorySearch",
    "ElasticsearchSearch",
    # Adapters
    "FeedAdapter",
    "BaseFeedAdapter",
    "FeedError",
    "RSSFeedAdapter",
    "JSONFeedAdapter",
    # Enrichers
    "PassthroughEnricher",
    "MetadataEnricher",
    # App Factory
    "FeedSpineApp",
    "create_feed_spine",
    # Services
    "FeedCollectionService",
    "CollectionOutcome",
]
