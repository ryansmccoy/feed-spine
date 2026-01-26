"""Protocol definitions - all extension points."""

from feedspine.protocols.blob import BlobInfo, BlobStorage
from feedspine.protocols.cache import CacheBackend
from feedspine.protocols.enricher import (
    Enricher,
    EnricherConfig,
    EnrichmentResult,
    EnrichmentStatus,
)
from feedspine.protocols.executor import Executor
from feedspine.protocols.feed import FeedAdapter
from feedspine.protocols.notification import Notification, Notifier, Severity
from feedspine.protocols.queue import Message, MessageQueue
from feedspine.protocols.scheduler import ScheduleInfo, Scheduler
from feedspine.protocols.search import SearchBackend, SearchResponse, SearchResult, SearchType
from feedspine.protocols.storage import StorageBackend
from feedspine.protocols.strategy import (
    BaseCollectionStrategy,
    CollectionPlan,
    CollectionStrategy,
    DateRange,
    IncrementalStrategy,
    SourceFetch,
    SourcePriority,
    date_range_days,
)

__all__ = [
    # Storage
    "StorageBackend",
    # Search
    "SearchBackend",
    "SearchResult",
    "SearchResponse",
    "SearchType",
    # Cache
    "CacheBackend",
    # Blob
    "BlobInfo",
    "BlobStorage",
    # Queue
    "Message",
    "MessageQueue",
    # Notification
    "Notification",
    "Notifier",
    "Severity",
    # Executor
    "Executor",
    # Feed
    "FeedAdapter",
    # Scheduler
    "ScheduleInfo",
    "Scheduler",
    # Enricher
    "Enricher",
    "EnricherConfig",
    "EnrichmentResult",
    "EnrichmentStatus",
    # Collection Strategy
    "CollectionStrategy",
    "IncrementalStrategy",
    "BaseCollectionStrategy",
    "CollectionPlan",
    "SourceFetch",
    "SourcePriority",
    "DateRange",
    "date_range_days",
]
