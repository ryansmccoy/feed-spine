"""Tests for feedspine.reporter module.

Covers SimpleProgressReporter lifecycle (start/report/finish).
"""

from __future__ import annotations

from feedspine.reporter.simple import SimpleProgressReporter


class TestSimpleProgressReporter:
    """Tests for the SimpleProgressReporter."""

    def test_construction(self):
        reporter = SimpleProgressReporter()
        assert reporter is not None

    def test_start(self):
        reporter = SimpleProgressReporter()
        reporter.start()  # should not raise

    def test_finish_success(self):
        reporter = SimpleProgressReporter()
        reporter.start()
        reporter.finish(success=True)  # should not raise

    def test_finish_failure(self):
        reporter = SimpleProgressReporter()
        reporter.start()
        reporter.finish(success=False)  # should not raise
