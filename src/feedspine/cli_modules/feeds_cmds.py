"""Feed management CLI commands."""

from __future__ import annotations

from typing import Annotated

import typer

from feedspine.cli_modules.shared import console

feeds_app = typer.Typer(name="feeds", help="Manage feed adapters and configurations", no_args_is_help=True)


@feeds_app.command("list-types")
def list_adapter_types() -> None:
    """List all available feed adapter types.

    Shows the built-in adapter registry with type keys and their
    implementing classes. Use these type names in feeds.yaml configs.

    Examples:
        feedspine feeds list-types
    """
    from rich.table import Table

    from feedspine.core.feed_config import list_adapter_types

    adapters = list_adapter_types()

    table = Table(title="Available Feed Adapter Types")
    table.add_column("Type", style="cyan", width=15)
    table.add_column("Class", style="green")
    table.add_column("Module", style="dim")

    for type_key, class_path in sorted(adapters.items()):
        module_path, class_name = class_path.rsplit(".", 1)
        table.add_row(type_key, class_name, module_path)

    console.print(table)
    console.print(f"\n[dim]{len(adapters)} adapter types available[/dim]")


@feeds_app.command("list")
def list_configured_feeds(
    config: Annotated[
        str | None,
        typer.Option("--config", "-f", help="Path to feeds config file"),
    ] = None,
) -> None:
    """List feeds defined in the current configuration.

    Reads the feeds.yaml (or .toml) config and displays all
    configured feeds without starting collection.

    Examples:
        feedspine feeds list
        feedspine feeds list --config ./my-feeds.yaml
    """
    from rich.table import Table

    from feedspine.core.feed_config import find_config_file, load_config

    config_path = config or find_config_file()
    if not config_path:
        console.print("[yellow]No feed config found.[/yellow]")
        console.print("  Create one with: feedspine collect init")
        console.print("  Or specify: feedspine feeds list --config path/to/feeds.yaml")
        raise typer.Exit(1)

    try:
        feeds_config = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Failed to load config: {e}[/red]")
        raise typer.Exit(1) from None

    feeds = feeds_config.feeds or []
    if not feeds:
        console.print(f"[yellow]No feeds defined in {config_path}[/yellow]")
        raise typer.Exit(1)

    table = Table(title=f"Configured Feeds ({config_path})")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan", max_width=30)
    table.add_column("Type", style="green", width=12)
    table.add_column("URL / Source", max_width=50)
    table.add_column("Enabled", width=8)

    for i, feed in enumerate(feeds, 1):
        name = feed.get("name", "unnamed")
        feed_type = feed.get("type", "?")
        url = feed.get("url", feed.get("source_url", ""))
        enabled = "✓" if feed.get("enabled", True) else "✗"
        style = "" if feed.get("enabled", True) else "dim"

        table.add_row(str(i), name, feed_type, str(url)[:50], enabled, style=style)

    console.print(table)
    console.print(f"\n[dim]{len(feeds)} feeds configured[/dim]")


@feeds_app.command("validate")
def validate_config(
    config: Annotated[
        str | None,
        typer.Option("--config", "-f", help="Path to feeds config file"),
    ] = None,
) -> None:
    """Validate a feed configuration file.

    Checks that the config file is valid YAML/TOML, all feed types
    are recognized, and required fields are present.

    Examples:
        feedspine feeds validate
        feedspine feeds validate --config ./my-feeds.yaml
    """
    from feedspine.core.feed_config import (
        create_adapters_from_config,
        find_config_file,
        load_config,
    )

    config_path = config or find_config_file()
    if not config_path:
        console.print("[red]No feed config found.[/red]")
        raise typer.Exit(1)

    console.print(f"Validating [cyan]{config_path}[/cyan]...")

    try:
        feeds_config = load_config(config_path)
        console.print("  [green]✓[/green] Config file parsed successfully")
    except Exception as e:
        console.print(f"  [red]✗[/red] Parse error: {e}")
        raise typer.Exit(1) from None

    feeds = feeds_config.feeds or []
    if not feeds:
        console.print("  [yellow]⚠[/yellow] No feeds defined")
        raise typer.Exit(1)

    console.print(f"  [green]✓[/green] {len(feeds)} feeds defined")

    # Try creating adapters to validate types and fields
    try:
        adapters = create_adapters_from_config(feeds_config)
        console.print(f"  [green]✓[/green] {len(adapters)} adapters created successfully")
    except Exception as e:
        console.print(f"  [red]✗[/red] Adapter creation failed: {e}")
        raise typer.Exit(1) from None

    console.print("\n[green]Config is valid.[/green]")
