"""Collection statistics and metrics CLI commands.

Provides commands for viewing storage stats, collection metrics, and health info.
Delegates all business logic to :mod:`feedspine.ops.stats`.
"""

from __future__ import annotations

from typing import Annotated

import typer

from feedspine.cli_modules.shared import async_command, console, get_storage

stats_app = typer.Typer(name="stats", help="Collection statistics and metrics", no_args_is_help=True)


def _make_ctx(storage: object) -> object:
    """Build an OperationContext from a storage backend."""
    from feedspine.ops import OperationContext

    return OperationContext(storage=storage, caller="cli")


@stats_app.command("summary")
def stats_summary(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show overall collection statistics.

    Displays record counts, layer distribution, and storage info.

    Examples:
        feedspine stats summary
        feedspine stats summary --json
    """

    @async_command
    async def _summary() -> None:
        from feedspine.ops.stats import fetch_layer_distribution

        storage = get_storage(connection=connection)
        try:
            await storage.initialize()

            result = await fetch_layer_distribution(_make_ctx(storage))

            if not result.success:
                console.print(f"[yellow]{result.error}[/yellow]")
                return

            data = result.data
            total = data["total"]
            layer_counts = data["by_layer"]

            if json_output:
                import json

                console.print(json.dumps(data, indent=2))
            else:
                from rich.panel import Panel
                from rich.table import Table

                console.print(
                    Panel.fit(
                        f"[bold green]{total:,}[/bold green] total records",
                        title="FeedSpine Storage Statistics",
                    )
                )

                if layer_counts:
                    table = Table(title="Records by Layer")
                    table.add_column("Layer", style="cyan")
                    table.add_column("Count", style="green", justify="right")
                    table.add_column("Percentage", style="dim", justify="right")

                    for layer_name, count in sorted(layer_counts.items()):
                        pct = (count / total * 100) if total > 0 else 0
                        table.add_row(layer_name, f"{count:,}", f"{pct:.1f}%")

                    console.print(table)

                console.print(f"\n[dim]Storage backend: {data['storage_type']}[/dim]")

        finally:
            await storage.close()

    _summary()


@stats_app.command("feeds")
def stats_feeds(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    feed: Annotated[
        str | None,
        typer.Option("--feed", "-f", help="Filter by specific feed name"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max feed runs to show"),
    ] = 10,
) -> None:
    """Show per-feed collection statistics.

    Lists recent feed runs with their stats.

    Examples:
        feedspine stats feeds
        feedspine stats feeds --feed sec-rss --limit 20
    """

    @async_command
    async def _feeds() -> None:
        from feedspine.ops.stats import fetch_feed_runs

        storage = get_storage(connection=connection)
        try:
            await storage.initialize()

            result = await fetch_feed_runs(
                _make_ctx(storage),
                feed_name=feed,
                limit=limit,
            )

            if not result.success:
                console.print(f"[yellow]{result.error}[/yellow]")
                return

            runs = result.data
            if not runs:
                console.print("[dim]No feed runs recorded yet.[/dim]")
                return

            from rich.table import Table

            table = Table(title=f"Recent Feed Runs{f' ({feed})' if feed else ''}")
            table.add_column("Feed", style="cyan")
            table.add_column("Started", style="dim")
            table.add_column("Status", style="green")
            table.add_column("Fetched", justify="right")
            table.add_column("New", justify="right", style="green")
            table.add_column("Errors", justify="right", style="red")
            table.add_column("Duration", justify="right")

            for run in runs:
                status_style = "green" if run["status"] == "completed" else "yellow"
                duration = f"{run['duration_seconds']:.1f}s" if run["duration_seconds"] else ""

                table.add_row(
                    run["feed_name"],
                    run["started_at"] or "-",
                    f"[{status_style}]{run['status']}[/{status_style}]",
                    str(run["fetched_count"]),
                    str(run["new_count"]),
                    str(run["error_count"]),
                    duration,
                )

            console.print(table)

        finally:
            await storage.close()

    _feeds()


@stats_app.command("health")
def stats_health(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
) -> None:
    """Check storage health and connectivity.

    Validates that the storage backend is accessible and operational.

    Examples:
        feedspine stats health
    """

    @async_command
    async def _health() -> None:
        from feedspine.ops.stats import check_storage_health

        storage = get_storage(connection=connection)
        try:
            await storage.initialize()
            result = await check_storage_health(_make_ctx(storage))

            if not result.success:
                console.print(f"[red]✗ Storage connection failed: {result.error}[/red]")
                raise typer.Exit(1) from None

            console.print("[green]✓ Storage connection healthy[/green]")
            console.print(f"  Backend: {result.data['backend']}")
            console.print(f"  Records: {result.data['record_count']:,}")
        except typer.Exit:
            raise
        except Exception as e:
            console.print(f"[red]✗ Storage connection failed: {e}[/red]")
            raise typer.Exit(1) from None
        finally:
            try:
                await storage.close()
            except Exception as e:
                console.print(f"[dim]Warning: Could not close storage: {e}[/dim]")

    _health()


@stats_app.command("collection")
def stats_collection(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Days to aggregate"),
    ] = 30,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show aggregated collection run statistics.

    Displays metrics across all collection runs for the specified time window,
    including success rate, record counts, and error counts.

    Examples:
        feedspine stats collection
        feedspine stats collection --days 7
        feedspine stats collection --json
    """

    @async_command
    async def _collection() -> None:
        from feedspine.ops.stats import fetch_collection_stats

        storage = get_storage(connection=connection)
        try:
            await storage.initialize()

            result = await fetch_collection_stats(_make_ctx(storage), days=days)

            if not result.success:
                console.print(f"[yellow]{result.error}[/yellow]")
                return

            stats = result.data

            if json_output:
                import json

                console.print(json.dumps(stats, indent=2))
                return

            if stats.get("total_runs", 0) == 0:
                console.print(f"[dim]No collection runs in the past {days} days.[/dim]")
                return

            from rich.table import Table

            table = Table(title=f"Collection Statistics ({days} days)")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white", justify="right")

            total_runs = stats.get("total_runs", 0)
            successful = stats.get("successful_runs", 0)
            success_rate = successful / total_runs if total_runs > 0 else 0

            table.add_row("Total Runs", f"{total_runs:,}")
            table.add_row("Successful Runs", f"{successful:,}")
            table.add_row("Failed Runs", f"{stats.get('failed_runs', 0):,}")
            table.add_row("Success Rate", f"{success_rate:.1%}")
            table.add_row("Records Collected", f"{stats.get('total_records_collected', 0):,}")
            table.add_row("Total Errors", f"{stats.get('total_errors', 0):,}")
            table.add_row("Avg Records/Run", f"{stats.get('avg_records_per_run', 0):.1f}")
            table.add_row("Active Feeds", f"{stats.get('feeds_active', 0):,}")
            table.add_row("Runs/Day", f"{stats.get('runs_per_day', 0):.1f}")

            console.print(table)

        finally:
            await storage.close()

    _collection()


@stats_app.command("records")
def stats_records(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
) -> None:
    """Show record counts by layer with visual bars.

    Displays a breakdown of records across Bronze, Silver, and Gold layers
    with visual bar representation of distribution.

    Examples:
        feedspine stats records
    """

    @async_command
    async def _records() -> None:
        from feedspine.models.base import Layer
        from feedspine.ops.stats import fetch_layer_distribution

        storage = get_storage(connection=connection)
        try:
            await storage.initialize()

            result = await fetch_layer_distribution(_make_ctx(storage))

            if not result.success:
                console.print(f"[yellow]{result.error}[/yellow]")
                return

            total = result.data["total"]

            if total == 0:
                console.print("[dim]No records in storage.[/dim]")
                return

            # Get counts for ALL layers (including zero)
            layer_counts: dict[str, int] = {}
            for layer in Layer:
                count = await storage.count(layer=layer)
                layer_counts[layer.value] = count

            from rich.table import Table

            table = Table(title="Record Distribution by Layer")
            table.add_column("Layer", style="cyan")
            table.add_column("Count", justify="right", style="white")
            table.add_column("Percentage", justify="right")
            table.add_column("Bar", min_width=20)

            for layer_name, count in layer_counts.items():
                pct = count / total if total > 0 else 0
                bar_len = int(pct * 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)

                # Color code by layer
                if layer_name == "bronze":
                    bar_style = "orange3"
                elif layer_name == "silver":
                    bar_style = "grey70"
                else:
                    bar_style = "gold1"

                table.add_row(
                    layer_name.title(),
                    f"{count:,}",
                    f"{pct:.1%}",
                    f"[{bar_style}]{bar}[/{bar_style}]",
                )

            table.add_row("", "", "", "")
            table.add_row("[bold]Total[/bold]", f"[bold]{total:,}[/bold]", "[bold]100%[/bold]", "")

            console.print(table)

        finally:
            await storage.close()

    _records()


__all__ = ["stats_app"]
