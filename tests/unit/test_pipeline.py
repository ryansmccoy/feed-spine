"""Tests for the FeedSpine Pipeline - TDD approach.

These tests define how the pipeline SHOULD work. We write tests first,
then implement the functionality to make them pass.

The Pipeline is the core orchestrator that:
1. Fetches records from feed adapters
2. Deduplicates using natural keys
3. Stores new records
4. Tracks sightings for duplicates
5. Optionally notifies on new records
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

pytest.importorskip("spine", reason="spine-core not installed")
from spine.events import EventBus

from feedspine import (
    Layer,
    MemoryStorage,
    RecordCandidate,
)

# =============================================================================
# Test Fixtures - Simple Feed Adapter for Testing
# =============================================================================


class MockFeedAdapter:
    """A simple feed adapter for testing."""

    def __init__(self, name: str, candidates: list[RecordCandidate]):
        self._name = name
        self._candidates = candidates
        self._initialized = False

    @property
    def name(self) -> str:
        return self._name

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        for candidate in self._candidates:
            yield candidate

    async def initialize(self) -> None:
        self._initialized = True

    async def close(self) -> None:
        self._initialized = False


def make_candidate(
    natural_key: str,
    title: str = "Test Record",
    source: str = "test_feed",
) -> RecordCandidate:
    """Helper to create test candidates."""
    from feedspine.models.base import Metadata

    return RecordCandidate(
        natural_key=natural_key,
        published_at=datetime.now(UTC),
        content={"title": title},
        metadata=Metadata(source=source),
    )


# =============================================================================
# Pipeline Creation Tests
# =============================================================================


class TestPipelineCreation:
    """Test Pipeline instantiation and configuration."""

    async def test_create_with_storage(self):
        """Pipeline requires a storage backend."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        pipeline = Pipeline(storage=storage)

        assert pipeline.storage is storage

    async def test_create_with_optional_event_bus(self):
        """Pipeline can optionally have an event bus."""
        from unittest.mock import MagicMock

        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        event_bus = MagicMock(spec=EventBus)
        pipeline = Pipeline(storage=storage, event_bus=event_bus)

        assert pipeline.event_bus is event_bus

    async def test_create_without_event_bus(self):
        """Pipeline works without an event bus."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        pipeline = Pipeline(storage=storage)

        assert pipeline.event_bus is None


# =============================================================================
# Pipeline Processing Tests - Core Functionality
# =============================================================================


class TestPipelineProcessing:
    """Test the core record processing flow."""

    async def test_process_single_new_record(self):
        """Processing a new record stores it and returns ProcessResult with CREATED action."""
        from feedspine.pipeline import Pipeline, ProcessAction

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        candidate = make_candidate("acc-001", title="First Filing")

        result = await pipeline.process(candidate, source="test_feed")

        assert result is not None
        assert result.action == ProcessAction.CREATED
        assert result.is_new is True
        assert result.record.natural_key == "acc-001"
        assert result.record.content.get("title") == "First Filing"
        assert result.record.layer == Layer.BRONZE

    async def test_process_duplicate_returns_duplicate_action(self):
        """Processing a duplicate returns ProcessResult with DUPLICATE action."""
        from feedspine.pipeline import Pipeline, ProcessAction

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        candidate = make_candidate("acc-001")

        # First time - new record
        result1 = await pipeline.process(candidate, source="feed_a")
        assert result1.action == ProcessAction.CREATED
        assert result1.is_new is True

        # Second time - duplicate (same content)
        result2 = await pipeline.process(candidate, source="feed_b")
        assert result2.action == ProcessAction.DUPLICATE
        assert result2.is_duplicate is True
        assert result2.record.id == result1.record.id  # Same record

    async def test_process_duplicate_records_sighting(self):
        """Duplicate records should have sightings tracked."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        candidate = make_candidate("acc-001")

        await pipeline.process(candidate, source="feed_a")
        await pipeline.process(candidate, source="feed_b")
        await pipeline.process(candidate, source="feed_c")

        # Should have 3 sightings (using natural_key, not record.id)
        sightings = await storage.get_sightings("acc-001")

        assert len(sightings) == 3
        sources = {s.source for s in sightings}
        assert sources == {"feed_a", "feed_b", "feed_c"}

    async def test_process_stores_in_bronze_layer(self):
        """New records are stored in Bronze layer."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        candidate = make_candidate("acc-001")
        result = await pipeline.process(candidate, source="test")

        assert result.record.layer == Layer.BRONZE

        # Verify it's queryable from Bronze
        count = await storage.count(layer=Layer.BRONZE)
        assert count == 1

    async def test_process_detects_content_update(self):
        """Same natural_key with different content should trigger UPDATE."""
        from feedspine.pipeline import Pipeline, ProcessAction

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        # Original record
        candidate1 = make_candidate("acc-001", title="Original Title")
        result1 = await pipeline.process(candidate1, source="feed_a")
        assert result1.action == ProcessAction.CREATED
        original_hash = result1.record.content_hash

        # Same natural_key but different content (title changed)
        candidate2 = make_candidate("acc-001", title="Updated Title")
        result2 = await pipeline.process(candidate2, source="feed_b")

        assert result2.action == ProcessAction.UPDATED
        assert result2.is_update is True
        assert result2.previous_content_hash == original_hash
        assert result2.record.content_hash != original_hash
        assert result2.record.content_version == 2
        assert result2.record.content.get("title") == "Updated Title"

    async def test_process_update_preserves_record_id(self):
        """UPDATE should preserve the original record ID."""
        from feedspine.pipeline import Pipeline, ProcessAction

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        candidate1 = make_candidate("acc-001", title="V1")
        result1 = await pipeline.process(candidate1, source="feed")
        original_id = result1.record.id

        candidate2 = make_candidate("acc-001", title="V2")
        result2 = await pipeline.process(candidate2, source="feed")

        assert result2.action == ProcessAction.UPDATED
        assert result2.record.id == original_id  # Same record ID


# =============================================================================
# Pipeline Run Tests - Feed Adapter Integration
# =============================================================================


class TestPipelineRun:
    """Test running pipeline with feed adapters."""

    async def test_run_processes_all_candidates(self):
        """Run should process all candidates from a feed."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        candidates = [
            make_candidate("acc-001", "Filing 1"),
            make_candidate("acc-002", "Filing 2"),
            make_candidate("acc-003", "Filing 3"),
        ]
        feed = MockFeedAdapter("test_feed", candidates)

        stats = await pipeline.run(feed)

        assert stats.processed == 3
        assert stats.new == 3
        assert stats.duplicates == 0

    async def test_run_counts_duplicates(self):
        """Run should count duplicates separately."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        # First feed
        feed1 = MockFeedAdapter(
            "feed_a",
            [
                make_candidate("acc-001"),
                make_candidate("acc-002"),
            ],
        )

        # Second feed with one duplicate
        feed2 = MockFeedAdapter(
            "feed_b",
            [
                make_candidate("acc-002"),  # duplicate
                make_candidate("acc-003"),  # new
            ],
        )

        await pipeline.run(feed1)
        stats = await pipeline.run(feed2)

        assert stats.processed == 2
        assert stats.new == 1
        assert stats.duplicates == 1

    async def test_run_returns_stats(self):
        """Run should return comprehensive statistics."""
        from feedspine.pipeline import Pipeline, PipelineStats

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        feed = MockFeedAdapter("test", [make_candidate("acc-001")])
        stats = await pipeline.run(feed)

        assert isinstance(stats, PipelineStats)
        assert stats.feed_name == "test"
        assert stats.processed >= 0
        assert stats.new >= 0
        assert stats.duplicates >= 0
        assert stats.errors >= 0
        assert stats.duration_ms >= 0

    async def test_run_handles_empty_feed(self):
        """Run should handle feeds with no candidates."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        empty_feed = MockFeedAdapter("empty", [])
        stats = await pipeline.run(empty_feed)

        assert stats.processed == 0
        assert stats.new == 0


