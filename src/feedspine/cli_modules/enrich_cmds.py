"""Enrichment CLI commands — WorkItem-based batch enrichment.

Delegates all business logic to :mod:`feedspine.ops.enrich`.
"""

from __future__ import annotations

from typing import Annotated

import typer

from feedspine.cli_modules.shared import async_command, console

enrich_app = typer.Typer(name="enrich", help="Record enrichment operations", no_args_is_help=True)


def _make_ctx(work_item_store: object) -> object:
    """Build an OperationContext with only a work_item_store (no storage needed)."""
    from feedspine.ops import OperationContext
    from feedspine.storage.memory import MemoryStorage

    # Enrichment ops only need work_item_store; use a no-op storage placeholder
    return OperationContext(
        storage=MemoryStorage(),
        work_item_store=work_item_store,
        caller="cli",
    )


def _open_work_item_store(db_path: str | None) -> tuple[object, object]:
    """Open a SQLite work-item store. Returns (store, connection).

    This is a sync helper — callers in async contexts should invoke
    via ``await asyncio.to_thread(_open_work_item_store, db_path)``.
    """
    import sqlite3

    try:
        from spine.data.stores.sqlite.work_item_store import SqliteWorkItemStore
    except ImportError:
        raise SystemExit(
            "spine-core is required for work-item based enrichment. "
            "Install it with: pip install spine-core"
        )

    db = db_path or "spine.db"
    conn = sqlite3.connect(db)
    return SqliteWorkItemStore(conn), conn


@enrich_app.command("run")
@async_command
async def enrich_run(
    enricher_name: Annotated[
        str,
        typer.Option("--enricher", "-e", help="Enricher to use: passthrough, metadata, entity"),
    ] = "passthrough",
    record_ids: Annotated[
        list[str] | None,
        typer.Argument(help="Record IDs to enrich"),
    ] = None,
    source_layer: Annotated[
        str,
        typer.Option("--source-layer", help="Source layer"),
    ] = "BRONZE",
    target_layer: Annotated[
        str,
        typer.Option("--target-layer", help="Target layer"),
    ] = "SILVER",
    db_path: Annotated[
        str | None,
        typer.Option("--db", help="Path to spine-core SQLite database"),
    ] = None,
) -> None:
    """Submit a batch of enrichment WorkItems.

    Creates one WorkItem per record_id with ``workflow="feed.enrich"``.
    Items are claimed and processed by FeedEnrichmentWorker asynchronously.

    Examples:
        feedspine enrich run rec-001 rec-002 --enricher passthrough
        feedspine enrich run rec-001 --enricher entity --db data/spine.db
    """
    from feedspine.ops.enrich import submit_enrichment_batch

    if not record_ids:
        console.print("[yellow]No record IDs provided.[/yellow]")
        raise typer.Exit(code=1)

    import asyncio

    store, conn = await asyncio.to_thread(_open_work_item_store, db_path)
    try:
        result = await submit_enrichment_batch(
            _make_ctx(store),
            enricher_name=enricher_name,
            record_ids=record_ids,
            source_layer=source_layer,
            target_layer=target_layer,
        )
    finally:
        await asyncio.to_thread(conn.close)

    if not result.success:
        console.print(f"[red]{result.error}[/red]")
        raise typer.Exit(code=1)

    data = result.data
    console.print(f"[bold green]Batch created[/bold green]  batch_id={data['batch_id']}")
    console.print(f"  WorkItems: {data['count']}")
    console.print(f"  Enricher:  {data['enricher']}")


@enrich_app.command("status")
@async_command
async def enrich_status(
    batch_id: Annotated[
        str,
        typer.Argument(help="Batch ID to check"),
    ],
    db_path: Annotated[
        str | None,
        typer.Option("--db", help="Path to spine-core SQLite database"),
    ] = None,
) -> None:
    """Check status of an enrichment batch.

    Examples:
        feedspine enrich status abc123def456
    """
    import asyncio

    from feedspine.ops.enrich import get_batch_status

    store, conn = await asyncio.to_thread(_open_work_item_store, db_path)
    try:
        result = await get_batch_status(_make_ctx(store), batch_id=batch_id)
    finally:
        await asyncio.to_thread(conn.close)

    if not result.success:
        console.print(f"[red]{result.error}[/red]")
        raise typer.Exit(code=1)

    batch = result.data

    console.print(f"[cyan]Batch ID:[/cyan]    {batch['batch_id']}")
    console.print(f"[cyan]Enricher:[/cyan]    {batch['enricher']}")

    style_map = {
        "QUEUED": "yellow",
        "IN_PROGRESS": "blue",
        "COMPLETED": "green",
        "COMPLETED_WITH_FAILURES": "red",
        "PARTIAL_SUCCESS": "yellow",
        "CANCELLED": "dim",
        "EMPTY": "dim",
    }
    style = style_map.get(batch["status"], "dim")
    console.print(f"[cyan]Status:[/cyan]     [{style}]{batch['status']}[/{style}]")

    console.print(f"[cyan]Total:[/cyan]      {batch['total']}")
    console.print(f"[cyan]Succeeded:[/cyan]  {batch['succeeded']}")
    console.print(f"[cyan]Queued:[/cyan]     {batch['queued']}")
    console.print(f"[cyan]Leased:[/cyan]     {batch['leased']}")
    if batch.dead_lettered:
        console.print(f"[red]Failed:[/red]     {batch.dead_lettered}")
    if batch.cancelled:
        console.print(f"[dim]Cancelled:[/dim]   {batch.cancelled}")
