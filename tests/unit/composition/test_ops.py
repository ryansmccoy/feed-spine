"""Tests for pipeline operations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.composition import ops
from feedspine.composition.ops import (
    AsyncFilterOp,
    AsyncTransformOp,
    BatchOp,
    CheckpointOp,
    DedupeOp,
    EnrichOp,
    FilterOp,
    NotifyOp,
    PipelineOp,
    RateLimitOp,
    TransformOp,
)
from feedspine.composition.testing import MockEnricher
from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record
from feedspine.notifier.console import ConsoleNotifier


def make_record(natural_key: str = "test-1", **content: object) -> Record:
    """Create a test record."""
    now = datetime.now(UTC)
    return Record(
        id=f"id-{natural_key}",
        natural_key=natural_key,
        metadata=Metadata(source="test"),
        content=dict(content),
        layer=Layer.BRONZE,
        published_at=now,
        captured_at=now,
    )


class TestFilterOp:
    """Tests for FilterOp."""

    async def test_filter_pass(self) -> None:
        """Test record passing filter."""
        op = FilterOp(lambda r: r.layer == Layer.BRONZE)
        record = make_record()

        result = await op.apply(record)

        assert result is record

    async def test_filter_reject(self) -> None:
        """Test record rejected by filter."""
        op = FilterOp(lambda r: r.layer == Layer.SILVER)
        record = make_record()

        result = await op.apply(record)

        assert result is None

    async def test_filter_content_based(self) -> None:
        """Test filtering by content."""
        op = FilterOp(lambda r: r.content.get("category") == "A")
        record_a = make_record(category="A")
        record_b = make_record(category="B")

        assert await op.apply(record_a) is record_a
        assert await op.apply(record_b) is None


class TestAsyncFilterOp:
    """Tests for AsyncFilterOp."""

    async def test_async_filter_pass(self) -> None:
        """Test async filter passing."""

        async def is_bronze(r: Record) -> bool:
            return r.layer == Layer.BRONZE

        op = AsyncFilterOp(is_bronze)
        record = make_record()

        result = await op.apply(record)

        assert result is record

    async def test_async_filter_reject(self) -> None:
        """Test async filter rejecting."""

        async def is_silver(r: Record) -> bool:
            return r.layer == Layer.SILVER

        op = AsyncFilterOp(is_silver)
        record = make_record()

        result = await op.apply(record)

        assert result is None


class TestTransformOp:
    """Tests for TransformOp."""

    async def test_transform_content(self) -> None:
        """Test transforming record content."""

        def add_tag(r: Record) -> Record:
            return r.model_copy(update={"content": {**r.content, "tag": "processed"}})

        op = TransformOp(add_tag)
        record = make_record(value=1)

        result = await op.apply(record)

        assert result is not None
        assert result.content["tag"] == "processed"
        assert result.content["value"] == 1

    async def test_transform_immutable(self) -> None:
        """Test that transform doesn't modify original."""

        def add_tag(r: Record) -> Record:
            return r.model_copy(update={"content": {**r.content, "tag": "new"}})

        op = TransformOp(add_tag)
        record = make_record(value=1)

        result = await op.apply(record)

        assert "tag" not in record.content
        assert result is not None
        assert result.content["tag"] == "new"


class TestAsyncTransformOp:
    """Tests for AsyncTransformOp."""

    async def test_async_transform(self) -> None:
        """Test async transformation."""

        async def add_tag(r: Record) -> Record:
            return r.model_copy(update={"content": {**r.content, "async": True}})

        op = AsyncTransformOp(add_tag)
        record = make_record()

        result = await op.apply(record)

        assert result is not None
        assert result.content["async"] is True


class TestEnrichOp:
    """Tests for EnrichOp."""

    async def test_enrich(self) -> None:
        """Test enrichment operation."""
        enricher = MockEnricher(
            transform=lambda c: {**c, "enriched": True},
        )
        await enricher.initialize()
        op = EnrichOp(enricher)
        record = make_record()

        result = await op.apply(record)

        assert result is not None
        assert result.content["enriched"] is True


