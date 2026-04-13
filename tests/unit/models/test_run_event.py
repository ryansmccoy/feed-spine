"""Tests for RunEvent and RunEventType."""

from feedspine.models.run_event import RunEvent, RunEventType


class TestRunEventType:
    """Test RunEventType enum."""

    def test_run_lifecycle_events(self):
        """Verify run lifecycle event types exist."""
        assert RunEventType.RUN_STARTED.value == "run_started"
        assert RunEventType.RUN_COMPLETED.value == "run_completed"
        assert RunEventType.RUN_ERROR.value == "run_error"

    def test_fetch_lifecycle_events(self):
        """Verify fetch lifecycle event types exist."""
        assert RunEventType.FETCH_STARTED.value == "fetch_started"
        assert RunEventType.FETCH_COMPLETED.value == "fetch_completed"
        assert RunEventType.FETCH_ERROR.value == "fetch_error"
        assert RunEventType.FETCH_NOT_MODIFIED.value == "fetch_not_modified"

    def test_record_events(self):
        """Verify record event types exist."""
        assert RunEventType.RECORD_CREATED.value == "record_created"
        assert RunEventType.RECORD_UPDATED.value == "record_updated"
        assert RunEventType.RECORD_DUPLICATE.value == "record_duplicate"


class TestRunEvent:
    """Test RunEvent dataclass."""

    def test_basic_creation(self):
        """RunEvent can be created with required fields."""
        event = RunEvent(
            run_id="run-123",
            event_type=RunEventType.RUN_STARTED,
            feed_name="test-feed",
            message="Starting run",
        )

        assert event.run_id == "run-123"
        assert event.event_type == RunEventType.RUN_STARTED
        assert event.feed_name == "test-feed"
        assert event.message == "Starting run"
        assert event.event_id is not None  # Auto-generated
        assert event.timestamp is not None  # Auto-generated

    def test_is_error_property(self):
        """is_error should identify error events."""
        run_error = RunEvent(
            run_id="r1",
            event_type=RunEventType.RUN_ERROR,
            feed_name="f",
            message="err",
        )
        fetch_error = RunEvent(
            run_id="r1",
            event_type=RunEventType.FETCH_ERROR,
            feed_name="f",
            message="err",
        )
        started = RunEvent(
            run_id="r1",
            event_type=RunEventType.RUN_STARTED,
            feed_name="f",
            message="ok",
        )

        assert run_error.is_error is True
        assert fetch_error.is_error is True
        assert started.is_error is False

    def test_is_record_event_property(self):
        """is_record_event should identify record events."""
        created = RunEvent(
            run_id="r1",
            event_type=RunEventType.RECORD_CREATED,
            feed_name="f",
            message="created",
        )
        updated = RunEvent(
            run_id="r1",
            event_type=RunEventType.RECORD_UPDATED,
            feed_name="f",
            message="updated",
        )
        dup = RunEvent(
            run_id="r1",
            event_type=RunEventType.RECORD_DUPLICATE,
            feed_name="f",
            message="dup",
        )
        started = RunEvent(
            run_id="r1",
            event_type=RunEventType.RUN_STARTED,
            feed_name="f",
            message="start",
        )

        assert created.is_record_event is True
        assert updated.is_record_event is True
        assert dup.is_record_event is True
        assert started.is_record_event is False

    def test_to_dict_serialization(self):
        """to_dict should serialize all fields."""
        event = RunEvent(
            run_id="run-123",
            event_type=RunEventType.RECORD_CREATED,
            feed_name="sec-filings",
            message="Created record",
            data={"natural_key": "acc-001"},
        )

        d = event.to_dict()

        assert d["run_id"] == "run-123"
        assert d["event_type"] == "record_created"
        assert d["feed_name"] == "sec-filings"
        assert d["message"] == "Created record"
        assert d["data"] == {"natural_key": "acc-001"}
        assert "timestamp" in d
        assert "event_id" in d

    def test_from_dict_deserialization(self):
        """from_dict should deserialize correctly."""
        data = {
            "event_id": "evt-456",
            "run_id": "run-123",
            "event_type": "run_completed",
            "feed_name": "test",
            "message": "Done",
            "timestamp": "2026-01-15T10:30:00+00:00",
            "data": {"processed": 100},
        }

        event = RunEvent.from_dict(data)

        assert event.event_id == "evt-456"
        assert event.run_id == "run-123"
        assert event.event_type == RunEventType.RUN_COMPLETED
        assert event.feed_name == "test"
        assert event.data == {"processed": 100}


class TestRunEventFactories:
    """Test RunEvent factory methods."""

    def test_run_started_factory(self):
        """run_started should create correct event."""
        event = RunEvent.run_started("run-1", "my-feed", feeds=["a", "b"])

        assert event.run_id == "run-1"
        assert event.event_type == RunEventType.RUN_STARTED
        assert event.feed_name == "my-feed"
        assert "my-feed" in event.message
        assert event.data.get("feeds") == ["a", "b"]

    def test_run_completed_factory(self):
        """run_completed should include stats."""
        event = RunEvent.run_completed(
            "run-1",
            "my-feed",
            processed=100,
            new=80,
            updated=10,
            duplicates=10,
            errors=0,
            duration_ms=1500.5,
        )

        assert event.event_type == RunEventType.RUN_COMPLETED
        assert event.data["processed"] == 100
        assert event.data["new"] == 80
        assert event.data["updated"] == 10
        assert event.data["duplicates"] == 10
        assert event.data["duration_ms"] == 1500.5

    def test_run_error_factory(self):
        """run_error should capture error details."""
        event = RunEvent.run_error(
            "run-1",
            "my-feed",
            error="Connection timeout",
            error_type="TimeoutError",
        )

        assert event.event_type == RunEventType.RUN_ERROR
        assert event.data["error"] == "Connection timeout"
        assert event.data["error_type"] == "TimeoutError"
        assert event.is_error is True

    def test_record_created_factory(self):
        """record_created should capture record info."""
        event = RunEvent.record_created(
            "run-1",
            "my-feed",
            natural_key="acc-001",
            record_id="uuid-123",
        )

        assert event.event_type == RunEventType.RECORD_CREATED
        assert event.data["natural_key"] == "acc-001"
        assert event.data["record_id"] == "uuid-123"
        assert event.is_record_event is True

    def test_record_updated_factory(self):
        """record_updated should capture update info."""
        event = RunEvent.record_updated(
            "run-1",
            "my-feed",
            natural_key="acc-001",
            record_id="uuid-123",
            previous_hash="abc123",
            new_hash="def456",
            version=2,
        )

        assert event.event_type == RunEventType.RECORD_UPDATED
        assert event.data["previous_hash"] == "abc123"
        assert event.data["new_hash"] == "def456"
        assert event.data["version"] == 2

    def test_fetch_not_modified_factory(self):
        """fetch_not_modified for HTTP 304."""
        event = RunEvent.fetch_not_modified(
            "run-1",
            "my-feed",
            url="https://api.example.com/feed",
        )

        assert event.event_type == RunEventType.FETCH_NOT_MODIFIED
        assert event.data.get("url") == "https://api.example.com/feed"
