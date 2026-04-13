"""Tests for FeedRunProjection."""

from __future__ import annotations

import json

import pytest

from feedspine.models.feed_run import FeedRunProjection, _map_state


class TestMapState:
    """Test state mapping from WorkItem states to user-facing statuses."""

    @pytest.mark.parametrize(
        ("wi_state", "expected"),
        [
            ("QUEUED", "QUEUED"),
            ("LEASED", "RUNNING"),
            ("SUCCEEDED", "SUCCEEDED"),
            ("DEAD_LETTERED", "FAILED"),
            ("CANCELLED", "CANCELLED"),
        ],
    )
    def test_known_states(self, wi_state: str, expected: str) -> None:
        assert _map_state(wi_state) == expected

    def test_unknown_state_passthrough(self) -> None:
        assert _map_state("UNKNOWN_STATE") == "UNKNOWN_STATE"


class TestFeedRunProjectionFromWorkItem:
    """Test FeedRunProjection.from_work_item()."""

    def _make_item(self, **overrides) -> dict:
        base = {
            "id": 42,
            "domain": "feed-spine",
            "workflow": "feed.collect",
            "partition_key": "sec-rss",
            "state": "QUEUED",
            "params_json": json.dumps({"feed_name": "sec-rss"}),
            "result_json": None,
            "locked_at": None,
            "completed_at": None,
            "last_error": None,
        }
        base.update(overrides)
        return base

    def test_queued_item(self) -> None:
        item = self._make_item()
        proj = FeedRunProjection.from_work_item(item)

        assert proj.work_item_id == 42
        assert proj.feed_name == "sec-rss"
        assert proj.status == "QUEUED"
        assert proj.started_at is None
        assert proj.completed_at is None
        assert proj.items_processed == 0
        assert proj.items_new == 0

    def test_succeeded_with_result_json(self) -> None:
        result = {
            "feed_name": "sec-rss",
            "processed": 100,
            "new": 25,
            "duplicates": 70,
            "errors": 5,
            "duration_ms": 1500.0,
        }
        item = self._make_item(
            state="SUCCEEDED",
            result_json=json.dumps(result),
            locked_at="2025-01-01T10:00:00Z",
            completed_at="2025-01-01T10:00:02Z",
        )
        proj = FeedRunProjection.from_work_item(item)

        assert proj.status == "SUCCEEDED"
        assert proj.items_processed == 100
        assert proj.items_new == 25
        assert proj.items_duplicate == 70
        assert proj.items_failed == 5
        assert proj.started_at == "2025-01-01T10:00:00Z"
        assert proj.completed_at == "2025-01-01T10:00:02Z"

    def test_records_stored_fallback(self) -> None:
        """result_json may use records_stored instead of new."""
        result = {"processed": 10, "records_stored": 8, "duplicates": 2, "errors": 0}
        item = self._make_item(
            state="SUCCEEDED",
            result_json=json.dumps(result),
        )
        proj = FeedRunProjection.from_work_item(item)
        assert proj.items_new == 8

    def test_failed_item_with_error(self) -> None:
        item = self._make_item(
            state="DEAD_LETTERED",
            last_error="Connection timeout",
            locked_at="2025-01-01T10:00:00Z",
        )
        proj = FeedRunProjection.from_work_item(item)

        assert proj.status == "FAILED"
        assert proj.errors == "Connection timeout"

    def test_params_json_as_dict(self) -> None:
        """params_json may already be parsed as dict."""
        item = self._make_item(params_json={"feed_name": "polygon"})
        proj = FeedRunProjection.from_work_item(item)
        assert proj.feed_name == "polygon"

    def test_result_json_as_dict(self) -> None:
        """result_json may already be parsed as dict."""
        item = self._make_item(
            state="SUCCEEDED",
            result_json={"processed": 5, "new": 3, "duplicates": 2, "errors": 0},
        )
        proj = FeedRunProjection.from_work_item(item)
        assert proj.items_processed == 5

    def test_missing_params_json(self) -> None:
        item = self._make_item(params_json=None)
        proj = FeedRunProjection.from_work_item(item)
        assert proj.feed_name == "unknown"

    def test_frozen(self) -> None:
        item = self._make_item()
        proj = FeedRunProjection.from_work_item(item)
        with pytest.raises(AttributeError):
            proj.status = "RUNNING"  # type: ignore[misc]
