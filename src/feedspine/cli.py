"""CLI entry point."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(
    name="feedspine",
    help="Storage-agnostic feed capture framework",
    no_args_is_help=True,
)
console = Console()


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
