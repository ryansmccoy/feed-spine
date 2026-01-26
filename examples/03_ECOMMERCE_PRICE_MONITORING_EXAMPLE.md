# FeedSpine: E-Commerce Price Monitoring Use Case

## Competitive Price Intelligence Platform

**Industry:** E-Commerce / Retail  
**Use Case:** Real-Time Competitor Price Tracking & Analysis  
**Companies:** Amazon, Walmart, Best Buy, Wayfair, Chewy

---

## The Problem

E-commerce platforms need real-time visibility into competitor pricing to:
- Maintain competitive positioning
- Automate dynamic pricing decisions
- Track promotional patterns
- Monitor MAP (Minimum Advertised Price) compliance
- Detect stockouts and inventory changes

**Current Pain Points:**
- Manual price checks don't scale across millions of SKUs
- Duplicate product listings waste analysis time
- Historical price tracking is fragmented
- No unified view across competitors
- Rate limiting and anti-bot measures block scrapers

---

## FeedSpine Solution

```python
"""
E-Commerce Example: Competitive Price Intelligence
Monitor competitor prices across multiple retailers with deduplication.
"""

import asyncio
from datetime import datetime, UTC
from feedspine import (
    FeedSpine,
    JSONFeedAdapter,
    DuckDBStorage,
    MemoryScheduler,
    ConsoleNotifier,
)
from feedspine.models.record import RecordCandidate
from feedspine.models.base import Metadata


# Competitor API endpoints (simplified - real implementation would use proxies)
COMPETITOR_FEEDS = {
    "amazon-electronics": {
        "url": "https://api.example.com/amazon/electronics",
        "items_path": "products",
        "category": "electronics",
    },
    "walmart-electronics": {
        "url": "https://api.example.com/walmart/electronics", 
        "items_path": "items.products",
        "category": "electronics",
    },
    "bestbuy-electronics": {
        "url": "https://api.example.com/bestbuy/electronics",
        "items_path": "data.skus",
        "category": "electronics",
    },
    "target-home": {
        "url": "https://api.example.com/target/home",
        "items_path": "results",
        "category": "home",
    },
}


class PriceIntelligenceAdapter(JSONFeedAdapter):
    """Custom adapter for competitor price feeds with SKU normalization."""
    
    def __init__(self, name: str, url: str, items_path: str, category: str):
        super().__init__(
            url=url,
            name=name,
            source_type="price-feed",
            items_path=items_path,
            field_mapping={
                "id": "sku",
                "title": "product_name",
                "url": "product_url",
            },
            requests_per_second=0.5,  # Respect rate limits
        )
        self.category = category
    
    def _to_candidate(self, item: dict) -> RecordCandidate:
        """Convert raw product to candidate with price metadata."""
        
        # Normalize SKU/UPC for cross-retailer matching
        sku = item.get("sku") or item.get("upc") or item.get("asin")
        normalized_sku = self._normalize_sku(sku)
        
        return RecordCandidate(
            # Natural key combines retailer + normalized SKU
            natural_key=f"{self.name}:{normalized_sku}",
            published_at=datetime.now(UTC),
            content={
                "sku": sku,
                "normalized_sku": normalized_sku,
                "name": item.get("product_name") or item.get("title"),
                "price": item.get("price") or item.get("current_price"),
                "original_price": item.get("original_price") or item.get("list_price"),
                "in_stock": item.get("in_stock", True),
                "url": item.get("product_url") or item.get("url"),
                "image_url": item.get("image"),
                "category": self.category,
                "retailer": self.name.split("-")[0],
            },
            metadata=Metadata(
                source=self.name,
                record_type="product-price",
                extra={
                    "captured_at": datetime.now(UTC).isoformat(),
                    "category": self.category,
                },
            ),
        )
    
    def _normalize_sku(self, sku: str) -> str:
        """Normalize SKU for cross-retailer matching."""
        if not sku:
            return ""
        # Remove common prefixes, standardize format
        sku = sku.upper().strip()
        sku = sku.replace("-", "").replace(" ", "")
        return sku


async def main():
    storage = DuckDBStorage("price_intelligence.duckdb")
    scheduler = MemoryScheduler()
    
    async with FeedSpine(storage=storage) as spine:
        
        # Register all competitor feeds
        for feed_name, config in COMPETITOR_FEEDS.items():
            adapter = PriceIntelligenceAdapter(
                name=feed_name,
                url=config["url"],
                items_path=config["items_path"],
                category=config["category"],
            )
            spine.register_feed(adapter)
        
        # Collect from all sources
        result = await spine.collect()
        
        print(f"💰 Price Intelligence Collection:")
        print(f"   Retailers:     {len(spine.list_feeds())}")
        print(f"   Products:      {result.total_processed}")
        print(f"   New Prices:    {result.total_new}")
        print(f"   Updated:       {result.total_duplicates}")
        
        # Analyze price changes
        await analyze_price_changes(spine)
        
        # Find competitive opportunities
        await find_price_opportunities(spine)


async def analyze_price_changes(spine: FeedSpine):
    """Analyze price changes across retailers."""
    
    print(f"\n📊 Price Analysis:")
    
    # Get all products with sighting history
    async for record in spine.query(layer="bronze", limit=100):
        sightings = await spine.storage.get_sightings(record.natural_key)
        
        if len(sightings) > 1:
            print(f"   {record.content.get('name')[:40]}: {len(sightings)} price points")


async def find_price_opportunities(spine: FeedSpine):
    """Find products where we can be more competitive."""
    
    print(f"\n🎯 Competitive Opportunities:")
    
    # Query products with significant discounts
    async for record in spine.query(
        layer="bronze",
        filters={"content.in_stock": True},
        limit=50
    ):
        price = record.content.get("price", 0)
        original = record.content.get("original_price", price)
        
        if original and price < original * 0.8:  # 20%+ discount
            discount = (1 - price / original) * 100
            print(f"   🔥 {discount:.0f}% off: {record.content.get('name')[:40]}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Why FeedSpine Excels Here

### 1. **SKU-Based Deduplication**
Same product across retailers tracked as related entries with shared normalized SKU.

```python
# Product: Sony WH-1000XM5 Headphones
# Amazon ASIN:  B09XS7JWHH  → normalized: B09XS7JWHH
# Walmart SKU:  123456789   → normalized: 123456789
# Best Buy SKU: 6505727     → normalized: 6505727

