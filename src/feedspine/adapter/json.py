"""JSON API feed adapter implementation.

Provides JSONFeedAdapter for fetching and parsing JSON API responses
and converting items to RecordCandidate objects.

Example:
    >>> from feedspine.adapter.json import JSONFeedAdapter
    >>> adapter = JSONFeedAdapter(
    ...     url="https://api.example.com/items",
    ...     name="example-api",
    ... )
    >>> # Use with Pipeline
    >>> # stats = await pipeline.run(adapter)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from feedspine.adapter.base import BaseFeedAdapter, FeedError
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate

# Default field mapping from internal names to common JSON field names
DEFAULT_FIELD_MAPPING: dict[str, str] = {
    "id": "id",
    "title": "title",
    "url": "url",
    "summary": "summary",
    "published_at": "published",
}


class JSONFeedAdapter(BaseFeedAdapter):
    """Feed adapter for JSON API endpoints.

    Fetches JSON from API endpoints and yields RecordCandidate objects
    for each item. Supports nested JSON structures and custom field mapping.

    Args:
        url: API URL to fetch.
        name: Unique identifier for this adapter.
        source_type: Record type for metadata (default: "json").
        headers: Optional HTTP headers for requests.
        timeout: Request timeout in seconds (default: 30.0).
        items_path: Dot-notation path to items array (e.g., "data.items").
        field_mapping: Map from internal names to JSON field names.
        requests_per_second: Rate limit (default: 1.0).

    Example:
        >>> from feedspine.adapter.json import JSONFeedAdapter
        >>> adapter = JSONFeedAdapter(
        ...     url="https://api.example.com/items",
        ...     name="my-api",
        ...     items_path="data.results",
        ...     field_mapping={"id": "item_id", "title": "headline"},
        ... )
        >>> adapter.name
        'my-api'
    """

    def __init__(
        self,
        url: str,
        name: str,
        *,
        source_type: str = "json",
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        items_path: str | None = None,
        field_mapping: dict[str, str] | None = None,
        requests_per_second: float = 1.0,
    ) -> None:
        """Initialize JSON feed adapter.

        Args:
            url: API URL to fetch.
            name: Unique identifier for this adapter.
            source_type: Record type for metadata (default: "json").
            headers: Optional HTTP headers for requests.
            timeout: Request timeout in seconds (default: 30.0).
            items_path: Dot-notation path to items array.
            field_mapping: Map from internal names to JSON field names.
            requests_per_second: Rate limit (default: 1.0).
        """
        super().__init__(name=name, requests_per_second=requests_per_second)
        self.url = url
        self.source_type = source_type
        self.headers = headers or {}
        self.timeout = timeout
        self.items_path = items_path
        self.field_mapping = {**DEFAULT_FIELD_MAPPING, **(field_mapping or {})}

    @property
    def info(self) -> dict[str, Any]:
        """Return adapter metadata.

        Returns:
            Dictionary with adapter info.
        """
        return {
            "name": self.name,
            "url": self.url,
            "source_type": self.source_type,
            "items_path": self.items_path,
            "last_fetch_at": self.last_fetch_at,
            "last_fetch_count": self.last_fetch_count,
        }

    async def _fetch_json(self) -> Any:
        """Fetch JSON from the API URL.

        This method is designed to be mocked in tests.
        In production, override with actual HTTP client.

        Returns:
            Parsed JSON data.

        Raises:
            FeedError: If fetch fails.
        """
        # This is the integration point for HTTP clients
        # Default implementation raises - must be mocked in tests
        # or overridden with httpx/aiohttp in production
        raise NotImplementedError("Override _fetch_json with HTTP client implementation")

    async def _fetch_items(self) -> list[dict[str, Any]]:
        """Fetch and extract items from JSON response.

        Returns:
            List of item dictionaries.

        Raises:
            FeedError: If fetch or extraction fails.
        """
        try:
            data = await self._fetch_json()
        except NotImplementedError:
            raise
        except Exception as e:
            raise FeedError(
                f"Failed to fetch JSON: {e}",
                source=self.name,
                cause=e,
            ) from e

        # Extract items from nested path if specified
        items = self._extract_items(data)

        if not isinstance(items, list):
            raise FeedError(
                f"Expected list of items, got {type(items).__name__}",
                source=self.name,
            )

        return items

    def _extract_items(self, data: Any) -> Any:
        """Extract items from JSON data using items_path.

        Args:
            data: Parsed JSON data.

        Returns:
            Extracted items (should be a list).
        """
        if self.items_path is None:
            # Assume data is already the items array
            return data

        # Navigate dot-notation path
        result = data
        for key in self.items_path.split("."):
            if isinstance(result, dict):
                result = result.get(key)
            else:
                return []

        return result if result is not None else []

    def _get_field(self, item: dict[str, Any], internal_name: str) -> Any:
        """Get a field value using the field mapping.

        Args:
            item: Item dictionary.
            internal_name: Internal field name (e.g., "id", "title").

        Returns:
            Field value or None if not found.
        """
        json_field = self.field_mapping.get(internal_name, internal_name)
        return item.get(json_field)

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Parse a datetime value from various formats.

        Args:
            value: Datetime value (string or None).

        Returns:
            Parsed datetime or None.
        """
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if not isinstance(value, str):
            return None

        # Try ISO 8601 format
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass

        # Try Unix timestamp
        try:
            timestamp = float(value)
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except (ValueError, TypeError):
            pass

        return None

    def _to_candidate(self, item: dict[str, Any]) -> RecordCandidate:
        """Convert a JSON item to RecordCandidate.

        Args:
            item: Item dictionary from JSON.

        Returns:
            RecordCandidate for the item.
        """
        # Get natural key (prefer id field)
        natural_key = self._get_field(item, "id")
        if natural_key is None:
            # Fallback to URL or generate from title
            natural_key = (
                self._get_field(item, "url")
                or f"{self.name}:{self._get_field(item, 'title') or 'unknown'}"
            )

        # Get published timestamp
        published_at = self._parse_datetime(self._get_field(item, "published_at"))
        if published_at is None:
            published_at = datetime.now(UTC)

        # Build content dict
        content: dict[str, Any] = {}

        title = self._get_field(item, "title")
        if title:
            content["title"] = title

        url = self._get_field(item, "url")
        if url:
            content["url"] = url

        summary = self._get_field(item, "summary")
        if summary:
            content["summary"] = summary

        # Include all unmapped fields in content
        for key, value in item.items():
            if key not in content and key not in self.field_mapping.values():
                content[key] = value

        return RecordCandidate(
            natural_key=str(natural_key),
            published_at=published_at,
            content=content,
            metadata=Metadata(
                source=self.name,
                extra={"record_type": self.source_type},
            ),
        )
