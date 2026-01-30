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

EntitySpine Integration:
    >>> from feedspine.enricher import EntityEnricher
    >>>
    >>> # Requires: pip install entityspine
    >>> from entityspine import SqliteStore
    >>>
    >>> store = SqliteStore("entities.db")
    >>> store.initialize()
    >>> store.load_sec_data()
    >>>
    >>> enricher = EntityEnricher(store)
    >>> await enricher.enrich(record)  # Adds entity_id, entity_name, etc.
"""

from feedspine.enricher.metadata import MetadataEnricher
from feedspine.enricher.passthrough import PassthroughEnricher

# EntityEnricher requires optional entityspine dependency
try:
    from feedspine.enricher.entity_enricher import EntityEnricher

    __all__ = ["MetadataEnricher", "PassthroughEnricher", "EntityEnricher"]
except ImportError:
    __all__ = ["MetadataEnricher", "PassthroughEnricher"]
