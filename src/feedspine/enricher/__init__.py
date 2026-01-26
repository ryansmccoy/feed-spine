"""Enricher implementations for record enhancement.

This module provides enricher implementations for adding data and
promoting records through the Bronze → Silver → Gold layers.

Example:
    >>> from feedspine.enricher import PassthroughEnricher, MetadataEnricher
    >>>
    >>> # Simple promotion without adding data
    >>> enricher = PassthroughEnricher()
    >>> await enricher.enrich(record)  # BRONZE → SILVER
    >>>
    >>> # Add specific metadata fields
    >>> enricher = MetadataEnricher(fields={"processed": True})
    >>> await enricher.enrich(record)
"""

from feedspine.enricher.metadata import MetadataEnricher
from feedspine.enricher.passthrough import PassthroughEnricher

__all__ = ["MetadataEnricher", "PassthroughEnricher"]
