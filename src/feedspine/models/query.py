"""Domain query builder for type-safe, fluent queries.

Provides ``Query`` (fluent builder) and ``QuerySpec`` (compiled spec)
for constructing storage queries instead of raw dict filters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from feedspine.models.base import Layer


@dataclass
class QuerySpec:
    """Internal query specification built by QueryBuilder.

    This is the compiled result of a query builder chain.

    Attributes:
        layer: Optional layer filter.
        filters: Content filters as key-value pairs.
        order_by: Field to order by.
        order_desc: Whether to order descending.
        limit_value: Maximum records to return.
        offset_value: Number of records to skip.
        published_after_dt: Filter for records published after this time.
        published_before_dt: Filter for records published before this time.
    """

    layer: Layer | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    order_by: str | None = None
    order_desc: bool = False
    limit_value: int = 100
    offset_value: int = 0
    published_after_dt: datetime | None = None
    published_before_dt: datetime | None = None


class Query:
    """Fluent query builder for storage queries.

    Example:
        >>> from feedspine.models.query import Query
        >>> q = Query().where("verified", True).limit(10)
        >>> q.build()["filters"]["verified"]
        True
    """

    __slots__ = ("_spec",)

    def __init__(self) -> None:
        """Initialize a new query builder."""
        self._spec = QuerySpec()

    def layer(self, layer: Layer) -> Query:
        """Filter by medallion layer.

        Args:
            layer: The layer to filter by.

        Returns:
            Self for chaining.
        """
        self._spec.layer = layer
        return self

    def where(self, field: str, value: Any) -> Query:
        """Add a content filter condition.

        Args:
            field: Field name in content to filter.
            value: Value to match.

        Returns:
            Self for chaining.
        """
        self._spec.filters[field] = value
        return self

    def where_in(self, field: str, values: list[Any]) -> Query:
        """Filter where field value is in a list."""
        self._spec.filters[f"{field}__in"] = values
        return self

    def where_like(self, field: str, pattern: str) -> Query:
        """Filter using LIKE pattern matching."""
        self._spec.filters[f"{field}__like"] = pattern
        return self

    def where_gt(self, field: str, value: Any) -> Query:
        """Filter where field is greater than value."""
        self._spec.filters[f"{field}__gt"] = value
        return self

    def where_lt(self, field: str, value: Any) -> Query:
        """Filter where field is less than value."""
        self._spec.filters[f"{field}__lt"] = value
        return self

    def where_gte(self, field: str, value: Any) -> Query:
        """Filter where field is greater than or equal to value."""
        self._spec.filters[f"{field}__gte"] = value
        return self

    def where_lte(self, field: str, value: Any) -> Query:
        """Filter where field is less than or equal to value."""
        self._spec.filters[f"{field}__lte"] = value
        return self

    def where_null(self, field: str) -> Query:
        """Filter where field is null.

        Args:
            field: Field name in content.

        Returns:
            Self for chaining.
        """
        self._spec.filters[f"{field}__null"] = True
        return self

    def where_not_null(self, field: str) -> Query:
        """Filter where field is not null.

        Args:
            field: Field name in content.

        Returns:
            Self for chaining.
        """
        self._spec.filters[f"{field}__not_null"] = True
        return self

    def published_after(self, dt: datetime) -> Query:
        """Filter records published after a datetime.

        Args:
            dt: Datetime threshold (exclusive).

        Returns:
            Self for chaining.
        """
        self._spec.published_after_dt = dt
        return self

    def published_before(self, dt: datetime) -> Query:
        """Filter records published before a datetime.

        Args:
            dt: Datetime threshold (exclusive).

        Returns:
            Self for chaining.
        """
        self._spec.published_before_dt = dt
        return self

    def published_between(self, start: datetime, end: datetime) -> Query:
        """Filter records published in a date range.

        Args:
            start: Start datetime (inclusive).
            end: End datetime (exclusive).

        Returns:
            Self for chaining.
        """
        self._spec.published_after_dt = start
        self._spec.published_before_dt = end
        return self

    def order_by(self, field: str, descending: bool = False) -> Query:
        """Set the ordering field.

        Args:
            field: Field to order by.
            descending: If True, order descending (newest first).

        Returns:
            Self for chaining.
        """
        self._spec.order_by = field
        self._spec.order_desc = descending
        return self

    def limit(self, n: int) -> Query:
        """Limit the number of results.

        Args:
            n: Maximum number of records to return.

        Returns:
            Self for chaining.
        """
        self._spec.limit_value = n
        return self

    def offset(self, n: int) -> Query:
        """Skip a number of results (for pagination).

        Args:
            n: Number of records to skip.

        Returns:
            Self for chaining.
        """
        self._spec.offset_value = n
        return self

    def page(self, page_num: int, page_size: int = 100) -> Query:
        """Set pagination by page number (1-indexed)."""
        self._spec.limit_value = page_size
        self._spec.offset_value = (page_num - 1) * page_size
        return self

    def build(self) -> dict[str, Any]:
        """Build the query specification dict.

        Returns:
            Dictionary that can be passed to ``storage.query()``.
        """
        result: dict[str, Any] = {
            "layer": self._spec.layer,
            "filters": self._spec.filters,
            "order_by": self._spec.order_by,
            "order_desc": self._spec.order_desc,
            "limit": self._spec.limit_value,
            "offset": self._spec.offset_value,
        }
        if self._spec.published_after_dt:
            result["published_after"] = self._spec.published_after_dt
        if self._spec.published_before_dt:
            result["published_before"] = self._spec.published_before_dt
        return result

    def copy(self) -> Query:
        """Create a copy of this query builder."""
        new_query = Query()
        new_query._spec = QuerySpec(
            layer=self._spec.layer,
            filters={**self._spec.filters},
            order_by=self._spec.order_by,
            order_desc=self._spec.order_desc,
            limit_value=self._spec.limit_value,
            offset_value=self._spec.offset_value,
            published_after_dt=self._spec.published_after_dt,
            published_before_dt=self._spec.published_before_dt,
        )
        return new_query
