"""Natural key generation utilities for FeedSpine.

This module provides utilities for generating stable, unique natural keys
when the data source doesn't provide a suitable identifier.

Key Generation Strategies:
1. Content Hash: SHA-256 of normalized content
2. Composite Key: Combine multiple fields
3. URL-based: Extract unique portion of URL
4. Timestamp + Content: For time-series data

Example:
    >>> from feedspine.utils.keys import generate_content_key, CompositeKeyBuilder
    >>>
    >>> # Content-based key
    >>> key = generate_content_key({"title": "Hello", "body": "World"})
    >>> key
    'ch_a591a6d40bf420404a011733...'
    >>>
    >>> # Composite key from fields
    >>> builder = CompositeKeyBuilder(["author", "date", "title"])
    >>> key = builder.build({"author": "John", "date": "2024-01-01", "title": "Hello"})
    >>> key
    'john::2024-01-01::hello'
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any, Callable
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
    if fields:
        data = {k: v for k, v in content.items() if k in fields}
    else:
        data = content
    
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
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif obj is None:
        return ""
    else:
        return obj


# =============================================================================
# Key Transforms - Preprocessing functions for extracting/transforming values
# =============================================================================

class KeyTransform:
    """Base class for key value transformations.
    
    Transforms extract or modify values before they're used in key generation.
    Useful for messy data: JSON blobs, concatenated fields, nested structures.
    """
    
    def __call__(self, value: Any) -> Any:
        """Transform the value."""
        raise NotImplementedError


class JsonPath(KeyTransform):
    """Extract value from JSON/nested dict using dot notation.
    
    Example:
        >>> transform = JsonPath("metadata.source.id")
        >>> transform({"metadata": {"source": {"id": "abc123"}}})
        'abc123'
        >>> 
        >>> # Use with UniqueConstraint
        >>> constraint = UniqueConstraint(
        ...     ("data", JsonPath("ticker")),
        ...     ("data", JsonPath("pricing.date")),
        ... )
    """
    
    def __init__(self, path: str, default: Any = None):
        self.path = path
        self.parts = path.split(".")
        self.default = default
    
    def __call__(self, value: Any) -> Any:
        result = value
        for part in self.parts:
            if isinstance(result, dict):
                result = result.get(part)
            elif isinstance(result, (list, tuple)) and part.isdigit():
                idx = int(part)
                result = result[idx] if 0 <= idx < len(result) else None
            else:
                return self.default
            if result is None:
                return self.default
        return result
    
    def __repr__(self) -> str:
        return f"JsonPath({self.path!r})"


class Split(KeyTransform):
    """Split string and take specific part.
    
    Example:
        >>> transform = Split("_", index=0)  # First part
        >>> transform("AAPL_2024-01-15_close")
        'AAPL'
        >>> 
        >>> transform = Split("_", index=-1)  # Last part
        >>> transform("AAPL_2024-01-15_close")
        'close'
    """
    
    def __init__(self, separator: str = "_", index: int = 0):
        self.separator = separator
        self.index = index
    
    def __call__(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        parts = value.split(self.separator)
        if abs(self.index) < len(parts):
            return parts[self.index]
        return value
    
    def __repr__(self) -> str:
        return f"Split({self.separator!r}, index={self.index})"


class RegexExtract(KeyTransform):
    r"""Extract value using regex pattern.
    
    Example:
        >>> transform = RegexExtract(r"CIK(\d+)")
        >>> transform("Company CIK0001234567 filed")
        '0001234567'
    """
    
    def __init__(self, pattern: str, group: int = 1, default: Any = None):
        self.pattern = re.compile(pattern)
        self.group = group
        self.default = default
    
    def __call__(self, value: Any) -> Any:
        if not isinstance(value, str):
            return self.default
        match = self.pattern.search(value)
        if match:
            try:
                return match.group(self.group)
            except IndexError:
                return self.default
        return self.default
    
    def __repr__(self) -> str:
        return f"RegexExtract({self.pattern.pattern!r})"


class DatePart(KeyTransform):
    """Extract part of a date (year, month, day, quarter).
    
    Example:
        >>> transform = DatePart("year")
        >>> transform("2024-01-15")
        2024
        >>> transform = DatePart("quarter")
        >>> transform("2024-08-15")
        3
    """
    
    def __init__(self, part: str):
        """
        Args:
            part: One of 'year', 'month', 'day', 'quarter', 'week', 'yearmonth'
        """
        self.part = part.lower()
    
    def __call__(self, value: Any) -> Any:
        # Parse date if string
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        
        if not isinstance(value, (datetime, date)):
            return value
        
        if self.part == "year":
            return value.year
        elif self.part == "month":
            return value.month
        elif self.part == "day":
            return value.day
        elif self.part == "quarter":
            return (value.month - 1) // 3 + 1
        elif self.part == "week":
            return value.isocalendar()[1]
        elif self.part == "yearmonth":
            return f"{value.year}-{value.month:02d}"
        elif self.part == "yearquarter":
            q = (value.month - 1) // 3 + 1
            return f"{value.year}Q{q}"
        return value
    
    def __repr__(self) -> str:
        return f"DatePart({self.part!r})"


class Concat(KeyTransform):
    """Concatenate multiple fields into one value.
    
    Example:
        >>> transform = Concat("first_name", "last_name", separator=" ")
        >>> transform({"first_name": "John", "last_name": "Doe"})
        'John Doe'
    """
    
    def __init__(self, *fields: str, separator: str = "_"):
        self.fields = fields
        self.separator = separator
    
    def __call__(self, value: Any) -> Any:
        # value should be the full record for Concat
        if not isinstance(value, dict):
            return value
        parts = [str(value.get(f, "")) for f in self.fields]
        return self.separator.join(parts)
    
    def __repr__(self) -> str:
        return f"Concat({', '.join(repr(f) for f in self.fields)})"


class Lower(KeyTransform):
    """Lowercase a string value."""
    
    def __call__(self, value: Any) -> Any:
        return value.lower() if isinstance(value, str) else value
    
    def __repr__(self) -> str:
        return "Lower()"


class Strip(KeyTransform):
    """Strip whitespace or specific characters."""
    
    def __init__(self, chars: str | None = None):
        self.chars = chars
    
    def __call__(self, value: Any) -> Any:
        return value.strip(self.chars) if isinstance(value, str) else value
    
    def __repr__(self) -> str:
        return f"Strip({self.chars!r})" if self.chars else "Strip()"


class Chain(KeyTransform):
    """Chain multiple transforms together.
    
    Example:
        >>> transform = Chain(JsonPath("data.ticker"), Lower(), Strip())
        >>> transform({"data": {"ticker": "  AAPL  "}})
        'aapl'
    """
    
    def __init__(self, *transforms: KeyTransform):
        self.transforms = transforms
    
    def __call__(self, value: Any) -> Any:
        result = value
        for t in self.transforms:
            result = t(result)
        return result
    
    def __repr__(self) -> str:
        return f"Chain({', '.join(repr(t) for t in self.transforms)})"


# Type alias for column spec: either a string (field name) or (field, transform)
ColumnSpec = str | tuple[str, KeyTransform]


class UniqueConstraint:
    """Define unique constraint columns for deduplication.
    
    Works like a database unique constraint - records with the same
    values in the specified columns are considered duplicates.
    
    Basic Example:
        >>> # Like SQL: UNIQUE(ticker, date, metric_name)
        >>> constraint = UniqueConstraint("ticker", "date", "metric_name")
        >>> 
        >>> # Same constraint values = same key = duplicate
        >>> constraint.key({"ticker": "AAPL", "date": "2024-01-15", "metric_name": "close", "value": 150.0})
        'aapl|2024-01-15|close'
    
    With Transforms (for messy data):
        >>> # Extract from nested JSON
        >>> constraint = UniqueConstraint(
        ...     ("payload", JsonPath("ticker")),
        ...     ("payload", JsonPath("pricing.date")),
        ... )
        >>> constraint.key({"payload": {"ticker": "AAPL", "pricing": {"date": "2024-01-15"}}})
        'aapl|2024-01-15'
        >>> 
        >>> # Split concatenated field
        >>> constraint = UniqueConstraint(
        ...     ("record_id", Split("_", index=0)),  # ticker
        ...     ("record_id", Split("_", index=1)),  # date
        ... )
        >>> constraint.key({"record_id": "AAPL_2024-01-15_close"})
        'aapl|2024-01-15'
        >>> 
        >>> # Extract with regex
        >>> constraint = UniqueConstraint(
        ...     ("description", RegexExtract(r"CIK[0-9]+")),
        ... )
        >>> constraint.key({"description": "Filed by CIK0001234567"})
        '0001234567'
    
    Real-world examples:
        # Financial data: one price per ticker per day
        UniqueConstraint("ticker", "date", "price_type")
        
        # SEC filings: one filing per accession number
        UniqueConstraint("accession_number")
        
        # Nested API response
        UniqueConstraint(
            ("data", JsonPath("symbol")),
            ("data", JsonPath("date")),
        )
    """
    
    def __init__(
        self,
        *columns: ColumnSpec,
        name: str | None = None,
        case_sensitive: bool = False,
        null_value: str = "__NULL__",
        transforms: dict[str, KeyTransform] | None = None,
    ):
        """Define unique constraint columns.
        
        Args:
            *columns: Column specs - either field names (str) or tuples of (field, transform)
            name: Optional constraint name (for logging/debugging)
            case_sensitive: Whether string comparisons are case-sensitive
            null_value: Value to use when a column is None/missing
            transforms: Dict mapping column names to transforms (alternative to tuple syntax)
            
        Raises:
            ValueError: If no columns specified
        """
        if not columns:
            raise ValueError("UniqueConstraint requires at least one column")
        
        # Parse column specs into (field, transform) pairs
        self._column_specs: list[tuple[str, KeyTransform | None]] = []
        column_names = []
        
        for col in columns:
            if isinstance(col, tuple):
                field, transform = col
                self._column_specs.append((field, transform))
                column_names.append(field)
            else:
                # Check if transform provided via transforms dict
                transform = transforms.get(col) if transforms else None
                self._column_specs.append((col, transform))
                column_names.append(col)
        
        self.columns = tuple(column_names)
        self.name = name or f"uq_{'_'.join(column_names)}"
        self.case_sensitive = case_sensitive
        self.null_value = null_value
    
    def key(self, record: dict[str, Any]) -> str:
        """Generate unique key from record based on constraint columns.
        
        Args:
            record: Data record (dict)
            
        Returns:
            Unique key string based on constraint columns
        """
        parts = []
        for field, transform in self._column_specs:
            value = record.get(field)
            
            # Apply transform if specified
            if transform is not None:
                # For transforms that need full record (like Concat), pass record
                if isinstance(transform, Concat):
                    value = transform(record)
                else:
                    value = transform(value)
            
            # Format value for key
            if value is None:
                parts.append(self.null_value)
            elif isinstance(value, (datetime, date)):
                parts.append(value.isoformat()[:10])
            elif isinstance(value, str):
                parts.append(value if self.case_sensitive else value.lower())
            else:
                parts.append(str(value))
        
        return "|".join(parts)
    
    def __repr__(self) -> str:
        cols = ", ".join(self.columns)
        return f"UniqueConstraint({cols})"
    
    def is_duplicate(self, record1: dict[str, Any], record2: dict[str, Any]) -> bool:
        """Check if two records are duplicates based on constraint."""
        return self.key(record1) == self.key(record2)


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
        if isinstance(value, (datetime, date)):
            return value.isoformat()[:10]  # YYYY-MM-DD
        
        text = str(value).lower()
        # Replace non-alphanumeric with hyphen
        text = re.sub(r'[^a-z0-9]+', '-', text)
        # Remove leading/trailing hyphens
        text = text.strip('-')
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
            path = parsed.path.strip('/')
            if path:
                return path.split('/')[-1]
        
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
            "id", "guid", "uuid", "_id", "key",
            # Common API patterns
            "item_id", "post_id", "article_id", "entry_id",
            # Financial/SEC patterns
            "accession_number", "cik", "filing_id", "ticker",
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
