"""EntitySpine enricher for FeedSpine records.

This module provides an enricher that resolves entity information from
EntitySpine and adds it to FeedSpine records.

Example:
    >>> from feedspine.enricher import EntityEnricher
    >>>
    >>> # Requires EntitySpine: pip install entityspine
    >>> from entityspine import SqliteStore
    >>>
    >>> store = SqliteStore("entities.db")
    >>> store.initialize()
    >>> store.load_sec_data()
    >>>
    >>> enricher = EntityEnricher(store)
    >>> result = await enricher.enrich(record)
    >>>
    >>> # Record now has entity_id, entity_name, etc.
    >>> print(record.metadata.get("entity_id"))
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from feedspine.models.base import Layer
from feedspine.protocols.enricher import EnrichmentResult, EnrichmentStatus

if TYPE_CHECKING:
    from feedspine.models.record import Record

logger = logging.getLogger(__name__)


# =============================================================================
# EntitySpine Protocol (to avoid hard dependency)
# =============================================================================


@runtime_checkable
class EntityStoreProtocol(Protocol):
    """Protocol for EntitySpine store (duck-typed to avoid import dependency).

    This allows EntityEnricher to work with any EntitySpine store
    without requiring entityspine as a hard dependency.
    """

    def get_entities_by_cik(self, cik: str) -> list[Any]:
        """Get entities by CIK."""
        ...

    def search_entities(self, query: str, limit: int = 10) -> list[tuple[Any, float]]:
        """Search entities by name."""
        ...


# =============================================================================
# Layer promotion map
# =============================================================================

NEXT_LAYER = {
    Layer.BRONZE: Layer.SILVER,
    Layer.SILVER: Layer.GOLD,
    Layer.GOLD: None,  # Cannot promote further
}


# =============================================================================
# EntityEnricher
# =============================================================================


class EntityEnricher:
    """Enrich FeedSpine records with EntitySpine entity resolution.

    This enricher adds entity information to records by:
    1. Extracting identifier (CIK, ticker, name) from record content
    2. Resolving the identifier against EntitySpine
    3. Adding entity_id, entity_name, resolution_score to record metadata
    4. Optionally promoting the record to the next layer

    Added Fields:
        entity_id: EntitySpine entity ID (if resolved)
        entity_name: Canonical entity name (if resolved)
        entity_cik: Normalized CIK (if available)
        resolution_score: Confidence score (0.0-1.0)
        resolution_method: How the entity was resolved (cik, ticker, name)

    Example:
        >>> from feedspine.enricher import EntityEnricher
        >>> from entityspine import SqliteStore
        >>>
        >>> store = SqliteStore("entities.db")
        >>> store.initialize()
        >>> store.load_sec_data()
        >>>
        >>> enricher = EntityEnricher(store)
        >>>
        >>> # Enrich a record with CIK
        >>> record.content = {"cik": "0000320193", "form": "10-K"}
        >>> result = await enricher.enrich(record)
        >>>
        >>> print(record.metadata.get("entity_name"))
        # "Apple Inc."

    Note:
        EntitySpine is an optional dependency. Install with:
        pip install entityspine
    """

    def __init__(
        self,
        entity_store: EntityStoreProtocol,
        name: str = "EntityEnricher",
        promote_layer: bool = True,
        min_confidence: float = 0.7,
    ):
        """Initialize the entity enricher.

        Args:
            entity_store: EntitySpine store instance for resolution
            name: Custom name for this enricher instance
            promote_layer: Whether to promote records to next layer on success
            min_confidence: Minimum confidence score for name-based resolution
        """
        self._store = entity_store
        self._name = name
        self._promote_layer = promote_layer
        self._min_confidence = min_confidence

    @property
    def name(self) -> str:
        """The unique name of this enricher."""
        return self._name

    async def can_enrich(self, record: Record) -> bool:
        """Check if this enricher can process the given record.

        Returns True if:
        - Record has CIK, ticker, or name in content
        - Record doesn't already have entity_id in metadata
        - Record is not already at GOLD layer (unless promote_layer=False)

        Args:
            record: The record to check.

        Returns:
            True if this enricher can add entity resolution.
        """
        # Skip if already enriched
        if record.metadata and hasattr(record.metadata, "extra"):
            if record.metadata.extra.get("entity_id"):
                return False

        # Skip if at GOLD and we promote
        if self._promote_layer and record.layer == Layer.GOLD:
            return False

        # Check for resolvable identifiers
        content = record.content if hasattr(record, "content") else {}
        return bool(
            content.get("cik")
            or content.get("ticker")
            or content.get("name")
            or content.get("company_name")
        )

    async def enrich(self, record: Record) -> EnrichmentResult:
        """Enrich a record with EntitySpine entity resolution.

        Attempts resolution in order:
        1. By CIK (highest confidence)
        2. By ticker (high confidence)
        3. By name (fuzzy match, configurable threshold)

        Args:
            record: The record to enrich. Modified in place.

        Returns:
            EnrichmentResult describing the outcome.
        """
        start = time.perf_counter()
        source_layer = record.layer

        # Try to resolve entity
        entity_info = self._resolve_entity(record)

        if entity_info is None:
            # No resolution found
            duration_ms = (time.perf_counter() - start) * 1000
            return EnrichmentResult(
                record_id=record.id,
                status=EnrichmentStatus.SKIPPED,
                enricher_name=self.name,
                source_layer=source_layer,
                target_layer=source_layer,
                duration_ms=duration_ms,
                metadata={"reason": "no_entity_resolved"},
            )

        # Add entity info to record metadata
        fields_added = self._add_entity_to_record(record, entity_info)

        # Optionally promote layer
        target_layer = source_layer
        if self._promote_layer:
            next_layer = NEXT_LAYER.get(source_layer)
            if next_layer:
                record.layer = next_layer
                target_layer = next_layer

        duration_ms = (time.perf_counter() - start) * 1000

        logger.debug(
            f"Enriched record {record.id} with entity: {entity_info.get('entity_name')}"
        )

        return EnrichmentResult(
            record_id=record.id,
            status=EnrichmentStatus.SUCCESS,
            enricher_name=self.name,
            source_layer=source_layer,
            target_layer=target_layer,
            fields_added=fields_added,
            duration_ms=duration_ms,
            metadata=entity_info,
        )

    def _resolve_entity(self, record: Record) -> dict[str, Any] | None:
        """Resolve entity from record content.

        Returns:
            Dict with entity_id, entity_name, entity_cik, resolution_score, resolution_method
            or None if no entity resolved.
        """
        content = record.content if hasattr(record, "content") else {}

        # Try CIK resolution (highest confidence)
        cik = content.get("cik")
        if cik:
            cik = str(cik).lstrip("0").zfill(10)
            entities = self._store.get_entities_by_cik(cik)
            if entities:
                entity = entities[0]
                return {
                    "entity_id": entity.entity_id,
                    "entity_name": entity.primary_name,
                    "entity_cik": cik,
                    "resolution_score": 1.0,
                    "resolution_method": "cik",
                }

        # Try ticker resolution
        ticker = content.get("ticker")
        if ticker:
            results = self._store.search_entities(ticker.upper(), limit=1)
            if results:
                entity, score = results[0]
                if score >= 0.95:  # High confidence for ticker
                    return {
                        "entity_id": entity.entity_id,
                        "entity_name": entity.primary_name,
                        "entity_cik": getattr(entity, "source_id", None),
                        "resolution_score": score,
                        "resolution_method": "ticker",
                    }

        # Try name resolution (fuzzy match)
        name = content.get("name") or content.get("company_name")
        if name:
            results = self._store.search_entities(name, limit=1)
            if results:
                entity, score = results[0]
                if score >= self._min_confidence:
                    return {
                        "entity_id": entity.entity_id,
                        "entity_name": entity.primary_name,
                        "entity_cik": getattr(entity, "source_id", None),
                        "resolution_score": score,
                        "resolution_method": "name",
                    }

        return None

    def _add_entity_to_record(
        self,
        record: Record,
        entity_info: dict[str, Any],
    ) -> list[str]:
        """Add entity information to record metadata.

        Returns:
            List of field names added.
        """
        fields_added = []

        # Access record.metadata.extra (Pydantic model)
        if hasattr(record, "metadata") and record.metadata:
            extra = getattr(record.metadata, "extra", {})
            if extra is None:
                extra = {}

            for key, value in entity_info.items():
                if value is not None:
                    extra[key] = value
                    fields_added.append(key)

            # Update metadata
            if hasattr(record.metadata, "extra"):
                record.metadata.extra = extra

        return fields_added
