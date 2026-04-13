"""Tests for feedspine.storage.optimization module.

Covers Cursor encode/decode, Page dataclass, batch_iterator,
and paginate_with_cursor helper.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.storage.optimization import (
    BatchConfig,
    Cursor,
    Page,
    batch_iterator,
    paginate_with_cursor,
    process_in_batches,
)

# ── Cursor ──────────────────────────────────────────────────────


class TestCursor:
    """Tests for Cursor encode/decode round-trip."""

    def test_encode_returns_string(self):
        c = Cursor(key="rec-001", captured_at=datetime(2025, 1, 1, tzinfo=UTC))
        encoded = c.encode()
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_decode_roundtrip(self):
        original = Cursor(key="rec-001", captured_at=datetime(2025, 6, 15, 12, 30, 0, tzinfo=UTC))
        encoded = original.encode()
        decoded = Cursor.decode(encoded)
        assert decoded.key == original.key
        assert decoded.captured_at == original.captured_at

    def test_different_keys_produce_different_encodings(self):
        c1 = Cursor(key="aaa", captured_at=datetime(2025, 1, 1, tzinfo=UTC))
        c2 = Cursor(key="bbb", captured_at=datetime(2025, 1, 1, tzinfo=UTC))
        assert c1.encode() != c2.encode()

    def test_decode_invalid_raises(self):
        with pytest.raises((ValueError, KeyError)):
            Cursor.decode("not-valid-base64-json!!!")


# ── Page ────────────────────────────────────────────────────────


class TestPage:
    """Tests for Page dataclass."""

    def test_empty_page(self):
        page: Page[str] = Page(items=[])
        assert page.items == []
        assert page.next_cursor is None
        assert page.has_more is False
        assert page.total_estimate is None

    def test_page_with_items(self):
        page: Page[int] = Page(items=[1, 2, 3], has_more=True, total_estimate=100)
        assert len(page.items) == 3
        assert page.has_more is True
        assert page.total_estimate == 100


# ── batch_iterator ──────────────────────────────────────────────


class TestBatchIterator:
    """Tests for batch_iterator generator."""

    def test_empty_input(self):
        batches = list(batch_iterator(iter([]), batch_size=10))
        assert batches == []

    def test_single_batch(self):
        batches = list(batch_iterator(iter([1, 2, 3]), batch_size=10))
        assert batches == [[1, 2, 3]]

    def test_exact_batches(self):
        items = list(range(6))
        batches = list(batch_iterator(iter(items), batch_size=3))
        assert batches == [[0, 1, 2], [3, 4, 5]]

    def test_leftover_batch(self):
        items = list(range(7))
        batches = list(batch_iterator(iter(items), batch_size=3))
        assert len(batches) == 3
        assert batches[-1] == [6]

    def test_batch_size_one(self):
        items = [10, 20, 30]
        batches = list(batch_iterator(iter(items), batch_size=1))
        assert len(batches) == 3
        assert all(len(b) == 1 for b in batches)


# ── paginate_with_cursor ────────────────────────────────────────


class TestPaginateWithCursor:
    """Tests for the paginate_with_cursor async helper."""

    @pytest.mark.asyncio
    async def test_empty_results(self):
        async def query_fn(cursor, limit):
            return [], False

        page = await paginate_with_cursor(query_fn, page_size=10)
        assert page.items == []
        assert page.has_more is False
        assert page.next_cursor is None

    @pytest.mark.asyncio
    async def test_single_page(self):
        async def query_fn(cursor, limit):
            return [1, 2, 3], False

        page = await paginate_with_cursor(query_fn, page_size=10)
        assert page.items == [1, 2, 3]
        assert page.has_more is False

    @pytest.mark.asyncio
    async def test_has_more_detected(self):
        """When query returns more items than page_size, has_more is set."""

        async def query_fn(cursor, limit):
            # Return limit items (page_size + 1), simulating more available
            return list(range(limit)), False

        page = await paginate_with_cursor(query_fn, page_size=5)
        # Should trim to page_size and set has_more
        assert len(page.items) == 5
        assert page.has_more is True


# ── process_in_batches ──────────────────────────────────────────


class TestProcessInBatches:
    """Tests for process_in_batches async helper."""

    @pytest.mark.asyncio
    async def test_processes_all_items(self):
        processed = []

        async def processor(batch):
            processed.extend(batch)

        total = await process_in_batches(
            iter(range(10)),
            processor,
            BatchConfig(batch_size=3),
        )
        assert total == 10
        assert processed == list(range(10))

    @pytest.mark.asyncio
    async def test_empty_input(self):
        async def processor(batch):
            pass

        total = await process_in_batches(iter([]), processor)
        assert total == 0
