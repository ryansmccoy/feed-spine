"""Tests for FetchContextMixin — in-memory FetchContext storage.

Covers all 8 protocol methods: get, save, delete, list_all,
get_stale, get_unhealthy, initialize, close.
Also tests get_stats and _url_to_key.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from feedspine.models.fetch_context import FetchContext
from feedspine.storage.shared.mixins.fetch_context import FetchContextMixin

# ── Helpers ──────────────────────────────────────────────


def _ctx(
    url: str = "https://example.com/feed.xml",
    *,
    etag: str | None = None,
    last_fetch_at: datetime | None = None,
    consecutive_failures: int = 0,
    total_fetches: int = 0,
    total_304s: int = 0,
) -> FetchContext:
    return FetchContext(
        endpoint_url=url,
        etag=etag,
        last_fetch_at=last_fetch_at,
        consecutive_failures=consecutive_failures,
        total_fetches=total_fetches,
        total_304s=total_304s,
    )


@pytest.fixture
def mixin() -> FetchContextMixin:
    return FetchContextMixin()


# ── save / get ───────────────────────────────────────────


class TestSaveAndGet:
    async def test_save_then_get(self, mixin: FetchContextMixin) -> None:
        ctx = _ctx("https://a.com/feed")
        await mixin.save(ctx)
        result = await mixin.get("https://a.com/feed")
        assert result is not None
        assert result.endpoint_url == "https://a.com/feed"

    async def test_get_unknown_returns_none(self, mixin: FetchContextMixin) -> None:
        result = await mixin.get("https://no-such-url.com")
        assert result is None

    async def test_save_overwrites(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com/feed", etag='"v1"'))
        await mixin.save(_ctx("https://a.com/feed", etag='"v2"'))
        result = await mixin.get("https://a.com/feed")
        assert result is not None
        assert result.etag == '"v2"'


# ── delete ───────────────────────────────────────────────


class TestDelete:
    async def test_delete_existing(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com/feed"))
        deleted = await mixin.delete("https://a.com/feed")
        assert deleted is True
        assert await mixin.get("https://a.com/feed") is None

    async def test_delete_nonexistent(self, mixin: FetchContextMixin) -> None:
        deleted = await mixin.delete("https://no-such.com")
        assert deleted is False


# ── list_all ─────────────────────────────────────────────


class TestListAll:
    async def test_empty(self, mixin: FetchContextMixin) -> None:
        result = await mixin.list_all()
        assert result == []

    async def test_returns_all(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com"))
        await mixin.save(_ctx("https://b.com"))
        result = await mixin.list_all()
        assert len(result) == 2
        urls = {c.endpoint_url for c in result}
        assert urls == {"https://a.com", "https://b.com"}


# ── get_stale ────────────────────────────────────────────


class TestGetStale:
    async def test_never_fetched_is_stale(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com", last_fetch_at=None))
        stale = await mixin.get_stale(max_age_hours=1)
        assert len(stale) == 1

    async def test_recently_fetched_not_stale(self, mixin: FetchContextMixin) -> None:
        now = datetime.now(UTC)
        await mixin.save(_ctx("https://a.com", last_fetch_at=now))
        stale = await mixin.get_stale(max_age_hours=1)
        assert stale == []

    async def test_old_fetch_is_stale(self, mixin: FetchContextMixin) -> None:
        old = datetime.now(UTC) - timedelta(hours=48)
        await mixin.save(_ctx("https://a.com", last_fetch_at=old))
        stale = await mixin.get_stale(max_age_hours=24)
        assert len(stale) == 1


# ── get_unhealthy ────────────────────────────────────────


class TestGetUnhealthy:
    async def test_healthy_excluded(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com", consecutive_failures=0))
        unhealthy = await mixin.get_unhealthy(min_failures=3)
        assert unhealthy == []

    async def test_unhealthy_returned(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com", consecutive_failures=5))
        unhealthy = await mixin.get_unhealthy(min_failures=3)
        assert len(unhealthy) == 1

    async def test_threshold_boundary(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com", consecutive_failures=3))
        assert len(await mixin.get_unhealthy(min_failures=3)) == 1
        assert len(await mixin.get_unhealthy(min_failures=4)) == 0


# ── get_stats ────────────────────────────────────────────


class TestGetStats:
    async def test_empty_stats(self, mixin: FetchContextMixin) -> None:
        stats = await mixin.get_stats()
        assert stats["total_endpoints"] == 0
        assert stats["total_fetches"] == 0
        assert stats["overall_cache_hit_rate"] == 0.0

    async def test_aggregate_stats(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com", total_fetches=10, total_304s=3))
        await mixin.save(_ctx("https://b.com", total_fetches=20, total_304s=7))

        stats = await mixin.get_stats()
        assert stats["total_endpoints"] == 2
        assert stats["total_fetches"] == 30
        assert stats["total_304s"] == 10
        assert stats["overall_cache_hit_rate"] == pytest.approx(10 / 30)

    async def test_unhealthy_count(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com", consecutive_failures=5))
        await mixin.save(_ctx("https://b.com", consecutive_failures=0))
        stats = await mixin.get_stats()
        assert stats["unhealthy_count"] == 1


# ── initialize / close ──────────────────────────────────


class TestLifecycle:
    async def test_initialize_is_noop(self, mixin: FetchContextMixin) -> None:
        await mixin.initialize()  # should not raise

    async def test_close_is_noop(self, mixin: FetchContextMixin) -> None:
        await mixin.close()  # should not raise


# ── _url_to_key ──────────────────────────────────────────


class TestUrlToKey:
    def test_deterministic(self, mixin: FetchContextMixin) -> None:
        k1 = mixin._url_to_key("https://example.com")
        k2 = mixin._url_to_key("https://example.com")
        assert k1 == k2

    def test_different_urls_different_keys(self, mixin: FetchContextMixin) -> None:
        k1 = mixin._url_to_key("https://a.com")
        k2 = mixin._url_to_key("https://b.com")
        assert k1 != k2

    def test_key_length(self, mixin: FetchContextMixin) -> None:
        key = mixin._url_to_key("https://example.com")
        assert len(key) == 16


# ── _clear_fetch_contexts ───────────────────────────────


class TestClear:
    async def test_clears_all(self, mixin: FetchContextMixin) -> None:
        await mixin.save(_ctx("https://a.com"))
        mixin._clear_fetch_contexts()
        assert await mixin.list_all() == []