# =============================================================================
# Pipeline Error Handling Tests
# =============================================================================


class TestPipelineErrorHandling:
    """Test pipeline error handling."""

    async def test_process_invalid_candidate_raises(self):
        """Processing invalid candidate should raise."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        # None should raise
        with pytest.raises((TypeError, ValueError)):
            await pipeline.process(None, source="test")

    async def test_run_continues_on_single_error(self):
        """Run should continue processing after single errors."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        # Mix of valid and problematic candidates handled gracefully
        candidates = [
            make_candidate("acc-001"),
            make_candidate("acc-002"),
        ]
        feed = MockFeedAdapter("test", candidates)

        stats = await pipeline.run(feed)

        # Should process what it can
        assert stats.processed == 2


# =============================================================================
# Pipeline Notification Tests
# =============================================================================


class TestPipelineNotifications:
    """Test pipeline notification integration."""

    async def test_notifies_on_new_record(self):
        """Pipeline should notify when new record is stored."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()

        # Track events
        events = []

        class TrackingEventBus:
            def __init__(self):
                self.handlers = {}

            def subscribe(self, event_type, handler):
                pass

            def unsubscribe(self, event_type, handler):
                pass

            async def publish(self, event) -> None:
                events.append(event)

            async def shutdown(self):
                pass

        pipeline = Pipeline(storage=storage, event_bus=TrackingEventBus())

        candidate = make_candidate("acc-001", title="Important Filing")
        await pipeline.process(candidate, source="test")

        assert len(events) == 1
        assert events[0].event_type == "feed.record.created"
        assert events[0].payload["natural_key"] == "acc-001"
        assert events[0].payload["title"] == "Important Filing"

    async def test_does_not_notify_on_duplicate(self):
        """Pipeline should NOT notify for duplicates."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()

        events = []

        class TrackingEventBus:
            def __init__(self):
                self.handlers = {}

            def subscribe(self, event_type, handler):
                pass

            def unsubscribe(self, event_type, handler):
                pass

            async def publish(self, event) -> None:
                events.append(event)

            async def shutdown(self):
                pass

        pipeline = Pipeline(storage=storage, event_bus=TrackingEventBus())

        candidate = make_candidate("acc-001")
        await pipeline.process(candidate, source="feed_a")  # New - notifies
        await pipeline.process(candidate, source="feed_b")  # Duplicate - no notify

        assert len(events) == 1  # Only one tracking event


