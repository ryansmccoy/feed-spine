"""Data collection CLI commands."""

from __future__ import annotations

from typing import Annotated

import typer

from feedspine.cli_modules.shared import async_command, console, get_storage

collect_app = typer.Typer(name="collect", help="Feed collection commands", no_args_is_help=True)


def _load_feeds_into_spine(spine: object, config_path: str | None = None) -> int:
    """Load feed adapters from config file into a FeedSpine instance.

    Returns the number of feeds registered.
    """
    from feedspine.core.feed_config import (
        create_adapters_from_config,
        find_config_file,
        load_config,
    )

    if config_path:
        from pathlib import Path

        path = Path(config_path)
    else:
        path = find_config_file()

    if path is None:
        return 0

    config = load_config(path)
    adapters = create_adapters_from_config(config)

    for adapter in adapters:
        spine.register_feed(adapter)  # type: ignore[attr-defined]

    return len(adapters)


@collect_app.command("run")
@async_command
async def collect_run(
    feeds: Annotated[
        list[str] | None,
        typer.Argument(help="Feed names to collect. Omit for all registered feeds."),
    ] = None,
    config: Annotated[
        str | None,
        typer.Option("--config", "-f", help="Path to feeds.yaml config file"),
    ] = None,
    db_path: Annotated[
        str | None,
        typer.Option("--db", help="Path to spine-core SQLite database"),
    ] = None,
) -> None:
    """Submit feed collection as WorkItems.

    Creates one WorkItem per feed with ``workflow="feed.collect"``.
    Items are processed by the spine-core execution engine asynchronously.

    Examples:
        feedspine collect run
        feedspine collect run sec-rss polygon-earnings
        feedspine collect run --config feeds.yaml
        feedspine collect run --db data/spine.db
    """
    import asyncio
    import sqlite3

    from spine.data.stores.sqlite.work_item_store import SqliteWorkItemStore

    from feedspine.core.feed_config import create_adapters_from_config, find_config_file, load_config
    from feedspine.ops import OperationContext
    from feedspine.ops.collection import submit_collection
    from feedspine.storage.memory import MemoryStorage

    # Resolve feed names from config
    config_path = config
    if config_path:
        from pathlib import Path as P

        path = P(config_path)
    else:
        path = find_config_file()

    if path is None:
        console.print("[yellow]No feeds.yaml found.[/yellow]\nRun [bold]feedspine collect init[/bold] to create one.")
        raise typer.Exit(code=1)

    cfg = load_config(path)
    adapters = create_adapters_from_config(cfg)
    adapter_names = [a.name for a in adapters]

    if feeds:
        unknown = set(feeds) - set(adapter_names)
        if unknown:
            console.print(f"[red]Unknown feeds: {', '.join(sorted(unknown))}[/red]")
            raise typer.Exit(code=1)
        adapter_names = [n for n in adapter_names if n in feeds]

    if not adapter_names:
        console.print("[yellow]No feeds to collect.[/yellow]")
        raise typer.Exit(code=1)

    # Open work-item store (in thread to avoid blocking the event loop)
    db = db_path or "spine.db"
    conn = await asyncio.to_thread(sqlite3.connect, db)
    store = SqliteWorkItemStore(conn)

    try:
        ctx = OperationContext(
            storage=MemoryStorage(),
            work_item_store=store,
            caller="cli",
        )
        result = await submit_collection(ctx, feed_names=adapter_names)
    finally:
        await asyncio.to_thread(conn.close)

    if not result.success:
        console.print(f"[red]{result.error}[/red]")
        raise typer.Exit(code=1)

    created = result.data
    console.print(f"[bold green]Created {len(created)} collection WorkItem(s)[/bold green]")
    for item in created:
        console.print(f"  • {item['feed_name']}  →  work_item_id={item['work_item_id']}")


@collect_app.command("init")
def collect_init(
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output file path"),
    ] = "feeds.yaml",
) -> None:
    """Generate a starter feeds.yaml configuration file.

    Creates a commented example config with common feed types.

    Examples:
        feedspine collect init
        feedspine collect init --output .feedspine/feeds.yaml
    """
    from pathlib import Path

    path = Path(output)
    if path.exists():
        console.print(f"[red]File already exists: {path}[/red]")
        raise typer.Exit(code=1)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_STARTER_CONFIG)
    console.print(f"[green]Created starter config: {path}[/green]")
    console.print("Edit the file to add your feed sources, then run:")
    console.print(f"  [bold]feedspine collect run --config {path}[/bold]")


_STARTER_CONFIG = """\
# FeedSpine feed configuration
# See: feedspine feeds list-types for available adapter types

# Storage backend (optional — can also use --connection or FEEDSPINE_DATABASE_URL)
# storage:
#   type: sqlite
#   connection: feeds.db

# Feed definitions
feeds:
  # RSS feed example
  # - name: sec-10k-filings
  #   type: rss
  #   url: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=10-K&output=atom
  #   requests_per_second: 0.5

  # JSON API example
  # - name: polygon-earnings
  #   type: json
  #   url: https://api.polygon.io/v2/reference/financials
  #   headers:
  #     Authorization: "Bearer ${POLYGON_API_KEY}"
  #   items_path: results
  #   timeout: 60

  # SEC EDGAR filings adapter
  # - name: edgar-filings
  #   type: sec_edgar
  #   source_url: https://www.sec.gov/cgi-bin/browse-edgar
"""


@collect_app.command("status")
@async_command
async def collect_status(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type"),
    ] = None,
) -> None:
    """Show collection status and statistics.

    Displays record counts, last collection time, and storage info.
    """
    from feedspine.models.base import Layer

    storage = get_storage(connection, storage_type)
    await storage.initialize()

    try:
        total = await storage.count()
        console.print("\n[bold]Storage Status[/bold]")
        console.print(f"  Total records: {total:,}")

        for layer in Layer:
            count = await storage.count(layer=layer)
            if count > 0:
                console.print(f"  {layer.value:>10}: {count:,}")
    finally:
        await storage.close()
