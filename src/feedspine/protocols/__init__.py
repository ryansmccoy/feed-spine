"""Protocol definitions — public extension points.

Import directly from submodules for the full API surface::

    from feedspine.protocols.storage import StorageBackend
    from feedspine.protocols.search import SearchBackend
    from feedspine.protocols.feed import FeedAdapter
"""

from feedspine.protocols.enricher import Enricher
from feedspine.protocols.feed import FeedAdapter
from feedspine.protocols.progress import ProgressReporter
from feedspine.protocols.search import SearchBackend
from feedspine.protocols.storage import RecordStore, SightingStore, StorageBackend, StorageLifecycle

__all__ = [
    "StorageBackend",
    "RecordStore",
    "SightingStore",
    "StorageLifecycle",
    "SearchBackend",
    "FeedAdapter",
    "Enricher",
    "ProgressReporter",
]
