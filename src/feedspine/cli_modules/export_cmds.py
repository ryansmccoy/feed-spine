"""Export CLI commands — JSON, CSV, Parquet.

Extracted from :mod:`feedspine.cli_modules.query_cmds` for single-responsibility.
Thin CLI wrappers that delegate to :mod:`feedspine.ops.export` for business logic.
"""

from __future__ import annotations

import pathlib
from typing import Annotated

import typer

from feedspine.cli_modules.shared import async_command, console, get_storage
from feedspine.ops import OperationContext

export_app = typer.Typer(name="export", help="Export data in various formats", no_args_is_help=True)


@export_app.command("json")
@async_command
async def export_json(
    output_file: Annotated[str, typer.Argument(help="Output file path")],
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Filter by layer"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max records to export (0 = all)"),
    ] = 0,
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type"),
    ] = None,
) -> None:
    """Export records to JSON file.

    Examples:
        feedspine export json records.json
        feedspine export json bronze.json --layer bronze
        feedspine export json sample.json --limit 100
    """
    from feedspine.ops.export import export_to_json

    storage = get_storage(connection, storage_type)
    ctx = OperationContext(storage=storage, caller="cli")
    await storage.initialize()

    try:
        result = await export_to_json(ctx, pathlib.Path(output_file), layer=layer, limit=limit)
        console.print(f"[green]Exported {result.data['count']} records to {result.data['path']}[/green]")
    finally:
        await storage.close()


@export_app.command("csv")
@async_command
async def export_csv(
    output_file: Annotated[str, typer.Argument(help="Output file path")],
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Filter by layer"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max records to export (0 = all)"),
    ] = 0,
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type"),
    ] = None,
) -> None:
    """Export records to CSV file.

    Examples:
        feedspine export csv records.csv
        feedspine export csv bronze.csv --layer bronze --limit 1000
    """
    from feedspine.ops.export import export_to_csv

    storage = get_storage(connection, storage_type)
    ctx = OperationContext(storage=storage, caller="cli")
    await storage.initialize()

    try:
        result = await export_to_csv(ctx, pathlib.Path(output_file), layer=layer, limit=limit)
        if result.data["count"] == 0:
            console.print("[dim]No records to export.[/dim]")
        else:
            console.print(f"[green]Exported {result.data['count']} records to {result.data['path']}[/green]")
    finally:
        await storage.close()


@export_app.command("parquet")
@async_command
async def export_parquet(
    output_file: Annotated[str, typer.Argument(help="Output Parquet file path")],
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Filter by layer"),
    ] = None,
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string (DuckDB)"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage type (must be duckdb)"),
    ] = "duckdb",
) -> None:
    """Export records to Parquet file.

    Uses DuckDB's native Parquet export for efficient columnar output.
    Ideal for data warehouse integration and analytics pipelines.

    Examples:
        feedspine export parquet records.parquet
        feedspine export parquet bronze.parquet --layer bronze
        feedspine export parquet data.parquet --connection feedspine.duckdb
    """
    from feedspine.ops.export import export_to_parquet

    # Force DuckDB storage for parquet export
    if storage_type not in ("duckdb", None):
        console.print("[yellow]Parquet export requires DuckDB storage.[/yellow]")
        console.print("  Switching to DuckDB backend automatically.")

    storage = get_storage(connection, "duckdb")

    try:
        await storage.initialize()
        ctx = OperationContext(storage=storage, caller="cli")

        result = await export_to_parquet(ctx, pathlib.Path(output_file), layer=layer)

        if not result.success:
            console.print(f"[red]{result.error}[/red]")
            raise typer.Exit(1)

        data = result.data
        if data["count"] == 0:
            console.print("[dim]No records to export.[/dim]")
        else:
            size_mb = data["size_bytes"] / (1024 * 1024)
            console.print(f"[green]Exported {data['count']:,} records to {data['path']}[/green] ({size_mb:.2f} MB)")

    except ImportError as e:
        console.print(f"[red]DuckDB not available: {e}[/red]")
        console.print("  Install with: pip install feedspine[duckdb]")
        raise typer.Exit(1) from e
    finally:
        await storage.close()
