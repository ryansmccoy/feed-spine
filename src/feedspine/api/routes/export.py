"""Export API routes for FeedSpine.

# Manifesto
Export capabilities are essential for data interoperability, enabling FeedSpine
to integrate with analytics tools, spreadsheet applications, and data pipelines.
Each format serves distinct use cases:
- Parquet: Columnar format for analytics and data warehouses (DuckDB native)
- CSV: Universal spreadsheet compatibility with minimal dependencies
- JSONL: Line-delimited JSON for streaming and log-style processing

# Architecture
Export flow follows a two-step pattern:
1. POST /export/{format} creates temporary file, returns metadata + download URL
2. GET /download/{export_id} streams the file to client

This decouples export generation from download, enabling:
- Progress tracking for large exports
- Resume capability
- Async export processing (future: background tasks)

Temp files stored in system temp dir with UUID-based naming to prevent
collisions. Files managed in app.state.exports registry for download lookup.
Entries expire after ``_EXPORT_TTL_SECONDS`` and the registry is capped at
``_MAX_EXPORTS`` to prevent unbounded memory growth.

# Features
- F8.1: Parquet Export (DuckDB native, requires duckdb backend)
- F8.2: CSV Export (universal compatibility, works with all backends)
- F8.3: JSONL Export (streaming-friendly, works with all backends)
- Layer filtering (bronze/silver/gold) on all formats
- Status endpoint reports backend capabilities

# Guardrails
- Validate layer enum before querying to prevent SQL injection
- Use temp files with UUIDs to prevent path traversal
- Check backend capabilities before attempting format-specific exports
- Return 501 Not Implemented for unsupported format/backend combinations
- Clean up temp files (TODO: implement TTL-based cleanup in production)

# Tags
doc-types: api-routes, data-export, file-handling
patterns: two-phase-export, temp-file-management
security: input-validation, path-safety
"""

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from spine.core.logging import get_logger

from feedspine.api.models import ExportStatusResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/export", tags=["export"])

_EXPORT_TTL_SECONDS = 3600  # 1 hour
_MAX_EXPORTS = 1000


# =============================================================================
# Export Registry — replaces ad-hoc request.app.state.exports dict
# =============================================================================


class ExportRegistry:
    """Thread-safe registry of pending export downloads.

    Stores metadata for the two-phase export pattern (POST creates file,
    GET downloads it).  Instantiate once at app startup and store on
    ``app.state.export_registry``.

    Entries are evicted after ``_EXPORT_TTL_SECONDS`` and the registry
    is capped at ``_MAX_EXPORTS`` to prevent unbounded memory growth.
    """

    def __init__(self) -> None:
        self._exports: dict[str, dict[str, Any]] = {}

    def register(self, export_id: str, *, path: str, filename: str, count: int) -> None:
        """Register an export for later download."""
        self._evict_expired()
        # Cap registry size — evict oldest first
        if len(self._exports) >= _MAX_EXPORTS:
            oldest = sorted(
                self._exports,
                key=lambda k: self._exports[k].get("created_at", datetime.min),
            )
            for eid in oldest[: len(self._exports) - _MAX_EXPORTS + 1]:
                self._exports.pop(eid, None)
        self._exports[export_id] = {
            "path": path,
            "filename": filename,
            "count": count,
            "created_at": datetime.now(UTC),
        }

    def get(self, export_id: str) -> dict[str, Any] | None:
        """Retrieve export metadata, or *None* if not found."""
        return self._exports.get(export_id)

    def pop(self, export_id: str) -> dict[str, Any] | None:
        """Retrieve and remove export metadata (cleanup on download)."""
        return self._exports.pop(export_id, None)

    def _evict_expired(self) -> None:
        """Remove entries older than TTL."""
        now = datetime.now(UTC)
        expired = [
            eid
            for eid, meta in self._exports.items()
            if (now - meta.get("created_at", now)).total_seconds() > _EXPORT_TTL_SECONDS
        ]
        for eid in expired:
            self._exports.pop(eid, None)


