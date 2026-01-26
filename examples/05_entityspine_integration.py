#!/usr/bin/env python3
"""
FeedSpine with EntitySpine Integration

Shows how to enrich feed records with entity resolution from EntitySpine.
This is the integration pattern for py-sec-edgar ecosystem.

Usage:
    pip install entityspine
    python examples/05_entityspine_integration.py
"""

import asyncio
from typing import Any

from feedspine import (
    FeedSpine,
    MemoryStorage,
    RSSFeedAdapter,
    RecordCandidate,
)
from feedspine.enricher.passthrough import PassthroughEnricher

# EntitySpine is optional
try:
    from entityspine import SqliteStore
    HAS_ENTITYSPINE = True
except ImportError:
    HAS_ENTITYSPINE = False


class EntityEnricher(PassthroughEnricher):
    """
    Enricher that resolves entity identifiers using EntitySpine.
    
    This is the recommended integration pattern:
    - FeedSpine handles feed collection and deduplication
    - EntitySpine handles entity resolution (CIK → company details)
    """
    
    def __init__(self, entity_store: Any):
        super().__init__()
        self.entity_store = entity_store
    
    async def enrich(self, candidate: RecordCandidate) -> RecordCandidate:
        """Enrich record with entity data from EntitySpine."""
        content = dict(candidate.content or {})
        
        # If content has a CIK, resolve to full entity details
        cik = content.get("cik")
        if cik and hasattr(self.entity_store, "search"):
            entities = self.entity_store.search(cik, limit=1)
            if entities:
                entity = entities[0]
                content["entity_name"] = entity.name
                content["entity_id"] = entity.entity_id
                content["ticker"] = entity.get_identifier("ticker")
        
        return RecordCandidate(
            natural_key=candidate.natural_key,
            published_at=candidate.published_at,
            content=content,
        )


async def main() -> None:
    """Demonstrate FeedSpine + EntitySpine integration."""
    
    if not HAS_ENTITYSPINE:
        print("EntitySpine not installed. Install with: pip install entityspine")
        print("\nShowing pattern without actual EntitySpine...")
        # Continue with demo pattern
    
    storage = MemoryStorage()
    
    async with FeedSpine(storage=storage) as spine:
        # In production, you would:
        # 1. Set up EntitySpine with SEC company data
        #    store = SqliteStore("entities.db")
        #    store.load_sec_data()  # Auto-downloads ~8,000 companies
        #
        # 2. Add EntityEnricher to the pipeline
        #    spine.set_enricher(EntityEnricher(store))
        #
        # 3. Now when you collect SEC filings, they're enriched
        #    with full company details from EntitySpine
        
        spine.register_feed(RSSFeedAdapter(
            name="example",
            url="https://news.ycombinator.com/rss",
        ))
        
        result = await spine.collect()
        print(f"Collected: {result.total_new} new records")
        
        print("\n" + "="*60)
        print("INTEGRATION PATTERN: FeedSpine + EntitySpine")
        print("="*60)
        print("""
1. FeedSpine:
   - Collects from RSS feeds, JSON APIs
   - Deduplicates by natural key (accession number)
   - Tracks sighting history

2. EntitySpine:
   - Resolves CIK → company name, ticker
   - Provides ticker → CIK lookup
   - Maintains entity knowledge graph

3. Integration:
   - EntityEnricher uses EntitySpine to enrich records
   - FilingFacts contract for structured data exchange
   - py-sec-edgar uses both for complete workflows
""")


if __name__ == "__main__":
    asyncio.run(main())
