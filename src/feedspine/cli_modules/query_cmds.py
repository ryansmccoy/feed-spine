"""Query and search CLI commands.

Thin CLI wrappers that delegate to :mod:`feedspine.ops.query` for
business logic and handle only argument parsing and output formatting.

Export commands have been extracted to :mod:`feedspine.cli_modules.export_cmds`.
"""

from __future__ import annotations

from typing import Annotated

import typer

from feedspine.cli_modules.formatters import (
    format_history_table,
    format_records_table,
    format_search_table,
    format_sightings_table,
    format_timeline_table,
    output_json,
    output_jsonl,
)
from feedspine.cli_modules.shared import async_command, console, get_storage
from feedspine.ops import OperationContext

query_app = typer.Typer(name="query", help="Query stored records", no_args_is_help=True)


def _get_search_backend(backend: str | None, es_hosts: str | None) -> object:
    """Create a search backend from CLI args.

    Args:
        backend: Backend type ("memory" or "elasticsearch"). Defaults to memory.
        es_hosts: Comma-separated Elasticsearch host URLs (required for elasticsearch backend).

    Returns:
        A SearchBackend instance.
    """
    backend = backend or "memory"

    if backend == "elasticsearch":
        if not es_hosts:
            console.print("[red]--es-hosts is required for elasticsearch backend[/red]")
            raise typer.Exit(1)
        try:
            from feedspine.search.elasticsearch import ElasticsearchSearch
        except ImportError:
            console.print("[red]Elasticsearch support not installed.[/red]\n  pip install feedspine[elasticsearch]")
            raise typer.Exit(1) from None
        hosts = [h.strip() for h in es_hosts.split(",")]
        return ElasticsearchSearch(hosts=hosts)

    # Default: memory
    from feedspine.search.memory import MemorySearch

    return MemorySearch()


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------


@query_app.command("search")
@async_command
async def search_records(
    query: Annotated[str, typer.Argument(help="Search query string")],
    search_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Search type: keyword, fulltext"),
    ] = "fulltext",
    backend: Annotated[
        str | None,
        typer.Option("--backend", "-b", help="Search backend: memory, elasticsearch"),
    ] = None,
    es_hosts: Annotated[
        str | None,
        typer.Option("--es-hosts", help="Elasticsearch hosts (comma-separated)"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max results to return"),
    ] = 10,
    offset: Annotated[
        int,
        typer.Option("--offset", help="Skip N results"),
    ] = 0,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table, json, jsonl"),
    ] = "table",
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type"),
    ] = None,
) -> None:
    """Full-text search across stored records.

    Uses a SearchBackend (memory or elasticsearch) to run full-text,
    keyword, or fulltext queries against indexed content.

    Examples:
        feedspine query search "quarterly earnings"
        feedspine query search "SEC filing" --type keyword --limit 20
        feedspine query search "10-K" --backend elasticsearch --es-hosts http://localhost:9200
        feedspine query search "revenue growth" --output json
    """
    from feedspine.ops.query import execute_search

    search_backend = _get_search_backend(backend, es_hosts)
    storage = get_storage(connection, storage_type)
    ctx = OperationContext(storage=storage, search=search_backend, caller="cli")

    await storage.initialize()
    await search_backend.initialize()  # type: ignore[union-attr]

    try:
        result = await execute_search(ctx, query, search_type, limit, offset)

        if not result.success:
            console.print(f"[red]{result.error}[/red]")
            raise typer.Exit(1)

        data = result.data
        if output == "json":
            output_json(data, console)
        elif output == "jsonl":
            output_jsonl(data["results"])
        else:
            format_search_table(data, query, search_type, console)
    finally:
        await search_backend.close()  # type: ignore[union-attr]
        await storage.close()


@query_app.command("records")
@async_command
async def query_records(
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Filter by layer: bronze, silver, gold"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max records to return"),
    ] = 20,
    offset: Annotated[
        int,
        typer.Option("--offset", help="Skip N records"),
    ] = 0,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table, json, jsonl"),
    ] = "table",
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type"),
    ] = None,
) -> None:
    """Query stored records with filtering and pagination.

    Examples:
        feedspine query records
        feedspine query records --layer bronze --limit 50
        feedspine query records --output json > records.json
        feedspine query records --output jsonl | jq '.natural_key'
    """
    from feedspine.ops.query import fetch_records

    storage = get_storage(connection, storage_type)
    ctx = OperationContext(storage=storage, caller="cli")
    await storage.initialize()

    try:
        result = await fetch_records(ctx, layer=layer, limit=limit, offset=offset)
        data = result.data

        if output == "json":
            output_json(data, console)
        elif output == "jsonl":
            output_jsonl(data)
        else:
            format_records_table(data, offset, console)
    finally:
        await storage.close()


