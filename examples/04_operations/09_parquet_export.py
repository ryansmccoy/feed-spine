#!/usr/bin/env python3
"""
FeedSpine Parquet Export Example

Demonstrates exporting data to Apache Parquet format using DuckDB:
- Native Parquet export for analytics
- Layer-filtered exports
- File size and record count reporting

Parquet is ideal for:
- Data warehouse integration
- Analytics pipelines
- Long-term archival
- Cross-platform data sharing

Requires: pip install feedspine[duckdb]

Usage:
    python examples/04_operations/09_parquet_export.py
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from feedspine import Layer, Record
from feedspine.models.base import Metadata


async def main() -> None:
    """Demonstrate Parquet export capabilities."""
    print("=" * 60)
    print("FeedSpine Parquet Export Example")
    print("=" * 60)
    print()

    # Check for DuckDB availability
    try:
        from feedspine.storage.backends.duckdb import DuckDBStorage
    except ImportError:
        print("DuckDB is required for this example.")
        print("Install with: pip install feedspine[duckdb]")
        return

    db_path = "parquet_demo.duckdb"
    export_dir = Path("parquet_exports")

    # Clean up any existing demo files
    if os.path.exists(db_path):
        os.remove(db_path)
    if export_dir.exists():
        for f in export_dir.glob("*.parquet"):
            f.unlink()
    else:
        export_dir.mkdir()

    storage = DuckDBStorage(db_path)
    await storage.initialize()

    print("1. Populating demo data...")

    now = datetime.now(UTC)

    # Create records across different layers
    layers_data = [
        (Layer.BRONZE, 100, "Raw feed data"),
        (Layer.SILVER, 50, "Normalized data"),
        (Layer.GOLD, 20, "Enriched analytics"),
    ]

    for layer, count, description in layers_data:
        print(f"  Creating {count} {layer.value} records ({description})...")
        for i in range(count):
            record = Record(
                id=str(uuid4()),
                natural_key=f"{layer.value}:item:{i}",
                layer=layer,
                content={
                    "index": i,
                    "layer": layer.value,
                    "description": description,
                    "value": i * 1.5,
                    "tags": ["demo", layer.value],
                },
                metadata=Metadata(source="demo-export"),
                published_at=now - timedelta(hours=i),
                captured_at=now,
            )
            await storage.store(record)

    total = await storage.count()
    print(f"  Total records created: {total}")
    print()

    # -------------------------------------------------------------------------
    # 2. Export All Records
    # -------------------------------------------------------------------------
    print("2. Exporting all records to Parquet...")

    all_export_path = export_dir / "all_records.parquet"
    count = await storage.export_to_parquet(all_export_path)

    file_size = all_export_path.stat().st_size if all_export_path.exists() else 0
    size_kb = file_size / 1024

    print(f"  Exported: {count} records")
    print(f"  File: {all_export_path}")
    print(f"  Size: {size_kb:.1f} KB")
    print()

    # -------------------------------------------------------------------------
    # 3. Export by Layer
    # -------------------------------------------------------------------------
    print("3. Exporting records by layer...")

    for layer in Layer:
        export_path = export_dir / f"{layer.value}_records.parquet"
        count = await storage.export_to_parquet(export_path, layer=layer)

        if count > 0:
            file_size = export_path.stat().st_size
            size_kb = file_size / 1024
            print(f"  {layer.value.title()}: {count} records ({size_kb:.1f} KB)")

    print()

    # -------------------------------------------------------------------------
    # 4. Custom Query Export
    # -------------------------------------------------------------------------
    print("4. Exporting custom query results...")

    if hasattr(storage, "export_query_to_parquet"):
        # Export only records with index > 50
        custom_path = export_dir / "high_index_records.parquet"
        custom_sql = """
            SELECT id, natural_key, layer, content, published_at
            FROM records
            WHERE json_extract_string(content, '$.index') > '50'
        """

        try:
            count = await storage.export_query_to_parquet(custom_sql, custom_path)
            if custom_path.exists():
                size_kb = custom_path.stat().st_size / 1024
                print(f"  Custom query: {count} records ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"  Custom query export not available: {e}")

    print()

    # -------------------------------------------------------------------------
    # 5. Verify Exports
    # -------------------------------------------------------------------------
    print("5. Listing exported files...")

    parquet_files = list(export_dir.glob("*.parquet"))
    total_size = sum(f.stat().st_size for f in parquet_files)

    for f in sorted(parquet_files):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name}: {size_kb:.1f} KB")

    print(f"  Total: {len(parquet_files)} files, {total_size / 1024:.1f} KB")
    print()

    # -------------------------------------------------------------------------
    # 6. Clean Up
    # -------------------------------------------------------------------------
    print("6. Cleaning up...")

    await storage.close()

    # Remove demo database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"  Removed: {db_path}")

    # Remove parquet exports
    for f in export_dir.glob("*.parquet"):
        f.unlink()
        print(f"  Removed: {f.name}")

    if export_dir.exists():
        export_dir.rmdir()
        print(f"  Removed: {export_dir}/")

    print()
    print("=" * 60)
    print("Parquet export example complete!")
    print("=" * 60)
    print()
    print("In production, use these CLI commands:")
    print("  feedspine export parquet all_data.parquet")
    print("  feedspine export parquet bronze.parquet --layer bronze")
    print()
    print("Or via API:")
    print("  POST /api/v1/export/parquet?layer=bronze")
    print("  GET /api/v1/export/download/{export_id}")


if __name__ == "__main__":
    asyncio.run(main())
