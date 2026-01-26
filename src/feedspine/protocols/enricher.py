"""Enricher protocol for record enhancement and layer promotion.

This module defines the protocol for enriching records and promoting
them through the Bronze → Silver → Gold data layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from feedspine.models.base import Layer
    from feedspine.models.record import Record


class EnrichmentStatus(Enum):
    """Status of an enrichment operation.

    Attributes:
        SUCCESS: Enrichment completed successfully.
        SKIPPED: Record was skipped (doesn't meet criteria).
        FAILED: Enrichment failed with an error.
        PARTIAL: Some enrichments succeeded, some failed.
    """

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation.

    Attributes:
        record_id: The ID of the enriched record.
        status: The outcome of the enrichment.
        enricher_name: Name of the enricher that produced this result.
        source_layer: Layer the record was at before enrichment.
        target_layer: Layer the record is at after enrichment (if promoted).
        fields_added: Names of fields added to the record.
        fields_updated: Names of fields updated in the record.
        error_message: Error message if status is FAILED.
        duration_ms: Time taken for enrichment in milliseconds.
        metadata: Additional enrichment-specific data.

    Example:
        >>> result = EnrichmentResult(
        ...     record_id="sec:10-k:0001234",
        ...     status=EnrichmentStatus.SUCCESS,
        ...     enricher_name="SECFilingEnricher",
        ...     source_layer=Layer.BRONZE,
        ...     target_layer=Layer.SILVER,
        ...     fields_added=["form_type", "cik", "company_name"],
        ... )
    """

    record_id: str
    status: EnrichmentStatus
    enricher_name: str
    source_layer: Layer | None = None
    target_layer: Layer | None = None
    fields_added: list[str] = field(default_factory=list)
    fields_updated: list[str] = field(default_factory=list)
    error_message: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class Enricher(Protocol):
    """Protocol for record enrichment.

    An Enricher takes a record and adds additional data to it,
    potentially promoting it to a higher data quality layer.

    The data layer model:
    - BRONZE: Raw capture, minimal processing
    - SILVER: Validated, deduplicated, enhanced
    - GOLD: Fully enriched, business-ready

    Example:
        >>> class SECFilingEnricher:
        ...     name = "SECFilingEnricher"
        ...
        ...     async def enrich(self, record: Record) -> EnrichmentResult:
        ...         # Extract form type, CIK, etc from SEC filing
        ...         record.metadata["form_type"] = "10-K"
        ...         return EnrichmentResult(
        ...             record_id=record.id,
        ...             status=EnrichmentStatus.SUCCESS,
        ...             enricher_name=self.name,
        ...             source_layer=record.layer,
        ...             target_layer=Layer.SILVER,
        ...         )
    """

    @property
    def name(self) -> str:
        """The unique name of this enricher.

        Used for logging, tracking, and result identification.
        """
        ...

    async def can_enrich(self, record: Record) -> bool:
        """Check if this enricher can process the given record.

        Args:
            record: The record to check.

        Returns:
            True if this enricher can process the record.

        Note:
            This is a fast check - don't do heavy processing here.
            Check record type, layer, or metadata to decide.
        """
        ...

    async def enrich(self, record: Record) -> EnrichmentResult:
        """Enrich a record with additional data.

        This method should:
        1. Add/update fields in record.metadata
        2. Optionally update record.layer to promote it
        3. Return an EnrichmentResult describing what was done

        Args:
            record: The record to enrich. Will be modified in place.

        Returns:
            EnrichmentResult describing the outcome.

        Note:
            - Call can_enrich() first if unsure about compatibility
            - Set status=SKIPPED if record doesn't need enrichment
            - Set status=FAILED with error_message on errors
        """
        ...


@runtime_checkable
class BatchEnricher(Protocol):
    """Protocol for batch record enrichment.

    Extends the basic Enricher concept to support efficient batch processing.
    Implementations can optimize by batching API calls, database queries, etc.

    Example:
        >>> class BatchSECEnricher:
        ...     name = "BatchSECEnricher"
        ...     max_batch_size = 100
        ...
        ...     async def enrich_batch(
        ...         self, records: list[Record]
        ...     ) -> list[EnrichmentResult]:
        ...         # Batch API call for all records at once
        ...         results = []
        ...         for record in records:
        ...             results.append(EnrichmentResult(
        ...                 record_id=record.id,
        ...                 status=EnrichmentStatus.SUCCESS,
        ...                 enricher_name=self.name,
        ...             ))
        ...         return results
    """

    @property
    def name(self) -> str:
        """The unique name of this enricher."""
        ...

    @property
    def max_batch_size(self) -> int:
        """Maximum number of records to process in one batch.

        The framework will chunk records into batches of this size.
        """
        ...

    async def enrich_batch(self, records: list[Record]) -> list[EnrichmentResult]:
        """Enrich multiple records in a single batch operation.

        This method should:
        1. Process all records efficiently (e.g., single API call)
        2. Return a result for each input record (same order)
        3. Handle partial failures gracefully

        Args:
            records: List of records to enrich.

        Returns:
            List of EnrichmentResults, one per input record.

        Note:
            Results must be in the same order as input records.
            Use status=FAILED for individual record failures.
        """
        ...


@dataclass
class BatchEnrichmentResult:
    """Result of a batch enrichment operation.

    Attributes:
        enricher_name: Name of the enricher that produced these results.
        results: Individual results for each record.
        total_records: Total number of records processed.
        successful: Number of successfully enriched records.
        failed: Number of failed enrichments.
        skipped: Number of skipped records.
        duration_ms: Total time for batch operation.

    Example:
        >>> result = BatchEnrichmentResult(
        ...     enricher_name="BatchEnricher",
        ...     results=[],
        ...     total_records=100,
        ...     successful=95,
        ...     failed=3,
        ...     skipped=2,
        ... )
    """

    enricher_name: str
    results: list[EnrichmentResult]
    total_records: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: float = 0.0


@dataclass
class EnricherConfig:
    """Configuration for an enricher.

    Attributes:
        name: Enricher name (must match Enricher.name).
        enabled: Whether this enricher is active.
        priority: Processing order (lower = earlier). Default 100.
        target_layers: Which layers this enricher applies to.
        options: Enricher-specific configuration.

    Example:
        >>> config = EnricherConfig(
        ...     name="SECFilingEnricher",
        ...     enabled=True,
        ...     priority=10,
        ...     target_layers=[Layer.BRONZE],
        ...     options={"extract_xbrl": True},
        ... )
    """

    name: str
    enabled: bool = True
    priority: int = 100
    target_layers: list[Layer] = field(default_factory=list)
    options: dict[str, object] = field(default_factory=dict)
