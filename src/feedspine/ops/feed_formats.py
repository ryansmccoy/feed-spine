"""Feed format generation — RSS 2.0, Atom 1.0, dict conversion.

Extracted from :mod:`feedspine.ops.feed` for single-responsibility.

Functions
---------
generate_rss_feed
    Generate RSS 2.0 XML from timeline items.
generate_atom_feed
    Generate Atom 1.0 XML from timeline items.
timeline_item_to_dict
    Convert TimelineItem to JSON-serializable dict.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from xml.etree.ElementTree import Element, SubElement, tostring

if TYPE_CHECKING:
    from feedspine.ops.feed import TimelineItem


def _format_rfc822(dt: datetime | None) -> str:
    """Format datetime in RFC 822 format for RSS."""
    if dt is None:
        dt = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _format_rfc3339(dt: datetime | None) -> str:
    """Format datetime in RFC 3339 format for Atom."""
    if dt is None:
        dt = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def generate_rss_feed(
    items: list[TimelineItem],
    layer: str = "all",
    records: list[Any] | None = None,
) -> str:
    """Generate RSS 2.0 XML from timeline items.

    Args:
        items: List of TimelineItem objects.
        layer: Layer name for feed title.
        records: Optional raw records for additional content.

    Returns:
        RSS XML string.
    """
    rss = Element("rss")
    rss.set("version", "2.0")

    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = f"FeedSpine Timeline ({layer})"
    SubElement(channel, "link").text = "http://localhost:8000/api/v1/feed"
    SubElement(channel, "description").text = "Unified feed timeline from FeedSpine"
    SubElement(channel, "language").text = "en"
    SubElement(channel, "lastBuildDate").text = _format_rfc822(datetime.now(UTC))

    for _i, item in enumerate(items):
        rss_item = SubElement(channel, "item")
        SubElement(rss_item, "title").text = item.title

        if item.content_preview:
            SubElement(rss_item, "description").text = item.content_preview[:500]

        guid = SubElement(rss_item, "guid")
        guid.text = item.id
        guid.set("isPermaLink", "false")

        pub_date = item.published_at or item.captured_at
        SubElement(rss_item, "pubDate").text = _format_rfc822(pub_date)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode")


def generate_atom_feed(
    items: list[TimelineItem],
    layer: str = "all",
) -> str:
    """Generate Atom 1.0 XML from timeline items.

    Args:
        items: List of TimelineItem objects.
        layer: Layer name for feed title.

    Returns:
        Atom XML string.
    """
    feed = Element("feed")
    feed.set("xmlns", "http://www.w3.org/2005/Atom")

    SubElement(feed, "title").text = f"FeedSpine Timeline ({layer})"
    SubElement(feed, "id").text = f"urn:feedspine:timeline:{layer}"
    SubElement(feed, "updated").text = _format_rfc3339(datetime.now(UTC))

    for item in items:
        entry = SubElement(feed, "entry")
        SubElement(entry, "title").text = item.title
        SubElement(entry, "id").text = f"urn:feedspine:record:{item.id}"

        pub_date = item.published_at or item.captured_at
        if pub_date:
            SubElement(entry, "updated").text = _format_rfc3339(pub_date)
            SubElement(entry, "published").text = _format_rfc3339(pub_date)

        if item.content_preview:
            content_el = SubElement(entry, "content")
            content_el.set("type", "text")
            content_el.text = item.content_preview[:500]

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(feed, encoding="unicode")


def timeline_item_to_dict(item: TimelineItem) -> dict[str, Any]:
    """Convert TimelineItem to JSON-serializable dict.

    Args:
        item: TimelineItem object.

    Returns:
        Dict representation.
    """
    return {
        "id": item.id,
        "natural_key": item.natural_key,
        "layer": item.layer,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "captured_at": item.captured_at.isoformat() if item.captured_at else None,
        "source": item.source,
        "source_type": item.source_type,
        "title": item.title,
        "content_preview": item.content_preview,
        "version": item.version,
    }
