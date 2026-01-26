"""RSS/Atom feed adapter implementation.

Provides RSSFeedAdapter for parsing RSS 2.0 and Atom feeds
and converting entries to RecordCandidate objects.

Example:
    >>> from feedspine.adapter.rss import RSSFeedAdapter
    >>> adapter = RSSFeedAdapter(
    ...     url="https://example.com/feed.xml",
    ...     name="example-feed",
    ... )
    >>> # Use with Pipeline
    >>> # stats = await pipeline.run(adapter)
"""

from __future__ import annotations

import contextlib
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from feedspine.adapter.base import BaseFeedAdapter, FeedError
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate


class RSSFeedAdapter(BaseFeedAdapter):
    """Feed adapter for RSS 2.0 and Atom feeds.

    Parses RSS and Atom XML feeds and yields RecordCandidate objects
    for each item/entry. Supports custom namespaces for feeds like SEC EDGAR.

    Args:
        url: Feed URL to fetch.
        name: Unique identifier for this adapter.
        source_type: Record type for metadata (default: "rss").
        headers: Optional HTTP headers for requests.
        timeout: Request timeout in seconds (default: 30.0).
        namespace_map: Optional namespace prefix to URI mapping.
        requests_per_second: Rate limit (default: 1.0).

    Example:
        >>> from feedspine.adapter.rss import RSSFeedAdapter
        >>> adapter = RSSFeedAdapter(
        ...     url="https://example.com/feed.xml",
        ...     name="my-feed",
        ...     source_type="custom.rss",
        ... )
        >>> adapter.name
        'my-feed'
        >>> adapter.source_type
        'custom.rss'
    """

    # Atom namespace
    ATOM_NS = "http://www.w3.org/2005/Atom"

    def __init__(
        self,
        url: str,
        name: str,
        *,
        source_type: str = "rss",
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        namespace_map: dict[str, str] | None = None,
        requests_per_second: float = 1.0,
    ) -> None:
        """Initialize RSS feed adapter.

        Args:
            url: Feed URL to fetch.
            name: Unique identifier for this adapter.
            source_type: Record type for metadata (default: "rss").
            headers: Optional HTTP headers for requests.
            timeout: Request timeout in seconds (default: 30.0).
            namespace_map: Optional namespace prefix to URI mapping.
            requests_per_second: Rate limit (default: 1.0).
        """
        super().__init__(name=name, requests_per_second=requests_per_second)
        self.url = url
        self.source_type = source_type
        self.headers = headers or {}
        self.timeout = timeout
        self.namespace_map = namespace_map or {}

    @property
    def info(self) -> dict[str, Any]:
        """Return adapter metadata.

        Returns:
            Dictionary with adapter info.

        Example:
            >>> from feedspine.adapter.rss import RSSFeedAdapter
            >>> adapter = RSSFeedAdapter(
            ...     url="https://example.com/feed.xml",
            ...     name="test",
            ...     source_type="sec.rss",
            ... )
            >>> info = adapter.info
            >>> info["name"]
            'test'
        """
        return {
            "name": self.name,
            "url": self.url,
            "source_type": self.source_type,
            "last_fetch_at": self.last_fetch_at,
            "last_fetch_count": self.last_fetch_count,
        }

    async def _fetch_xml(self) -> str:
        """Fetch raw XML from the feed URL.

        This method is designed to be mocked in tests.
        In production, override with actual HTTP client.

        Returns:
            Raw XML string.

        Raises:
            FeedError: If fetch fails.
        """
        # This is the integration point for HTTP clients
        # Default implementation raises - must be mocked in tests
        # or overridden with httpx/aiohttp in production
        raise NotImplementedError("Override _fetch_xml with HTTP client implementation")

    async def _fetch_items(self) -> list[dict[str, Any]]:
        """Fetch and parse RSS/Atom feed items.

        Returns:
            List of dictionaries with parsed feed item data.

        Raises:
            FeedError: If fetch or parse fails.
        """
        try:
            xml_content = await self._fetch_xml()
        except NotImplementedError:
            raise
        except Exception as e:
            raise FeedError(
                f"Failed to fetch feed: {e}",
                source=self.name,
                cause=e,
            ) from e

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise FeedError(
                f"Failed to parse feed XML: {e}",
                source=self.name,
                cause=e,
            ) from e

        # Detect feed type and parse accordingly
        if self._is_atom_feed(root):
            return self._parse_atom(root)
        else:
            return self._parse_rss(root)

    def _is_atom_feed(self, root: ET.Element) -> bool:
        """Check if root element is an Atom feed.

        Args:
            root: XML root element.

        Returns:
            True if Atom feed, False otherwise.
        """
        # Check for Atom namespace in tag or tag name
        return (
            root.tag == f"{{{self.ATOM_NS}}}feed"
            or root.tag == "feed"
            or "atom" in root.tag.lower()
        )

    def _parse_rss(self, root: ET.Element) -> list[dict[str, Any]]:
        """Parse RSS 2.0 feed items.

        Args:
            root: XML root element.

        Returns:
            List of dictionaries with item data.
        """
        # Find all items in channel
        return [self._parse_rss_item(item) for item in root.findall(".//item")]

    def _parse_rss_item(self, item: ET.Element) -> dict[str, Any]:
        """Parse a single RSS item element.

        Args:
            item: RSS item XML element.

        Returns:
            Dictionary with parsed data.
        """
        data: dict[str, Any] = {}

        # Standard RSS elements
        title_elem = item.find("title")
        if title_elem is not None and title_elem.text:
            data["title"] = title_elem.text.strip()

        link_elem = item.find("link")
        if link_elem is not None and link_elem.text:
            data["url"] = link_elem.text.strip()

        guid_elem = item.find("guid")
        if guid_elem is not None and guid_elem.text:
            data["guid"] = guid_elem.text.strip()

        desc_elem = item.find("description")
        if desc_elem is not None and desc_elem.text:
            data["description"] = desc_elem.text.strip()

        pubdate_elem = item.find("pubDate")
        if pubdate_elem is not None and pubdate_elem.text:
            data["pubdate_raw"] = pubdate_elem.text.strip()
            with contextlib.suppress(ValueError, TypeError):
                data["published_at"] = parsedate_to_datetime(data["pubdate_raw"])

        # Parse namespaced elements
        for prefix, uri in self.namespace_map.items():
            for elem in item:
                if elem.tag.startswith(f"{{{uri}}}"):
                    local_name = elem.tag[len(f"{{{uri}}}") :]
                    if elem.text:
                        data[f"{prefix}:{local_name}"] = elem.text.strip()

        return data

    def _parse_atom(self, root: ET.Element) -> list[dict[str, Any]]:
        """Parse Atom feed entries.

        Args:
            root: XML root element.

        Returns:
            List of dictionaries with entry data.
        """
        # Handle both namespaced and non-namespaced Atom
        ns = {"atom": self.ATOM_NS}

        # Try multiple ways to find entries
        entries = (
            root.findall(f"{{{self.ATOM_NS}}}entry")  # Full namespace
            or root.findall("atom:entry", ns)  # Prefix notation
            or root.findall("entry")  # No namespace
        )

        return [self._parse_atom_entry(entry) for entry in entries]

    def _parse_atom_entry(self, entry: ET.Element) -> dict[str, Any]:
        """Parse a single Atom entry element.

        Args:
            entry: Atom entry XML element.

        Returns:
            Dictionary with parsed data.
        """
        data: dict[str, Any] = {}
        ns = self.ATOM_NS

        # Try namespaced first, then non-namespaced
        def find_text(tag: str) -> str | None:
            # Try with full namespace URI
            elem = entry.find(f"{{{ns}}}{tag}")
            if elem is None:
                # Try without namespace
                elem = entry.find(tag)
            return elem.text.strip() if elem is not None and elem.text else None

        title = find_text("title")
        if title:
            data["title"] = title

        id_val = find_text("id")
        if id_val:
            data["id"] = id_val

        summary = find_text("summary")
        if summary:
            data["description"] = summary

        updated = find_text("updated")
        if updated:
            data["updated_raw"] = updated
            with contextlib.suppress(ValueError):
                # Parse ISO 8601 format
                data["published_at"] = datetime.fromisoformat(updated.replace("Z", "+00:00"))

        # Get link href - try with and without namespace
        link = entry.find(f"{{{ns}}}link") or entry.find("link")
        if link is not None:
            href = link.get("href")
            if href:
                data["url"] = href

        return data

    def _to_candidate(self, item: dict[str, Any]) -> RecordCandidate:
        """Convert parsed item to RecordCandidate.

        Args:
            item: Parsed item dictionary.

        Returns:
            RecordCandidate for the item.
        """
        # Determine natural key (prefer guid > id > url)
        natural_key = (
            item.get("guid")
            or item.get("id")
            or item.get("url")
            or f"{self.name}:{item.get('title', 'unknown')}"
        )

        # Get published timestamp
        published_at = item.get("published_at")
        if published_at is None:
            published_at = datetime.now(UTC)

        # Build content dict
        content: dict[str, Any] = {}
        if "title" in item:
            content["title"] = item["title"]
        if "url" in item:
            content["url"] = item["url"]
        if "description" in item:
            content["description"] = item["description"]

        # Include any namespaced fields
        for key, value in item.items():
            if ":" in key:  # Namespaced field
                content[key] = value

        return RecordCandidate(
            natural_key=natural_key,
            published_at=published_at,
            content=content,
            metadata=Metadata(
                source=self.name,
                extra={"record_type": self.source_type},
            ),
        )
