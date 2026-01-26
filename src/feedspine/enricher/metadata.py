"""Metadata enricher implementation.

This module provides an enricher that adds specific metadata fields to records.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from feedspine.protocols.enricher import EnrichmentResult, EnrichmentStatus

if TYPE_CHECKING:
    from feedspine.models.record import Record


class MetadataEnricher:
    """Enricher that adds specified metadata fields to records.

    This enricher adds/updates fields in record.metadata.extra without
    promoting the record to a higher layer.

    Example:
        >>> enricher = MetadataEnricher(
        ...     fields={"processed": True, "version": "1.0"}
        ... )
        >>> record = Record(layer=Layer.BRONZE, ...)
        >>> result = await enricher.enrich(record)
        >>> print(record.metadata.extra["processed"])  # True
    """

    def __init__(
        self,
        fields: dict[str, Any],
        name: str = "MetadataEnricher",
    ) -> None:
        """Create a MetadataEnricher.

        Args:
            fields: Dictionary of fields to add/update in metadata.extra.
            name: Custom name for this enricher instance.
        """
        self._fields = fields
        self._name = name

    @property
    def name(self) -> str:
        """The unique name of this enricher."""
        return self._name

    async def can_enrich(self, record: Record) -> bool:
        """Check if this enricher can process the given record.

        MetadataEnricher can enrich records at any layer.

        Args:
            record: The record to check.

        Returns:
            Always True - can add metadata to any record.
        """
        return True

    async def enrich(self, record: Record) -> EnrichmentResult:
        """Add metadata fields to the record.

        Args:
            record: The record to enrich. Modified in place.

        Returns:
            EnrichmentResult describing the fields added/updated.
        """
        start = time.perf_counter()

        source_layer = record.layer
        fields_added: list[str] = []
        fields_updated: list[str] = []

        for key, value in self._fields.items():
            if key in record.metadata.extra:
                fields_updated.append(key)
            else:
                fields_added.append(key)
            record.metadata.extra[key] = value

        duration_ms = (time.perf_counter() - start) * 1000
        return EnrichmentResult(
            record_id=record.id,
            status=EnrichmentStatus.SUCCESS,
            enricher_name=self.name,
            source_layer=source_layer,
            target_layer=source_layer,  # No promotion
            fields_added=sorted(fields_added),
            fields_updated=sorted(fields_updated),
            duration_ms=duration_ms,
        )
