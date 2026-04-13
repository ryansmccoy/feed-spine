"""Tests for feedspine.metrics.collector module.

Covers CollectionMetrics recording, MetricsSummary formatting,
and time_operation context manager.
"""

from __future__ import annotations

import pytest

from feedspine.metrics.collector import CollectionMetrics, MetricsSummary

# ── MetricsSummary ──────────────────────────────────────────────


class TestMetricsSummary:
    """Tests for MetricsSummary dataclass."""

    def test_default_values(self):
        s = MetricsSummary()
        assert s.total_items == 0
        assert s.total_errors == 0
        assert s.total_fetch_time == 0.0
        assert s.total_parse_time == 0.0

    def test_str_output(self):
        s = MetricsSummary(total_items=100, total_errors=2)
        text = str(s)
        assert "100" in text
        assert "2" in text

    def test_str_with_source_breakdown(self):
        s = MetricsSummary(
            total_items=50,
            items_by_source={"quarterly": 30, "daily": 20},
        )
        text = str(s)
        assert "quarterly" in text
        assert "daily" in text

    def test_to_dict(self):
        s = MetricsSummary(total_items=10, total_errors=1)
        d = s.to_dict()
        assert d["total_items"] == 10
        assert d["total_errors"] == 1
        assert isinstance(d, dict)


# ── CollectionMetrics ───────────────────────────────────────────


class TestCollectionMetrics:
    """Tests for CollectionMetrics recording."""

    @pytest.fixture
    def metrics(self):
        return CollectionMetrics()

    def test_prometheus_disabled_by_default(self, metrics):
        assert metrics.prometheus_enabled is False

    def test_record_items(self, metrics):
        metrics.record_items("quarterly", category="10-K", count=100)
        summary = metrics.summary()
        assert summary.total_items == 100
        assert summary.items_by_source["quarterly"] == 100
        assert summary.items_by_category["10-K"] == 100

    def test_record_items_multiple_sources(self, metrics):
        metrics.record_items("quarterly", count=50)
        metrics.record_items("daily", count=30)
        summary = metrics.summary()
        assert summary.total_items == 80

    def test_record_error(self, metrics):
        metrics.record_error("quarterly", "network_timeout")
        metrics.record_error("quarterly", "parse_error")
        summary = metrics.summary()
        assert summary.total_errors == 2
        assert summary.errors_by_source["quarterly"] == 2

    def test_time_operation(self, metrics):
        with metrics.time_operation("fetch", adapter="quarterly"):
            pass  # simulate quick operation
        summary = metrics.summary()
        assert summary.total_fetch_time >= 0.0

    def test_start(self, metrics):
        metrics.start()
        # Should not raise

    def test_empty_summary(self, metrics):
        summary = metrics.summary()
        assert summary.total_items == 0
        assert summary.total_errors == 0

    def test_reset_clears_all(self, metrics):
        metrics.record_items("src", count=10)
        metrics.record_error("src", "timeout")
        with metrics.time_operation("fetch", adapter="src"):
            pass
        metrics.reset()
        summary = metrics.summary()
        assert summary.total_items == 0
        assert summary.total_errors == 0
        assert summary.items_by_source == {}
        assert summary.errors_by_source == {}
        assert summary.operation_times == {}
        assert summary.operation_histograms == {}

    def test_to_dict_matches_summary(self, metrics):
        metrics.record_items("q", count=5)
        d = metrics.to_dict()
        assert d["total_items"] == 5
        assert "operation_histograms" in d

    def test_operation_histograms_populated(self, metrics):
        """time_operation populates operation_histograms in summary."""
        for _ in range(5):
            with metrics.time_operation("fetch", adapter="daily"):
                pass
        summary = metrics.summary()
        hist = summary.operation_histograms.get("fetch.daily")
        assert hist is not None
        assert hist["count"] == 5
        assert hist["min"] >= 0
        assert hist["max"] >= hist["min"]
        assert hist["mean"] >= 0
        assert hist["p50"] >= 0
        assert hist["p95"] >= hist["p50"]
        assert hist["p99"] >= hist["p95"]

    def test_histograms_in_to_dict(self, metrics):
        with metrics.time_operation("parse", adapter="rss"):
            pass
        d = metrics.to_dict()
        assert "parse.rss" in d["operation_histograms"]


# ── _percentile / _histogram helpers ────────────────────────────


class TestPercentileHelper:
    """Tests for the _percentile internal helper."""

    def test_single_value(self):
        from feedspine.metrics.collector import _percentile

        assert _percentile([42.0], 50) == 42.0
        assert _percentile([42.0], 99) == 42.0

    def test_two_values(self):
        from feedspine.metrics.collector import _percentile

        vals = [1.0, 2.0]
        assert _percentile(vals, 50) == 1.0
        assert _percentile(vals, 99) == 2.0

    def test_sorted_input_required(self):
        from feedspine.metrics.collector import _percentile

        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        p50 = _percentile(vals, 50)
        assert p50 == 3.0


class TestHistogramHelper:
    """Tests for the _histogram internal helper."""

    def test_basic_stats(self):
        from feedspine.metrics.collector import _histogram

        h = _histogram([1.0, 2.0, 3.0, 4.0, 5.0])
        assert h["count"] == 5
        assert h["min"] == 1.0
        assert h["max"] == 5.0
        assert h["mean"] == 3.0

    def test_single_value(self):
        from feedspine.metrics.collector import _histogram

        h = _histogram([7.5])
        assert h["count"] == 1
        assert h["min"] == 7.5
        assert h["max"] == 7.5
        assert h["p50"] == 7.5
        assert h["p95"] == 7.5
        assert h["p99"] == 7.5

    def test_all_keys_present(self):
        from feedspine.metrics.collector import _histogram

        h = _histogram([1.0, 2.0])
        expected_keys = {"count", "min", "max", "mean", "p50", "p95", "p99"}
        assert set(h.keys()) == expected_keys
