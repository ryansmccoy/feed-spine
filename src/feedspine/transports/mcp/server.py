"""Modern MCP server for feedspine — WorkItem-based.

Exposes feed collection, enrichment, and run-status tools
backed by spine-core WorkItems.

Entry points:
    feedspine-mcp                              # stdio
    feedspine-mcp --transport http --port 11310  # HTTP

Configuration:
    FEEDSPINE_MCP_DB: Path to spine-core SQLite database (default: spine.db)
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from feedspine._vendor.logging import get_logger
from spine_mcp import (
    Context,
    ErrorCode,
    FastMCP,
    ToolError,
    create_spine_mcp,
    run_spine_mcp,
    safe_tool,
    to_json,
)

logger = get_logger("feedspine.mcp")

_DEFAULT_DB = os.environ.get("FEEDSPINE_MCP_DB", "spine.db")


def _get_store(db_path: str | None = None):
    """Open a SqliteWorkItemStore for use by tool handlers.

    Args:
        db_path: Path to SQLite database. If None, uses FEEDSPINE_MCP_DB env
            var or defaults to 'spine.db'.

    Returns:
        Tuple of (SqliteWorkItemStore, sqlite3.Connection).
    """
    from spine.data.stores.sqlite.work_item_store import SqliteWorkItemStore

    path = db_path or _DEFAULT_DB
    logger.debug("opening_work_item_store", db_path=path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with conn:
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
        finally:
            cur.close()
    return SqliteWorkItemStore(conn), conn


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    from feedspine.ops import OperationContext
    from feedspine.storage import MemoryStorage

    logger.info("feedspine MCP starting")
    storage = MemoryStorage()
    opctx = OperationContext(storage=storage, caller="mcp")
    yield {"opctx": opctx}
    logger.info("feedspine MCP shutting down")


mcp = create_spine_mcp(
    name="feedspine",
    instructions=(
        "FeedSpine: storage-agnostic feed collection framework with "
        "medallion architecture, deduplication, and WorkItem-based scheduling."
    ),
    lifespan=app_lifespan,
)


def _get_opctx(ctx: Context) -> Any:
    """Get shared OperationContext from MCP lifespan, with fallback.

    Falls back to creating a fresh context if lifespan data is unavailable
    (e.g., during testing or when run outside the MCP server).
    """
    from feedspine.ops import OperationContext
    from feedspine.storage import MemoryStorage

    # Try to get from lifespan context (must be a real dict, not a MagicMock)
    try:
        lifespan_ctx = ctx.request_context.lifespan_context
        if isinstance(lifespan_ctx, dict) and "opctx" in lifespan_ctx:
            return lifespan_ctx["opctx"]
    except (AttributeError, TypeError):
        pass

    # Fallback: create fresh context
    return OperationContext(storage=MemoryStorage(), caller="mcp")


# ═══════════════════════════════════════════════════════════════════════════
# Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def health_check(ctx: Context) -> str:
    """Check feedspine health and report available components."""
    components: dict[str, Any] = {"status": "healthy", "server": "feedspine"}
    try:
        from feedspine.workflows.collect import FeedCollectionRuntime  # noqa: F401

        components["collection_runtime"] = True
    except ImportError:
        components["collection_runtime"] = False
    try:
        from feedspine.enricher.worker import FeedEnrichmentWorker  # noqa: F401

        components["enrichment_worker"] = True
    except ImportError:
        components["enrichment_worker"] = False
    return to_json(components)


@mcp.tool()
@safe_tool
async def feed_collect(
    ctx: Context,
    feed_name: str,
    db_path: str = _DEFAULT_DB,
) -> str:
    """Create a WorkItem to collect from the named feed.

    The spine-core execution engine picks it up asynchronously.

    Args:
        feed_name: Name of the feed to collect.
        db_path: Path to spine-core SQLite database.
    """
    from feedspine.ops import OperationContext
    from feedspine.ops.collection import submit_collection

    store, conn = _get_store(db_path)
    try:
        op_ctx = OperationContext(storage=None, work_item_store=store, caller="mcp")
        result = await submit_collection(op_ctx, feed_names=[feed_name])

        if not result.success:
            return to_json({"error": result.error})

        item = result.data[0] if result.data else {}
        return to_json(
            {
                "work_item_id": item.get("work_item_id"),
                "status": "QUEUED",
                "feed_name": feed_name,
            }
        )
    finally:
        conn.close()


@mcp.tool()
@safe_tool
async def feed_enrich(
    ctx: Context,
    enricher: str,
    record_ids: list[str],
    source_layer: str = "BRONZE",
    target_layer: str = "SILVER",
    db_path: str = _DEFAULT_DB,
) -> str:
    """Create enrichment WorkItems for the given records.

    One WorkItem per record with ``workflow="feed.enrich"``.

    Args:
        enricher: Enricher to use (passthrough, metadata, entity).
        record_ids: Record IDs to enrich.
        source_layer: Layer records are currently at.
        target_layer: Layer records should be promoted to.
        db_path: Path to spine-core SQLite database.
    """
    from feedspine.ops import OperationContext
    from feedspine.ops.enrich import submit_enrichment_batch

    store, conn = _get_store(db_path)
    try:
        op_ctx = OperationContext(storage=None, work_item_store=store, caller="mcp")
        result = await submit_enrichment_batch(
            op_ctx,
            enricher_name=enricher,
            record_ids=record_ids,
            source_layer=source_layer,
            target_layer=target_layer,
        )

        if not result.success:
            return to_json({"error": result.error})

        return to_json(
            {
                "batch_id": result.data.get("batch_id"),
                "work_items_created": result.data.get("count", 0),
            }
        )
    finally:
        conn.close()


@mcp.tool()
@safe_tool
async def feed_runs(
    ctx: Context,
    feed_name: str | None = None,
    limit: int = 50,
    db_path: str = _DEFAULT_DB,
) -> str:
    """List recent feed collection runs.

    Queries WorkItems with ``workflow="feed.collect"`` and returns
    FeedRunProjection summaries.

    Args:
        feed_name: Optional filter by feed name.
        limit: Maximum number of runs to return.
        db_path: Path to spine-core SQLite database.
    """
    from feedspine.ops import OperationContext
    from feedspine.ops.runs import query_feed_runs

    store, conn = _get_store(db_path)
    try:
        op_ctx = OperationContext(storage=None, work_item_store=store, caller="mcp")
        result = await query_feed_runs(op_ctx, feed_name=feed_name, limit=limit)

        if not result.success:
            return to_json({"error": result.error})

        return to_json(
            {
                "runs": [asdict(p) for p in (result.data or [])],
                "total": len(result.data or []),
            }
        )
    finally:
        conn.close()


@mcp.tool()
@safe_tool
async def feed_enrich_status(
    ctx: Context,
    batch_id: str,
    db_path: str = _DEFAULT_DB,
) -> str:
    """Get enrichment batch status.

    Args:
        batch_id: Enrichment batch ID.
        db_path: Path to spine-core SQLite database.
    """
    from feedspine.ops import OperationContext
    from feedspine.ops.enrich import get_batch_status

    store, conn = _get_store(db_path)
    try:
        op_ctx = OperationContext(storage=None, work_item_store=store, caller="mcp")
        result = await get_batch_status(op_ctx, batch_id=batch_id)

        if not result.success:
            raise ToolError(
                error=result.error or f"Batch not found: {batch_id}",
                code=ErrorCode.INTERNAL_ERROR,
            )

        return to_json(result.data)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Timeline & Analytics Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
@safe_tool
async def timeline_query(
    ctx: Context,
    limit: int = 50,
    layer: str | None = None,
    since: str | None = None,
    until: str | None = None,
    source: str | None = None,
    offset: int = 0,
) -> str:
    """Query records by time range for timeline view.

    Args:
        limit: Maximum number of records to return.
        layer: Filter by medallion layer (bronze, silver, gold).
        since: ISO datetime - return records after this time.
        until: ISO datetime - return records before this time.
        source: Filter by source/feed name.
        offset: Number of records to skip for pagination.
    """
    from datetime import datetime as dt

    from feedspine.ops.feed import fetch_timeline
    from feedspine.ops.feed_formats import timeline_item_to_dict

    since_dt = dt.fromisoformat(since) if since else None
    until_dt = dt.fromisoformat(until) if until else None

    opctx = _get_opctx(ctx)

    result = await fetch_timeline(
        ctx=opctx,
        limit=limit,
        layer=layer,
        since=since_dt,
        until=until_dt,
        source=source,
        offset=offset,
    )

    if not result.success:
        return to_json({"error": result.error, "items": [], "count": 0})

    items = [timeline_item_to_dict(i) for i in result.data.items]
    return to_json(
        {
            "items": items,
            "count": len(items),
            "total": result.data.total,
            "has_more": result.data.has_more,
            "filters": {"layer": layer, "since": since, "until": until, "source": source},
        }
    )


@mcp.tool()
@safe_tool
async def storage_stats(ctx: Context) -> str:
    """Get storage analytics: record counts by layer, date range, totals.

    Returns summary statistics about collected feed data.
    """
    from feedspine.ops.stats import fetch_layer_distribution, fetch_storage_summary

    opctx = _get_opctx(ctx)

    summary_result = await fetch_storage_summary(opctx)
    layers_result = await fetch_layer_distribution(opctx)

    if not summary_result.success:
        return to_json({"error": summary_result.error})

    summary = summary_result.data
    layers = layers_result.data if layers_result.success else {}

    return to_json(
        {
            "total_records": summary.get("records", {}).get("total", 0),
            "by_layer": layers.get("by_layer", {}),
            "storage_type": layers.get("storage_type", "unknown"),
            "summary": summary,
        }
    )


@mcp.tool()
@safe_tool
async def feed_health(
    ctx: Context,
    feed_name: str | None = None,
    days: int = 7,
) -> str:
    """Get health status for feeds.

    Args:
        feed_name: Optional specific feed to check. If None, returns all feeds.
        days: Number of days to analyze for health calculation.
    """
    from feedspine.ops.health import fetch_all_feed_health, fetch_feed_health

    opctx = _get_opctx(ctx)

    if feed_name:
        result = await fetch_feed_health(opctx, feed_name, days=days)
        if not result.success:
            return to_json({"feed": feed_name, "error": result.error})
        return to_json({"feed": feed_name, "health": result.data})
    else:
        result = await fetch_all_feed_health(opctx, days=days)
        if not result.success:
            return to_json({"error": result.error, "feeds": []})
        return to_json(result.data)


@mcp.tool()
@safe_tool
async def list_feeds(ctx: Context, config_path: str = "") -> str:
    """List all registered feed adapters from config.

    Args:
        config_path: Optional path to feeds.yaml config file.
    """
    try:
        from pathlib import Path

        from feedspine.core.feed_config import (
            create_adapters_from_config,
            find_config_file,
            load_config,
        )

        path = Path(config_path) if config_path else find_config_file()
        if path is None:
            return to_json({"feeds": [], "total": 0, "note": "No feeds.yaml found"})

        config = load_config(path)
        adapters = create_adapters_from_config(config)
        feeds = [{"name": a.name, "type": type(a).__name__} for a in adapters]
        return to_json({"feeds": feeds, "total": len(feeds)})
    except Exception as exc:
        return to_json({"feeds": [], "total": 0, "error": str(exc)})


@mcp.tool()
@safe_tool
async def search_records(
    ctx: Context,
    query: str,
    limit: int = 20,
) -> str:
    """Search collected records using full-text search.

    Args:
        query: Search query string.
        limit: Maximum number of results (default 20).
    """
    from feedspine.ops.query import execute_search

    opctx = _get_opctx(ctx)

    result = await execute_search(opctx, query=query, search_type="keyword", limit=limit)

    if not result.success:
        return to_json(
            {
                "query": query,
                "results": [],
                "count": 0,
                "status": result.error or "search_unavailable",
            }
        )

    return to_json(
        {
            "query": query,
            "results": result.data.get("results", []),
            "count": result.data.get("total_count", 0),
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# Record & Export Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
@safe_tool
async def fetch_records_tool(
    ctx: Context,
    layer: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """Fetch stored records with optional layer filtering and pagination.

    Args:
        layer: Filter by medallion layer (bronze, silver, gold).
        limit: Maximum records to return.
        offset: Number of records to skip for pagination.
    """
    from feedspine.ops.query import fetch_records

    opctx = _get_opctx(ctx)

    result = await fetch_records(opctx, layer=layer, limit=limit, offset=offset)
    if not result.success:
        return to_json({"error": result.error, "records": []})

    return to_json(
        {
            "records": result.data,
            "count": len(result.data),
            "offset": offset,
        }
    )


@mcp.tool()
@safe_tool
async def record_history(
    ctx: Context,
    natural_key: str,
    limit: int = 20,
) -> str:
    """Get version history for a record by its natural key.

    Args:
        natural_key: The natural key identifying the record.
        limit: Maximum number of versions to return.
    """
    from feedspine.ops.query import fetch_record_history

    opctx = _get_opctx(ctx)

    result = await fetch_record_history(opctx, natural_key=natural_key, limit=limit)
    if not result.success:
        return to_json({"error": result.error, "versions": []})

    return to_json(
        {
            "natural_key": natural_key,
            "versions": result.data,
            "count": len(result.data),
        }
    )


@mcp.tool()
@safe_tool
async def export_data(
    ctx: Context,
    format: str = "json",
    output_path: str = "",
    layer: str | None = None,
    limit: int = 0,
) -> str:
    """Export records to JSON or CSV file.

    Args:
        format: Export format — 'json' or 'csv'.
        output_path: Destination file path. Auto-generated if empty.
        layer: Optional layer filter (bronze, silver, gold).
        limit: Maximum records to export (0 = all, capped at 100k).
    """
    import tempfile
    from pathlib import Path

    from feedspine.ops.export import export_to_csv, export_to_json

    opctx = _get_opctx(ctx)

    fmt = format.lower()
    if fmt not in ("json", "csv"):
        return to_json({"error": f"Unsupported format: {format}. Use 'json' or 'csv'."})

    if output_path:
        path = Path(output_path)
    else:
        suffix = ".json" if fmt == "json" else ".csv"
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            prefix="feedspine_export_",
            delete=False,
        ) as tmp:
            path = Path(tmp.name)

    if fmt == "json":
        result = await export_to_json(opctx, output_path=path, layer=layer, limit=limit)
    else:
        result = await export_to_csv(opctx, output_path=path, layer=layer, limit=limit)

    if not result.success:
        return to_json({"error": result.error})

    return to_json(result.data)


# ═══════════════════════════════════════════════════════════════════════════
# Entry points
# ═══════════════════════════════════════════════════════════════════════════


def create_server() -> FastMCP:
    return mcp


def run() -> None:
    run_spine_mcp(mcp, default_port=11310)


if __name__ == "__main__":
    run()
