"""Tests for registration helpers and create_feed_spine factory (Phase 2)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("spine", reason="spine-core not installed")

from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate
from feedspine.storage.memory import MemoryStorage

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
        self.events.append(event)
        return event_id

    def get_since(self, cursor: int) -> list[dict[str, Any]]:
        return self.events[cursor:]


def _make_candidate(key: str) -> RecordCandidate:
    return RecordCandidate(
        natural_key=key,
        published_at=datetime.now(UTC),
        content={"title": key},
        metadata=Metadata(source="test"),
    )


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_feed(self) -> None:
        import sqlite3

        from spine.core.schema_loader import apply_schema
        from spine.data.stores.sqlite.schedule_store import SqliteScheduleStore

        from feedspine.registration import register_feed

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn)
        store = SqliteScheduleStore(conn)

        schedule_id = register_feed(
            store,
            "sec-rss",
            cron_expression="*/30 * * * *",
            priority=200,
        )

        assert schedule_id is not None
        schedule = store.get_by_id(schedule_id)
        assert schedule is not None
        assert schedule["name"] == "feed-collect:sec-rss"
        assert schedule["cron_expression"] == "*/30 * * * *"
        assert schedule["priority"] == 200
        assert schedule["target_name"] == "feed.collect"
        assert schedule["dispatch_type"] == "agent"

    def test_register_enrichment_on_collection(self) -> None:
        import sqlite3

        from spine.core.schema_loader import apply_schema
        from spine.data.stores.sqlite.event_rule_store import SqliteEventRuleStore

        from feedspine.registration import register_enrichment_on_collection

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn)
        store = SqliteEventRuleStore(conn)

        rule_id = register_enrichment_on_collection(
            store,
            feed_name="sec-rss",
            enricher_name="sec-metadata",
        )

        assert rule_id is not None
        # Verify the rule matches the expected event
        matched = store.match({"event_type": "feed.collection.completed"})
        assert len(matched) == 1
        assert matched[0]["name"] == "enrich-on-collect:sec-rss:sec-metadata"
        assert matched[0]["action"] == "CALLBACK"


# ---------------------------------------------------------------------------
# App factory tests
# ---------------------------------------------------------------------------


class TestCreateFeedSpine:
    def test_basic_factory(self) -> None:
        from feedspine.core.app import create_feed_spine

        storage = MemoryStorage()
        app = create_feed_spine(storage)

        assert app.storage is storage
        assert app.collection_service is not None
        assert app.recorder is not None
        assert app.publisher is not None
        assert app.runtime is not None
        assert app.runtime.name == "feed-collection"

    def test_factory_with_event_store(self) -> None:
        from feedspine.core.app import create_feed_spine

        storage = MemoryStorage()
        event_store = MockEventStore()
        app = create_feed_spine(storage, event_store=event_store)

        assert app.publisher is not None
        # Publisher should use our event store
        from feedspine.services.publishing import CollectionEventPublisher

        assert isinstance(app.publisher, CollectionEventPublisher)

    def test_factory_with_feeds(self) -> None:
        from feedspine.core.app import create_feed_spine

        storage = MemoryStorage()
        adapter = MockFeedAdapter("test-feed")
        app = create_feed_spine(storage, feeds={"test-feed": adapter})

        assert "test-feed" in app.feeds
        assert app.collection_service.available_feeds == ["test-feed"]

    def test_register_feed_on_app(self) -> None:
        from feedspine.core.app import create_feed_spine

        storage = MemoryStorage()
        app = create_feed_spine(storage)
        adapter = MockFeedAdapter("my-feed")
        app.register_feed(adapter)

        assert "my-feed" in app.feeds
        # Shared reference — service sees same registry
        assert "my-feed" in app.collection_service.available_feeds

    def test_register_feed_duplicate(self) -> None:
        from feedspine.core.app import create_feed_spine

        storage = MemoryStorage()
        app = create_feed_spine(storage)
        app.register_feed(MockFeedAdapter("dup"))
        with pytest.raises(ValueError, match="dup"):
            app.register_feed(MockFeedAdapter("dup"))

    @pytest.mark.asyncio
    async def test_factory_collection_e2e(self) -> None:
        """End-to-end: factory → register → collect."""
        from feedspine.core.app import create_feed_spine

        storage = MemoryStorage()
        await storage.initialize()
        event_store = MockEventStore()

        app = create_feed_spine(storage, event_store=event_store)
        adapter = MockFeedAdapter(
            "test-feed",
            [_make_candidate(f"k{i}") for i in range(5)],
        )
        app.register_feed(adapter)

        outcome = await app.collection_service.run_collection("test-feed")
        assert outcome.records_stored == 5

        app.recorder.record(outcome)
        app.publisher.publish_completed(outcome)

        assert len(event_store.events) == 1
        assert event_store.events[0]["data"]["feed_name"] == "test-feed"

    def test_runtime_scoring(self) -> None:
        from spine.runtime.requests import AgentRequest

        from feedspine.core.app import create_feed_spine

        storage = MemoryStorage()
        app = create_feed_spine(storage)

        assert app.runtime.score(AgentRequest(name="feed.collect")) == 100
        assert app.runtime.score(AgentRequest(name="other")) == 0


class TestEnrichmentCallbackFactory:
    def test_creates_work_items_from_event(self) -> None:
        import sqlite3

        from spine.core.schema_loader import apply_schema
        from spine.data.stores.sqlite.work_item_store import SqliteWorkItemStore

        from feedspine.registration import enrichment_callback_factory

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn)
        store = SqliteWorkItemStore(conn)

        handler = enrichment_callback_factory(
            store,
            MemoryStorage(),
            "my-enricher",
        )
        event = {
            "event_type": "feed.collection.completed",
            "data": {"feed_name": "sec-rss", "record_ids": ["r1", "r2"]},
        }
        result = handler(event)

        # handler returns empty — items persisted directly
        assert result == []
        # but work items were created
        # list all items from the store
        all_rows = conn.execute("SELECT * FROM core_work_items").fetchall()
        assert len(all_rows) == 2

    def test_no_record_ids_is_noop(self) -> None:
        import sqlite3

        from spine.core.schema_loader import apply_schema
        from spine.data.stores.sqlite.work_item_store import SqliteWorkItemStore

        from feedspine.registration import enrichment_callback_factory

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn)
        store = SqliteWorkItemStore(conn)

        handler = enrichment_callback_factory(
            store,
            MemoryStorage(),
            "my-enricher",
        )
        result = handler({"event_type": "feed.collection.completed", "data": {}})
        assert result == []

        all_rows = conn.execute("SELECT * FROM core_work_items").fetchall()
        assert len(all_rows) == 0


class TestFactoryEnrichmentWiring:
    def test_factory_with_enrichers(self) -> None:
        import sqlite3

        from spine.core.schema_loader import apply_schema
        from spine.data.stores.sqlite.work_item_store import SqliteWorkItemStore

        from feedspine.core.app import create_feed_spine

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn)
        store = SqliteWorkItemStore(conn)

        storage = MemoryStorage()

        class DummyEnricher:
            name = "dummy"

            async def can_enrich(self, record):
                return True

            async def enrich(self, record): ...

        app = create_feed_spine(
            storage,
            work_item_store=store,
            enrichers={"dummy": DummyEnricher()},
        )

        assert "dummy" in app.enrichers
        assert app.enrichment_worker is not None

    def test_factory_without_enrichers_no_worker(self) -> None:
        from feedspine.core.app import create_feed_spine

        storage = MemoryStorage()
        app = create_feed_spine(storage)

        assert app.enrichers == {}
        assert app.enrichment_worker is None