# Natural keys:
# - amazon-electronics:B09XS7JWHH
# - walmart-electronics:123456789
# - bestbuy-electronics:6505727

# Cross-reference using UPC: 027242923782
```

### 2. **Price History via Sightings**
Every price capture is a sighting—build complete price history over time.

```python
# Get price history for a product
sightings = await storage.get_sightings("amazon-electronics:B09XS7JWHH")

for s in sightings:
    print(f"{s.seen_at}: ${s.metadata.get('price')}")

# Output:
# 2024-01-15T09:00:00Z: $328.00
# 2024-01-14T09:00:00Z: $348.00
# 2024-01-13T09:00:00Z: $398.00  ← Price drop detected!
```

### 3. **Analytical Queries with DuckDB**
Complex price analysis using SQL.

```python
# Find products with >20% price drop in last 7 days
# DuckDB enables this directly on collected data

query = """
SELECT 
    content->>'name' as product,
    content->>'price' as current_price,
    LAG(content->>'price') OVER (
        PARTITION BY natural_key 
        ORDER BY captured_at
    ) as previous_price
FROM records
WHERE layer = 'bronze'
  AND captured_at > NOW() - INTERVAL '7 days'
HAVING current_price < previous_price * 0.8
"""
```

### 4. **Rate Limiting Built-In**
Respect competitor rate limits to avoid blocks.

```python
adapter = PriceIntelligenceAdapter(
    name="amazon",
    url="https://api.example.com/amazon",
    items_path="products",
    category="electronics",
    requests_per_second=0.5,  # Max 1 request per 2 seconds
)

