"""Tests for FeedCollectionService, CollectionOutcomeRecorder, and CollectionEventPublisher."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("spine", reason="spine-core not installed")

from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate
from feedspine.pipeline.stats import PipelineStats
from feedspine.services.collection import CollectionOutcome, FeedCollectionService
from feedspine.services.publishing import CollectionEventPublisher
from feedspine.services.recording import CollectionOutcomeRecorder
from feedspine.storage.memory import MemoryStorage

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class MockFeedAdapter:
    """Minimal feed adapter for testing."""

    def __init__(self, name: str, candidates: list[RecordCandidate] | None = None):
        self._name = name
        self._candidates = candidates or []

    @property
    def name(self) -> str:
        return self._name

    async def fetch(self) -> AsyncIterator[RecordCandidate]:
        for c in self._candidates:
            yield c

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass


class MockEventStore:
    """In-memory EventStore for testing."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._counter = 0

    def append(self, event: dict[str, Any]) -> str:
        self._counter += 1
        event_id = f"evt-{self._counter}"
        event["id"] = event_id
        self.events.append(event)
        return event_id

    def get_since(self, cursor: int) -> list[dict[str, Any]]:
        return self.events[cursor:]


def _make_candidate(key: str, title: str = "Test") -> RecordCandidate:
    return RecordCandidate(
        natural_key=key,
        published_at=datetime.now(UTC),
        content={"title": title},
        metadata=Metadata(source="test-feed"),
    )


def _make_outcome(
    feed_name: str = "test-feed",
    processed: int = 5,
    new: int = 3,
    duplicates: int = 2,
) -> CollectionOutcome:
    return CollectionOutcome(
        feed_name=feed_name,
        stats=PipelineStats(
            feed_name=feed_name,
            processed=processed,
            new=new,
            duplicates=duplicates,
        ),
        records_stored=new,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# CollectionOutcome tests
# ---------------------------------------------------------------------------


class TestCollectionOutcome:
    def test_fields(self) -> None:
        stats = PipelineStats(feed_name="f1", processed=10, new=7, duplicates=3)
        outcome = CollectionOutcome(
            feed_name="f1",
            stats=stats,
            records_stored=7,
        )
        assert outcome.feed_name == "f1"
        assert outcome.records_stored == 7
        assert outcome.stats.processed == 10
        assert outcome.started_at is not None

    def test_frozen(self) -> None:
        outcome = _make_outcome()
        with pytest.raises(AttributeError):
            outcome.feed_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FeedCollectionService tests
# ---------------------------------------------------------------------------


class TestFeedCollectionService:
    @pytest.fixture
    def storage(self) -> MemoryStorage:
        return MemoryStorage()

    @pytest.fixture
    def adapter(self) -> MockFeedAdapter:
        return MockFeedAdapter(
            "test-feed",
            [_make_candidate(f"key-{i}") for i in range(3)],
        )

    @pytest.fixture
    def service(self, storage: MemoryStorage, adapter: MockFeedAdapter) -> FeedCollectionService:
        return FeedCollectionService(
            feed_registry={"test-feed": adapter},
            storage=storage,
        )

    @pytest.mark.asyncio
    async def test_run_collection_basic(self, service: FeedCollectionService, storage: MemoryStorage) -> None:
        await storage.initialize()
        outcome = await service.run_collection("test-feed")
        assert outcome.feed_name == "test-feed"
        assert outcome.stats.processed == 3
        assert outcome.records_stored == 3
        assert outcome.completed_at is not None

    @pytest.mark.asyncio
    async def test_run_collection_unknown_feed(self, service: FeedCollectionService) -> None:
        with pytest.raises(KeyError, match="not-registered"):
            await service.run_collection("not-registered")

    def test_available_feeds(self, service: FeedCollectionService) -> None:
        assert service.available_feeds == ["test-feed"]

    @pytest.mark.asyncio
    async def test_run_collection_empty_feed(self, storage: MemoryStorage) -> None:
        await storage.initialize()
        empty = MockFeedAdapter("empty", [])
        svc = FeedCollectionService(
            feed_registry={"empty": empty},
            storage=storage,
        )
        outcome = await svc.run_collection("empty")
        assert outcome.stats.processed == 0
        assert outcome.records_stored == 0


# ---------------------------------------------------------------------------
# CollectionOutcomeRecorder tests
# ---------------------------------------------------------------------------


class TestCollectionOutcomeRecorder:
    def test_record_advances_watermark(self) -> None:
        from spine.domain.watermarks import WatermarkStore

        wm_store = WatermarkStore()
        recorder = CollectionOutcomeRecorder(watermark_store=wm_store)
        outcome = _make_outcome(feed_name="sec-rss")

        recorder.record(outcome)

        wm = wm_store.get("feed-spine", "collection", "sec-rss")
        assert wm is not None
        assert wm.metadata["records_stored"] == 3
        assert wm.metadata["new"] == 3
        assert wm.metadata["duplicates"] == 2

    def test_record_multiple_feeds(self) -> None:
        from spine.domain.watermarks import WatermarkStore

        wm_store = WatermarkStore()
        recorder = CollectionOutcomeRecorder(watermark_store=wm_store)

        recorder.record(_make_outcome(feed_name="feed-a", new=10))
        recorder.record(_make_outcome(feed_name="feed-b", new=5))

        wm_a = wm_store.get("feed-spine", "collection", "feed-a")
        wm_b = wm_store.get("feed-spine", "collection", "feed-b")
        assert wm_a is not None
        assert wm_b is not None
        assert wm_a.metadata["records_stored"] == 10
        assert wm_b.metadata["records_stored"] == 5


# ---------------------------------------------------------------------------
# CollectionEventPublisher tests
# ---------------------------------------------------------------------------


class TestCollectionEventPublisher:
    def test_publish_completed_emits_event(self) -> None:
        event_store = MockEventStore()
        publisher = CollectionEventPublisher(event_store=event_store)
        outcome = _make_outcome(feed_name="sec-rss", processed=10, new=7)

        event_id = publisher.publish_completed(outcome)

        assert event_id == "evt-1"
        assert len(event_store.events) == 1
        evt = event_store.events[0]
        assert evt["event_type"] == "feed.collection.completed"
        assert evt["source"] == "feed-spine"
        assert evt["data"]["feed_name"] == "sec-rss"
        assert evt["data"]["processed"] == 10
        assert evt["data"]["new"] == 7

    def test_publish_multiple(self) -> None:
        event_store = MockEventStore()
        publisher = CollectionEventPublisher(event_store=event_store)

        publisher.publish_completed(_make_outcome("feed-a"))
        publisher.publish_completed(_make_outcome("feed-b"))

        assert len(event_store.events) == 2
        assert event_store.events[0]["data"]["feed_name"] == "feed-a"
        assert event_store.events[1]["data"]["feed_name"] == "feed-b"
