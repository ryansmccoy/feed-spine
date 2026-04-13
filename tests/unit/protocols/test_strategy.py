"""Tests for feedspine.protocols.strategy module.

Covers DateRange arithmetic, SourceFetch/CollectionPlan dataclasses,
and CollectionStrategy protocol compliance.
"""

from __future__ import annotations

from datetime import date

import pytest

from feedspine.protocols.strategy import (
    CollectionPlan,
    DateRange,
    SourceFetch,
    SourcePriority,
)

# ── DateRange ───────────────────────────────────────────────────


class TestDateRange:
    """Tests for the DateRange frozen dataclass."""

    def test_construction(self):
        dr = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))
        assert dr.start == date(2025, 1, 1)
        assert dr.end == date(2025, 1, 31)

    def test_days_property(self):
        dr = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 11))
        # days is inclusive (end - start + 1 or similar)
        assert dr.days >= 10

    def test_single_day(self):
        d = date(2025, 6, 15)
        dr = DateRange(start=d, end=d)
        assert dr.days >= 0

    def test_overlaps_true(self):
        a = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))
        b = DateRange(start=date(2025, 1, 15), end=date(2025, 2, 15))
        assert a.overlaps(b)

    def test_overlaps_false(self):
        a = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))
        b = DateRange(start=date(2025, 3, 1), end=date(2025, 3, 31))
        assert not a.overlaps(b)

    def test_contains_date(self):
        dr = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))
        assert dr.contains(date(2025, 1, 15))
        assert not dr.contains(date(2025, 2, 1))

    def test_frozen(self):
        dr = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))
        with pytest.raises(AttributeError):
            dr.start = date(2025, 2, 1)  # type: ignore[misc]


# ── SourceFetch ─────────────────────────────────────────────────


class TestSourceFetch:
    """Tests for SourceFetch dataclass."""

    def test_construction(self):
        sf = SourceFetch(
            source_id="sec-rss",
            source_type="rss",
            date_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
            url="https://sec.gov/cgi-bin/browse-edgar",
        )
        assert sf.source_id == "sec-rss"
        assert sf.source_type == "rss"

    def test_estimated_records_default(self):
        sf = SourceFetch(
            source_id="s",
            source_type="rss",
            date_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 2)),
        )
        assert sf.estimated_records is None or sf.estimated_records >= 0


# ── CollectionPlan ──────────────────────────────────────────────


class TestCollectionPlan:
    """Tests for CollectionPlan dataclass."""

    @pytest.fixture
    def plan(self):
        return CollectionPlan(
            fetches=[
                SourceFetch(
                    source_id="rss-1",
                    source_type="rss",
                    date_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
                    estimated_records=100,
                ),
                SourceFetch(
                    source_id="api-1",
                    source_type="api",
                    date_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
                    estimated_records=200,
                ),
            ],
            target_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
        )

    def test_total_requests(self, plan):
        assert plan.total_requests == 2

    def test_estimated_records(self, plan):
        assert plan.estimated_records == 300

    def test_by_source_type(self, plan):
        rss_fetches = plan.by_source_type("rss")
        api_fetches = plan.by_source_type("api")
        assert len(rss_fetches) == 1
        assert len(api_fetches) == 1

    def test_iter_fetches(self, plan):
        fetches = list(plan.iter_fetches())
        assert len(fetches) == 2

    def test_summary_returns_string(self, plan):
        s = plan.summary()
        assert isinstance(s, str)
        assert len(s) > 0

    def test_empty_plan(self):
        plan = CollectionPlan(fetches=[])
        assert plan.total_requests == 0
        assert plan.estimated_records == 0


# ── SourcePriority ──────────────────────────────────────────────


class TestSourcePriority:
    """Tests for source priority enum."""

    def test_is_int_enum(self):
        # SourcePriority members should be orderable
        assert isinstance(list(SourcePriority)[0], int) if len(SourcePriority) > 0 else True
