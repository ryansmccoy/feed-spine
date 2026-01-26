"""Tests for feed composition pattern."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.composition import Feed, FeedConfig, collect
from feedspine.composition.preset import MinimalPreset, Preset
from feedspine.composition.testing import (
    MockAdapter,
    MockEnricher,
)
from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate
from feedspine.storage.memory import MemoryStorage


def make_metadata() -> Metadata:
    """Create test metadata."""
    return Metadata(source="test")


def make_candidate(natural_key: str, **content: object) -> RecordCandidate:
    """Create a test RecordCandidate."""
    return RecordCandidate(
        natural_key=natural_key,
        published_at=datetime.now(UTC),
        metadata=make_metadata(),
        content=dict(content),
    )


class TestFeedConfigBasic:
    """Tests for FeedConfig creation."""

    def test_create_minimal(self) -> None:
        """Test creating minimal config."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()

        config = FeedConfig(adapter=adapter, storage=storage)

        assert config.adapter is adapter
        assert config.storage is storage
        assert config.enrichers == ()
        assert config.rate_limit is None
        assert config.concurrency == 1

    def test_create_with_options(self) -> None:
        """Test creating config with options."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        enrichers = [MockEnricher()]

        config = FeedConfig(
            adapter=adapter,
            storage=storage,
            enrichers=enrichers,
            rate_limit=10.0,
            batch_size=50,
        )

        assert config.rate_limit == 10.0
        assert config.batch_size == 50
        assert len(config.enrichers) == 1

    def test_frozen_immutable(self) -> None:
        """Test that config is immutable."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        config = FeedConfig(adapter=adapter, storage=storage)

        with pytest.raises(AttributeError):
            config.rate_limit = 5.0  # type: ignore[misc]


class TestFeedConfigWithMethods:
    """Tests for FeedConfig with_* methods."""

    def test_with_enricher(self) -> None:
        """Test adding enricher returns new config."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        config = FeedConfig(adapter=adapter, storage=storage)
        enricher = MockEnricher()

        config2 = config.with_enricher(enricher)

        assert len(config.enrichers) == 0  # Original unchanged
        assert len(config2.enrichers) == 1
        assert config2.enrichers[0] is enricher

    def test_with_enrichers_multiple(self) -> None:
        """Test adding multiple enrichers."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        config = FeedConfig(adapter=adapter, storage=storage)

        config2 = config.with_enrichers(MockEnricher(), MockEnricher())

        assert len(config2.enrichers) == 2

    def test_with_rate_limit(self) -> None:
        """Test setting rate limit."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        config = FeedConfig(adapter=adapter, storage=storage)

        config2 = config.with_rate_limit(5.0)

        assert config.rate_limit is None
        assert config2.rate_limit == 5.0

    def test_with_concurrency(self) -> None:
        """Test setting concurrency."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        config = FeedConfig(adapter=adapter, storage=storage)

        config2 = config.with_concurrency(4)

        assert config.concurrency == 1
        assert config2.concurrency == 4

    def test_with_checkpoint(self) -> None:
        """Test enabling checkpoint."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        config = FeedConfig(adapter=adapter, storage=storage)

        config2 = config.with_checkpoint(interval=50)

        assert config.checkpoint_interval is None
        assert config2.checkpoint_interval == 50

    def test_with_metadata(self) -> None:
        """Test adding metadata."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        config = FeedConfig(adapter=adapter, storage=storage)

        config2 = config.with_metadata(source="sec", version="1.0")

        assert config.metadata == {}
        assert config2.metadata == {"source": "sec", "version": "1.0"}

    def test_chained_with_methods(self) -> None:
        """Test chaining with_* methods."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()

        config = (
            FeedConfig(adapter=adapter, storage=storage)
            .with_rate_limit(10.0)
            .with_concurrency(2)
            .with_enricher(MockEnricher())
            .with_checkpoint(interval=100)
        )

        assert config.rate_limit == 10.0
        assert config.concurrency == 2
        assert len(config.enrichers) == 1
        assert config.checkpoint_interval == 100


class TestFeedBasic:
    """Tests for Feed class basics."""

    def test_create_with_kwargs(self) -> None:
        """Test creating Feed with kwargs."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()

        feed = Feed(adapter=adapter, storage=storage)

        assert feed.adapter is adapter
        assert feed.storage is storage

    def test_create_with_config(self) -> None:
        """Test creating Feed with FeedConfig."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        config = FeedConfig(adapter=adapter, storage=storage, batch_size=25)

        feed = Feed(config)

        assert feed.config.batch_size == 25

    def test_create_without_adapter_raises(self) -> None:
        """Test that missing adapter raises TypeError."""
        storage = MemoryStorage()

        with pytest.raises(TypeError, match="adapter is required"):
            Feed(storage=storage)

    def test_create_without_storage_raises(self) -> None:
        """Test that missing storage raises TypeError."""
        adapter = MockAdapter(records=[])

        with pytest.raises(TypeError, match="storage is required"):
            Feed(adapter=adapter)


class TestFeedContextManager:
    """Tests for Feed as context manager."""

    async def test_context_manager_initializes(self) -> None:
        """Test that context manager initializes components."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()

        async with Feed(adapter=adapter, storage=storage) as feed:
            assert feed._initialized is True
            assert adapter._initialized is True

    async def test_context_manager_closes(self) -> None:
        """Test that context manager closes components."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()

        async with Feed(adapter=adapter, storage=storage):
            pass

        assert adapter._initialized is False

    async def test_context_manager_closes_on_error(self) -> None:
        """Test that context manager closes even on error."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()

        with pytest.raises(ValueError):
            async with Feed(adapter=adapter, storage=storage):
                raise ValueError("test error")

        assert adapter._initialized is False


