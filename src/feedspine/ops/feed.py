"""Feed timeline operations — pure business logic.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`. They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Feed format generation (RSS, Atom) has been extracted to
:mod:`feedspine.ops.feed_formats`.

Functions
---------
fetch_timeline
    Fetch unified feed timeline with filters.
fetch_sources
    List available feed sources.
record_to_timeline_item
    Convert a record to a timeline item dict.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.ops import OperationContext, OperationResult


@dataclass
class TimelineItem:
    """A single item in the feed timeline."""

    id: str
    natural_key: str
    layer: str | None
    published_at: datetime | None
    captured_at: datetime | None
    source: str | None
    source_type: str | None
    title: str
    content_preview: str | None
    version: int


@dataclass
class TimelineResult:
    """Result of fetching the timeline."""

    items: list[TimelineItem]
    total: int
    limit: int
    offset: int
    has_more: bool


@dataclass
class FeedSource:
    """A feed source with health info."""

    name: str
    total_runs: int
    last_run_at: datetime | None
    status: str


def record_to_timeline_item(record: Any) -> TimelineItem:
    """Convert a feedspine record to a timeline item.

    Args:
        record: Feedspine record object.

    Returns:
        TimelineItem with extracted fields.
    """
    content = record.content if isinstance(record.content, dict) else {}
    title = content.get("title") or content.get("name") or record.natural_key

    source = None
    source_type = None
    if record.metadata:
        source = getattr(record.metadata, "source", None)
        source_type = getattr(record.metadata, "source_type", None)

    return TimelineItem(
        id=record.id,
        natural_key=record.natural_key,
        layer=record.layer.value if record.layer else None,
        published_at=record.published_at,
        captured_at=record.captured_at,
        source=source,
        source_type=source_type,
        title=str(title) if title else "",
        content_preview=_get_preview(content),
        version=record.version,
    )


def _get_preview(content: dict, max_len: int = 200) -> str | None:
    """Extract a preview from content.

    Args:
        content: Content dictionary.
        max_len: Maximum preview length.

    Returns:
        Preview string or None.
    """
    for key in ("description", "summary", "text", "body"):
        if key in content:
            preview = str(content[key])
            if len(preview) > max_len:
                return preview[:max_len] + "..."
            return preview
    return None


def _passes_filters(
    record: Any,
    since: datetime | None,
    until: datetime | None,
    source: str | None,
    search: str | None,
) -> bool:
    """Return True if *record* passes all active filters."""
    ts = record.captured_at or record.published_at
    if since and ts and ts < since:
        return False
    if until and ts and ts > until:
        return False

    record_source = None
    if record.metadata:
        record_source = getattr(record.metadata, "source", None)
    if source and record_source != source:
        return False

    if search:
        content_str = json.dumps(record.content).lower()
        if search.lower() not in content_str:
            return False

    return True


async def fetch_timeline(
    ctx: OperationContext,
    layer: str | None = None,
    source: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> OperationResult[TimelineResult]:
    """Fetch unified feed timeline with filters.

    Args:
        ctx: Operation context with storage.
        layer: Optional layer filter (bronze, silver, gold).
        source: Optional source name filter.
        since: Only items after this datetime.
        until: Only items before this datetime.
        search: Search text in content.
        limit: Maximum items to return.
        offset: Number of items to skip.

    Returns:
        OperationResult with TimelineResult.
    """
    from feedspine.models.base import Layer
    from feedspine.ops import OperationResult

    try:
        layer_filter = Layer(layer.lower()) if layer else None

        items = []
        skip_count = offset

        async for record in ctx.storage.query(layer=layer_filter, limit=limit + offset):
            if skip_count > 0:
                skip_count -= 1
                continue

            if not _passes_filters(record, since, until, source, search):
                continue

            items.append(record_to_timeline_item(record))
            if len(items) >= limit:
                break

        total = await ctx.storage.count(layer=layer_filter)

        return OperationResult.ok(
            TimelineResult(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
                has_more=(offset + len(items)) < total,
            )
        )
    except Exception as e:
        return OperationResult.fail(f"Failed to fetch timeline: {e}")


async def fetch_sources(
    ctx: OperationContext,
) -> OperationResult[list[FeedSource]]:
    """List available feed sources.

    Args:
        ctx: Operation context with storage.

    Returns:
        OperationResult with list of FeedSource objects.
    """
    from feedspine.ops import OperationResult

    try:
        sources = []
        if hasattr(ctx.storage, "get_all_feed_health"):
            health = await ctx.storage.get_all_feed_health()
            for h in health:
                last_run = h.get("last_run_at")
                if isinstance(last_run, str):
                    last_run = datetime.fromisoformat(last_run)

                sources.append(
                    FeedSource(
                        name=h.get("feed_name", h.get("name", "unknown")),
                        total_runs=h.get("total_runs", 0),
                        last_run_at=last_run,
                        status=h.get("status", "unknown"),
                    )
                )

        return OperationResult.ok(sources, metadata={"count": len(sources)})
    except Exception as e:
        return OperationResult.fail(f"Failed to fetch sources: {e}")
