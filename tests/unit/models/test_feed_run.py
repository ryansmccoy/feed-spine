"""Tests for feedspine.models.feed_run - FeedRun operational tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from feedspine.models.feed_run import FeedRun, FeedRunStatus


class TestFeedRunCreation:
    """Tests for FeedRun creation."""

    def test_create_minimal(self) -> None:
        """Can create with just feed_name."""
        run = FeedRun(feed_name="my-feed")
        assert run.feed_name == "my-feed"
        assert run.status == FeedRunStatus.PENDING
        assert run.items_processed == 0
        assert run.id is not None

    def test_create_with_all_fields(self) -> None:
        """Can create with all optional fields."""
        now = datetime.now(UTC)
        run = FeedRun(
            id="run-123",
            feed_name="sec-daily",
            status=FeedRunStatus.SUCCESS,
            started_at=now,
            completed_at=now + timedelta(seconds=10),
            items_processed=100,
            items_new=80,
            items_duplicate=20,
            items_failed=0,
            errors=["warning: slow response"],
            metadata={"source_url": "https://example.com"},
        )
        assert run.id == "run-123"
        assert run.items_new == 80
        assert run.items_duplicate == 20

    def test_feed_name_required(self) -> None:
        """feed_name is required."""
        with pytest.raises(Exception):
            FeedRun()  # type: ignore[call-arg]

    def test_feed_name_cannot_be_empty(self) -> None:
        """feed_name cannot be empty string."""
        with pytest.raises(ValueError):
            FeedRun(feed_name="   ")


class TestFeedRunStatus:
    """Tests for FeedRunStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """All expected statuses exist."""
        assert FeedRunStatus.PENDING.value == "pending"
        assert FeedRunStatus.RUNNING.value == "running"
        assert FeedRunStatus.SUCCESS.value == "success"
        assert FeedRunStatus.FAILED.value == "failed"
        assert FeedRunStatus.CANCELLED.value == "cancelled"

    def test_status_from_string(self) -> None:
        """Can create status from string."""
        assert FeedRunStatus("running") == FeedRunStatus.RUNNING
        assert FeedRunStatus("success") == FeedRunStatus.SUCCESS


class TestFeedRunProperties:
    """Tests for FeedRun computed properties."""

    def test_is_complete_pending(self) -> None:
        """PENDING is not complete."""
        run = FeedRun(feed_name="test", status=FeedRunStatus.PENDING)
        assert run.is_complete is False

    def test_is_complete_running(self) -> None:
        """RUNNING is not complete."""
        run = FeedRun(feed_name="test", status=FeedRunStatus.RUNNING)
        assert run.is_complete is False

    def test_is_complete_success(self) -> None:
        """SUCCESS is complete."""
        run = FeedRun(feed_name="test", status=FeedRunStatus.SUCCESS)
        assert run.is_complete is True

    def test_is_complete_failed(self) -> None:
        """FAILED is complete."""
        run = FeedRun(feed_name="test", status=FeedRunStatus.FAILED)
        assert run.is_complete is True

    def test_is_complete_cancelled(self) -> None:
        """CANCELLED is complete."""
        run = FeedRun(feed_name="test", status=FeedRunStatus.CANCELLED)
        assert run.is_complete is True

    def test_is_success(self) -> None:
        """is_success property."""
        assert FeedRun(feed_name="test", status=FeedRunStatus.SUCCESS).is_success is True
        assert FeedRun(feed_name="test", status=FeedRunStatus.FAILED).is_success is False

    def test_is_failure(self) -> None:
        """is_failure property."""
        assert FeedRun(feed_name="test", status=FeedRunStatus.FAILED).is_failure is True
        assert FeedRun(feed_name="test", status=FeedRunStatus.SUCCESS).is_failure is False

    def test_duration_seconds_incomplete(self) -> None:
        """Duration is None when not completed."""
        run = FeedRun(feed_name="test", status=FeedRunStatus.RUNNING)
        assert run.duration_seconds is None

    def test_duration_seconds_complete(self) -> None:
        """Duration is calculated when completed."""
        start = datetime.now(UTC)
        end = start + timedelta(seconds=42.5)
        run = FeedRun(
            feed_name="test",
            status=FeedRunStatus.SUCCESS,
            started_at=start,
            completed_at=end,
        )
        assert run.duration_seconds == 42.5

    def test_success_rate_no_failures(self) -> None:
        """100% success rate when no failures."""
        run = FeedRun(feed_name="test", items_processed=100, items_failed=0)
        assert run.success_rate == 1.0

    def test_success_rate_with_failures(self) -> None:
        """Calculates success rate correctly."""
        run = FeedRun(feed_name="test", items_processed=100, items_failed=10)
        assert run.success_rate == 0.9

    def test_success_rate_empty(self) -> None:
        """Success rate is 1.0 when nothing processed."""
        run = FeedRun(feed_name="test", items_processed=0)
        assert run.success_rate == 1.0

    def test_dedup_rate_none(self) -> None:
        """Dedup rate is 0.0 when no duplicates."""
        run = FeedRun(feed_name="test", items_processed=100, items_duplicate=0)
        assert run.dedup_rate == 0.0

    def test_dedup_rate_all(self) -> None:
        """Dedup rate is 1.0 when all duplicates."""
        run = FeedRun(feed_name="test", items_processed=100, items_duplicate=100)
        assert run.dedup_rate == 1.0

    def test_dedup_rate_empty(self) -> None:
        """Dedup rate is 0.0 when nothing processed."""
        run = FeedRun(feed_name="test", items_processed=0)
        assert run.dedup_rate == 0.0