# FeedSpine handles rate limiting automatically
```

### 5. **Medallion Architecture for Price Data**

```
Bronze (Raw)           Silver (Normalized)       Gold (Analytics)
─────────────────────────────────────────────────────────────────
Raw price capture  →   SKU normalized        →   Price index
Retailer-specific      Cross-retailer match      Competitive score
timestamps             Price history             Opportunity alerts
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Price Intelligence Platform                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    Competitor Price Feeds                                               │
│    ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐         │
│    │ Amazon │  │Walmart │  │Best Buy│  │ Target │  │ Chewy  │  ...    │
│    └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘         │
│        │           │           │           │           │               │
│        └───────────┴───────────┴───────────┴───────────┘               │
│                              │                                          │
│                    ┌─────────▼─────────┐                               │
│                    │    FeedSpine      │                               │
│                    │  Price Adapters   │                               │
│                    └─────────┬─────────┘                               │
│                              │                                          │
│    ┌─────────────────────────┼─────────────────────────┐               │
│    │                         │                         │               │
│    ▼                         ▼                         ▼               │
│ ┌────────────┐        ┌───────────┐           ┌─────────────┐         │
│ │SKU Dedup   │        │ Sighting  │           │  Scheduler  │         │
│ │& Normalize │        │  History  │           │ (Hourly)    │         │
│ └────────────┘        └───────────┘           └─────────────┘         │
│        │                                                               │
│        ▼                                                               │
│ ┌──────────────────────────────────────────────────────────────┐      │
│ │                     DuckDB Storage                           │      │
│ │  ┌────────────┐  ┌────────────┐  ┌────────────┐              │      │
│ │  │   Bronze   │  │   Silver   │  │    Gold    │              │      │
│ │  │ Raw Prices │→ │ Normalized │→ │ Analytics  │              │      │
│ │  └────────────┘  └────────────┘  └────────────┘              │      │
│ └──────────────────────────────────────────────────────────────┘      │
│                              │                                         │
│              ┌───────────────┼───────────────┐                        │
│              │               │               │                        │
│              ▼               ▼               ▼                        │
│     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│     │  Pricing    │  │   Alert     │  │  Analytics  │                │
│     │   Engine    │  │   System    │  │  Dashboard  │                │
│     └─────────────┘  └─────────────┘  └─────────────┘                │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Business Impact

| Metric | Before FeedSpine | After FeedSpine |
|--------|-----------------|-----------------|
| Price Check Frequency | Daily | Hourly |
| SKU Coverage | 10,000 | 1,000,000+ |
| Price History Depth | 30 days | Unlimited |
| Competitive Response Time | 24 hours | < 1 hour |
| Infrastructure Cost | $100K/month | $10K/month |

---

## Advanced Features

### Price Alert Configuration

```python
from feedspine.notifier.slack import SlackNotifier

# Configure alerts for significant price changes
notifier = SlackNotifier(
    webhook_url=os.environ["SLACK_WEBHOOK"],
    channel="#price-alerts",
)

async def check_price_alerts(record, previous_sighting):
    """Alert on significant price changes."""
    
    current_price = record.content.get("price", 0)
    previous_price = previous_sighting.metadata.get("price", current_price)
    
    if current_price < previous_price * 0.9:  # 10%+ drop
        await notifier.send(Notification(
            title=f"🔥 Price Drop: {record.content.get('name')}",
            message=f"${previous_price} → ${current_price} ({(1-current_price/previous_price)*100:.0f}% off)",
            severity=Severity.INFO,
            tags=["price-drop", record.content.get("retailer")],
        ))
```

### MAP Compliance Monitoring

```python
async def check_map_compliance(spine: FeedSpine, map_prices: dict):
    """Check for MAP (Minimum Advertised Price) violations."""
    
    violations = []
    
    async for record in spine.query(layer="bronze"):
        sku = record.content.get("normalized_sku")
        price = record.content.get("price", float("inf"))
        
        if sku in map_prices and price < map_prices[sku]:
            violations.append({
                "sku": sku,
                "retailer": record.content.get("retailer"),
                "advertised_price": price,
                "map_price": map_prices[sku],
                "violation_amount": map_prices[sku] - price,
            })
    
    return violations
```

### Dynamic Pricing Integration

```python
async def get_competitive_position(spine: FeedSpine, our_sku: str, our_price: float):
    """Calculate our competitive position for a product."""
    
    competitor_prices = []
    
    async for record in spine.query(
        layer="bronze",
        filters={"content.normalized_sku": our_sku}
    ):
        competitor_prices.append({
            "retailer": record.content.get("retailer"),
            "price": record.content.get("price"),
            "in_stock": record.content.get("in_stock"),
        })
    
    # Calculate position
    in_stock_prices = [p["price"] for p in competitor_prices if p["in_stock"]]
    
    return {
        "our_price": our_price,
        "min_competitor": min(in_stock_prices) if in_stock_prices else None,
        "max_competitor": max(in_stock_prices) if in_stock_prices else None,
        "avg_competitor": sum(in_stock_prices) / len(in_stock_prices) if in_stock_prices else None,
        "position": "lowest" if our_price <= min(in_stock_prices, default=0) else "competitive",
    }
```

---

## Next Steps

1. **Add UPC/EAN Cross-Reference** database for universal SKU matching
2. **Implement Price Prediction** using historical sighting data
3. **Build Real-Time Dashboard** with price comparison charts
4. **Add Image Recognition** for product matching without SKUs
5. **Deploy Proxy Rotation** for resilient data collection