# Re-export for backward compatibility (cli.py imports export_app from here)
from feedspine.cli_modules.export_cmds import export_app  # noqa: E402, F401


@query_app.command("history")
@async_command
async def record_history(
    natural_key: Annotated[
        str,
        typer.Argument(help="Natural key of the record to get history for"),
    ],
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max versions to return"),
    ] = 20,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table, json, jsonl"),
    ] = "table",
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type"),
    ] = None,
) -> None:
    """Show version history for a record.

    Examples:
        feedspine query history ticker:AAPL
        feedspine query history "my:natural:key" --limit 5 --output json
    """
    from feedspine.ops.query import fetch_record_history

    storage = get_storage(connection, storage_type)
    ctx = OperationContext(storage=storage, caller="cli")
    await storage.initialize()

    try:
        result = await fetch_record_history(ctx, natural_key, limit)

        if not result.success:
            console.print(f"[yellow]{result.error}[/yellow]")
            return

        versions = result.data
        if output == "json":
            output_json(versions, console)
        elif output == "jsonl":
            output_jsonl(versions)
        else:
            format_history_table(versions, natural_key, console)
    finally:
        await storage.close()


@query_app.command("sightings")
@async_command
async def list_sightings(
    natural_key: Annotated[
        str | None,
        typer.Argument(help="Filter by natural key (optional)"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max sightings to return"),
    ] = 50,
    source: Annotated[
        str | None,
        typer.Option("--source", help="Filter by source"),
    ] = None,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table, json, jsonl"),
    ] = "table",
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type"),
    ] = None,
) -> None:
    """List record sightings (observation events).

    Examples:
        feedspine query sightings
        feedspine query sightings ticker:AAPL --limit 10
        feedspine query sightings --source "feed:rss" --output json
    """
    from feedspine.ops.query import fetch_sightings

    storage = get_storage(connection, storage_type)
    ctx = OperationContext(storage=storage, caller="cli")
    await storage.initialize()

    try:
        result = await fetch_sightings(ctx, natural_key=natural_key, limit=limit, source=source)

        if not result.success:
            console.print(f"[yellow]{result.error}[/yellow]")
            return

        sightings = result.data
        if output == "json":
            output_json(sightings, console)
        elif output == "jsonl":
            output_jsonl(sightings)
        else:
            format_sightings_table(sightings, natural_key, console)
    finally:
        await storage.close()


@query_app.command("timeline")
@async_command
async def query_timeline(
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Filter by layer: bronze, silver, gold"),
    ] = None,
    source: Annotated[
        str | None,
        typer.Option("--source", help="Filter by feed source name"),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Only records after this ISO timestamp"),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="Only records before this ISO timestamp"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max records to display"),
    ] = 20,
    offset: Annotated[
        int,
        typer.Option("--offset", help="Skip N records"),
    ] = 0,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table, json, jsonl"),
    ] = "table",
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type"),
    ] = None,
) -> None:
    """Unified feed timeline -- merged, time-sorted view of all records.

    Shows records across all feeds, sorted by capture time (newest first).
    Equivalent to the GET /api/v1/feed API endpoint.

    Examples:
        feedspine query timeline
        feedspine query timeline --layer bronze --limit 50
        feedspine query timeline --source sec-filings --since 2024-01-01
        feedspine query timeline --output json
    """
    from datetime import datetime as dt

    from feedspine.ops.feed import fetch_timeline
    from feedspine.ops.feed_formats import timeline_item_to_dict

    since_dt = dt.fromisoformat(since) if since else None
    until_dt = dt.fromisoformat(until) if until else None

    storage = get_storage(connection, storage_type)
    ctx = OperationContext(storage=storage, caller="cli")
    await storage.initialize()

    try:
        result = await fetch_timeline(
            ctx,
            layer=layer,
            source=source,
            since=since_dt,
            until=until_dt,
            limit=limit,
            offset=offset,
        )
        items = [timeline_item_to_dict(i) for i in result.data.items]

        if output == "json":
            output_json(items, console)
        elif output == "jsonl":
            output_jsonl(items)
        else:
            format_timeline_table(items, offset, console)
    finally:
        await storage.close()
