"""Testing utilities for feed composition.

This module provides mock implementations for testing feeds
without external dependencies.

Example:
    >>> from feedspine.composition.testing import MockAdapter, MockEnricher
    >>> from feedspine.models.base import Metadata
    >>> from feedspine.models.record import RecordCandidate
    >>> from datetime import datetime, timezone
    >>>
    >>> # Create mock adapter with test data
    >>> records = [
    ...     RecordCandidate(
    ...         natural_key="test-1",
    ...         published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    ...         metadata=Metadata(source="test"),
    ...         content={"value": 1},
    ...     )
    ... ]
    >>> adapter = MockAdapter(records=records)
    >>> adapter.name
    'mock'
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from feedspine.protocols.enricher import EnrichmentResult, EnrichmentStatus

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from feedspine.models.record import Record, RecordCandidate


@dataclass
class MockAdapter:
    """Mock feed adapter for testing.

    Yields predefined records without any network calls.

    Args:
        records: Records to yield on fetch().
        name: Adapter name (default: "mock").

    Example:
        >>> import asyncio
        >>> from feedspine.composition.testing import MockAdapter
        >>> from feedspine.models.base import Metadata
        >>> from feedspine.models.record import RecordCandidate
        >>> from datetime import datetime, timezone
        >>>
        >>> records = [
        ...     RecordCandidate(
        ...         natural_key="test-1",
        ...         published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...         metadata=Metadata(source="test"),
        ...         content={"value": 1},
        ...     )
        ... ]
        >>> adapter = MockAdapter(records=records)
        >>>
        >>> async def example():
        ...     await adapter.initialize()
        ...     count = 0
        ...     async for _ in adapter.fetch():
        ...         count += 1
        ...     await adapter.close()
        ...     return count
        >>> asyncio.run(example())
        1
    """

    records: Sequence[RecordCandidate] = field(default_factory=list)
    name: str = "mock"
    _initialized: bool = field(default=False, init=False)

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True

    async def close(self) -> None:
        """Close the adapter."""
        self._initialized = False

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        """Yield predefined records.

        Yields:
            RecordCandidate instances from the records list.

        Example:
            >>> import asyncio
            >>> from feedspine.composition.testing import MockAdapter
            >>>
            >>> adapter = MockAdapter(records=[])
            >>>
            >>> async def example():
            ...     await adapter.initialize()
            ...     results = [r async for r in adapter.fetch()]
            ...     return len(results)
            >>> asyncio.run(example())
            0
        """
        for record in self.records:
            yield record


@dataclass
class MockEnricher:
    """Mock enricher for testing.

    Passes through records unchanged by default, or applies
    a custom transformation function.

    Args:
        transform: Optional function to transform record content.
        name: Enricher name (default: "mock_enricher").

    Example:
        >>> import asyncio
        >>> from feedspine.composition.testing import MockEnricher
        >>> from feedspine.models.base import Layer, Metadata
        >>> from feedspine.models.record import Record
        >>> from datetime import datetime, timezone
        >>>
        >>> enricher = MockEnricher()
        >>>
        >>> async def example():
        ...     await enricher.initialize()
        ...     record = Record(
        ...         id="test-1",
        ...         natural_key="src-1",
        ...         published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...         captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...         metadata=Metadata(source="test"),
        ...         content={"value": 1},
        ...         layer=Layer.BRONZE,
        ...     )
        ...     result = await enricher.enrich(record)
        ...     await enricher.close()
        ...     return result.status.value
        >>> asyncio.run(example())
        'success'
    """

    transform: callable | None = None  # type: ignore[type-arg]
    name: str = "mock_enricher"
    _initialized: bool = field(default=False, init=False)
    _enrich_count: int = field(default=0, init=False)

    async def initialize(self) -> None:
        """Initialize the enricher."""
        self._initialized = True

    async def close(self) -> None:
        """Close the enricher."""
        self._initialized = False

    async def enrich(self, record: Record) -> EnrichmentResult:
        """Enrich the record (modifies in place as per protocol).

        Args:
            record: Record to enrich.

        Returns:
            EnrichmentResult with enrichment metadata.

        Example:
            >>> import asyncio
            >>> from feedspine.composition.testing import MockEnricher
            >>> from feedspine.models.base import Layer, Metadata
            >>> from feedspine.models.record import Record
            >>> from datetime import datetime, timezone
            >>>
            >>> # Enricher that adds a field
            >>> def add_processed(content):
            ...     return {**content, "processed": True}
            >>>
            >>> enricher = MockEnricher(transform=add_processed)
            >>>
            >>> async def example():
            ...     await enricher.initialize()
            ...     record = Record(
            ...         id="test-1",
            ...         natural_key="src-1",
            ...         published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...         captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...         metadata=Metadata(source="test"),
            ...         content={"value": 1},
            ...         layer=Layer.BRONZE,
            ...     )
            ...     result = await enricher.enrich(record)
            ...     return result.status.value
            >>> asyncio.run(example())
            'success'
        """
        self._enrich_count += 1
        fields_added: list[str] = []

        # For MockEnricher, we need to mutate the content dict in-place
        # since Record is a Pydantic model and content is a dict field
        if self.transform is not None:
            new_content = self.transform(record.content)
            # Update content dict in-place
            record.content.clear()
            record.content.update(new_content)
            fields_added = list(new_content.keys())

        return EnrichmentResult(
            record_id=record.id,
            status=EnrichmentStatus.SUCCESS,
            enricher_name=self.name,
            fields_added=fields_added,
        )

    @property
    def enrich_count(self) -> int:
        """Number of times enrich() was called."""
        return self._enrich_count


@dataclass
class FailingEnricher:
    """Enricher that always fails, for testing error handling.

    Args:
        error_message: Message for the raised exception.
        name: Enricher name.

    Example:
        >>> import asyncio
        >>> from feedspine.composition.testing import FailingEnricher
        >>> from feedspine.models.base import Layer, Metadata
        >>> from feedspine.models.record import Record
        >>> from datetime import datetime, timezone
        >>>
        >>> enricher = FailingEnricher(error_message="Test error")
        >>>
        >>> async def example():
        ...     await enricher.initialize()
        ...     record = Record(
        ...         id="test-1",
        ...         natural_key="src-1",
        ...         published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...         captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...         metadata=Metadata(source="test"),
        ...         content={},
        ...         layer=Layer.BRONZE,
        ...     )
        ...     try:
        ...         await enricher.enrich(record)
        ...     except RuntimeError as e:
        ...         return str(e)
        >>> asyncio.run(example())
        'Test error'
    """

    error_message: str = "Enrichment failed"
    name: str = "failing_enricher"
    _initialized: bool = field(default=False, init=False)

    async def initialize(self) -> None:
        """Initialize the enricher."""
        self._initialized = True

    async def close(self) -> None:
        """Close the enricher."""
        self._initialized = False

    async def enrich(self, record: Record) -> EnrichmentResult:
        """Always raise an error.

        Args:
            record: Record (ignored).

        Raises:
            RuntimeError: Always raised with error_message.
        """
        raise RuntimeError(self.error_message)


@dataclass
class SlowEnricher:
    """Enricher with configurable delay, for testing timeouts.

    Args:
        delay_seconds: How long to delay before returning.
        name: Enricher name.

    Example:
        >>> import asyncio
        >>> from feedspine.composition.testing import SlowEnricher
        >>> from feedspine.models.base import Layer, Metadata
        >>> from feedspine.models.record import Record
        >>> from datetime import datetime, timezone
        >>>
        >>> enricher = SlowEnricher(delay_seconds=0.01)
        >>>
        >>> async def example():
        ...     await enricher.initialize()
        ...     record = Record(
        ...         id="test-1",
        ...         natural_key="src-1",
        ...         published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...         captured_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...         metadata=Metadata(source="test"),
        ...         content={},
        ...         layer=Layer.BRONZE,
        ...     )
        ...     result = await enricher.enrich(record)
        ...     return result.status.value
        >>> asyncio.run(example())
        'success'
    """

    delay_seconds: float = 0.1
    name: str = "slow_enricher"
    _initialized: bool = field(default=False, init=False)

    async def initialize(self) -> None:
        """Initialize the enricher."""
        self._initialized = True

    async def close(self) -> None:
        """Close the enricher."""
        self._initialized = False

    async def enrich(self, record: Record) -> EnrichmentResult:
        """Delay then return the record unchanged.

        Args:
            record: Record to return.

        Returns:
            EnrichmentResult after delay.
        """
        import asyncio

        await asyncio.sleep(self.delay_seconds)
        return EnrichmentResult(
            record_id=record.id,
            status=EnrichmentStatus.SUCCESS,
            enricher_name=self.name,
        )
