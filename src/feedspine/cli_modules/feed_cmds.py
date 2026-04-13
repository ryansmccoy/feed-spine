"""Unified feed timeline CLI commands.

Provides the flagship `feedspine feed` command to query the merged timeline
of records from all feeds.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from feedspine.cli_modules.shared import async_command, console, get_storage
from feedspine.ops import OperationContext
from feedspine.ops.feed import fetch_sources, fetch_timeline
from feedspine.ops.feed_formats import (
    generate_atom_feed,
    generate_rss_feed,
    timeline_item_to_dict,
)
from feedspine.ops.stats import fetch_layer_distribution

feed_app = typer.Typer(
    name="feed",
    help="Unified feed timeline",
    no_args_is_help=False,
)


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "[dim]—[/dim]"
    return dt.strftime("%Y-%m-%d %H:%M")


def _output_json(timeline: object, items: list) -> None:
    """Emit timeline as JSON."""
    data = {
        "items": [timeline_item_to_dict(item) for item in items],
        "total": timeline.total,
        "limit": timeline.limit,
        "offset": timeline.offset,
        "has_more": timeline.has_more,
    }
    console.print_json(json.dumps(data, default=str))


def _output_jsonl(items: list) -> None:
    """Emit timeline as JSONL (one JSON object per line)."""
    for item in items:
        print(json.dumps(timeline_item_to_dict(item), default=str))


def _output_table(items: list, timeline: object, offset: int) -> None:
    """Render timeline as a Rich table."""
    if not items:
        console.print(
            Panel(
                "[dim]No records found matching your criteria.[/dim]",
                title="FeedSpine Timeline",
            )
        )
        return

    table = Table(title=f"FeedSpine Timeline ({len(items)} of {timeline.total:,})")
    table.add_column("Date", style="dim", width=16)
    table.add_column("Source", style="cyan", max_width=15)
    table.add_column("Layer", style="yellow", width=8)
    table.add_column("Title", max_width=50)
    table.add_column("Natural Key", style="dim", max_width=25)

    for item in items:
        ts = item.captured_at or item.published_at
        title = item.title
        if isinstance(title, str) and len(title) > 50:
            title = title[:47] + "..."

        table.add_row(
            _format_datetime(ts),
            (item.source or "")[:15],
            item.layer or "",
            title,
            item.natural_key[:25] if item.natural_key else "",
        )

    console.print(table)

    if timeline.has_more:
        console.print(f"[dim]Use --offset {offset + len(items)} for more results[/dim]")


@feed_app.callback(invoke_without_command=True)
@async_command
async def feed_timeline(
    ctx: typer.Context,
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Filter by layer: bronze, silver, gold"),
    ] = None,
    source: Annotated[
        str | None,
        typer.Option("--source", "-s", help="Filter by feed source name"),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Only items after this date (ISO format or YYYY-MM-DD)"),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="Only items before this date (ISO format or YYYY-MM-DD)"),
    ] = None,
    search: Annotated[
        str | None,
        typer.Option("--search", "-q", help="Search text in content"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max items to return"),
    ] = 20,
    offset: Annotated[
        int,
        typer.Option("--offset", help="Skip N items"),
    ] = 0,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table, json, jsonl, rss, atom"),
    ] = "table",
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", help="Storage type"),
    ] = None,
) -> None:
    """Unified feed timeline — merged, time-sorted records across all feeds.

    The flagship FeedSpine command. Shows a merged view of all collected
    records, sorted by capture time (newest first).

    Examples:
        feedspine feed
        feedspine feed --layer bronze --limit 50
        feedspine feed --source sec-rss --since 2024-01-01
        feedspine feed --output json > timeline.json
        feedspine feed --output rss > timeline.rss
        feedspine feed --search "quarterly earnings" --limit 10
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    storage = get_storage(connection, storage_type)
    await storage.initialize()

    try:
        # Parse date filters
        since_dt = None
        until_dt = None
        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if until:
            until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))

        # Fetch timeline using ops layer
        op_ctx = OperationContext(storage=storage)
        result = await fetch_timeline(
            op_ctx,
            layer=layer,
            source=source,
            since=since_dt,
            until=until_dt,
            search=search,
            limit=limit,
            offset=offset,
        )

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        timeline = result.data
        items = timeline.items

        # Output formatting — dispatch by format
        if output == "json":
            _output_json(timeline, items)
        elif output == "jsonl":
            _output_jsonl(items)
        elif output == "rss":
            print(generate_rss_feed(items, layer or "all"))
        elif output == "atom":
            print(generate_atom_feed(items, layer or "all"))
        else:
            _output_table(items, timeline, offset)

    finally:
        await storage.close()


@feed_app.command("sources")
@async_command
async def feed_sources(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", help="Storage type"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List available feed sources.

    Shows all feed sources that have contributed records.

    Examples:
        feedspine feed sources
        feedspine feed sources --json
    """
    storage = get_storage(connection, storage_type)
    await storage.initialize()

    try:
        ctx = OperationContext(storage=storage)
        result = await fetch_sources(ctx)

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        sources = result.data

        if json_output:
            output = {
                "sources": [
                    {
                        "name": s.name,
                        "total_runs": s.total_runs,
                        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                        "status": s.status,
                    }
                    for s in sources
                ],
                "count": len(sources),
            }
            console.print_json(json.dumps(output, default=str))
            return

        if not sources:
            console.print("[dim]No feed sources found.[/dim]")
            console.print("Per-source stats require FeedRepository storage backend.")
            return

        table = Table(title="Feed Sources")
        table.add_column("Name", style="cyan")
        table.add_column("Total Runs", justify="right")
        table.add_column("Last Run")
        table.add_column("Status")

        for s in sources:
            last_run = _format_datetime(s.last_run_at)
            status_style = "green" if s.status == "healthy" else "yellow" if s.status == "degraded" else "dim"
            table.add_row(
                s.name,
                str(s.total_runs),
                last_run,
                f"[{status_style}]{s.status}[/{status_style}]",
            )

        console.print(table)

    finally:
        await storage.close()


@feed_app.command("stats")
@async_command
async def feed_stats(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", help="Storage type"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show feed timeline statistics.

    Displays record counts by layer and overall stats.

    Examples:
        feedspine feed stats
        feedspine feed stats --json
    """
    storage = get_storage(connection, storage_type)
    await storage.initialize()

    try:
        ctx = OperationContext(storage=storage)
        result = await fetch_layer_distribution(ctx)

        if not result.success:
            console.print(f"[red]Error: {result.error}[/red]")
            raise typer.Exit(1)

        stats = result.data

        if json_output:
            output = {
                "total_records": stats["total"],
                "by_layer": stats["by_layer"],
                "storage_type": stats["storage_type"],
            }
            console.print_json(json.dumps(output))
            return

        console.print(
            Panel.fit(
                f"[bold green]{stats['total']:,}[/bold green] total records",
                title="FeedSpine Timeline Statistics",
            )
        )

        if stats["by_layer"]:
            table = Table()
            table.add_column("Layer", style="cyan")
            table.add_column("Count", justify="right", style="green")
            table.add_column("Percentage", justify="right", style="dim")

            for layer_name, count in sorted(stats["by_layer"].items()):
                pct = (count / stats["total"] * 100) if stats["total"] > 0 else 0
                table.add_row(layer_name, f"{count:,}", f"{pct:.1f}%")

            console.print(table)

        console.print(f"\n[dim]Storage backend: {stats['storage_type']}[/dim]")

    finally:
        await storage.close()