class TestFeedCollect:
    """Tests for Feed.collect()."""

    async def test_collect_empty(self) -> None:
        """Test collecting with no records."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()

        async with Feed(adapter=adapter, storage=storage) as feed:
            result = await feed.collect()

        assert result.total_processed == 0
        assert result.total_new == 0

    async def test_collect_records(self) -> None:
        """Test collecting records."""
        records = [make_candidate(f"rec-{i}", value=i) for i in range(5)]
        adapter = MockAdapter(records=records)
        storage = MemoryStorage()

        async with Feed(adapter=adapter, storage=storage) as feed:
            result = await feed.collect()

        assert result.total_processed == 5
        assert result.total_new == 5

    async def test_collect_with_limit(self) -> None:
        """Test collecting with limit."""
        records = [make_candidate(f"rec-{i}", value=i) for i in range(10)]
        adapter = MockAdapter(records=records)
        storage = MemoryStorage()

        async with Feed(adapter=adapter, storage=storage) as feed:
            result = await feed.collect(limit=3)

        assert result.total_processed == 3

    async def test_collect_with_enricher(self) -> None:
        """Test collecting with enricher."""
        records = [make_candidate("rec-1", value=1)]
        adapter = MockAdapter(records=records)
        storage = MemoryStorage()
        enricher = MockEnricher(
            transform=lambda c: {**c, "enriched": True},
        )

        async with Feed(
            adapter=adapter,
            storage=storage,
            enrichers=[enricher],
        ) as feed:
            result = await feed.collect()

        assert result.total_new == 1
        assert enricher.enrich_count == 1

    async def test_collect_not_initialized_raises(self) -> None:
        """Test that collect without init raises."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        feed = Feed(adapter=adapter, storage=storage)

        with pytest.raises(RuntimeError, match="not initialized"):
            await feed.collect()


class TestFeedQuery:
    """Tests for Feed.query()."""

    async def test_query_all(self) -> None:
        """Test querying all records."""
        records = [make_candidate(f"rec-{i}", value=i) for i in range(3)]
        adapter = MockAdapter(records=records)
        storage = MemoryStorage()

        async with Feed(adapter=adapter, storage=storage) as feed:
            await feed.collect()
            results = [r async for r in feed.query()]

        assert len(results) == 3

    async def test_query_not_initialized_raises(self) -> None:
        """Test that query without init raises."""
        adapter = MockAdapter(records=[])
        storage = MemoryStorage()
        feed = Feed(adapter=adapter, storage=storage)

        with pytest.raises(RuntimeError, match="not initialized"):
            async for _ in feed.query():
                pass


class TestCollectFunction:
    """Tests for the collect() convenience function."""

    async def test_collect_simple(self) -> None:
        """Test simple collect function."""
        records = [make_candidate("rec-1", value=1)]
        adapter = MockAdapter(records=records)
        storage = MemoryStorage()

        result = await collect(adapter, storage)

        assert result.total_new == 1

    async def test_collect_with_enrichers(self) -> None:
        """Test collect with enrichers."""
        records = [make_candidate("rec-1", value=1)]
        adapter = MockAdapter(records=records)
        storage = MemoryStorage()
        enricher = MockEnricher()

        result = await collect(adapter, storage, enrichers=[enricher])

        assert result.total_new == 1
        assert enricher.enrich_count == 1


class TestPreset:
    """Tests for Preset class."""

    def test_minimal_preset_build(self) -> None:
        """Test building from MinimalPreset."""
        adapter = MockAdapter(records=[])

        config = MinimalPreset.build(adapter=adapter)

        assert config.adapter is adapter
        assert config.storage is not None

    def test_custom_preset(self) -> None:
        """Test custom preset."""

        class CustomPreset(Preset):
            storage_class = MemoryStorage
            rate_limit = 5.0
            batch_size = 25

        adapter = MockAdapter(records=[])
        config = CustomPreset.build(adapter=adapter)

        assert config.rate_limit == 5.0
        assert config.batch_size == 25

    def test_preset_override(self) -> None:
        """Test overriding preset values."""

        class CustomPreset(Preset):
            storage_class = MemoryStorage
            rate_limit = 5.0

        adapter = MockAdapter(records=[])
        config = CustomPreset.build(adapter=adapter, rate_limit=10.0)

        assert config.rate_limit == 10.0

    def test_preset_without_storage_raises(self) -> None:
        """Test preset without storage raises."""

        class EmptyPreset(Preset):
            pass

        adapter = MockAdapter(records=[])

        with pytest.raises(ValueError, match="storage"):
            EmptyPreset.build(adapter=adapter)


class TestFeedFromPreset:
    """Tests for Feed.from_preset()."""

    def test_from_preset(self) -> None:
        """Test creating Feed from preset."""
        adapter = MockAdapter(records=[])

        feed = Feed.from_preset(MinimalPreset, adapter=adapter)

        assert feed.adapter is adapter

    async def test_from_preset_collect(self) -> None:
        """Test collecting with preset-based Feed."""
        records = [make_candidate("rec-1", value=1)]
        adapter = MockAdapter(records=records)

        feed = Feed.from_preset(MinimalPreset, adapter=adapter)

        async with feed:
            result = await feed.collect()

        assert result.total_new == 1
