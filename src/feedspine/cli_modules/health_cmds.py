"""Health monitoring CLI commands.

Provides commands for viewing feed health with RAG status indicators.
Delegates all business logic to :mod:`feedspine.ops.health`.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from feedspine.cli_modules.shared import async_command, console, get_storage

health_app = typer.Typer(
    name="health",
    help="Feed health monitoring",
    no_args_is_help=True,
)


def _rag_emoji(status: str) -> str:
    """Get emoji for RAG status."""
    return {
        "healthy": "🟢",
        "degraded": "🟡",
        "failing": "🔴",
        "unknown": "⚪",
    }.get(status, "⚪")


def _rag_style(status: str) -> str:
    """Get Rich style for RAG status."""
    return {
        "healthy": "green",
        "degraded": "yellow",
        "failing": "red",
        "unknown": "dim",
    }.get(status, "dim")


def _make_ctx(storage: object) -> object:
    """Build an OperationContext from a storage backend."""
    from feedspine.ops import OperationContext

    return OperationContext(storage=storage, caller="cli")


@health_app.command("summary")
def health_summary(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to analyze"),
    ] = 7,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show health summary for all feeds.

    Displays RAG status (Red/Amber/Green) for each feed based on
    success rate and consecutive failure count.

    Examples:
        feedspine health summary
        feedspine health summary --days 30
        feedspine health summary --json
    """

    @async_command
    async def _summary() -> None:
        from feedspine.ops.health import fetch_all_feed_health

        storage = get_storage(connection)
        await storage.initialize()

        try:
            result = await fetch_all_feed_health(_make_ctx(storage), days=days)

            if not result.success:
                console.print(f"[yellow]{result.error}[/yellow]")
                return

            health_list = result.data["feeds"]
            summary = result.data["summary"]

            if not health_list:
                console.print("[dim]No feed runs recorded yet.[/dim]")
                return

            if json_output:
                console.print(json.dumps(result.data, indent=2, default=str))
                return

            healthy = summary["healthy"]
            degraded = summary["degraded"]
            failing = summary["failing"]
            unknown = summary["unknown"]

            summary_text = f"""🟢 Healthy: {healthy}  |  🟡 Degraded: {degraded}  |  🔴 Failing: {failing}  |  ⚪ Unknown: {unknown}"""
            console.print(Panel(summary_text, title=f"Feed Health (Last {days} Days)"))
            console.print()

            table = Table(title="Feed Health Details")
            table.add_column("Feed", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Success Rate", justify="right")
            table.add_column("Runs", justify="right")
            table.add_column("Failures", justify="right")
            table.add_column("Last Success")
            table.add_column("Avg Records", justify="right")

            for h in health_list:
                status_str = f"{_rag_emoji(h['status'])} [{_rag_style(h['status'])}]{h['status'].upper()}[/{_rag_style(h['status'])}]"
                success_rate = f"{h['success_rate']:.0%}"
                last_success = h.get("last_success_at", "Never")
                if last_success and hasattr(last_success, "strftime"):
                    last_success = last_success.strftime("%Y-%m-%d %H:%M")
                elif last_success:
                    last_success = str(last_success)[:16]

                failures_style = (
                    "red" if h["consecutive_failures"] >= 3 else "yellow" if h["consecutive_failures"] > 0 else ""
                )

                table.add_row(
                    h["feed_name"],
                    status_str,
                    success_rate,
                    str(h["total_runs"]),
                    f"[{failures_style}]{h['consecutive_failures']}[/{failures_style}]"
                    if failures_style
                    else str(h["consecutive_failures"]),
                    last_success or "[dim]Never[/dim]",
                    f"{h.get('avg_records_per_run', 0):.0f}",
                )

            console.print(table)

        finally:
            await storage.close()

    _summary()


@health_app.command("feed")
def health_feed(
    feed: Annotated[
        str,
        typer.Argument(help="Feed name to check"),
    ],
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to analyze"),
    ] = 7,
) -> None:
    """Show detailed health for a specific feed.

    Examples:
        feedspine health feed sec-rss
        feedspine health feed news --days 30
    """

    @async_command
    async def _feed() -> None:
        from feedspine.ops.health import fetch_feed_health

        storage = get_storage(connection)
        await storage.initialize()

        try:
            result = await fetch_feed_health(_make_ctx(storage), feed_name=feed, days=days)

            if not result.success:
                console.print(f"[yellow]{result.error}[/yellow]")
                return

            h = result.data

            if h["total_runs"] == 0:
                console.print(f"[dim]No runs recorded for '{feed}' in the last {days} days.[/dim]")
                return

            status_str = f"{_rag_emoji(h['status'])} {h['status'].upper()}"
            last_success = h.get("last_success_at", "Never")
            if last_success and hasattr(last_success, "strftime"):
                last_success = last_success.strftime("%Y-%m-%d %H:%M:%S")
            elif last_success:
                last_success = str(last_success)

            content = f"""[bold]{feed}[/bold]

Status:             {status_str}
Success Rate:       {h["success_rate"]:.1%}
Total Runs:         {h["total_runs"]}
Consec. Failures:   {h["consecutive_failures"]}
Last Success:       {last_success or "Never"}
Avg Records/Run:    {h.get("avg_records_per_run", 0):.1f}"""

            console.print(Panel(content, title=f"Feed Health (Last {days} Days)"))

        finally:
            await storage.close()

    _feed()


@health_app.command("alerts")
def health_alerts(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    threshold: Annotated[
        int,
        typer.Option("--threshold", "-t", help="Consecutive failure threshold"),
    ] = 3,
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to analyze"),
    ] = 7,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show feeds that need attention.

    Lists feeds with status 'failing' or with consecutive failures
    exceeding the threshold.

    Examples:
        feedspine health alerts
        feedspine health alerts --threshold 5
        feedspine health alerts --json
    """

    @async_command
    async def _alerts() -> None:
        from feedspine.ops.health import fetch_health_alerts

        storage = get_storage(connection)
        await storage.initialize()

        try:
            result = await fetch_health_alerts(
                _make_ctx(storage),
                threshold=threshold,
                days=days,
            )

            if not result.success:
                console.print(f"[yellow]{result.error}[/yellow]")
                return

            alerts = result.data

            if json_output:
                console.print(json.dumps(alerts, indent=2, default=str))
                return

            if not alerts:
                console.print(f"[green]✓ No feeds failing above threshold ({threshold} consecutive failures)[/green]")
                return

            console.print(f"[red]⚠️  {len(alerts)} feed(s) need attention:[/red]\n")

            table = Table()
            table.add_column("Feed", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Failures", justify="right", style="red")
            table.add_column("Success Rate", justify="right")
            table.add_column("Last Success")

            for a in alerts:
                status_str = f"{_rag_emoji(a['status'])} {a['status'].upper()}"
                last_success = a.get("last_success_at", "Never")
                if last_success and hasattr(last_success, "strftime"):
                    last_success = last_success.strftime("%Y-%m-%d %H:%M")
                elif last_success:
                    last_success = str(last_success)[:16]

                table.add_row(
                    a["feed_name"],
                    status_str,
                    str(a["consecutive_failures"]),
                    f"{a['success_rate']:.0%}",
                    last_success or "[dim]Never[/dim]",
                )

            console.print(table)

        finally:
            await storage.close()

    _alerts()
