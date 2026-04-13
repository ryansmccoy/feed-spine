"""CLI entry point — thin router.

All command implementations live in feedspine.cli_modules.
"""

from __future__ import annotations

import typer
from rich.console import Console

from feedspine.cli_modules.api_cmds import api_app
from feedspine.cli_modules.capture_cmds import capture_app
from feedspine.cli_modules.collect_cmds import collect_app
from feedspine.cli_modules.enrich_cmds import enrich_app
from feedspine.cli_modules.feed_cmds import feed_app
from feedspine.cli_modules.feeds_cmds import feeds_app
from feedspine.cli_modules.health_cmds import health_app
from feedspine.cli_modules.migrate_cmds import migrate_app
from feedspine.cli_modules.query_cmds import export_app, query_app
from feedspine.cli_modules.stats_cmds import stats_app
from feedspine.cli_modules.util_cmds import config_app

app = typer.Typer(
    name="feedspine",
    help="Storage-agnostic feed capture framework",
    no_args_is_help=True,
)
console = Console()

# ── Sub-apps ─────────────────────────────────────────────
app.add_typer(capture_app)
app.add_typer(collect_app)
app.add_typer(enrich_app)
app.add_typer(feed_app)
app.add_typer(feeds_app)
app.add_typer(health_app)
app.add_typer(query_app)
app.add_typer(export_app)
app.add_typer(config_app)
app.add_typer(api_app)
app.add_typer(migrate_app)
app.add_typer(stats_app)


# ── Top-level commands ───────────────────────────────────


@app.command()
def version() -> None:
    """Show version."""
    from feedspine import __version__

    console.print(f"feedspine {__version__}")


@app.command()
def info() -> None:
    """Show system information."""
    import sys

    from feedspine import __version__

    console.print(f"[bold]FeedSpine[/bold] {__version__}")
    console.print(f"Python {sys.version}")


if __name__ == "__main__":
    app()
