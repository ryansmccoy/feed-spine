"""Pipeline operations for feed composition.

This module provides functional operators for building feed pipelines.
Operations are composable, testable, and can be combined in any order.

Example:
    >>> from feedspine.composition import ops
    >>> from feedspine.composition.testing import MockEnricher

    Create a pipeline with multiple operations:

    >>> pipeline = [
    ...     ops.filter(lambda r: r.layer.value == "BRONZE"),
    ...     ops.enrich(MockEnricher()),
    ...     ops.dedupe(key="natural_key"),
    ... ]
    >>> len(pipeline)
    3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from feedspine.core.checkpoint import CheckpointStore
    from feedspine.models.record import Record
    from feedspine.protocols.enricher import Enricher
    from feedspine.protocols.notification import Notifier


class PipelineOp(ABC):
    """Base class for pipeline operations.

    Pipeline operations transform, filter, or process records
    as they flow through the collection pipeline.
    """

    @abstractmethod
    async def apply(self, record: Record) -> Record | None:
        """Apply the operation to a record.

        Args:
            record: The record to process.

        Returns:
            Processed record, or None to filter out.
        """
        ...


@dataclass(frozen=True)
class FilterOp(PipelineOp):
    """Filter records by predicate.

    Records where the predicate returns False are dropped.

    Example:
        >>> from feedspine.composition.ops import FilterOp
        >>> from feedspine.models.base import Layer, Metadata
        >>> from feedspine.models.record import Record
        >>> from datetime import datetime, timezone
        >>> import asyncio
        >>>
        >>> # Filter for bronze records only
        >>> op = FilterOp(lambda r: r.layer == Layer.BRONZE)
        >>> record = Record(
        ...     id="test-1",
        ...     natural_key="src-1",
        ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     metadata=Metadata(source="test"),
        ...     content={},
        ...     layer=Layer.BRONZE,
        ... )
        >>> result = asyncio.run(op.apply(record))
        >>> result is not None
        True
    """

    predicate: Callable[[Record], bool]

    async def apply(self, record: Record) -> Record | None:
        """Apply filter predicate.

        Args:
            record: Record to filter.

        Returns:
            Record if predicate is True, None otherwise.
        """
        if self.predicate(record):
            return record
        return None


@dataclass(frozen=True)
class AsyncFilterOp(PipelineOp):
    """Filter records by async predicate.

    Example:
        >>> from feedspine.composition.ops import AsyncFilterOp
        >>> from feedspine.models.base import Layer, Metadata
        >>> from feedspine.models.record import Record
        >>> from datetime import datetime, timezone
        >>> import asyncio
        >>>
        >>> async def is_valid(r: Record) -> bool:
        ...     return r.layer == Layer.BRONZE
        >>>
        >>> op = AsyncFilterOp(is_valid)
        >>> record = Record(
        ...     id="test-1",
        ...     natural_key="src-1",
        ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     metadata=Metadata(source="test"),
        ...     content={},
        ...     layer=Layer.BRONZE,
        ... )
        >>> result = asyncio.run(op.apply(record))
        >>> result is not None
        True
    """

    predicate: Callable[[Record], Coroutine[None, None, bool]]

    async def apply(self, record: Record) -> Record | None:
        """Apply async filter predicate.

        Args:
            record: Record to filter.

        Returns:
            Record if predicate is True, None otherwise.
        """
        if await self.predicate(record):
            return record
        return None


@dataclass(frozen=True)
class EnrichOp(PipelineOp):
    """Enrich records with an enricher.

    Example:
        >>> from feedspine.composition.ops import EnrichOp
        >>> from feedspine.composition.testing import MockEnricher
        >>>
        >>> op = EnrichOp(MockEnricher())
        >>> op.enricher is not None
        True
    """

    enricher: Enricher

    async def apply(self, record: Record) -> Record | None:
        """Apply enricher to record.

        Args:
            record: Record to enrich.

        Returns:
            Enriched record (enricher modifies in-place per protocol).
        """
        await self.enricher.enrich(record)
        return record


@dataclass(frozen=True)
class TransformOp(PipelineOp):
    """Transform records with a function.

    Example:
        >>> from feedspine.composition.ops import TransformOp
        >>> from feedspine.models.base import Layer, Metadata
        >>> from feedspine.models.record import Record
        >>> from datetime import datetime, timezone
        >>> import asyncio
        >>>
        >>> def add_tag(r: Record) -> Record:
        ...     return r.model_copy(update={"content": {**r.content, "tag": "processed"}})
        >>>
        >>> op = TransformOp(add_tag)
        >>> record = Record(
        ...     id="test-1",
        ...     natural_key="src-1",
        ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     metadata=Metadata(source="test"),
        ...     content={},
        ...     layer=Layer.BRONZE,
        ... )
        >>> result = asyncio.run(op.apply(record))
        >>> result.content["tag"]
        'processed'
    """

    func: Callable[[Record], Record]

    async def apply(self, record: Record) -> Record | None:
        """Apply transformation function.

        Args:
            record: Record to transform.

        Returns:
            Transformed record.
        """
        return self.func(record)


@dataclass(frozen=True)
class AsyncTransformOp(PipelineOp):
    """Transform records with an async function.

    Example:
        >>> from feedspine.composition.ops import AsyncTransformOp
        >>> from feedspine.models.base import Layer, Metadata
        >>> from feedspine.models.record import Record
        >>> from datetime import datetime, timezone
        >>> import asyncio
        >>>
        >>> async def add_tag(r: Record) -> Record:
        ...     return r.model_copy(update={"content": {**r.content, "tag": "async"}})
        >>>
        >>> op = AsyncTransformOp(add_tag)
        >>> record = Record(
        ...     id="test-1",
        ...     natural_key="src-1",
        ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     metadata=Metadata(source="test"),
        ...     content={},
        ...     layer=Layer.BRONZE,
        ... )
        >>> result = asyncio.run(op.apply(record))
        >>> result.content["tag"]
        'async'
    """

    func: Callable[[Record], Coroutine[None, None, Record]]

    async def apply(self, record: Record) -> Record | None:
        """Apply async transformation function.

        Args:
            record: Record to transform.

        Returns:
            Transformed record.
        """
        return await self.func(record)


@dataclass(frozen=True)
class DedupeOp(PipelineOp):
    """Deduplicate records by key.

    Note: This operation maintains state across records.

    Example:
        >>> from feedspine.composition.ops import DedupeOp
        >>>
        >>> op = DedupeOp(key="natural_key")
        >>> op.key
        'natural_key'
    """

    key: str | Callable[[Record], str]
    _seen: set[str] | None = None

    def __post_init__(self) -> None:
        """Initialize seen set."""
        object.__setattr__(self, "_seen", set())

    def _get_key(self, record: Record) -> str:
        """Get deduplication key for record."""
        if callable(self.key):
            return self.key(record)
        return str(getattr(record, self.key, record.content.get(self.key, "")))

    async def apply(self, record: Record) -> Record | None:
        """Apply deduplication.

        Args:
            record: Record to check.

        Returns:
            Record if not seen, None if duplicate.
        """
        if self._seen is None:
            return record
        key = self._get_key(record)
        if key in self._seen:
            return None
        self._seen.add(key)
        return record


@dataclass(frozen=True)
class NotifyOp(PipelineOp):
    """Send notifications for records.

    Example:
        >>> from feedspine.composition.ops import NotifyOp
        >>> from feedspine.notifier.console import ConsoleNotifier
        >>>
        >>> op = NotifyOp(ConsoleNotifier(), on="new")
        >>> op.on
        'new'
    """

    notifier: Notifier
    on: Literal["new", "error", "all"] = "new"

    async def apply(self, record: Record) -> Record | None:
        """Send notification and pass through record.

        Args:
            record: Record to notify about.

        Returns:
            Original record (notifications are side effects).
        """
        # For now, just pass through - actual notification happens at pipeline level
        return record


@dataclass(frozen=True)
class RateLimitOp(PipelineOp):
    """Limit processing rate.

    Note: This is a marker operation - actual rate limiting
    is handled by the Feed class.

    Example:
        >>> from feedspine.composition.ops import RateLimitOp
        >>>
        >>> op = RateLimitOp(rps=10.0)
        >>> op.rps
        10.0
    """

    rps: float

    async def apply(self, record: Record) -> Record | None:
        """Pass through record (rate limiting handled externally).

        Args:
            record: Record to process.

        Returns:
            Original record.
        """
        return record


@dataclass(frozen=True)
class CheckpointOp(PipelineOp):
    """Enable checkpointing.

    Note: This is a marker operation - actual checkpointing
    is handled by the Feed class.

    Example:
        >>> from feedspine.composition.ops import CheckpointOp
        >>>
        >>> op = CheckpointOp(interval=100)
        >>> op.interval
        100
    """

    interval: int = 100
    store: CheckpointStore | None = None

    async def apply(self, record: Record) -> Record | None:
        """Pass through record (checkpointing handled externally).

        Args:
            record: Record to process.

        Returns:
            Original record.
        """
        return record


@dataclass(frozen=True)
class BatchOp(PipelineOp):
    """Process records in batches.

    Note: This is a marker operation - actual batching
    is handled by the Feed class.

    Example:
        >>> from feedspine.composition.ops import BatchOp
        >>>
        >>> op = BatchOp(size=50)
        >>> op.size
        50
    """

    size: int

    async def apply(self, record: Record) -> Record | None:
        """Pass through record (batching handled externally).

        Args:
            record: Record to process.

        Returns:
            Original record.
        """
        return record


# Convenience factory functions


def filter(predicate: Callable[[Record], bool]) -> FilterOp:  # noqa: A001
    """Create a filter operation.

    Args:
        predicate: Function that returns True to keep record.

    Returns:
        FilterOp instance.

    Example:
        >>> from feedspine.composition import ops
        >>> op = ops.filter(lambda r: r.layer.value == "BRONZE")
        >>> isinstance(op, FilterOp)
        True
    """
    return FilterOp(predicate)


def filter_async(
    predicate: Callable[[Record], Coroutine[None, None, bool]],
) -> AsyncFilterOp:
    """Create an async filter operation.

    Args:
        predicate: Async function that returns True to keep record.

    Returns:
        AsyncFilterOp instance.
    """
    return AsyncFilterOp(predicate)


def enrich(enricher: Enricher) -> EnrichOp:
    """Create an enrich operation.

    Args:
        enricher: Enricher to apply.

    Returns:
        EnrichOp instance.

    Example:
        >>> from feedspine.composition import ops
        >>> from feedspine.composition.testing import MockEnricher
        >>> op = ops.enrich(MockEnricher())
        >>> isinstance(op, EnrichOp)
        True
    """
    return EnrichOp(enricher)


def transform(func: Callable[[Record], Record]) -> TransformOp:
    """Create a transform operation.

    Args:
        func: Function to transform records.

    Returns:
        TransformOp instance.

    Example:
        >>> from feedspine.composition import ops
        >>> op = ops.transform(lambda r: r)
        >>> isinstance(op, TransformOp)
        True
    """
    return TransformOp(func)


def transform_async(
    func: Callable[[Record], Coroutine[None, None, Record]],
) -> AsyncTransformOp:
    """Create an async transform operation.

    Args:
        func: Async function to transform records.

    Returns:
        AsyncTransformOp instance.
    """
    return AsyncTransformOp(func)


def dedupe(*, key: str | Callable[[Record], str]) -> DedupeOp:
    """Create a dedupe operation.

    Args:
        key: Field name or function to extract dedup key.

    Returns:
        DedupeOp instance.

    Example:
        >>> from feedspine.composition import ops
        >>> op = ops.dedupe(key="source_id")
        >>> isinstance(op, DedupeOp)
        True
    """
    return DedupeOp(key)


def notify(
    notifier: Notifier,
    *,
    on: Literal["new", "error", "all"] = "new",
) -> NotifyOp:
    """Create a notify operation.

    Args:
        notifier: Notifier to use.
        on: When to notify ("new", "error", or "all").

    Returns:
        NotifyOp instance.

    Example:
        >>> from feedspine.composition import ops
        >>> from feedspine.notifier.console import ConsoleNotifier
        >>> op = ops.notify(ConsoleNotifier())
        >>> isinstance(op, NotifyOp)
        True
    """
    return NotifyOp(notifier, on)


def rate_limit(rps: float) -> RateLimitOp:
    """Create a rate limit operation.

    Args:
        rps: Requests per second limit.

    Returns:
        RateLimitOp instance.

    Example:
        >>> from feedspine.composition import ops
        >>> op = ops.rate_limit(10.0)
        >>> op.rps
        10.0
    """
    return RateLimitOp(rps)


def checkpoint(
    interval: int = 100,
    store: CheckpointStore | None = None,
) -> CheckpointOp:
    """Create a checkpoint operation.

    Args:
        interval: Save checkpoint every N records.
        store: Where to save checkpoints.

    Returns:
        CheckpointOp instance.

    Example:
        >>> from feedspine.composition import ops
        >>> op = ops.checkpoint(interval=50)
        >>> op.interval
        50
    """
    return CheckpointOp(interval, store)


def batch(size: int) -> BatchOp:
    """Create a batch operation.

    Args:
        size: Batch size.

    Returns:
        BatchOp instance.

    Example:
        >>> from feedspine.composition import ops
        >>> op = ops.batch(100)
        >>> op.size
        100
    """
    return BatchOp(size)
