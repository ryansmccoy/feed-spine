"""Natural key generation utilities for FeedSpine.

Key generation strategies:
1. Content Hash: SHA-256 of normalized content
2. Composite Key: Combine multiple fields
3. URL-based: Extract unique portion of URL
4. Auto Key: Try strategies in order with fallback

Example:
    >>> from feedspine.utils.keys import generate_content_key, CompositeKeyBuilder
    >>> key = generate_content_key({"title": "Hello", "body": "World"})
    >>> key
    'ch_a591a6d40bf420404a011733...'
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse


def generate_content_key(
    content: dict[str, Any],
    *,
    prefix: str = "ch",
    fields: list[str] | None = None,
    hash_length: int = 16,
) -> str:
    """Generate a content-based hash key.

    Creates a stable hash from the content dictionary. Useful when
    there's no natural unique identifier in the data.

    Args:
        content: Dictionary of content to hash
        prefix: Key prefix (default: "ch" for content-hash)
        fields: Specific fields to include (default: all)
        hash_length: Length of hash suffix (default: 16 chars)

    Returns:
        Key in format "{prefix}_{hash}"

    Example:
        >>> generate_content_key({"title": "News", "body": "Content"})
        'ch_a591a6d40bf42040'
        >>> generate_content_key({"title": "News"}, fields=["title"])
        'ch_b93d8f4e2c1a3b5d'
    """
    # Select fields to hash
    data = {k: v for k, v in content.items() if k in fields} if fields else content

    # Normalize and serialize
    normalized = _normalize_for_hash(data)
    serialized = json.dumps(normalized, sort_keys=True, ensure_ascii=True)

    # Generate hash
    hash_digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    return f"{prefix}_{hash_digest[:hash_length]}"


def _normalize_for_hash(obj: Any) -> Any:
    """Normalize values for consistent hashing."""
    if isinstance(obj, dict):
        return {k: _normalize_for_hash(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [_normalize_for_hash(item) for item in obj]
    elif isinstance(obj, str):
        # Normalize whitespace and case
        return " ".join(obj.lower().split())
    elif isinstance(obj, datetime | date):
        return obj.isoformat()
    elif obj is None:
        return ""
    else:
        return obj


class CompositeKeyBuilder:
    """Build composite keys from multiple fields.

    Useful when uniqueness comes from a combination of fields
    rather than a single identifier.

    Example:
        >>> builder = CompositeKeyBuilder(["source", "date", "headline"])
        >>> key = builder.build({
        ...     "source": "Reuters",
        ...     "date": "2024-01-15",
        ...     "headline": "Market Update",
        ... })
        >>> key
        'reuters::2024-01-15::market-update'
    """

    def __init__(
        self,
        fields: list[str],
        *,
        separator: str = "::",
        normalize: bool = True,
        missing_value: str = "_",
    ):
        """Initialize composite key builder.

        Args:
            fields: Field names to include, in order
            separator: Separator between field values
            normalize: Whether to normalize values (lowercase, slugify)
            missing_value: Value to use for missing fields
        """
        self.fields = fields
        self.separator = separator
        self.normalize = normalize
        self.missing_value = missing_value

    def build(self, data: dict[str, Any]) -> str:
        """Build composite key from data.

        Args:
            data: Dictionary containing field values

        Returns:
            Composite key string
        """
        parts = []
        for field in self.fields:
            value = data.get(field)
            if value is None:
                parts.append(self.missing_value)
            elif self.normalize:
                parts.append(self._normalize_value(value))
            else:
                parts.append(str(value))

        return self.separator.join(parts)

    def _normalize_value(self, value: Any) -> str:
        """Normalize a value for use in key."""
        if isinstance(value, datetime | date):
            return value.isoformat()[:10]  # YYYY-MM-DD

        text = str(value).lower()
        # Replace non-alphanumeric with hyphen
        text = re.sub(r"[^a-z0-9]+", "-", text)
        # Remove leading/trailing hyphens
        text = text.strip("-")
        return text or self.missing_value


class URLKeyExtractor:
    r"""Extract unique keys from URLs.

    Useful for web scraping or API data where the URL contains
    the unique identifier.

    Example:
        >>> extractor = URLKeyExtractor(pattern=r'/article/(\d+)')
        >>> key = extractor.extract("https://news.com/article/12345")
        >>> key
        '12345'
    """

    def __init__(
        self,
        pattern: str | None = None,
        use_path: bool = True,
        use_query_param: str | None = None,
    ):
        """Initialize URL key extractor.

        Args:
            pattern: Regex pattern to extract key (must have one group)
            use_path: Use URL path as key if pattern doesn't match
            use_query_param: Query parameter name to use as key
        """
        self.pattern = re.compile(pattern) if pattern else None
        self.use_path = use_path
        self.use_query_param = use_query_param

    def extract(self, url: str) -> str | None:
        """Extract key from URL.

        Args:
            url: URL string

        Returns:
            Extracted key or None if no key found
        """
        # Try regex pattern first
        if self.pattern:
            match = self.pattern.search(url)
            if match:
                return match.group(1)

        parsed = urlparse(url)

        # Try query parameter
        if self.use_query_param:
            from urllib.parse import parse_qs

            params = parse_qs(parsed.query)
            if self.use_query_param in params:
                return params[self.use_query_param][0]

        # Use path
        if self.use_path:
            # Remove leading/trailing slashes, use last segment
            path = parsed.path.strip("/")
            if path:
                return path.split("/")[-1]

        return None


class AutoKeyGenerator:
    """Automatic key generator with fallback strategies.

    Tries multiple strategies in order to find or generate a unique key.

    Example:
        >>> generator = AutoKeyGenerator(
        ...     id_fields=["id", "guid", "uuid"],
        ...     url_field="link",
        ...     composite_fields=["author", "title", "date"],
        ... )
        >>>
        >>> # If data has 'id', uses that
        >>> generator.generate({"id": "123", "title": "Hello"})
        '123'
        >>>
        >>> # If no id, tries URL
        >>> generator.generate({"link": "https://x.com/post/456", "title": "Hi"})
        '456'
        >>>
        >>> # If no URL, uses composite
        >>> generator.generate({"author": "John", "title": "Hi", "date": "2024-01-01"})
        'john::hi::2024-01-01'
        >>>
        >>> # Last resort: content hash
        >>> generator.generate({"body": "Some random content"})
        'ch_a1b2c3d4e5f6g7h8'
    """

    def __init__(
        self,
        *,
        id_fields: list[str] | None = None,
        url_field: str | None = None,
        url_pattern: str | None = None,
        composite_fields: list[str] | None = None,
        hash_fields: list[str] | None = None,
        source_prefix: str | None = None,
    ):
        """Initialize auto key generator.

        Args:
            id_fields: Field names that might contain an ID (tried in order)
            url_field: Field containing URL to extract ID from
            url_pattern: Regex for URL extraction
            composite_fields: Fields to combine for composite key
            hash_fields: Fields to hash (default: all if needed)
            source_prefix: Prefix for generated keys
        """
        self.id_fields = id_fields or [
            "id",
            "guid",
            "uuid",
            "_id",
            "key",
            # Common API patterns
            "item_id",
            "post_id",
            "article_id",
            "entry_id",
            # Financial/SEC patterns
            "accession_number",
            "cik",
            "filing_id",
            "ticker",
        ]
        self.url_field = url_field
        self.url_extractor = URLKeyExtractor(pattern=url_pattern) if url_pattern else None
        self.composite_builder = CompositeKeyBuilder(composite_fields) if composite_fields else None
        self.hash_fields = hash_fields
        self.source_prefix = source_prefix

    def generate(self, data: dict[str, Any]) -> str:
        """Generate a unique key for the data.

        Tries strategies in order:
        1. Direct ID field
        2. URL extraction
        3. Composite key
        4. Content hash

        Args:
            data: Data dictionary

        Returns:
            Unique key string
        """
        # Try direct ID fields
        for field in self.id_fields:
            if field in data and data[field]:
                key = str(data[field])
                return self._apply_prefix(key)

        # Try URL extraction
        if self.url_field and self.url_field in data:
            url = data[self.url_field]
            if self.url_extractor:
                key = self.url_extractor.extract(url)
                if key:
                    return self._apply_prefix(key)
            # Fallback: use URL path
            extractor = URLKeyExtractor()
            key = extractor.extract(url)
            if key:
                return self._apply_prefix(key)

        # Try composite key
        if self.composite_builder:
            key = self.composite_builder.build(data)
            if key and key != self.composite_builder.separator.join(
                [self.composite_builder.missing_value] * len(self.composite_builder.fields)
            ):
                return self._apply_prefix(key)

        # Last resort: content hash
        key = generate_content_key(data, fields=self.hash_fields)
        return self._apply_prefix(key)

    def _apply_prefix(self, key: str) -> str:
        """Apply source prefix if configured."""
        if self.source_prefix:
            return f"{self.source_prefix}:{key}"
        return key


# Convenience function for quick key generation
def auto_key(
    data: dict[str, Any],
    *,
    id_fields: list[str] | None = None,
    source: str | None = None,
) -> str:
    """Quick auto-key generation with sensible defaults.

    Args:
        data: Data dictionary
        id_fields: Override default ID field names
        source: Source prefix

    Returns:
        Unique key

    Example:
        >>> auto_key({"id": "123"})
        '123'
        >>> auto_key({"title": "Hello", "content": "World"})
        'ch_a591a6d40bf42040'
        >>> auto_key({"guid": "abc"}, source="news")
        'news:abc'
    """
    generator = AutoKeyGenerator(
        id_fields=id_fields,
        source_prefix=source,
    )
    return generator.generate(data)
