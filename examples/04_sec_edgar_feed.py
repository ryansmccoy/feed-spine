#!/usr/bin/env python3
"""
FeedSpine SEC EDGAR Filing Monitor

Example of monitoring SEC filings with automatic deduplication.
The same filing may appear in RSS feed, daily index, and quarterly index.

Usage:
    python examples/04_sec_edgar_feed.py
"""

import asyncio
from typing import Any

from feedspine import (
    FeedSpine,
    MemoryStorage,
    RSSFeedAdapter,
    RecordCandidate,
)


class SECFilingFeed(RSSFeedAdapter):
    """
    SEC EDGAR RSS feed adapter.
    
    Creates natural keys based on accession number so the same
    filing from different sources is deduplicated automatically.
    """
    
    def __init__(self, form_type: str):
        # SEC EDGAR RSS feed for specific form type
        url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcurrent&type={form_type}&company=&dateb="
            f"&owner=include&count=40&output=atom"
        )
        super().__init__(
            name=f"sec-{form_type.lower().replace(' ', '-')}",
            url=url,
        )
        self.form_type = form_type
    
    def _entry_to_candidate(self, entry: dict[str, Any]) -> RecordCandidate:
        """Create candidate with SEC accession number as natural key."""
        # Extract accession number for deduplication
        accession = entry.get("id", "") or entry.get("link", "")
        
        # Natural key ensures same filing from multiple feeds = 1 record
        natural_key = f"sec-filing:{accession}"
        
        return RecordCandidate(
            natural_key=natural_key,
            published_at=entry.get("published"),
            content={
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "form_type": self.form_type,
            },
        )


async def main() -> None:
    """Monitor SEC filings with automatic deduplication."""
    
    storage = MemoryStorage()
    
    # Form types to monitor
    form_types = ["10-K", "10-Q", "8-K"]
    
    async with FeedSpine(storage=storage) as spine:
        # Register a feed for each form type
        for form_type in form_types:
            feed = SECFilingFeed(form_type)
            spine.register_feed(feed)
            print(f"Registered: {feed.name}")
        
        # Collect from all SEC feeds
        print("\nCollecting SEC filings...")
        result = await spine.collect()
        
        print(f"\n{'='*50}")
        print(f"SEC EDGAR Collection Results")
        print(f"{'='*50}")
        print(f"Total filings processed: {result.total_processed}")
        print(f"New filings: {result.total_new}")
        print(f"Duplicates: {result.total_duplicates}")
        
        # In production, the same filing might appear in:
        # - RSS feed (realtime)
        # - Daily index (next day)
        # - Quarterly index (quarterly)
        # FeedSpine stores it once, tracks all sightings
        print("\nNote: Same filing from multiple sources is stored once!")


if __name__ == "__main__":
    asyncio.run(main())
