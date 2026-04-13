"""Unique constraint for record deduplication.

Defines constraints on record fields for detecting duplicates,
similar to database UNIQUE constraints.

Example:
    >>> from feedspine.utils.constraints import UniqueConstraint
    >>> constraint = UniqueConstraint("ticker", "date", "metric_name")
    >>> constraint.key({"ticker": "AAPL", "date": "2024-01-15", "metric_name": "close"})
    'aapl|2024-01-15|close'
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from feedspine.utils.transforms import ColumnSpec, Concat, KeyTransform


class UniqueConstraint:
    """Define unique constraint columns for deduplication.

    Works like a database unique constraint — records with the same
    values in the specified columns are considered duplicates.

    Example:
        >>> constraint = UniqueConstraint("ticker", "date", "metric_name")
        >>> constraint.key({"ticker": "AAPL", "date": "2024-01-15", "metric_name": "close", "value": 150.0})
        'aapl|2024-01-15|close'
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
            *columns: Column specs — either field names (str) or tuples of (field, transform)
            name: Optional constraint name (for logging/debugging)
            case_sensitive: Whether string comparisons are case-sensitive
            null_value: Value to use when a column is None/missing
            transforms: Dict mapping column names to transforms (alternative to tuple syntax)

        Raises:
            ValueError: If no columns specified
        """
        if not columns:
            raise ValueError("UniqueConstraint requires at least one column")

        self._column_specs: list[tuple[str, KeyTransform | None]] = []
        column_names = []

        for col in columns:
            if isinstance(col, tuple):
                field, transform = col
                self._column_specs.append((field, transform))
                column_names.append(field)
            else:
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

            if transform is not None:
                value = transform(record) if isinstance(transform, Concat) else transform(value)

            if value is None:
                parts.append(self.null_value)
            elif isinstance(value, datetime | date):
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