class TestFeedRunStateTransitions:
    """Tests for FeedRun state transition methods."""

    def test_start(self) -> None:
        """start() transitions to RUNNING."""
        run = FeedRun(feed_name="test")
        started = run.start()
        assert started.status == FeedRunStatus.RUNNING
        assert started.started_at is not None
        # Original unchanged
        assert run.status == FeedRunStatus.PENDING

    def test_complete(self) -> None:
        """complete() transitions to SUCCESS with counts."""
        run = FeedRun(feed_name="test").start()
        completed = run.complete(
            items_processed=100,
            items_new=80,
            items_duplicate=20,
            items_failed=0,
        )
        assert completed.status == FeedRunStatus.SUCCESS
        assert completed.completed_at is not None
        assert completed.items_processed == 100
        assert completed.items_new == 80

    def test_fail(self) -> None:
        """fail() transitions to FAILED with error."""
        run = FeedRun(feed_name="test").start()
        failed = run.fail("Connection refused", "ConnectionError")
        assert failed.status == FeedRunStatus.FAILED
        assert failed.completed_at is not None
        assert "Connection refused" in failed.errors
        assert failed.error_type == "ConnectionError"

    def test_cancel(self) -> None:
        """cancel() transitions to CANCELLED."""
        run = FeedRun(feed_name="test").start()
        cancelled = run.cancel("User requested")
        assert cancelled.status == FeedRunStatus.CANCELLED
        assert cancelled.completed_at is not None
        assert "Cancelled: User requested" in cancelled.errors

    def test_cancel_without_reason(self) -> None:
        """cancel() works without reason."""
        run = FeedRun(feed_name="test").start()
        cancelled = run.cancel()
        assert cancelled.status == FeedRunStatus.CANCELLED

    def test_update_progress(self) -> None:
        """update_progress() updates counters."""
        run = FeedRun(feed_name="test").start()
        updated = run.update_progress(
            items_processed=50,
            items_new=40,
            checkpoint_position={"page": 5},
        )
        assert updated.items_processed == 50
        assert updated.items_new == 40
        assert updated.checkpoint_position == {"page": 5}

    def test_update_progress_partial(self) -> None:
        """update_progress() can update single fields."""
        run = FeedRun(
            feed_name="test",
            items_processed=10,
            items_new=8,
        ).start()
        updated = run.update_progress(items_processed=20)
        assert updated.items_processed == 20
        assert updated.items_new == 8  # Unchanged


class TestFeedRunSerialization:
    """Tests for FeedRun serialization."""

    def test_to_dict(self) -> None:
        """to_dict() produces serializable dictionary."""
        run = FeedRun(
            feed_name="test",
            status=FeedRunStatus.SUCCESS,
            items_processed=100,
        )
        d = run.to_dict()
        assert d["feed_name"] == "test"
        assert d["status"] == "success"
        assert d["items_processed"] == 100
        assert "started_at" in d

    def test_from_dict(self) -> None:
        """from_dict() recreates FeedRun."""
        original = FeedRun(
            feed_name="test",
            status=FeedRunStatus.SUCCESS,
            items_processed=100,
        )
        d = original.to_dict()
        restored = FeedRun.from_dict(d)
        assert restored.feed_name == original.feed_name
        assert restored.status == original.status
        assert restored.items_processed == original.items_processed

    def test_from_dict_minimal(self) -> None:
        """from_dict() works with minimal data."""
        data = {
            "feed_name": "test",
            "started_at": "2024-01-01T00:00:00+00:00",
        }
        run = FeedRun.from_dict(data)
        assert run.feed_name == "test"
        assert run.status == FeedRunStatus.PENDING

    def test_roundtrip_preserves_data(self) -> None:
        """to_dict() -> from_dict() preserves all fields."""
        original = FeedRun(feed_name="test").start()
        completed = original.complete(items_processed=50, items_new=30)
        d = completed.to_dict()
        restored = FeedRun.from_dict(d)
        assert restored.feed_name == completed.feed_name
        assert restored.items_processed == completed.items_processed
        assert restored.items_new == completed.items_new
