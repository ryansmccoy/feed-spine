"""Tests for FeedCollectionRuntime (Phase 2)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("spine", reason="spine-core not installed")
from spine.runtime.lifecycle import ExecutionState
from spine.runtime.requests import AgentRequest, CallableRequest, RequestEnvelope

from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate
from feedspine.services.collection import FeedCollectionService
from feedspine.services.publishing import CollectionEventPublisher
from feedspine.services.recording import CollectionOutcomeRecorder
from feedspine.storage.memory import MemoryStorage
from feedspine.workflows.collect import FeedCollectionRuntime

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class MockFeedAdapter:
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


def _make_candidate(key: str) -> RecordCandidate:
    return RecordCandidate(
        natural_key=key,
        published_at=datetime.now(UTC),
        content={"title": f"Record {key}"},
        metadata=Metadata(source="test"),
    )


# ---------------------------------------------------------------------------
# FeedCollectionRuntime tests
# ---------------------------------------------------------------------------


class TestFeedCollectionRuntime:
    @pytest.fixture
    async def runtime(self) -> FeedCollectionRuntime:
        from spine.domain.watermarks import WatermarkStore

        storage = MemoryStorage()
        await storage.initialize()
        adapter = MockFeedAdapter("test-feed", [_make_candidate(f"k{i}") for i in range(3)])
        event_store = MockEventStore()

        service = FeedCollectionService(
            feed_registry={"test-feed": adapter},
            storage=storage,
        )
        recorder = CollectionOutcomeRecorder(watermark_store=WatermarkStore())
        publisher = CollectionEventPublisher(event_store=event_store)

        return FeedCollectionRuntime(
            collection_service=service,
            recorder=recorder,
            publisher=publisher,
        )

    def test_name(self, runtime: FeedCollectionRuntime) -> None:
        assert runtime.name == "feed-collection"

    def test_score_feed_collect(self, runtime: FeedCollectionRuntime) -> None:
        req = AgentRequest(name="feed.collect")
        assert runtime.score(req) == 100

    def test_score_other(self, runtime: FeedCollectionRuntime) -> None:
        req = AgentRequest(name="feed.enrich")
        assert runtime.score(req) == 0

    def test_score_callable(self, runtime: FeedCollectionRuntime) -> None:
        req = CallableRequest(name="something-else")
        assert runtime.score(req) == 0

    @pytest.mark.asyncio
    async def test_submit_and_status(self, runtime: FeedCollectionRuntime) -> None:
        req = AgentRequest(
            name="feed.collect",
            params={"feed_name": "test-feed"},
        )
        handle = await runtime.submit(req)

        assert handle.runtime_name == "feed-collection"
        assert handle.request_name == "feed.collect"

        # Wait for the task to complete
        await asyncio.sleep(0.1)

        status = await runtime.status(handle)
        assert status.state == ExecutionState.COMPLETED
        assert status.output is not None
        assert status.output["feed_name"] == "test-feed"
        assert status.output["processed"] == 3
        assert status.output["records_stored"] == 3

    @pytest.mark.asyncio
    async def test_submit_with_envelope_params(self, runtime: FeedCollectionRuntime) -> None:
        req = AgentRequest(
            name="feed.collect",
            envelope=RequestEnvelope(params={"feed_name": "test-feed"}),
        )
        handle = await runtime.submit(req)
        await asyncio.sleep(0.1)

        status = await runtime.status(handle)
        assert status.state == ExecutionState.COMPLETED

    @pytest.mark.asyncio
    async def test_submit_missing_feed_name(self, runtime: FeedCollectionRuntime) -> None:
        req = AgentRequest(name="feed.collect", params={})
        with pytest.raises(ValueError, match="feed_name"):
            await runtime.submit(req)

    @pytest.mark.asyncio
    async def test_submit_unknown_feed(self, runtime: FeedCollectionRuntime) -> None:
        req = AgentRequest(
            name="feed.collect",
            params={"feed_name": "nonexistent"},
        )
        handle = await runtime.submit(req)
        await asyncio.sleep(0.1)

        status = await runtime.status(handle)
        assert status.state == ExecutionState.FAILED
        assert "nonexistent" in (status.error or "")

    @pytest.mark.asyncio
    async def test_status_unknown_handle(self, runtime: FeedCollectionRuntime) -> None:
        from spine.runtime.lifecycle import ExecutionHandle

        handle = ExecutionHandle.create(
            runtime_name="feed-collection",
            external_ref="unknown",
            request_name="feed.collect",
        )
        status = await runtime.status(handle)
        assert status.state == ExecutionState.FAILED

    @pytest.mark.asyncio
    async def test_cancel_running(self, runtime: FeedCollectionRuntime) -> None:
        """Cancel a task that hasn't completed yet."""
        from spine.domain.watermarks import WatermarkStore

        # Use an adapter that blocks long enough to be cancelled
        class SlowAdapter:
            @property
            def name(self) -> str:
                return "slow"

            async def fetch(self) -> AsyncIterator[RecordCandidate]:
                await asyncio.sleep(10)
                yield _make_candidate("never")  # pragma: no cover

            async def initialize(self) -> None:
                pass

            async def close(self) -> None:
                pass

        storage = MemoryStorage()
        await storage.initialize()
        service = FeedCollectionService(
            feed_registry={"slow": SlowAdapter()},
            storage=storage,
        )
        rt = FeedCollectionRuntime(
            collection_service=service,
            recorder=CollectionOutcomeRecorder(watermark_store=WatermarkStore()),
            publisher=CollectionEventPublisher(event_store=MockEventStore()),
        )

        req = AgentRequest(name="feed.collect", params={"feed_name": "slow"})
        handle = await rt.submit(req)

        # Give task a moment to start
        await asyncio.sleep(0.01)

        cancelled = await rt.cancel(handle)
        assert cancelled is True

        await asyncio.sleep(0.05)
        status = await rt.status(handle)
        assert status.state == ExecutionState.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed(self, runtime: FeedCollectionRuntime) -> None:
        req = AgentRequest(
            name="feed.collect",
            params={"feed_name": "test-feed"},
        )
        handle = await runtime.submit(req)
        await asyncio.sleep(0.1)

        cancelled = await runtime.cancel(handle)
        assert cancelled is False
