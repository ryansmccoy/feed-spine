"""Tests for feedspine.models.query."""

from __future__ import annotations

from datetime import UTC, datetime

from feedspine.models.base import Layer
from feedspine.models.query import Query


class TestQueryBasic:
    """Basic Query builder tests."""

    def test_empty_query(self) -> None:
        """Empty query has defaults."""
        q = Query()
        spec = q.build()
        assert spec["layer"] is None
        assert spec["filters"] == {}
        assert spec["limit"] == 100
        assert spec["offset"] == 0

    def test_layer_filter(self) -> None:
        """Can filter by layer."""
        q = Query().layer(Layer.SILVER)
        spec = q.build()
        assert spec["layer"] == Layer.SILVER


class TestQueryFilters:
    """Query filter tests."""

    def test_where_single(self) -> None:
        """Can add single where filter."""
        q = Query().where("status", "active")
        spec = q.build()
        assert spec["filters"]["status"] == "active"

    def test_where_multiple(self) -> None:
        """Can chain multiple where filters."""
        q = Query().where("status", "active").where("priority", 1)
        spec = q.build()
        assert spec["filters"]["status"] == "active"
        assert spec["filters"]["priority"] == 1

    def test_where_in(self) -> None:
        """Can filter with IN clause."""
        q = Query().where_in("type", ["A", "B", "C"])
        spec = q.build()
        assert spec["filters"]["type__in"] == ["A", "B", "C"]

    def test_where_like(self) -> None:
        """Can filter with LIKE pattern."""
        q = Query().where_like("name", "%Corp%")
        spec = q.build()
        assert spec["filters"]["name__like"] == "%Corp%"

    def test_where_gt(self) -> None:
        """Can filter greater than."""
        q = Query().where_gt("price", 100)
        spec = q.build()
        assert spec["filters"]["price__gt"] == 100

    def test_where_lt(self) -> None:
        """Can filter less than."""
        q = Query().where_lt("count", 50)
        spec = q.build()
        assert spec["filters"]["count__lt"] == 50

    def test_where_gte(self) -> None:
        """Can filter greater than or equal."""
        q = Query().where_gte("score", 80)
        spec = q.build()
        assert spec["filters"]["score__gte"] == 80

    def test_where_lte(self) -> None:
        """Can filter less than or equal."""
        q = Query().where_lte("age", 30)
        spec = q.build()
        assert spec["filters"]["age__lte"] == 30

    def test_where_null(self) -> None:
        """Can filter for null values."""
        q = Query().where_null("optional_field")
        spec = q.build()
        assert spec["filters"]["optional_field__null"] is True

    def test_where_not_null(self) -> None:
        """Can filter for non-null values."""
        q = Query().where_not_null("required_field")
        spec = q.build()
        assert spec["filters"]["required_field__not_null"] is True


class TestQueryDateFilters:
    """Query date filter tests."""

    def test_published_after(self) -> None:
        """Can filter by published_after."""
        dt = datetime(2024, 1, 1, tzinfo=UTC)
        q = Query().published_after(dt)
        spec = q.build()
        assert spec["published_after"] == dt

    def test_published_before(self) -> None:
        """Can filter by published_before."""
        dt = datetime(2024, 12, 31, tzinfo=UTC)
        q = Query().published_before(dt)
        spec = q.build()
        assert spec["published_before"] == dt

    def test_published_between(self) -> None:
        """Can filter by date range."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 12, 31, tzinfo=UTC)
        q = Query().published_between(start, end)
        spec = q.build()
        assert spec["published_after"] == start
        assert spec["published_before"] == end


class TestQueryPagination:
    """Query pagination tests."""

    def test_limit(self) -> None:
        """Can set limit."""
        q = Query().limit(25)
        spec = q.build()
        assert spec["limit"] == 25

    def test_offset(self) -> None:
        """Can set offset."""
        q = Query().offset(50)
        spec = q.build()
        assert spec["offset"] == 50

    def test_page(self) -> None:
        """Can set pagination by page."""
        q = Query().page(3, page_size=20)
        spec = q.build()
        assert spec["limit"] == 20
        assert spec["offset"] == 40  # (3-1) * 20


class TestQueryOrdering:
    """Query ordering tests."""

    def test_order_by_ascending(self) -> None:
        """Can order ascending."""
        q = Query().order_by("created_at")
        spec = q.build()
        assert spec["order_by"] == "created_at"
        assert spec["order_desc"] is False

    def test_order_by_descending(self) -> None:
        """Can order descending."""
        q = Query().order_by("published_at", descending=True)
        spec = q.build()
        assert spec["order_by"] == "published_at"
        assert spec["order_desc"] is True


class TestQueryChaining:
    """Query method chaining tests."""

    def test_fluent_chain(self) -> None:
        """Can chain all methods fluently."""
        dt = datetime(2024, 1, 1, tzinfo=UTC)
        q = (
            Query()
            .layer(Layer.GOLD)
            .where("type", "10-K")
            .where_gt("value", 1000)
            .published_after(dt)
            .order_by("published_at", descending=True)
            .limit(50)
            .offset(100)
        )
        spec = q.build()
        assert spec["layer"] == Layer.GOLD
        assert spec["filters"]["type"] == "10-K"
        assert spec["filters"]["value__gt"] == 1000
        assert spec["published_after"] == dt
        assert spec["order_by"] == "published_at"
        assert spec["order_desc"] is True
        assert spec["limit"] == 50
        assert spec["offset"] == 100


class TestQueryCopy:
    """Query copy tests."""

    def test_copy_independent(self) -> None:
        """Copied query is independent."""
        q1 = Query().layer(Layer.BRONZE).limit(10)
        q2 = q1.copy().layer(Layer.SILVER).limit(20)

        spec1 = q1.build()
        spec2 = q2.build()

        assert spec1["layer"] == Layer.BRONZE
        assert spec1["limit"] == 10
        assert spec2["layer"] == Layer.SILVER
        assert spec2["limit"] == 20

    def test_copy_preserves_filters(self) -> None:
        """Copy preserves all filters."""
        q1 = Query().where("a", 1).where("b", 2)
        q2 = q1.copy().where("c", 3)

        spec1 = q1.build()
        spec2 = q2.build()

        assert spec1["filters"] == {"a": 1, "b": 2}
        assert spec2["filters"] == {"a": 1, "b": 2, "c": 3}
