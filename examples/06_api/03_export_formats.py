#!/usr/bin/env python3
"""
FeedSpine Export Formats Example
================================

# Manifesto
Export is fundamental to data portability. FeedSpine's two-phase export pattern
(create → download) supports async processing, progress tracking, and resume
capability for large datasets.

# What You'll Learn
1. Two-phase export pattern (POST to create, GET to download)
2. Three output formats: Parquet (analytics), CSV (spreadsheets), JSONL (streaming)
3. Layer filtering (bronze/silver/gold)
4. Backend capability detection via /status endpoint
5. Real httpx client usage vs demo mode

# API Endpoints
- POST /api/v1/export/parquet - DuckDB native columnar export
- POST /api/v1/export/csv - Universal spreadsheet format
- POST /api/v1/export/jsonl - Line-delimited JSON for streaming
- GET /api/v1/export/download/{export_id} - Download generated file
- GET /api/v1/export/status - Check backend capabilities

# CLI Equivalents
- feedspine export json output.json --layer bronze
- feedspine export csv output.csv --limit 1000
- feedspine export parquet output.parquet

# Usage
python examples/06_api/03_export_formats.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Check if API is available
DEMO_MODE = True
API_BASE = "http://localhost:8000"
try:
    import httpx

    response = httpx.get(f"{API_BASE}/health/live", timeout=2.0)
    if response.status_code == 200:
        DEMO_MODE = False
except Exception:
    pass


def check_export_capabilities() -> dict[str, Any]:
    """Check which export formats are available (live API) or show demo response."""
    if not DEMO_MODE:
        try:
            import httpx

            response = httpx.get(f"{API_BASE}/api/v1/export/status", timeout=5.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            pass

    # Demo response for when API is offline
    return {
        "backend": "DuckDBStorage",
        "formats": {
            "parquet": {
                "available": True,
                "description": "Apache Parquet columnar format for analytics (DuckDB only)",
            },
            "csv": {
                "available": True,
                "description": "Universal spreadsheet compatibility (all backends)",
            },
            "jsonl": {
                "available": True,
                "description": "Streaming-friendly line-delimited JSON (all backends)",
            },
        },
    }


def export_parquet_demo() -> dict[str, Any]:
    """Demonstrate Parquet export (two-phase: create + download)."""
    if not DEMO_MODE:
        try:
            import httpx

            # Phase 1: Create export
            response = httpx.post(
                f"{API_BASE}/api/v1/export/parquet",
                params={"layer": "bronze"},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            # Phase 2: Download file (if records exist)
            if result.get("download_url"):
                download_response = httpx.get(
                    f"{API_BASE}{result['download_url']}",
                    timeout=60.0,
                )
                download_response.raise_for_status()

                # Save to temp file to show size
                temp_path = Path("/tmp/feedspine_demo.parquet")
                temp_path.write_bytes(download_response.content)
                result["downloaded_size_bytes"] = len(download_response.content)
                result["saved_to"] = str(temp_path)

            return result
        except Exception as e:
            return {"error": str(e), "mode": "live"}

    # Demo response
    return {
        "format": "parquet",
        "record_count": 1523,
        "file_path": "/tmp/feedspine_exports/feedspine_export_20260216_143022_bronze_a3f5b2c1.parquet",
        "download_url": "/api/v1/export/download/a3f5b2c1",
        "mode": "demo",
    }


def export_csv_demo() -> dict[str, Any]:
    """Demonstrate CSV export."""
    if not DEMO_MODE:
        try:
            import httpx

            response = httpx.post(
                f"{API_BASE}/api/v1/export/csv",
                params={"limit": 100},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("download_url"):
                download_response = httpx.get(
                    f"{API_BASE}{result['download_url']}",
                    timeout=60.0,
                )
                download_response.raise_for_status()

                # Preview first 3 lines
                lines = download_response.text.split("\n")[:3]
                result["preview"] = lines
                result["downloaded_size_bytes"] = len(download_response.content)

            return result
        except Exception as e:
            return {"error": str(e), "mode": "live"}

    # Demo response
    return {
        "format": "csv",
        "record_count": 100,
        "file_path": "/tmp/feedspine_exports/feedspine_export_20260216_143155_csv_b7d3e4a2.csv",
        "download_url": "/api/v1/export/download/b7d3e4a2",
        "preview": [
            "id,entity_id,feed_name,observed_at,layer,metadata",
            "rec-001,ent-AAPL,sec-filings,2026-02-15T10:30:00Z,bronze,{...}",
            "rec-002,ent-MSFT,sec-filings,2026-02-15T11:45:00Z,bronze,{...}",
        ],
        "mode": "demo",
    }


def export_jsonl_demo() -> dict[str, Any]:
    """Demonstrate JSONL export."""
    if not DEMO_MODE:
        try:
            import httpx

            response = httpx.post(
                f"{API_BASE}/api/v1/export/jsonl",
                params={"layer": "gold", "limit": 50},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("download_url"):
                download_response = httpx.get(
                    f"{API_BASE}{result['download_url']}",
                    timeout=60.0,
                )
                download_response.raise_for_status()

                # Parse first 2 lines as JSONL
                lines = download_response.text.strip().split("\n")[:2]
                result["preview"] = [json.loads(line) for line in lines if line]
                result["downloaded_size_bytes"] = len(download_response.content)

            return result
        except Exception as e:
            return {"error": str(e), "mode": "live"}

    # Demo response
    return {
        "format": "jsonl",
        "record_count": 50,
        "file_path": "/tmp/feedspine_exports/feedspine_export_20260216_143302_gold_c9e2f1b3.jsonl",
        "download_url": "/api/v1/export/download/c9e2f1b3",
        "preview": [
            {
                "id": "rec-001",
                "entity_id": "ent-AAPL",
                "feed_name": "sec-filings",
                "observed_at": "2026-02-15T10:30:00Z",
                "layer": "gold",
            },
            {
                "id": "rec-002",
                "entity_id": "ent-MSFT",
                "feed_name": "sec-filings",
                "observed_at": "2026-02-15T11:45:00Z",
                "layer": "gold",
            },
        ],
        "mode": "demo",
    }


def main() -> None:
    """Demonstrate Export API two-phase pattern and format capabilities."""
    print("=" * 70)
    print("  FeedSpine Export API Demo")
    print("=" * 70)
    print()

    mode_label = "🔴 DEMO MODE" if DEMO_MODE else "🟢 LIVE API"
    print(f"   {mode_label}")
    if DEMO_MODE:
        print("   Run `feedspine api start` for live API interaction")
    print()

    # =========================================================================
    # 1. Check Export Capabilities
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  1. CHECK EXPORT CAPABILITIES" + " " * 38 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    capabilities = check_export_capabilities()
    print(f"   Backend: {capabilities['backend']}")
    print()
    print("   Available Formats:")
    for fmt, info in capabilities["formats"].items():
        status = "✅" if info["available"] else "❌"
        print(f"   {status} {fmt:8} - {info['description']}")
    print()

    # =========================================================================
    # 2. Parquet Export (Two-Phase Pattern)
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  2. PARQUET EXPORT" + " " * 49 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   API Request (Phase 1 - Create Export):")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  POST /api/v1/export/parquet?layer=bronze                 │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    parquet_result = export_parquet_demo()
    if "error" not in parquet_result:
        print("   Response:")
        print(f"   • Format:       {parquet_result['format']}")
        print(f"   • Records:      {parquet_result['record_count']:,}")
        if parquet_result.get("download_url"):
            print(f"   • Download URL: {parquet_result['download_url']}")
            print()
            print("   Phase 2 - Download File:")
            print("   ┌────────────────────────────────────────────────────────────┐")
            print(f"   │  GET {parquet_result['download_url']:<52} │")
            print("   └────────────────────────────────────────────────────────────┘")
            if parquet_result.get("downloaded_size_bytes"):
                size_kb = parquet_result["downloaded_size_bytes"] / 1024
                print(f"   • Downloaded:   {size_kb:.1f} KB")
        print()
    else:
        print(f"   ❌ Error: {parquet_result['error']}")
        print()

    # =========================================================================
    # 3. CSV Export
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  3. CSV EXPORT (with limit)" + " " * 40 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   API Request:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  POST /api/v1/export/csv?limit=100                        │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    csv_result = export_csv_demo()
    if "error" not in csv_result:
        print("   Response:")
        print(f"   • Format:       {csv_result['format']}")
        print(f"   • Records:      {csv_result['record_count']:,}")
        if csv_result.get("download_url"):
            print(f"   • Download URL: {csv_result['download_url']}")
        print()
        if csv_result.get("preview"):
            print("   CSV Preview (first 3 lines):")
            print("   ┌────────────────────────────────────────────────────────────┐")
            for line in csv_result["preview"]:
                display = line[:58] + ".." if len(line) > 60 else line
                print(f"   │  {display:<60}│")
            print("   └────────────────────────────────────────────────────────────┘")
        print()
    else:
        print(f"   ❌ Error: {csv_result['error']}")
        print()

    # =========================================================================
    # 4. JSONL Export
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  4. JSONL EXPORT (streaming format)" + " " * 32 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   API Request:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  POST /api/v1/export/jsonl?layer=gold&limit=50            │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    jsonl_result = export_jsonl_demo()
    if "error" not in jsonl_result:
        print("   Response:")
        print(f"   • Format:       {jsonl_result['format']}")
        print(f"   • Records:      {jsonl_result['record_count']:,}")
        if jsonl_result.get("download_url"):
            print(f"   • Download URL: {jsonl_result['download_url']}")
        print()
        if jsonl_result.get("preview"):
            print("   JSONL Preview (first 2 records):")
            for i, record in enumerate(jsonl_result["preview"], 1):
                print(f"   {i}. {json.dumps(record, indent=None)}")
        print()
    else:
        print(f"   ❌ Error: {jsonl_result['error']}")
        print()

    # =========================================================================
    # 5. Python Client Examples
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  5. PYTHON CLIENT CODE" + " " * 44 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("""   import httpx
   from pathlib import Path

   # Parquet export (two-phase pattern)
   response = httpx.post(
       "http://localhost:8000/api/v1/export/parquet",
       params={"layer": "bronze"}
   )
   result = response.json()

   if result["download_url"]:
       # Download the file
       file_response = httpx.get(
           f"http://localhost:8000{result['download_url']}"
       )
       Path("export.parquet").write_bytes(file_response.content)
       print(f"Exported {result['record_count']} records")

   # CSV export with limit
   response = httpx.post(
       "http://localhost:8000/api/v1/export/csv",
       params={"limit": 1000}
   )
   result = response.json()

   # JSONL export and process line-by-line
   response = httpx.post(
       "http://localhost:8000/api/v1/export/jsonl",
       params={"layer": "gold"}
   )
   result = response.json()

   if result["download_url"]:
       file_response = httpx.get(
           f"http://localhost:8000{result['download_url']}"
       )
       for line in file_response.text.strip().split("\\n"):
           record = json.loads(line)
           # Process each record...
""")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 70)
    print("  ✅ Export API Demo Complete")
    print("=" * 70)
    print()
    print("   Two-Phase Export Pattern:")
    print("   1. POST /export/{format} → Returns metadata + download_url")
    print("   2. GET /download/{export_id} → Streams the file")
    print()
    print("   Supported Formats:")
    print("   • Parquet  - DuckDB native, columnar, compressed")
    print("   • CSV      - Universal spreadsheets, all backends")
    print("   • JSONL    - Streaming pipelines, all backends")
    print()
    print("   CLI Equivalents:")
    print("   • feedspine export json output.json --layer bronze")
    print("   • feedspine export csv output.csv --limit 1000")
    print("   • feedspine export parquet output.parquet")
    print()


if __name__ == "__main__":
    main()
