# Domain Implementations

FeedSpine is a generic framework, but it shines with domain-specific implementations. This section covers the reference implementation for SEC EDGAR and patterns for other domains.

## SEC EDGAR (Reference Implementation)

The SEC EDGAR domain demonstrates how to build a complete feed capture system:

- [SEC EDGAR Overview](sec-edgar/overview.md) - Feed types and data model
- [Feed Adapters](sec-edgar/feed-adapters.md) - RSS, Daily Index, Full Index, XBRL
- [Deduplication](sec-edgar/deduplication.md) - Accession number as natural key
- [Filing Extraction](sec-edgar/extraction.md) - Parsing SEC filing formats

## Domain Pattern

Each domain implementation follows this pattern:

```python
# 1. Define natural key for deduplication
class SECNormalizer(Normalizer):
    domain = "sec"
    
    def compute_dedup_key(self, item: BronzeItem) -> str:
        return item.metadata["accession_number"]

# 2. Create feed adapters
class SECRSSFeed(FeedAdapter):
    name = "sec.rss"
    # ...

# 3. Register with FeedSpine
feedspine.register_domain("sec", normalizer=SECNormalizer())
feedspine.register_feed(SECRSSFeed())
```

## Other Domains

Patterns for additional domains:

| Domain | Natural Key | Notes |
|--------|-------------|-------|
| Press Releases | `source:release_id` | GlobeNewswire, PRNewswire |
| News Articles | URL hash | Content fingerprinting |
| UK Companies House | Filing reference | Similar to SEC |
| Patents | Patent number | USPTO, EPO |
