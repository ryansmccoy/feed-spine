"""Record models - the core data unit.

This module contains the core record types for the FeedSpine framework:

- `RecordCandidate`: Raw records from feed adapters, pre-deduplication
- `Record`: Persisted records with full metadata and layer tracking

Example:
    >>> from feedspine.models.record import RecordCandidate, Record
    >>> from feedspine.models.base import Metadata, Layer
    >>> from datetime import datetime, timezone
    >>> meta = Metadata(source="test-feed")
    >>> candidate = RecordCandidate(
    ...     natural_key="article-123",
    ...     published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
    ...     content={"title": "Hello World"},
    ...     metadata=meta,
    ... )
    >>> candidate.natural_key  # Keys are normalized to lowercase
    'article-123'
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field, field_validator

from feedspine.models.base import FeedSpineModel, Layer, Metadata


class RecordCandidate(FeedSpineModel):
    """Incoming record from a feed, before deduplication.

    This is what FeedAdapters produce. It becomes a Record after storage.

    Example:
        >>> from feedspine.models.record import RecordCandidate
        >>> from feedspine.models.base import Metadata
        >>> from datetime import datetime, timezone
        >>> meta = Metadata(source="sec-feed")
        >>> c = RecordCandidate(
        ...     natural_key=" SEC-001 ",
        ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     metadata=meta,
        ... )
        >>> c.natural_key  # Whitespace stripped and lowercased
        'sec-001'
    """

    natural_key: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Unique identifier within the feed",
    )
    published_at: datetime = Field(
        ...,
        description="When the source published this item",
    )
    content: dict[str, Any] = Field(
        default_factory=dict,
        description="The actual record data",
    )
    metadata: Metadata = Field(
        ...,
        description="Source and capture metadata",
    )

    @field_validator("natural_key")
    @classmethod
    def normalize_natural_key(cls, v: str) -> str:
        """Normalize natural key for consistent deduplication."""
        return v.strip().lower()


class Record(FeedSpineModel):
    """A stored record with full metadata.

    Created from RecordCandidate after deduplication and storage.

    Example:
        >>> from feedspine.models.record import Record, RecordCandidate
        >>> from feedspine.models.base import Layer, Metadata
        >>> from datetime import datetime, timezone
        >>> meta = Metadata(source="test")
        >>> candidate = RecordCandidate(
        ...     natural_key="item-1",
        ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     content={"value": 42},
        ...     metadata=meta,
        ... )
        >>> record = Record.from_candidate(candidate, "uuid-1234")
        >>> record.layer
        <Layer.BRONZE: 'bronze'>
        >>> record.content
        {'value': 42}
    """

    id: str = Field(..., description="Internal unique identifier (UUID)")
    natural_key: str = Field(..., description="Natural key from candidate")
    layer: Layer = Field(default=Layer.BRONZE, description="Current medallion layer")
    published_at: datetime = Field(..., description="Original publication time")
    captured_at: datetime = Field(..., description="First capture time")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update time",
    )
    content: dict[str, Any] = Field(default_factory=dict)
    metadata: Metadata = Field(...)
    version: int = Field(default=1, ge=1, description="Version for optimistic locking")

    # Sighting tracking fields (optimized storage - avoids sighting table bloat)
    first_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this record was first seen across all feeds",
    )
    last_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this record was last seen (most recent sighting)",
    )
    seen_count: int = Field(
        default=1,
        ge=1,
        description="Total number of times this record was sighted",
    )

    @classmethod
    def from_candidate(cls, candidate: RecordCandidate, record_id: str) -> Record:
        """Create a Record from a RecordCandidate.

        Example:
            >>> from feedspine.models.record import Record, RecordCandidate
            >>> from feedspine.models.base import Layer, Metadata
            >>> from datetime import datetime, timezone
            >>> m = Metadata(source="src")
            >>> c = RecordCandidate(
            ...     natural_key="k1",
            ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...     metadata=m,
            ... )
            >>> r = Record.from_candidate(c, "id-123")
            >>> r.id
            'id-123'
            >>> r.layer
            <Layer.BRONZE: 'bronze'>
        """
        return cls(
            id=record_id,
            natural_key=candidate.natural_key,
            layer=Layer.BRONZE,
            published_at=candidate.published_at,
            captured_at=candidate.metadata.captured_at,
            content=candidate.content,
            metadata=candidate.metadata,
        )

    def promote(self, to_layer: Layer, enrichments: dict[str, Any] | None = None) -> Record:
        """Create a new version promoted to a higher layer.

        Example:
            >>> from feedspine.models.record import Record, RecordCandidate
            >>> from feedspine.models.base import Layer, Metadata
            >>> from datetime import datetime, timezone
            >>> m = Metadata(source="src")
            >>> c = RecordCandidate(
            ...     natural_key="k1",
            ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...     metadata=m,
            ... )
            >>> r = Record.from_candidate(c, "id-1")
            >>> r2 = r.promote(Layer.SILVER, {"enriched": True})
            >>> r2.layer
            <Layer.SILVER: 'silver'>
            >>> r2.content["enriched"]
            True
            >>> r2.version
            2
        """
        layer_order = [Layer.BRONZE, Layer.SILVER, Layer.GOLD]
        if layer_order.index(to_layer) <= layer_order.index(self.layer):
            msg = f"Cannot promote from {self.layer} to {to_layer}"
            raise ValueError(msg)

        new_content = {**self.content}
        if enrichments:
            new_content.update(enrichments)

        return self.model_copy(
            update={
                "layer": to_layer,
                "content": new_content,
                "updated_at": datetime.now(UTC),
                "version": self.version + 1,
            }
        )

    def record_sighting(self, seen_at: datetime | None = None) -> Record:
        """Create an updated record with sighting tracked.

        Updates last_seen_at and increments seen_count.
        This is the optimized sighting pattern that avoids table bloat.

        Args:
            seen_at: When the sighting occurred (defaults to now).

        Returns:
            A new Record with updated sighting fields.

        Example:
            >>> from feedspine.models.record import Record, RecordCandidate
            >>> from feedspine.models.base import Layer, Metadata
            >>> from datetime import datetime, timezone
            >>> m = Metadata(source="src")
            >>> c = RecordCandidate(
            ...     natural_key="k1",
            ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...     metadata=m,
            ... )
            >>> r = Record.from_candidate(c, "id-1")
            >>> r.seen_count
            1
            >>> r2 = r.record_sighting()
            >>> r2.seen_count
            2
            >>> r2.last_seen_at >= r.first_seen_at
            True
        """
        now = seen_at or datetime.now(UTC)
        return self.model_copy(
            update={
                "last_seen_at": now,
                "seen_count": self.seen_count + 1,
            }
        )