def _get_export_registry(request: Request) -> ExportRegistry:
    """Get the ExportRegistry from app state, or raise 503."""
    registry = getattr(request.app.state, "export_registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="Export registry not configured")
    return registry


# =============================================================================
# Models
# =============================================================================


class ExportResult(BaseModel):
    """Export operation result.

    Returned by all export endpoints after successful export generation.
    Contains metadata about the export and download URL for file retrieval.
    """

    format: str = Field(description="Export format (parquet, csv, jsonl)")
    record_count: int = Field(description="Number of records exported")
    file_path: str | None = Field(description="Path to exported file (if applicable)")
    download_url: str | None = Field(description="URL to download file via GET /download/{export_id}")


class ExportRequest(BaseModel):
    """Export request parameters."""

    layer: str | None = Field(None, description="Filter by layer (bronze, silver, gold)")
    format: str = Field("parquet", description="Export format")


# =============================================================================
# Shared export helpers
# =============================================================================


def _parse_layer_filter(layer: str | None):
    """Parse and validate optional layer filter string."""
    from feedspine.models.base import Layer

    if layer is None:
        return None
    try:
        return Layer(layer.lower())
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid layer '{layer}'. Must be one of: bronze, silver, gold",
        ) from None


def _prepare_export_path(fmt: str, layer: str | None) -> tuple[str, str, Path]:
    """Create temp directory and return (export_id, filename, export_path)."""
    temp_dir = Path(tempfile.gettempdir()) / "feedspine_exports"
    temp_dir.mkdir(exist_ok=True)

    export_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    layer_suffix = f"_{layer}" if layer else ""
    filename = f"feedspine_export_{timestamp}{layer_suffix}_{export_id}.{fmt}"
    export_path = temp_dir / filename
    return export_id, filename, export_path


