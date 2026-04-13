#!/usr/bin/env python3
"""
FeedSpine Enrichment Pipeline Example
======================================

This example demonstrates the enrichment pipeline for transforming raw feed records
through Bronze → Silver → Gold data quality layers (Medallion Architecture).

What You'll Learn:
    1. How to use enrichers to improve data quality
    2. How to promote records between layers (Bronze/Silver/Gold)
    3. How to add metadata and extract entities
    4. How to use enrichment via CLI and Python SDK

Why Use Enrichment?
    - **Data Quality**: Transform raw feeds into structured, validated data
    - **Layer Separation**: Bronze (raw) → Silver (cleaned) → Gold (analytics-ready)
    - **Metadata Addition**: Add timestamps, source tracking, processing flags
    - **Entity Extraction**: Extract companies, tickers, dates from content
    - **Standardization**: Normalize formats, fix encoding, deduplicate

Medallion Architecture:
    ┌──────────────┐
    │ Bronze       │  Raw ingestion, minimal processing
    │ (Raw)        │  • Preserve original data
    └──────┬───────┘  • Basic deduplication
           │
           ▼
    ┌──────────────┐
    │ Silver       │  Cleaned and enriched
    │ (Cleaned)    │  • Standardized formats
    └──────┬───────┘  • Metadata added
           │           • Entities extracted
           ▼
    ┌──────────────┐
    │ Gold         │  Analytics-ready
    │ (Curated)    │  • Business logic applied
    └──────────────┘  • Aggregations
                      • Quality validated

Available Enrichers:
    1. **PassthroughEnricher**: Promote records to next layer (bronze→silver→gold)
    2. **MetadataEnricher**: Add custom metadata fields (processing time, flags, etc.)
    3. **EntityEnricher**: Extract entities (companies, tickers, dates) from content

CLI Commands:
    # List available enrichers
    feedspine enrich list

    # Promote bronze records to silver
    feedspine enrich run --enricher passthrough --layer bronze

    # Add metadata to records
    feedspine enrich run --enricher metadata --fields '{"processed":"true","version":"1.0"}'

    # Extract entities (if entity-spine is available)
    feedspine enrich run --enricher entity --layer silver

    # Dry-run (preview without saving)
    feedspine enrich run --enricher passthrough --layer bronze --dry-run --limit 5

Usage:
    python examples/04_operations/05_enrichment_pipeline.py

Expected Output:
    - Creates sample records in bronze layer
    - Demonstrates enrichment transformations
    - Shows layer promotion workflow
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

from feedspine import Record
from feedspine.models.base import Layer, Metadata
from feedspine.storage import MemoryStorage


def main() -> None:
    """Demonstrate enrichment pipeline workflow."""
    print("=" * 70)
    print("FeedSpine Enrichment Pipeline Example")
    print("=" * 70)
    print()

    # 1. Create storage and ingest sample records
    print("📦 Step 1: Create Sample Bronze Records")
    print()

    storage = MemoryStorage()

    # Sample SEC filing records
    now = datetime.now(UTC)
    meta = Metadata(source="sec-rss")

    bronze_records = [
        Record(
            id="sec-8k-001",
            natural_key="sec-8k-aapl-2026-02-14",
            layer=Layer.BRONZE,
            published_at=datetime(2026, 2, 14, 8, 0, tzinfo=UTC),
            captured_at=now,
            metadata=meta,
            content={
                "title": "Apple Inc. - 8-K Filing",
                "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/aapl-8k.htm",
                "filing_type": "8-K",
                "company": "Apple Inc.",
                "ticker": "AAPL",
                "published": "2026-02-14T08:00:00Z",
                "content": "Apple Inc. announced quarterly results...",
            },
        ),
        Record(
            id="sec-10q-002",
            natural_key="sec-10q-msft-2026-02-14",
            layer=Layer.BRONZE,
            published_at=datetime(2026, 2, 14, 9, 30, tzinfo=UTC),
            captured_at=now,
            metadata=meta,
            content={
                "title": "Microsoft Corporation - 10-Q Filing",
                "url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000001/msft-10q.htm",
                "filing_type": "10-Q",
                "company": "Microsoft Corporation",
                "ticker": "MSFT",
                "published": "2026-02-14T09:30:00Z",
                "content": "Microsoft Corporation filed quarterly report...",
            },
        ),
        Record(
            id="sec-4-003",
            natural_key="sec-4-nvda-2026-02-14",
            layer=Layer.BRONZE,
            published_at=datetime(2026, 2, 14, 16, 0, tzinfo=UTC),
            captured_at=now,
            metadata=meta,
            content={
                "title": "NVIDIA Corporation - Form 4",
                "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000001/nvda-4.htm",
                "filing_type": "4",
                "company": "NVIDIA Corporation",
                "ticker": "NVDA",
                "published": "2026-02-14T16:00:00Z",
                "content": "Insider transaction reported...",
            },
        ),
    ]

    # Store bronze records (storage operations are async)
    import asyncio

    async def store_records():
        await storage.initialize()
        for record in bronze_records:
            await storage.store(record)

    asyncio.run(store_records())

    print(f"✅ Created {len(bronze_records)} bronze records:")
    for rec in bronze_records:
        print(f"   • {rec.id}: {rec.content.get('filing_type')} - {rec.content.get('company')}")
    print()

    # 2. Demonstrate enricher listing
    print("📋 Step 2: List Available Enrichers (CLI)")
    print("   Command: feedspine enrich list")
    print()

    try:
        result = subprocess.run(["feedspine", "enrich", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("   Available enrichers:")
            print("   • passthrough - Promote records to next layer")
            print("   • metadata - Add custom metadata fields")
            print("   • entity - Extract entities (requires entity-spine)")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("   Available enrichers:")
        print("   • passthrough - Promote records to next layer")
        print("   • metadata - Add custom metadata fields")
        print("   • entity - Extract entities (requires entity-spine)")
    print()

    # 3. Show enrichment transformations
    print("🔄 Step 3: Enrichment Transformations")
    print()

    print("   💡 Transformation 1: Layer Promotion (Bronze → Silver)")
    print("   Command: feedspine enrich run --enricher passthrough --layer bronze")
    print()
    print("   Effect:")
    print("   • Moves records from bronze layer to silver layer")
    print("   • Preserves all original data")
    print("   • Updates layer metadata")
    print()

    print("   💡 Transformation 2: Add Metadata")
    print("   Command: feedspine enrich run --enricher metadata \\")
    print('            --fields \'{"processed_at":"2026-02-14","quality_check":"passed"}\'')
    print()
    print("   Effect:")
    print("   • Adds custom metadata fields to each record")
    print("   • Useful for tracking processing stages")
    print("   • Can add version, flags, timestamps")
    print()

    print("   💡 Transformation 3: Entity Extraction")
    print("   Command: feedspine enrich run --enricher entity --layer silver")
    print()
    print("   Effect:")
    print("   • Extracts structured entities (companies, tickers, dates)")
    print("   • Creates normalized entity references")
    print("   • Links to entity-spine knowledge graph")
    print()

    # 4. Show dry-run workflow
    print("🔍 Step 4: Dry-Run Preview")
    print("   Command: feedspine enrich run --enricher passthrough --layer bronze \\")
    print("            --dry-run --limit 5")
    print()
    print("   Dry-run shows what WOULD happen without making changes:")
    print()

    # Get bronze records (async operation)
    async def get_bronze_records():
        recs = []
        async for rec in storage.query(layer=Layer.BRONZE, limit=5):
            recs.append(rec)
        return recs

    bronze_recs = asyncio.run(get_bronze_records())

    # Layer promotion: bronze → silver → gold
    layer_map = {Layer.BRONZE: Layer.SILVER, Layer.SILVER: Layer.GOLD}

    if bronze_recs:
        print(f"   Would process {len(bronze_recs)} records:")
        for rec in bronze_recs:
            target_layer = layer_map.get(rec.layer, rec.layer)
            print(f"   • {rec.id}: {rec.layer.value} → {target_layer.value}")
    else:
        print("   No bronze records found")
    print()

    # 5. Show typical workflow
    print("📊 Step 5: Complete Enrichment Workflow")
    print()
    print("   Typical production workflow:")
    print()
    print("   1. Ingest raw data (bronze layer)")
    print("      $ feedspine collect run sec-rss")
    print()
    print("   2. Add metadata (still bronze)")
    print("      $ feedspine enrich run --enricher metadata \\")
    print('        --fields \'{"ingested_at":"2026-02-14","source_version":"1.0"}\'')
    print()
    print("   3. Promote to silver (cleaned)")
    print("      $ feedspine enrich run --enricher passthrough --layer bronze")
    print()
    print("   4. Extract entities (silver layer)")
    print("      $ feedspine enrich run --enricher entity --layer silver")
    print()
    print("   5. Promote to gold (analytics-ready)")
    print("      $ feedspine enrich run --enricher passthrough --layer silver")
    print()

    # 6. Best practices
    print("💡 Best Practices:")
    print("   • Keep bronze layer unchanged (immutable raw data)")
    print("   • Use metadata enricher for tracking (timestamps, versions)")
    print("   • Promote to silver only after validation")
    print("   • Reserve gold layer for business-logic transforms")
    print("   • Use --dry-run first to preview changes")
    print("   • Monitor enrichment stats via API: GET /api/v1/enrich/stats")
    print()

    # 7. Show current stats
    print("📈 Step 6: Current Statistics")
    print()

    # Count records by layer (async operation)
    async def count_by_layer():
        return {
            Layer.BRONZE: await storage.count(layer=Layer.BRONZE),
            Layer.SILVER: await storage.count(layer=Layer.SILVER),
            Layer.GOLD: await storage.count(layer=Layer.GOLD),
        }

    layer_counts = asyncio.run(count_by_layer())

    print(f"   Bronze: {layer_counts[Layer.BRONZE]} records")
    print(f"   Silver: {layer_counts[Layer.SILVER]} records")
    print(f"   Gold: {layer_counts[Layer.GOLD]} records")
    print()

    print("=" * 70)
    print("✅ Example Complete!")
    print("=" * 70)
    print()
    print("Next Steps:")
    print("• Try enriching records via CLI: feedspine enrich run --help")
    print("• Check enrichment stats: GET /api/v1/enrich/stats")
    print("• View layer distribution: feedspine stats")
    print()


if __name__ == "__main__":
    main()
