"""Output formatting helpers for CLI commands.

Rich table formatting for various data types (search results, records,
history, sightings, timeline). Separated from CLI commands for cleaner
organization and potential reuse.
"""

from __future__ import annotations

import json


def format_search_table(data: dict, query: str, search_type: str, console) -> None:
    """Render search results as a Rich table."""
    results = data["results"]
    if not results:
        console.print(f"[dim]No results for query: {query}[/dim]")
        console.print(f"[dim]Search type: {search_type} | Time: {data['query_time_ms']:.1f}ms[/dim]")
        return

    from rich.table import Table

    table = Table(title=f"Search: '{query}' ({data['total_count']} results, {data['query_time_ms']:.1f}ms)")
    table.add_column("#", style="dim", width=4)
    table.add_column("Score", style="yellow", width=8)
    table.add_column("Record ID", max_width=30)
    table.add_column("Highlights", max_width=60)

    for i, r in enumerate(results, 1):
        highlight_text = ""
        if r["highlights"]:
            first_key = next(iter(r["highlights"]))
            highlight_text = str(r["highlights"][first_key])[:60]

        table.add_row(
            str(i),
            f"{r['score']:.3f}",
            r["record_id"][:30],
            highlight_text,
        )
    console.print(table)


def format_records_table(records: list[dict], offset: int, console) -> None:
    """Render records as a Rich table."""
    if not records:
        console.print("[dim]No records found.[/dim]")
        return

    from rich.table import Table

    table = Table(title=f"Records ({len(records)} of {len(records) + offset}+)")
    table.add_column("ID", style="dim", max_width=20)
    table.add_column("Natural Key", max_width=40)
    table.add_column("Layer", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Title", max_width=50)

    for r in records:
        meta = r.get("metadata") or {}
        source = meta.get("source", "") if isinstance(meta, dict) else ""
        title = meta.get("title", "") if isinstance(meta, dict) else ""
        table.add_row(
            str(r.get("id", ""))[:20],
            str(r.get("natural_key", ""))[:40],
            str(r.get("layer", "")),
            str(source),
            str(title)[:50],
        )
    console.print(table)


def format_history_table(versions: list[dict], natural_key: str, console) -> None:
    """Render version history as a Rich table."""
    if not versions:
        console.print(f"[dim]No version history for: {natural_key}[/dim]")
        return

    from rich.table import Table

    table = Table(title=f"Version History: {natural_key}")
    table.add_column("Ver", style="cyan", width=5)
    table.add_column("Change", max_width=12)
    table.add_column("Source", max_width=20)
    table.add_column("Created At", max_width=22)
    table.add_column("Hash", max_width=16)
    table.add_column("Reason", max_width=30)

    for v in versions:
        table.add_row(
            str(v["version"]),
            v["change_type"],
            v["source"][:20] if v["source"] else "",
            v["created_at"][:19] if v["created_at"] else "",
            v["content_hash"][:16] if v["content_hash"] else "",
            (v["change_reason"] or "")[:30],
        )
    console.print(table)


def format_sightings_table(sightings: list[dict], natural_key: str | None, console) -> None:
    """Render sightings as a Rich table."""
    if not sightings:
        console.print("[dim]No sightings found.[/dim]")
        return

    from rich.table import Table

    table = Table(title=f"Sightings{f' for {natural_key}' if natural_key else ''}")
    table.add_column("#", style="dim", width=4)
    table.add_column("Natural Key", max_width=25)
    table.add_column("Source", max_width=20)
    table.add_column("Seen At", max_width=22)
    table.add_column("New?", width=5)
    table.add_column("Record ID", max_width=16)

    for i, s in enumerate(sightings, 1):
        table.add_row(
            str(i),
            s["natural_key"][:25] if s["natural_key"] else "",
            s["source"][:20] if s["source"] else "",
            s["seen_at"][:19] if s["seen_at"] else "",
            "yes" if s["is_new"] else "",
            s["record_id"][:16] if s["record_id"] else "",
        )
    console.print(table)


def format_timeline_table(items: list[dict], offset: int, console) -> None:
    """Render timeline items as a Rich table."""
    if not items:
        console.print("[dim]No records found.[/dim]")
        return

    from rich.table import Table

    table = Table(title="Feed Timeline")
    table.add_column("#", style="dim", width=4)
    table.add_column("Source", max_width=20)
    table.add_column("Title", max_width=35)
    table.add_column("Layer", width=8)
    table.add_column("Captured", max_width=19)
    table.add_column("Seen", width=5, justify="right")

    for i, item in enumerate(items, 1):
        table.add_row(
            str(i),
            (item["source"] or "")[:20],
            (item["title"] or item["natural_key"])[:35],
            item["layer"],
            (item["captured_at"] or "")[:19],
            str(item["seen_count"]),
        )
    console.print(table)
    console.print(f"\n[dim]Showing {len(items)} records (offset={offset})[/dim]")


def output_json(data: object, console) -> None:
    """Print data as formatted JSON."""
    console.print_json(json.dumps(data, default=str))


def output_jsonl(items: list[dict]) -> None:
    """Print items as JSON Lines."""
    for item in items:
        print(json.dumps(item, default=str))


__all__ = [
    "format_history_table",
    "format_records_table",
    "format_search_table",
    "format_sightings_table",
    "format_timeline_table",
    "output_json",
    "output_jsonl",
]