# =============================================================================
# PipelineStats Tests
# =============================================================================


class TestPipelineStats:
    """Test PipelineStats dataclass."""

    def test_stats_creation(self):
        """PipelineStats should be creatable with all fields."""
        from feedspine.pipeline import PipelineStats

        stats = PipelineStats(
            feed_name="test_feed",
            processed=100,
            new=80,
            duplicates=15,
            updated=5,
            errors=0,
            duration_ms=150.5,
        )

        assert stats.feed_name == "test_feed"
        assert stats.processed == 100
        assert stats.new == 80
        assert stats.duplicates == 15
        assert stats.updated == 5
        assert stats.errors == 0
        assert stats.duration_ms == 150.5

    def test_stats_dedup_rate(self):
        """PipelineStats should calculate dedup rate."""
        from feedspine.pipeline import PipelineStats

        stats = PipelineStats(
            feed_name="test",
            processed=100,
            new=75,
            duplicates=25,
            errors=0,
            duration_ms=100,
        )

        assert stats.dedup_rate == 0.25  # 25% were duplicates

    def test_stats_update_rate(self):
        """PipelineStats should calculate update rate."""
        from feedspine.pipeline import PipelineStats

        stats = PipelineStats(
            feed_name="test",
            processed=100,
            new=70,
            duplicates=20,
            updated=10,
            errors=0,
            duration_ms=100,
        )

        assert stats.update_rate == 0.10  # 10% were updates

    def test_stats_dedup_rate_zero_processed(self):
        """Dedup rate should handle zero processed."""
        from feedspine.pipeline import PipelineStats

        stats = PipelineStats(
            feed_name="test",
            processed=0,
            new=0,
            duplicates=0,
            errors=0,
            duration_ms=0,
        )

        assert stats.dedup_rate == 0.0
        assert stats.update_rate == 0.0
