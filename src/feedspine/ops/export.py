"""Export operations — JSON, JSONL, CSV, Parquet.

Extracted from :mod:`feedspine.ops.query` for single-responsibility.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`. They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Functions
---------
export_to_json
    Export records to a JSON file on disk.
export_to_jsonl
    Export records to a JSONL file on disk.
export_to_csv
    Export records to a CSV file on disk.
export_to_parquet
    Export records to a Parquet file via DuckDB.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pathlib

    from feedspine.ops import OperationContext, OperationResult


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


async def export_to_json(
    ctx: OperationContext,
    output_path: pathlib.Path,
    layer: str | None = None,
    limit: int = 0,
) -> OperationResult[dict[str, Any]]:
    """Export records to a JSON file.

    Args:
        ctx: Operation context with storage backend.
        output_path: Destination file path.
        layer: Optional layer filter.
        limit: Maximum records to export (0 = all, capped at 100k).

    Returns:
        OperationResult with data containing ``count`` and ``path``.
    """
    from feedspine.models.base import Layer as LayerEnum
    from feedspine.ops import OperationResult

    layer_filter = LayerEnum(layer) if layer else None
    query_limit = limit if limit > 0 else 100_000

    records = []
    async for record in ctx.storage.query(layer=layer_filter, limit=query_limit):
        records.append(record.model_dump(mode="json"))

    output_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    return OperationResult.ok({"count": len(records), "path": str(output_path)})


async def export_to_jsonl(
    ctx: OperationContext,
    output_path: pathlib.Path,
    layer: str | None = None,
    limit: int = 0,
) -> OperationResult[dict[str, Any]]:
    """Export records to a JSONL (newline-delimited JSON) file.

    Args:
        ctx: Operation context with storage backend.
        output_path: Destination file path.
        layer: Optional layer filter.
        limit: Maximum records to export (0 = all, capped at 100k).

    Returns:
        OperationResult with data containing ``count`` and ``path``.
    """
    from feedspine.models.base import Layer as LayerEnum
    from feedspine.ops import OperationResult

    layer_filter = LayerEnum(layer) if layer else None
    query_limit = limit if limit > 0 else 100_000

    records = []
    async for record in ctx.storage.query(layer=layer_filter, limit=query_limit):
        records.append(record.model_dump(mode="json"))

    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, default=str) + "\n")

    return OperationResult.ok({"count": len(records), "path": str(output_path)})


async def export_to_csv(
    ctx: OperationContext,
    output_path: pathlib.Path,
    layer: str | None = None,
    limit: int = 0,
) -> OperationResult[dict[str, Any]]:
    """Export records to a CSV file.

    Args:
        ctx: Operation context with storage backend.
        output_path: Destination file path.
        layer: Optional layer filter.
        limit: Maximum records to export (0 = all, capped at 100k).

    Returns:
        OperationResult with data containing ``count`` and ``path``.
    """
    import csv

    from feedspine.models.base import Layer as LayerEnum
    from feedspine.ops import OperationResult

    layer_filter = LayerEnum(layer) if layer else None
    query_limit = limit if limit > 0 else 100_000

    records = []
    async for record in ctx.storage.query(layer=layer_filter, limit=query_limit):
        records.append(record.model_dump(mode="json"))

    if not records:
        return OperationResult.ok({"count": 0, "path": str(output_path)})

    fieldnames = list(records[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    return OperationResult.ok({"count": len(records), "path": str(output_path)})


async def export_to_parquet(
    ctx: OperationContext,
    output_path: pathlib.Path,
    layer: str | None = None,
) -> OperationResult[dict[str, Any]]:
    """Export records to a Parquet file via DuckDB storage.

    The storage backend must support ``export_to_parquet``.

    Args:
        ctx: Operation context with DuckDB storage backend.
        output_path: Destination file path.
        layer: Optional layer filter.

    Returns:
        OperationResult with data containing ``count``, ``path``, and
        ``size_bytes``.
    """
    from feedspine.models.base import Layer as LayerEnum
    from feedspine.ops import OperationResult

    if not hasattr(ctx.storage, "export_to_parquet"):
        return OperationResult.fail(
            "Parquet export not available with this storage backend. Requires: feedspine[duckdb]"
        )

    layer_filter = LayerEnum(layer) if layer else None

    # Ensure .parquet extension
    if output_path.suffix.lower() != ".parquet":
        output_path = output_path.with_suffix(".parquet")

    count = await ctx.storage.export_to_parquet(output_path, layer=layer_filter)
    size_bytes = output_path.stat().st_size if output_path.exists() else 0

    return OperationResult.ok(
        {
            "count": count,
            "path": str(output_path),
            "size_bytes": size_bytes,
        }
    )
