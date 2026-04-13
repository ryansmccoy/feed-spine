"""Enricher implementations for record enhancement.

This module provides enricher implementations for adding data and
promoting records through the Bronze -> Silver -> Gold layers.

Example:
    >>> from feedspine.enricher import PassthroughEnricher, MetadataEnricher
    >>>
    >>> # Simple promotion without adding data
    >>> enricher = PassthroughEnricher()
    >>> await enricher.enrich(record)  # BRONZE -> SILVER
    >>>
    >>> # Add specific metadata fields
    >>> enricher = MetadataEnricher(fields={"processed": True})
    >>> await enricher.enrich(record)

EntitySpine Integration (optional):
    Requires ``entityspine`` package.  When installed, ``EntityEnricher``
    resolves CIK/ticker/name against EntitySpine and adds entity metadata.

    >>> from feedspine.enricher import EntityEnricher  # only if entityspine installed
"""

from feedspine.enricher.batch import create_enrichment_work_items
from feedspine.enricher.job_store import (
    EnrichmentJob,
    EnrichmentJobRunner,
    EnrichmentJobStore,
    JobStatus,
    MemoryEnrichmentJobStore,
)
from feedspine.enricher.metadata import MetadataEnricher
from feedspine.enricher.passthrough import PassthroughEnricher
from feedspine.enricher.worker import FeedEnrichmentWorker

__all__ = [
    "MetadataEnricher",
    "PassthroughEnricher",
    "EnrichmentJob",
    "EnrichmentJobStore",
    "MemoryEnrichmentJobStore",
    "EnrichmentJobRunner",
    "JobStatus",
    "create_enrichment_work_items",
    "FeedEnrichmentWorker",
]

# EntityEnricher requires optional entityspine dependency
try:
    from feedspine.enricher.entity_enricher import EntityEnricher

    __all__ += ["EntityEnricher"]
except ImportError:
    pass
