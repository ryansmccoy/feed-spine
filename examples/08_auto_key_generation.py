#!/usr/bin/env python3
"""Example 8: Auto Key Generation for FeedSpine

Demonstrates how FeedSpine handles deduplication when source data
doesn't have a unique identifier.

Key Problem:
    Not all data sources provide unique IDs. For example:
    - Web scraped content
    - Sensor/IoT data streams
    - Some REST APIs
    - Log entries
    - Social media without stable IDs
    
Solution:
    FeedSpine provides multiple strategies for generating unique keys:
    1. ID Field Detection - Check common ID fields (id, guid, uuid, etc.)
    2. URL Extraction - Extract IDs from URLs using patterns
    3. Composite Keys - Combine multiple fields into a unique key
    4. Content Hashing - SHA-256 hash of the data content
"""

from datetime import datetime
from feedspine.utils import (
    auto_key,
    generate_content_key,
    AutoKeyGenerator,
    CompositeKeyBuilder,
    URLKeyExtractor,
)


def main():
    """Demonstrate all key generation strategies."""
    print("FeedSpine Auto Key Generation Examples")
    print("=" * 60)
    
    # =========================================================================
    # Strategy 1: ID Field Detection (Default)
    # =========================================================================
    print("\n1. ID Field Detection")
    print("-" * 40)
    
    # auto_key() automatically checks common ID fields
    examples = [
        {"id": "12345", "title": "Article"},
        {"guid": "abc-def-123", "content": "Content"},
        {"uuid": "550e8400-e29b-41d4-a716-446655440000"},
        {"_id": "mongo_doc_id", "data": "value"},
        {"accession_number": "0001234567-24-000001"},  # SEC-specific
    ]
    
    for data in examples:
        key = auto_key(data)
        id_field = next(iter(data.keys()))
        print(f"  {id_field}: {data[id_field][:30]:<35} → key: {key}")
    
    # =========================================================================
    # Strategy 2: Content Hashing (Fallback)
    # =========================================================================
    print("\n2. Content Hashing (No ID Available)")
    print("-" * 40)
    
    # When no ID field exists, auto_key() falls back to content hash
    sensor_reading = {
        "timestamp": "2024-01-15T10:30:00Z",
        "temperature": 72.5,
        "humidity": 45.2,
        "sensor": "room-1"
    }
    
    key1 = auto_key(sensor_reading)
    print(f"  Sensor reading → key: {key1}")
    
    # Same content = same key (deterministic)
    key2 = auto_key(sensor_reading)
    print(f"  Same reading   → key: {key2}")
    print(f"  Keys match: {key1 == key2}")
    
    # Different content = different key
    sensor_reading["temperature"] = 73.0
    key3 = auto_key(sensor_reading)
    print(f"  Updated temp   → key: {key3}")
    print(f"  Keys match: {key1 == key3}")
    
    # =========================================================================
    # Strategy 3: URL Key Extraction
    # =========================================================================
    print("\n3. URL Key Extraction")
    print("-" * 40)
    
    # Many web APIs include IDs in URLs
    extractor = URLKeyExtractor(pattern=r'/article/(\d+)')
    
    urls = [
        "https://news.com/article/12345/full-story",
        "https://news.com/article/67890",
        "https://news.com/latest",  # No match - returns None
    ]
    
    for url in urls:
        key = extractor.extract(url)
        print(f"  {url:<45} → key: {key}")
    
    # Extract from query parameters
    extractor2 = URLKeyExtractor(use_query_param="post_id")
    url = "https://api.example.com/posts?post_id=abc123&format=json"
    key = extractor2.extract(url)
    print(f"\n  Query param extraction:")
    print(f"  {url}")
    print(f"  → key: {key}")
    
    # =========================================================================
    # Strategy 4: Composite Keys
    # =========================================================================
    print("\n4. Composite Key Builder")
    print("-" * 40)
    
    # Combine multiple fields to create a unique key
    builder = CompositeKeyBuilder(["author", "published_date", "title"])
    
    article = {
        "author": "John Smith",
        "published_date": "2024-01-15",
        "title": "Market Analysis",
        "content": "Full article text...",
    }
    
    key = builder.build(article)
    print(f"  Fields: author + published_date + title")
    print(f"  Data: {article['author']} | {article['published_date']} | {article['title']}")
    print(f"  Key: {key}")
    
    # Useful for logs/events where combo of fields is unique
    builder2 = CompositeKeyBuilder(
        fields=["timestamp", "source", "event_type"],
        separator="_"  # Custom separator
    )
    
    log_entry = {
        "timestamp": "2024-01-15T10:30:00",
        "source": "web-server-1",
        "event_type": "request",
        "details": {"path": "/api/users"},
    }
    
    key = builder2.build(log_entry)
    print(f"\n  Log entry key: {key}")
    
    # =========================================================================
    # Strategy 5: AutoKeyGenerator (Full Pipeline)
    # =========================================================================
    print("\n5. AutoKeyGenerator (Full Pipeline)")
    print("-" * 40)
    
    # Configure a generator with multiple strategies
    generator = AutoKeyGenerator(
        id_fields=["id", "article_id", "guid"],  # Custom ID fields to check
        url_field="link",  # URL field to extract from
        url_pattern=r'/posts/(\d+)',  # Pattern to extract ID
        composite_fields=["author", "date"],  # Fallback composite
        source_prefix="myblog",  # Prefix all keys
    )
    
    test_cases = [
        # Has explicit ID
        {"id": "12345", "title": "Test"},
        
        # No ID, but has URL with ID
        {"link": "https://blog.com/posts/67890", "title": "Blog Post"},
        
        # No ID, no URL, uses composite
        {"author": "Jane", "date": "2024-01-15", "body": "Content..."},
        
        # Nothing matches - falls back to content hash
        {"body": "Just some content"},
    ]
    
    for data in test_cases:
        key = generator.generate(data)
        print(f"  {str(data)[:50]:<55} → {key}")
    
    # =========================================================================
    # Real-World Example: Adapter with Auto Keys
    # =========================================================================
    print("\n6. Real-World Example: Custom Adapter")
    print("-" * 40)
    
    print("""
    class WeatherApiAdapter(FeedAdapter):
        '''Adapter for weather API that doesn't provide unique IDs.'''
        
        def __init__(self, stations: list[str]):
            self.stations = stations
            self.key_builder = CompositeKeyBuilder(
                fields=["station_id", "timestamp", "reading_type"]
            )
        
        async def fetch(self) -> AsyncIterator[RecordCandidate]:
            for station in self.stations:
                data = await self._fetch_station(station)
                
                for reading in data["readings"]:
                    # Generate a unique key from the reading data
                    natural_key = self.key_builder.build(reading)
                    
                    yield RecordCandidate(
                        natural_key=natural_key,  # Auto-generated!
                        source=f"weather:{station}",
                        data=reading,
                        discovered_at=datetime.now(),
                    )
    """)
    
    # =========================================================================
    # Performance Characteristics
    # =========================================================================
    print("\n7. Performance Characteristics")
    print("-" * 40)
    
    import time
    
    # Benchmark key generation
    large_data = {f"field_{i}": f"value_{i}" * 100 for i in range(100)}
    
    iterations = 10000
    
    start = time.perf_counter()
    for _ in range(iterations):
        generate_content_key(large_data)
    elapsed = time.perf_counter() - start
    
    print(f"  Content hash of 100-field dict:")
    print(f"  {iterations:,} iterations in {elapsed:.3f}s")
    print(f"  {iterations/elapsed:,.0f} keys/second")
    
    # =========================================================================
    # Best Practices
    # =========================================================================
    print("\n8. Best Practices")
    print("-" * 40)
    print("""
    1. Prefer explicit IDs when available - most reliable
    
    2. For web data, use URL extraction - IDs in URLs are stable
    
    3. For events/logs, use composite keys:
       - timestamp + source + event_type
       - Ensures uniqueness without hashing
    
    4. Content hash is a last resort:
       - Deterministic and collision-resistant
       - BUT: slight data changes = new key (no dedup)
       - Good for: immutable records, sensor data
       
    5. Add source prefixes for multi-source systems:
       - Prevents key collisions across sources
       - Example: "sec:12345" vs "reuters:12345"
       
    6. Test your key generation:
       - Verify duplicate records get same key
       - Verify different records get different keys
    """)


if __name__ == "__main__":
    main()