class TestDedupeOp:
    """Tests for DedupeOp."""

    async def test_dedupe_by_field(self) -> None:
        """Test deduplication by field name."""
        op = DedupeOp(key="natural_key")
        record1 = make_record(natural_key="a")
        record2 = make_record(natural_key="a")  # Duplicate
        record3 = make_record(natural_key="b")

        assert await op.apply(record1) is record1
        assert await op.apply(record2) is None  # Filtered as duplicate
        assert await op.apply(record3) is record3

    async def test_dedupe_by_function(self) -> None:
        """Test deduplication by function."""
        op = DedupeOp(key=lambda r: r.content.get("url", ""))
        record1 = make_record(natural_key="1", url="http://a.com")
        record2 = make_record(natural_key="2", url="http://a.com")  # Same URL
        record3 = make_record(natural_key="3", url="http://b.com")

        assert await op.apply(record1) is record1
        assert await op.apply(record2) is None
        assert await op.apply(record3) is record3


class TestNotifyOp:
    """Tests for NotifyOp."""

    async def test_notify_passthrough(self) -> None:
        """Test that notify passes through records."""
        notifier = ConsoleNotifier()
        op = NotifyOp(notifier, on="new")
        record = make_record()

        result = await op.apply(record)

        assert result is record


class TestMarkerOps:
    """Tests for marker operations (handled externally)."""

    async def test_rate_limit_passthrough(self) -> None:
        """Test rate limit passes through."""
        op = RateLimitOp(rps=10.0)
        record = make_record()

        result = await op.apply(record)

        assert result is record
        assert op.rps == 10.0

    async def test_checkpoint_passthrough(self) -> None:
        """Test checkpoint passes through."""
        op = CheckpointOp(interval=50)
        record = make_record()

        result = await op.apply(record)

        assert result is record
        assert op.interval == 50

    async def test_batch_passthrough(self) -> None:
        """Test batch passes through."""
        op = BatchOp(size=25)
        record = make_record()

        result = await op.apply(record)

        assert result is record
        assert op.size == 25


class TestFactoryFunctions:
    """Tests for ops.* factory functions."""

    def test_filter_factory(self) -> None:
        """Test filter() factory."""
        op = ops.filter(lambda r: True)
        assert isinstance(op, FilterOp)

    def test_filter_async_factory(self) -> None:
        """Test filter_async() factory."""

        async def pred(r: Record) -> bool:
            return True

        op = ops.filter_async(pred)
        assert isinstance(op, AsyncFilterOp)

    def test_enrich_factory(self) -> None:
        """Test enrich() factory."""
        op = ops.enrich(MockEnricher())
        assert isinstance(op, EnrichOp)

    def test_transform_factory(self) -> None:
        """Test transform() factory."""
        op = ops.transform(lambda r: r)
        assert isinstance(op, TransformOp)

    def test_transform_async_factory(self) -> None:
        """Test transform_async() factory."""

        async def t(r: Record) -> Record:
            return r

        op = ops.transform_async(t)
        assert isinstance(op, AsyncTransformOp)

    def test_dedupe_factory(self) -> None:
        """Test dedupe() factory."""
        op = ops.dedupe(key="natural_key")
        assert isinstance(op, DedupeOp)

    def test_notify_factory(self) -> None:
        """Test notify() factory."""
        op = ops.notify(ConsoleNotifier(), on="error")
        assert isinstance(op, NotifyOp)
        assert op.on == "error"

    def test_rate_limit_factory(self) -> None:
        """Test rate_limit() factory."""
        op = ops.rate_limit(5.0)
        assert isinstance(op, RateLimitOp)
        assert op.rps == 5.0

    def test_checkpoint_factory(self) -> None:
        """Test checkpoint() factory."""
        op = ops.checkpoint(interval=200)
        assert isinstance(op, CheckpointOp)
        assert op.interval == 200

    def test_batch_factory(self) -> None:
        """Test batch() factory."""
        op = ops.batch(50)
        assert isinstance(op, BatchOp)
        assert op.size == 50