def _finalize_export(
    request: Request,
    *,
    fmt: str,
    export_id: str,
    filename: str,
    export_path: Path,
    count: int,
) -> ExportResult:
    """Register export in registry and return ExportResult."""
    if count == 0:
        return ExportResult(
            format=fmt,
            record_count=0,
            file_path=None,
            download_url=None,
        )

    registry = _get_export_registry(request)
    registry.register(export_id, path=str(export_path), filename=filename, count=count)

    return ExportResult(
        format=fmt,
        record_count=count,
        file_path=str(export_path),
        download_url=f"/api/v1/export/download/{export_id}",
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/parquet", response_model=ExportResult)
async def export_to_parquet(
    request: Request,
    layer: str | None = Query(None, description="Filter by layer (bronze, silver, gold)"),
) -> ExportResult:
    """Export records to Parquet format.

    # Purpose
    Generate Apache Parquet columnar file for analytics and data warehouse integration.
    Uses DuckDB's native export for maximum efficiency.

    # Parameters
    - layer: Optional filter (bronze/silver/gold). If omitted, exports all layers.

    # Returns
    ExportResult with download_url pointing to GET /download/{export_id}

    # Examples
    ```bash
    curl -X POST "http://localhost:8000/api/v1/export/parquet?layer=bronze"
    # => {"format": "parquet", "record_count": 1523, "download_url": "/api/v1/export/download/a3f5b2c1"}

    curl -O "http://localhost:8000/api/v1/export/download/a3f5b2c1"
    # Downloads feedspine_export_20260216_143022_bronze_a3f5b2c1.parquet
    ```

    # Constraints
    Requires DuckDB storage backend. Returns 501 if backend doesn't support parquet export.
    """
    storage = request.app.state.storage

    # Check if storage supports parquet export
    if not hasattr(storage, "export_to_parquet"):
        raise HTTPException(
            status_code=501,
            detail="Parquet export not available. Requires DuckDB storage backend.",
        )

    layer_filter = _parse_layer_filter(layer)
    export_id, filename, export_path = _prepare_export_path("parquet", layer)

    try:
        count = await storage.export_to_parquet(export_path, layer=layer_filter)
    except Exception as e:
        logger.exception("Parquet export failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

    return _finalize_export(
        request,
        fmt="parquet",
        export_id=export_id,
        filename=filename,
        export_path=export_path,
        count=count,
    )


@router.post("/csv", response_model=ExportResult)
async def export_to_csv(
    request: Request,
    layer: str | None = Query(None, description="Filter by layer (bronze, silver, gold)"),
    limit: int = Query(100_000, description="Max records to export (prevents runaway exports)"),
) -> ExportResult:
    """Export records to CSV format.

    Uses ops/export for record querying and file writing.
    """
    _parse_layer_filter(layer)  # validate early
    export_id, filename, export_path = _prepare_export_path("csv", layer)

    try:
        from feedspine.ops import OperationContext
        from feedspine.ops.export import export_to_csv as ops_csv

        ctx = OperationContext(storage=request.app.state.storage, caller="api")
        result = await ops_csv(ctx, output_path=export_path, layer=layer, limit=limit)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "CSV export failed")

        count = result.data.get("count", 0) if result.data else 0

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("CSV export failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

    return _finalize_export(
        request,
        fmt="csv",
        export_id=export_id,
        filename=filename,
        export_path=export_path,
        count=count,
    )


@router.post("/jsonl", response_model=ExportResult)
async def export_to_jsonl(
    request: Request,
    layer: str | None = Query(None, description="Filter by layer (bronze, silver, gold)"),
    limit: int = Query(100_000, description="Max records to export"),
) -> ExportResult:
    """Export records to JSONL (newline-delimited JSON) format.

    Uses ops/export for record querying and file writing.
    """
    _parse_layer_filter(layer)  # validate early
    export_id, filename, export_path = _prepare_export_path("jsonl", layer)

    try:
        from feedspine.ops import OperationContext
        from feedspine.ops.export import export_to_jsonl as ops_jsonl

        ctx = OperationContext(storage=request.app.state.storage, caller="api")
        result = await ops_jsonl(ctx, output_path=export_path, layer=layer, limit=limit)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "JSONL export failed")

        count = result.data.get("count", 0) if result.data else 0

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("JSONL export failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

    return _finalize_export(
        request,
        fmt="jsonl",
        export_id=export_id,
        filename=filename,
        export_path=export_path,
        count=count,
    )


@router.get("/download/{export_id}")
async def download_export(
    request: Request,
    export_id: str,
) -> FileResponse:
    """Download a previously exported file.

    # Purpose
    Retrieve the actual file after export generation. Second step of two-phase
    export pattern. Uses streaming file response for efficient large file transfers.

    # Parameters
    - export_id: 8-character UUID fragment returned in ExportResult.download_url

    # Returns
    FileResponse with appropriate Content-Type and Content-Disposition headers

    # Examples
    ```bash
    # After export creates id "a3f5b2c1"
    curl -O http://localhost:8000/api/v1/export/download/a3f5b2c1

    # Or use wget
    wget http://localhost:8000/api/v1/export/download/a3f5b2c1
    ```

    # Error Cases
    - 404 Not Found: export_id doesn't exist or expired
    - 404 Not Found: export file was deleted from temp directory

    # Future Improvements
    - Add TTL-based cleanup of old exports (current: manual cleanup)
    - Add download progress tracking via Server-Sent Events
    - Add byte-range support for resume capability
    """
    registry = _get_export_registry(request)
    export_info = registry.pop(export_id)

    if not export_info:
        raise HTTPException(status_code=404, detail="Export not found or expired")

    path = Path(export_info["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file no longer available")

    return FileResponse(
        path=path,
        filename=export_info["filename"],
        media_type="application/octet-stream",
    )


@router.get("/status", response_model=ExportStatusResponse)
async def export_status(request: Request) -> dict[str, Any]:
    """Get export capabilities for current storage backend.

    # Purpose
    Introspection endpoint reporting which export formats are available based
    on the configured storage backend and installed optional dependencies.

    # Returns
    Dictionary with:
    - backend: Storage class name (e.g., "DuckDBStorage", "PostgresStorage")
    - formats: Dict mapping format name to {available: bool, description: str}

    # Examples
    ```bash
    # Check capabilities
    curl http://localhost:8000/api/v1/export/status

    # Example response with DuckDB
    {
      "backend": "DuckDBStorage",
      "formats": {
        "parquet": {"available": true, "description": "Apache Parquet columnar format"},
        "csv": {"available": true, "description": "Universal spreadsheet compatibility"},
        "jsonl": {"available": true, "description": "Streaming-friendly line-delimited JSON"}
      }
    }

    # Example response with SQLite (no parquet support)
    {
      "backend": "SQLiteStorage",
      "formats": {
        "parquet": {"available": false, "description": "Requires DuckDB backend"},
        "csv": {"available": true, "description": "Universal spreadsheet compatibility"},
        "jsonl": {"available": true, "description": "Streaming-friendly line-delimited JSON"}
      }
    }
    ```

    # Use Case
    Client-side can call this before attempting export to show/hide format
    options in UI, or to display installation instructions for missing backends.
    """
    storage = request.app.state.storage

    supports_parquet = hasattr(storage, "export_to_parquet")

    return {
        "backend": type(storage).__name__,
        "formats": {
            "parquet": {
                "available": supports_parquet,
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
