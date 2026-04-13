"""Tests for cross-feed deduplication (DedupIndex + pipeline integration)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.models.base import Metadata
from feedspine.models.record import RecordCandidate
from feedspine.pipeline.action import ProcessAction
from feedspine.pipeline.context import PipelineContext
from feedspine.pipeline.dedup import DedupIndex, DedupMatch, DedupStats
from feedspine.pipeline.stages import process_candidate
from feedspine.storage.memory import MemoryStorage

# ── DedupIndex unit tests ────────────────────────────────────────────────────


class TestDedupIndex:
    def test_check_unknown_hash(self):
        idx = DedupIndex()
        result = idx.check("abc123")
        assert not result.is_duplicate
        assert result.existing_record_id is None

    def test_register_and_check(self):
        idx = DedupIndex()
        idx.register("abc123", "record-1")
        result = idx.check("abc123")
        assert result.is_duplicate
        assert result.existing_record_id == "record-1"

    def test_different_hashes_not_duplicate(self):
        idx = DedupIndex()
        idx.register("abc123", "record-1")
        result = idx.check("def456")
        assert not result.is_duplicate

    def test_size(self):
        idx = DedupIndex()
        assert idx.size == 0
        idx.register("h1", "r1")
        idx.register("h2", "r2")
        assert idx.size == 2

    def test_clear(self):
        idx = DedupIndex()
        idx.register("h1", "r1")
        idx.clear()
        assert idx.size == 0
        assert not idx.check("h1").is_duplicate


class TestDedupStats:
    def test_duplicate_rate_zero_checked(self):
        stats = DedupStats()
        assert stats.duplicate_rate == 0.0

    def test_duplicate_rate(self):
        stats = DedupStats(checked=10, cross_feed_duplicates=3)
        assert stats.duplicate_rate == pytest.approx(0.3)


class TestDedupMatch:
    def test_not_duplicate(self):
        m = DedupMatch(is_duplicate=False, content_hash="h1")
        assert not m.is_duplicate
        assert m.existing_record_id is None

    def test_duplicate(self):
        m = DedupMatch(is_duplicate=True, existing_record_id="r1", content_hash="h1")
        assert m.is_duplicate
        assert m.existing_record_id == "r1"


# ── Pipeline integration tests ───────────────────────────────────────────────


def _make_candidate(natural_key: str, content: dict, source: str = "test") -> tuple[RecordCandidate, str]:
    """Create a RecordCandidate and return (candidate, source)."""
    return (
        RecordCandidate(
            natural_key=natural_key,
            published_at=datetime(2024, 6, 15, tzinfo=UTC),
            content=content,
            metadata=Metadata(source=source),
        ),
        source,
    )


class TestCrossFeedDedup:
    """Test cross-feed dedup integration in process_candidate."""

    async def test_same_content_different_key_detected(self):
        """Two feeds producing same content with different keys → second is DUPLICATE."""
        storage = MemoryStorage()
        await storage.initialize()
        dedup = DedupIndex()
        ctx = PipelineContext(storage=storage, dedup_index=dedup)

        content = {"title": "Q4 Earnings Report", "cik": "0000320193"}

        # First feed ingests the content
        c1, s1 = _make_candidate("rss-001", content, source="sec-rss")
        r1 = await process_candidate(ctx, c1, s1)
        assert r1.action == ProcessAction.CREATED
        assert dedup.size == 1

        # Second feed produces same content with different natural key
        c2, s2 = _make_candidate("edgar-001", content, source="sec-edgar")
        r2 = await process_candidate(ctx, c2, s2)
        assert r2.action == ProcessAction.DUPLICATE
        assert r2.record.id == r1.record.id

    async def test_different_content_not_duplicate(self):
        """Different content from two feeds → both CREATED."""
        storage = MemoryStorage()
        await storage.initialize()
        dedup = DedupIndex()
        ctx = PipelineContext(storage=storage, dedup_index=dedup)

        c1, s1 = _make_candidate("rss-001", {"title": "Report A"}, source="sec-rss")
        r1 = await process_candidate(ctx, c1, s1)
        assert r1.action == ProcessAction.CREATED

        c2, s2 = _make_candidate("edgar-001", {"title": "Report B"}, source="sec-edgar")
        r2 = await process_candidate(ctx, c2, s2)
        assert r2.action == ProcessAction.CREATED
        assert dedup.size == 2

    async def test_no_dedup_index_skips_cross_feed(self):
        """Without DedupIndex, same content from two feeds → both CREATED."""
        storage = MemoryStorage()
        await storage.initialize()
        ctx = PipelineContext(storage=storage)  # No dedup_index

        content = {"title": "Same content"}

        c1, s1 = _make_candidate("rss-001", content, source="sec-rss")
        r1 = await process_candidate(ctx, c1, s1)
        assert r1.action == ProcessAction.CREATED

        c2, s2 = _make_candidate("edgar-001", content, source="sec-edgar")
        r2 = await process_candidate(ctx, c2, s2)
        assert r2.action == ProcessAction.CREATED  # No cross-feed dedup

    async def test_same_key_still_uses_natural_key_dedup(self):
        """Same natural_key from same feed → DUPLICATE via natural_key (not content hash)."""
        storage = MemoryStorage()
        await storage.initialize()
        dedup = DedupIndex()
        ctx = PipelineContext(storage=storage, dedup_index=dedup)

        content = {"title": "Same item"}

        c1, s1 = _make_candidate("key-001", content, source="rss")
        r1 = await process_candidate(ctx, c1, s1)
        assert r1.action == ProcessAction.CREATED

        # Same natural key → caught by natural_key dedup before cross-feed check
        c2, s2 = _make_candidate("key-001", content, source="rss")
        r2 = await process_candidate(ctx, c2, s2)
        assert r2.action == ProcessAction.DUPLICATE

    async def test_sighting_recorded_for_cross_feed_dup(self):
        """Cross-feed duplicate should record a sighting."""
        storage = MemoryStorage()
        await storage.initialize()
        dedup = DedupIndex()
        ctx = PipelineContext(storage=storage, dedup_index=dedup)

        content = {"title": "Shared Filing"}

        c1, s1 = _make_candidate("rss-x", content, source="feed-a")
        await process_candidate(ctx, c1, s1)

        c2, s2 = _make_candidate("edgar-x", content, source="feed-b")
        await process_candidate(ctx, c2, s2)

        # The cross-feed dup should have recorded a sighting under the new natural key
        sightings = await storage.get_sightings("edgar-x")
        assert len(sightings) == 1
        assert sightings[0].source == "feed-b"
