"""Key value transformations for preprocessing before key generation.

Transforms extract or modify values before they're used in key generation.
Useful for messy data: JSON blobs, concatenated fields, nested structures.

Example:
    >>> from feedspine.utils.transforms import JsonPath, Chain, Lower, Strip
    >>> transform = Chain(JsonPath("data.ticker"), Lower(), Strip())
    >>> transform({"data": {"ticker": "  AAPL  "}})
    'aapl'
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


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
            elif isinstance(result, list | tuple) and part.isdigit():
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
        >>> transform = Split("_", index=0)
        >>> transform("AAPL_2024-01-15_close")
        'AAPL'
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
        """Args:
        part: One of 'year', 'month', 'day', 'quarter', 'week', 'yearmonth'
        """
        self.part = part.lower()

    _EXTRACTORS: dict[str, Any] = {
        "year": lambda v: v.year,
        "month": lambda v: v.month,
        "day": lambda v: v.day,
        "quarter": lambda v: (v.month - 1) // 3 + 1,
        "week": lambda v: v.isocalendar()[1],
        "yearmonth": lambda v: f"{v.year}-{v.month:02d}",
        "yearquarter": lambda v: f"{v.year}Q{(v.month - 1) // 3 + 1}",
    }

    def __call__(self, value: Any) -> Any:
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value

        if not isinstance(value, datetime | date):
            return value

        extractor = self._EXTRACTORS.get(self.part)
        return extractor(value) if extractor else value

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


# Type alias for column spec: either a field name (str) or (field, transform)
ColumnSpec = str | tuple[str, KeyTransform]
