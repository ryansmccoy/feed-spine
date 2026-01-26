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

from feedspine import (
    ConsoleNotifier,
    Layer,
    MemoryStorage,
    RecordCandidate,
)
from feedspine.protocols.notification import Notification

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

    async def test_create_with_optional_notifier(self):
        """Pipeline can optionally have a notifier."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        notifier = ConsoleNotifier()
        pipeline = Pipeline(storage=storage, notifier=notifier)

        assert pipeline.notifier is notifier

    async def test_create_without_notifier(self):
        """Pipeline works without a notifier."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        pipeline = Pipeline(storage=storage)

        assert pipeline.notifier is None


# =============================================================================
# Pipeline Processing Tests - Core Functionality
# =============================================================================


class TestPipelineProcessing:
    """Test the core record processing flow."""

    async def test_process_single_new_record(self):
        """Processing a new record stores it and returns it."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        candidate = make_candidate("acc-001", title="First Filing")

        result = await pipeline.process(candidate, source="test_feed")

        assert result is not None
        assert result.natural_key == "acc-001"
        assert result.content.get("title") == "First Filing"
        assert result.layer == Layer.BRONZE

    async def test_process_duplicate_returns_none(self):
        """Processing a duplicate returns None (already exists)."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()
        pipeline = Pipeline(storage=storage)

        candidate = make_candidate("acc-001")

        # First time - new record
        result1 = await pipeline.process(candidate, source="feed_a")
        assert result1 is not None

        # Second time - duplicate
        result2 = await pipeline.process(candidate, source="feed_b")
        assert result2 is None

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
        record = await pipeline.process(candidate, source="test")

        assert record.layer == Layer.BRONZE

        # Verify it's queryable from Bronze
        count = await storage.count(layer=Layer.BRONZE)
        assert count == 1


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

        # Track notifications
        notifications = []

        class TrackingNotifier:
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def send(self, n: Notification) -> bool:
                notifications.append(n)
                return True

        pipeline = Pipeline(storage=storage, notifier=TrackingNotifier())

        candidate = make_candidate("acc-001", title="Important Filing")
        await pipeline.process(candidate, source="test")

        assert len(notifications) == 1
        assert (
            "Important Filing" in notifications[0].message or "acc-001" in notifications[0].message
        )

    async def test_does_not_notify_on_duplicate(self):
        """Pipeline should NOT notify for duplicates."""
        from feedspine.pipeline import Pipeline

        storage = MemoryStorage()
        await storage.initialize()

        notifications = []

        class TrackingNotifier:
            async def initialize(self):
                pass

            async def close(self):
                pass

            async def send(self, n: Notification) -> bool:
                notifications.append(n)
                return True

        pipeline = Pipeline(storage=storage, notifier=TrackingNotifier())

        candidate = make_candidate("acc-001")
        await pipeline.process(candidate, source="feed_a")  # New - notifies
        await pipeline.process(candidate, source="feed_b")  # Duplicate - no notify

        assert len(notifications) == 1  # Only one notification


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
            duplicates=20,
            errors=0,
            duration_ms=150.5,
        )

        assert stats.feed_name == "test_feed"
        assert stats.processed == 100
        assert stats.new == 80
        assert stats.duplicates == 20
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
