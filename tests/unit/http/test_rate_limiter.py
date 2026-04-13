"""Tests for feedspine.http.host_rate_limiter module.

Covers HostRateLimiter per-host throttling, HostConfig defaults,
and HostStats tracking.
"""

from __future__ import annotations

import pytest

from feedspine.http.host_rate_limiter import HostConfig, HostRateLimiter, HostStats

# ── HostStats ───────────────────────────────────────────────────


class TestHostStats:
    """Tests for HostStats dataclass."""

    def test_default_construction(self):
        stats = HostStats()
        assert stats.request_count == 0
        assert stats.error_count == 0
        assert stats.total_wait_time == 0.0


# ── HostConfig ──────────────────────────────────────────────────


class TestHostConfig:
    """Tests for HostConfig dataclass."""

    def test_default_values(self):
        cfg = HostConfig()
        assert cfg.rate > 0
        assert cfg.adaptive is True


# ── HostRateLimiter ─────────────────────────────────────────────


class TestHostRateLimiter:
    """Tests for per-host rate limiting."""

    def test_construction(self):
        limiter = HostRateLimiter(default_rate=5.0)
        assert limiter is not None

    def test_host_extraction(self):
        limiter = HostRateLimiter()
        host = limiter._get_host("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany")
        assert host == "www.sec.gov"

    def test_set_rate(self):
        limiter = HostRateLimiter()
        limiter.set_rate("api.example.com", 2.0, burst=5)
        config = limiter._get_config("api.example.com")
        assert config.rate == 2.0

    def test_different_hosts_have_independent_configs(self):
        limiter = HostRateLimiter()
        limiter.set_rate("a.com", 1.0)
        limiter.set_rate("b.com", 10.0)
        assert limiter._get_config("a.com").rate == 1.0
        assert limiter._get_config("b.com").rate == 10.0

    @pytest.mark.asyncio
    async def test_acquire_does_not_fail(self):
        """First request should not raise."""
        limiter = HostRateLimiter(default_rate=100.0)
        # Should complete without error
        await limiter.acquire("https://example.com/api/items")

    @pytest.mark.asyncio
    async def test_acquire_multiple(self):
        """Multiple acquires should work (may throttle)."""
        limiter = HostRateLimiter(default_rate=100.0)
        for _ in range(3):
            await limiter.acquire("https://example.com/api/test")
