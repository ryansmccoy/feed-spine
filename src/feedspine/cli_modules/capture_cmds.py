"""Capture-spine integration CLI commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from feedspine.cli_modules.shared import async_command, console, get_storage
from feedspine.core.config import get_settings
from feedspine.ops import OperationContext
from feedspine.ops.capture import (
    IngestPayload,
    check_capture_health,
    get_capture_status,
    ingest_batch,
    ingest_single,
    is_capture_client_available,
    load_body_from_file,
    query_records_for_batch,
)

_URL_HELP = "Capture-spine API URL (env: FEEDSPINE_CAPTURE_SPINE_URL)"

capture_app = typer.Typer(name="capture", help="Capture-spine integration commands", no_args_is_help=True)


def _display_dry_run_preview(records: list, url: str) -> None:
    """Show a table preview of records that would be sent (dry-run mode)."""
    console.print("[bold]Dry run mode — showing first 10 records:[/bold]\n")

    table = Table()
    table.add_column("Natural Key", style="cyan")
    table.add_column("Layer")
    table.add_column("Title", style="green")
    table.add_column("Published")

    for record in records[:10]:
        title = record.metadata.extra.get("title", "No title")
        if len(title) > 50:
            title = title[:47] + "..."

        table.add_row(
            record.natural_key,
            record.layer.value,
            title,
            record.published_at.strftime("%Y-%m-%d"),
        )

    console.print(table)
    console.print(f"\n[dim]Would send {len(records)} records to {url}[/dim]")
    console.print("[dim]Remove --dry-run to actually send[/dim]")


def _display_batch_results(result) -> None:
    """Print batch ingestion result summary with failure details."""
    console.print("\n[bold]Batch Ingest Results:[/bold]")
    console.print(f"  Total:      {result.total}")
    console.print(f"  [green]Accepted:   {result.accepted}[/green]")
    console.print(f"  [yellow]Duplicates: {result.duplicates}[/yellow]")
    console.print(f"  [red]Failed:     {result.failed}[/red]")

    if result.failed > 0:
        console.print("\n[red]Failed items:[/red]")
        failed_count = 0
        for i, item_result in enumerate(result.results):
            if item_result.get("status") == "failed":
                failed_count += 1
                if failed_count <= 10:
                    console.print(f"  {i}: {item_result.get('error')}")
                elif failed_count == 11:
                    console.print(f"  ... and {result.failed - 10} more failures")
                    break


def _display_ingest_result(ingest_result) -> None:
    """Print single-record ingestion result."""
    if ingest_result.status == "accepted":
        console.print("[green]✅ Ingested successfully[/green]")
        console.print(f"[dim]Record ID:   {ingest_result.record_id}[/dim]")
        console.print(f"[dim]Sighting ID: {ingest_result.sighting_id}[/dim]")
        if ingest_result.is_new:
            console.print("[dim]Status: New record created[/dim]")
        else:
            console.print("[dim]Status: Updated existing record[/dim]")
        if ingest_result.task_id:
            console.print(f"[dim]Task ID: {ingest_result.task_id}[/dim]")
    elif ingest_result.status == "duplicate":
        console.print("[yellow]⚠️  Duplicate detected[/yellow]")
        console.print(f"[dim]Record ID: {ingest_result.record_id}[/dim]")
    else:
        console.print(f"[red]❌ Ingestion failed: {ingest_result.error}[/red]")
        raise typer.Exit(1)


def _resolve_url(url: str | None) -> str:
    """Resolve capture-spine URL from argument or settings."""
    return url if url is not None else get_settings().capture_spine_url


def _check_capture_client_available() -> None:
    """Verify capture client is available."""
    if not is_capture_client_available():
        console.print("[red]❌ Capture-spine integration requires 'httpx' package[/red]")
        console.print("[dim]Install with: pip install httpx[/dim]")
        console.print("[dim]Or install feedspine with: pip install feedspine[http][/dim]")
        raise typer.Exit(1)


@capture_app.command("health")
@async_command
async def capture_health(
    url: Annotated[
        str | None,
        typer.Option("--url", help=_URL_HELP),
    ] = None,
) -> None:
    """Check capture-spine API health.

    Verifies that capture-spine is running and responding.

    Examples:
        feedspine capture health
        feedspine capture health --url http://localhost:8200
    """
    _check_capture_client_available()
    url = _resolve_url(url)

    console.print(f"\n[dim]Checking capture-spine at {url}...[/dim]")

    ctx = OperationContext(storage=None)
    result = await check_capture_health(ctx, url=url)

    if not result.success:
        console.print(f"[red]❌ {result.error}[/red]")
        console.print("[dim]Make sure capture-spine is running at the specified URL[/dim]")
        raise typer.Exit(1)

    if result.data:
        console.print(f"[green]✅ Capture-spine is healthy at {url}[/green]")
    else:
        console.print(f"[red]❌ Capture-spine is unreachable at {url}[/red]")
        console.print("[dim]Make sure capture-spine is running:[/dim]")
        console.print("[dim]  cd path/to/capture-spine[/dim]")
        console.print("[dim]  python -m capture_spine.cli serve[/dim]")
        raise typer.Exit(1)


@capture_app.command("ingest")
@async_command
async def capture_ingest(
    content_type: Annotated[
        str,
        typer.Option("--type", help="Content type (sec_filing, earnings_event, etc.)"),
    ],
    source_type: Annotated[
        str,
        typer.Option("--source", help="Source system (sec_edgar, polygon, etc.)"),
    ],
    source_id: Annotated[
        str,
        typer.Option("--id", help="Source identifier"),
    ],
    title: Annotated[
        str,
        typer.Option("--title", help="Content title"),
    ],
    body: Annotated[
        str,
        typer.Option("--body", help="Content body (or @filepath to read from file)"),
    ],
    fingerprint: Annotated[
        str,
        typer.Option("--fingerprint", help="Unique fingerprint for deduplication"),
    ],
    url: Annotated[
        str | None,
        typer.Option("--url", help=_URL_HELP),
    ] = None,
    format: Annotated[
        str,
        typer.Option("--format", help="Content format (text, html, markdown)"),
    ] = "text",
    generate_summary: Annotated[
        bool,
        typer.Option("--summary/--no-summary", help="Generate LLM summary"),
    ] = True,
    extract_entities: Annotated[
        bool,
        typer.Option("--entities/--no-entities", help="Extract entities"),
    ] = True,
) -> None:
    """Ingest a single observation to capture-spine.

    Examples:
        feedspine capture ingest \\
          --type sec_filing \\
          --source sec_edgar \\
          --id 0000320193-25-000106 \\
          --title "Apple Inc. 10-K" \\
          --body "Full filing text here..." \\
          --fingerprint "sec:AAPL:10-K:2025-11-01"

        feedspine capture ingest \\
          --type sec_filing \\
          --source sec_edgar \\
          --id 0000320193-25-000106 \\
          --title "Apple Inc. 10-K" \\
          --body "@path/to/filing.html" \\
          --fingerprint "sec:AAPL:10-K:2025-11-01" \\
          --format html
    """
    _check_capture_client_available()
    url = _resolve_url(url)

    # Handle @file syntax for body
    actual_body = body
    if body.startswith("@"):
        try:
            actual_body, file_path = load_body_from_file(body)
            console.print(f"[dim]Loaded content from {file_path} ({len(actual_body)} characters)[/dim]")
        except FileNotFoundError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(1) from None

    console.print("\n[bold]Ingesting to capture-spine...[/bold]")
    console.print(f"  Type:        {content_type}")
    console.print(f"  Source:      {source_type}:{source_id}")
    console.print(f"  Title:       {title}")
    console.print(f"  Fingerprint: {fingerprint}")
    console.print(f"  URL:         {url}\n")

    ctx = OperationContext(storage=None)
    payload = IngestPayload(
        content_type=content_type,
        source_type=source_type,
        source_id=source_id,
        title=title,
        body=actual_body,
        fingerprint=fingerprint,
        format=format,
        generate_summary=generate_summary,
        extract_entities=extract_entities,
    )

    result = await ingest_single(ctx, payload, url=url)

    if not result.success:
        console.print(f"[red]❌ {result.error}[/red]")
        raise typer.Exit(1)

    _display_ingest_result(result.data)


@capture_app.command("batch")
@async_command
async def capture_batch(
    feed_name: Annotated[
        str | None,
        typer.Option("--feed", "-f", help="Filter by feed name (stored in metadata)"),
    ] = None,
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Filter by layer (BRONZE, SILVER, GOLD)"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum records to ingest"),
    ] = 100,
    url: Annotated[
        str | None,
        typer.Option("--url", help=_URL_HELP),
    ] = None,
    content_type: Annotated[
        str,
        typer.Option("--content-type", help="Content type for all records"),
    ] = "feed_item",
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    storage_type: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Storage backend type"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview what would be sent without sending"),
    ] = False,
    stop_on_error: Annotated[
        bool,
        typer.Option("--stop-on-error", help="Stop batch on first error"),
    ] = False,
) -> None:
    """Batch ingest feedspine records to capture-spine.

    Queries feedspine storage for records and sends them to capture-spine
    for entity extraction, summarization, and observability.

    Examples:
        # Send last 100 records from any feed
        feedspine capture batch --limit 100

        # Send all records from SEC RSS feed
        feedspine capture batch --feed sec-rss

        # Send only BRONZE layer records
        feedspine capture batch --layer BRONZE --limit 50

        # Preview what would be sent (dry run)
        feedspine capture batch --feed sec-rss --dry-run
    """
    _check_capture_client_available()
    url = _resolve_url(url)

    storage = get_storage(connection, storage_type)
    await storage.initialize()

    try:
        console.print("\n[bold]Querying feedspine storage...[/bold]")
        if feed_name:
            console.print(f"  Feed filter:  {feed_name}")
        if layer:
            console.print(f"  Layer filter: {layer}")
        console.print(f"  Limit:        {limit}\n")

        # Query records using ops layer
        ctx = OperationContext(storage=storage)
        query_result = await query_records_for_batch(ctx, feed_name=feed_name, layer=layer, limit=limit)

        if not query_result.success:
            console.print(f"[red]❌ {query_result.error}[/red]")
            raise typer.Exit(1)

        records = query_result.data.records
        if not records:
            console.print("[yellow]⚠️  No records found matching filters[/yellow]")
            return

        console.print(f"[cyan]Found {len(records)} records to ingest[/cyan]\n")

        if dry_run:
            _display_dry_run_preview(records, url)
            return

        # Batch ingest using ops layer
        console.print(f"[bold]Ingesting {len(records)} records to {url}...[/bold]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Sending batch...", total=None)
            batch_result = await ingest_batch(
                ctx,
                records=records,
                content_type=content_type,
                url=url,
                stop_on_error=stop_on_error,
            )
            progress.update(task, completed=True)

        if not batch_result.success:
            console.print(f"[red]❌ {batch_result.error}[/red]")
            raise typer.Exit(1)

        _display_batch_results(batch_result.data)

    finally:
        await storage.close()


@capture_app.command("status")
@async_command
async def capture_status_cmd(
    url: Annotated[
        str | None,
        typer.Option("--url", help=_URL_HELP),
    ] = None,
) -> None:
    """Query capture-spine API status.

    Shows capture-spine connection info and health status.

    Examples:
        feedspine capture status
        feedspine capture status --url http://localhost:8200
    """
    _check_capture_client_available()
    url = _resolve_url(url)

    console.print("\n[bold]Capture-Spine Status[/bold]\n")

    ctx = OperationContext(storage=None)
    result = await get_capture_status(ctx, url=url)

    if not result.success:
        console.print(f"[red]❌ {result.error}[/red]")
        raise typer.Exit(1)

    status = result.data
    console.print(f"  URL:    {status['url']}")
    if status["healthy"]:
        console.print("  Health: [green]🟢 Healthy[/green]")
    else:
        console.print("  Health: [red]🔴 Unhealthy[/red]")

    console.print()

    if not status["healthy"]:
        console.print("[yellow]⚠️  Capture-spine is not responding[/yellow]")
        console.print("[dim]Make sure it's running at the specified URL[/dim]")
        raise typer.Exit(1)
