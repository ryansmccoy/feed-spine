---
title: "Domains"
type: reference
status: active
tags: [feedspine, domain]
created: 2026-01-15
updated: 2026-06-15
---
# Domain Implementations

FeedSpine is a generic framework, but it shines with domain-specific implementations. This section covers the reference implementation for SEC EDGAR and patterns for other domains.

## SEC EDGAR (Reference Implementation)

The SEC EDGAR domain demonstrates how to build a complete feed capture system:

- [SEC EDGAR Overview](sec-edgar/overview.md) - Feed types, data model, adapters, and deduplication

## Domain Pattern

Each domain implementation follows this pattern:

```python
from feedspine.adapter.base import BaseFeedAdapter
from feedspine.models.record import RecordCandidate

# 1. Create a feed adapter
class SECRSSFeed(BaseFeedAdapter):
    """SEC EDGAR RSS feed adapter."""

    def __init__(self) -> None:
        super().__init__(name="sec.rss", source_url="https://efts.sec.gov/...")

    async def _fetch_items(self) -> list[dict]:
        """Fetch raw items from SEC RSS."""
        # ... HTTP fetch logic ...
        return items

    def _to_candidate(self, item: dict) -> RecordCandidate:
        """Convert raw item to RecordCandidate with natural key."""
        return RecordCandidate(
            natural_key=item["accession_number"],
            content=item,
            source=self.name,
        )

# 2. Use the adapter with create_feed_spine()
from feedspine import create_feed_spine
from feedspine.storage.memory import MemoryStorage

app = create_feed_spine(MemoryStorage())
```

## Other Domains

Patterns for additional domains:

| Domain | Natural Key | Notes |
|--------|-------------|-------|
| Press Releases | `source:release_id` | GlobeNewswire, PRNewswire |
| News Articles | URL hash | Content fingerprinting |
| UK Companies House | Filing reference | Similar to SEC |
| Patents | Patent number | USPTO, EPO |
