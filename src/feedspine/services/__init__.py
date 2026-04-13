"""Feed-spine service layer — domain application services.

Services encapsulate business logic with clear single responsibilities:

- ``FeedCollectionService``: adapter → pipeline → storage (domain execution)
- ``CollectionOutcomeRecorder``: writes operational side effects (watermark, etc.)
- ``CollectionEventPublisher``: emits completion events via EventStore
"""

from __future__ import annotations

from feedspine.services.collection import CollectionOutcome, FeedCollectionService
from feedspine.services.publishing import CollectionEventPublisher
from feedspine.services.recording import CollectionOutcomeRecorder

__all__ = [
    "CollectionOutcome",
    "CollectionEventPublisher",
    "CollectionOutcomeRecorder",
    "FeedCollectionService",
]
