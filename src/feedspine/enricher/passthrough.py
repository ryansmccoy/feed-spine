"""Passthrough enricher implementation.

This module provides a simple enricher that promotes records through layers
without adding substantial data - useful for testing and as a base pattern.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from feedspine.models.base import Layer
from feedspine.protocols.enricher import EnrichmentResult, EnrichmentStatus

if TYPE_CHECKING:
    from feedspine.models.record import Record


# Layer promotion map
NEXT_LAYER = {
    Layer.BRONZE: Layer.SILVER,
    Layer.SILVER: Layer.GOLD,
    Layer.GOLD: None,  # Cannot promote further
}


class PassthroughEnricher:
    """Simple enricher that promotes records through layers.

    This enricher doesn't add data - it just promotes BRONZE → SILVER → GOLD.
    Useful for testing pipelines or when you just need layer promotion.

    Example:
        >>> enricher = PassthroughEnricher()
        >>> record = Record(layer=Layer.BRONZE, ...)
        >>> result = await enricher.enrich(record)
        >>> print(record.layer)  # Layer.SILVER
    """

    def __init__(self, name: str = "PassthroughEnricher") -> None:
        """Create a PassthroughEnricher.

        Args:
            name: Custom name for this enricher instance.
        """
        self._name = name

    @property
    def name(self) -> str:
        """The unique name of this enricher."""
        return self._name

    async def can_enrich(self, record: Record) -> bool:
        """Check if this enricher can process the given record.

        Returns True for BRONZE and SILVER, False for GOLD.

        Args:
            record: The record to check.

        Returns:
            True if record can be promoted to a higher layer.
        """
        return NEXT_LAYER.get(record.layer) is not None

    async def enrich(self, record: Record) -> EnrichmentResult:
        """Promote record to the next layer.

        Args:
            record: The record to enrich. Modified in place.

        Returns:
            EnrichmentResult describing the outcome.
        """
        start = time.perf_counter()

        source_layer = record.layer
        target_layer = NEXT_LAYER.get(source_layer)

        if target_layer is None:
            # Cannot promote GOLD records
            duration_ms = (time.perf_counter() - start) * 1000
            return EnrichmentResult(
                record_id=record.id,
                status=EnrichmentStatus.SKIPPED,
                enricher_name=self.name,
                source_layer=source_layer,
                target_layer=source_layer,
                duration_ms=duration_ms,
            )

        # Promote the record
        record.layer = target_layer

        duration_ms = (time.perf_counter() - start) * 1000
        return EnrichmentResult(
            record_id=record.id,
            status=EnrichmentStatus.SUCCESS,
            enricher_name=self.name,
            source_layer=source_layer,
            target_layer=target_layer,
            duration_ms=duration_ms,
        )
