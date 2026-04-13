"""Host-based rate limiting for multi-domain crawling.

This module provides per-host rate limiting to ensure polite
crawling behavior across multiple domains.

Example:
    >>> from feedspine.http.host_rate_limiter import HostRateLimiter
    >>>
    >>> limiter = HostRateLimiter(default_rate=10.0)
    >>> limiter.set_rate("api.sec.gov", 5.0)  # SEC has strict limits
    >>>
    >>> await limiter.acquire("https://api.sec.gov/filings/...")
    >>> await limiter.acquire("https://other-api.com/data")  # Different host
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass
class HostStats:
    """Statistics for a single host.

    Attributes:
        request_count: Total requests made to this host.
        total_wait_time: Total time spent waiting for rate limits.
        last_request: Timestamp of last request.
        error_count: Number of errors (429, timeouts, etc.)
        backoff_until: If set, don't make requests until this time.
    """

    request_count: int = 0
    total_wait_time: float = 0.0
    last_request: float = 0.0
    error_count: int = 0
    backoff_until: float | None = None


@dataclass
class HostConfig:
    """Configuration for a specific host.

    Attributes:
        rate: Requests per second for this host.
        burst: Burst capacity (0 for no bursting).
        min_interval: Minimum seconds between requests.
        adaptive: Whether to adjust rate based on errors.
    """

    rate: float = 10.0
    burst: int = 0
    min_interval: float | None = None
    adaptive: bool = True

    def __post_init__(self) -> None:
        if self.min_interval is None:
            self.min_interval = 1.0 / self.rate


class HostRateLimiter:
    """Per-host rate limiter for polite multi-domain crawling.

    Maintains separate rate limits per hostname, allowing different
    limits for different APIs (e.g., SEC has strict 10 req/sec limit).

    Features:
    - Per-host rate limiting
    - Configurable rates per domain
    - Adaptive backoff on errors
    - Statistics tracking
    - Automatic cleanup of stale limiters

    Example:
        >>> import asyncio
        >>> limiter = HostRateLimiter(default_rate=10.0)
        >>>
        >>> # Configure known hosts
        >>> limiter.set_rate("api.sec.gov", 5.0)
        >>> limiter.set_rate("data.sec.gov", 8.0)
        >>>
        >>> async def fetch(url: str):
        ...     await limiter.acquire(url)
        ...     # ... make request ...
        ...
        >>> asyncio.run(fetch("https://api.sec.gov/filings/recent"))

    Attributes:
        default_rate: Default requests per second for unknown hosts.
    """

    def __init__(
        self,
        default_rate: float = 10.0,
        default_burst: int = 0,
        adaptive: bool = True,
    ):
        """Initialize the host rate limiter.

        Args:
            default_rate: Default requests per second for unknown hosts.
            default_burst: Default burst capacity (0 = no bursting).
            adaptive: Enable adaptive rate limiting on errors.
        """
        self.default_rate = default_rate
        self.default_burst = default_burst
        self.adaptive = adaptive

        self._configs: dict[str, HostConfig] = {}
        self._last_request: dict[str, float] = defaultdict(float)
        self._tokens: dict[str, float] = {}
        self._stats: dict[str, HostStats] = defaultdict(HostStats)
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def set_rate(
        self,
        host: str,
        rate: float,
        *,
        burst: int | None = None,
        min_interval: float | None = None,
    ) -> None:
        """Set rate limit for a specific host.

        Args:
            host: Hostname (without scheme, e.g., "api.sec.gov").
            rate: Requests per second.
            burst: Burst capacity (None = use default).
            min_interval: Minimum seconds between requests.
        """
        self._configs[host] = HostConfig(
            rate=rate,
            burst=burst if burst is not None else self.default_burst,
            min_interval=min_interval,
            adaptive=self.adaptive,
        )

    def _get_host(self, url: str) -> str:
        """Extract hostname from URL."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split("/")[0]

    def _get_config(self, host: str) -> HostConfig:
        """Get or create config for a host."""
        if host not in self._configs:
            self._configs[host] = HostConfig(
                rate=self.default_rate,
                burst=self.default_burst,
                adaptive=self.adaptive,
            )
        return self._configs[host]

    async def _get_lock(self, host: str) -> asyncio.Lock:
        """Get or create lock for a host."""
        if host not in self._locks:
            async with self._global_lock:
                if host not in self._locks:
                    self._locks[host] = asyncio.Lock()
        return self._locks[host]

    async def acquire(self, url: str) -> float:
        """Wait until a request can be made to the URL's host.

        Args:
            url: Full URL or hostname.

        Returns:
            Time waited in seconds.

        Example:
            >>> limiter = HostRateLimiter()
            >>> waited = await limiter.acquire("https://api.sec.gov/filings")
            >>> print(f"Waited {waited:.3f}s")
        """
        host = self._get_host(url)
        config = self._get_config(host)
        lock = await self._get_lock(host)
        stats = self._stats[host]

        async with lock:
            now = time.monotonic()

            # Check if in backoff period
            if stats.backoff_until and now < stats.backoff_until:
                wait_time = stats.backoff_until - now
                await asyncio.sleep(wait_time)
                now = time.monotonic()
                stats.backoff_until = None

            # Calculate wait time
            elapsed = now - self._last_request[host]
            wait_time = 0.0

            if config.burst > 0:
                # Token bucket mode
                if host not in self._tokens:
                    self._tokens[host] = float(config.burst)

                # Refill tokens
                self._tokens[host] = min(config.burst, self._tokens[host] + elapsed * config.rate)

                if self._tokens[host] < 1:
                    wait_time = (1 - self._tokens[host]) / config.rate
                    await asyncio.sleep(wait_time)
                    self._tokens[host] = 0
                else:
                    self._tokens[host] -= 1
            else:
                # Simple interval mode
                min_interval = config.min_interval or (1.0 / config.rate)
                if elapsed < min_interval:
                    wait_time = min_interval - elapsed
                    await asyncio.sleep(wait_time)

            self._last_request[host] = time.monotonic()

            # Update stats
            stats.request_count += 1
            stats.total_wait_time += wait_time
            stats.last_request = self._last_request[host]

            return wait_time

    def report_error(self, url: str, error_type: str = "unknown") -> None:
        """Report an error for adaptive rate limiting.

        Call this when receiving 429 Too Many Requests or similar errors.

        Args:
            url: Full URL or hostname.
            error_type: Type of error ("429", "timeout", "connection").
        """
        host = self._get_host(url)
        config = self._get_config(host)
        stats = self._stats[host]

        stats.error_count += 1

        if config.adaptive:
            # Exponential backoff based on error count
            backoff_seconds = min(
                2 ** min(stats.error_count, 6),  # Cap at 64 seconds
                60.0,
            )
            stats.backoff_until = time.monotonic() + backoff_seconds

            # Optionally reduce rate
            if stats.error_count >= 3:
                config.rate = max(config.rate * 0.8, 1.0)  # Reduce by 20%

    def report_success(self, url: str) -> None:
        """Report a successful request.

        Can be used to gradually restore rates after errors.

        Args:
            url: Full URL or hostname.
        """
        host = self._get_host(url)
        stats = self._stats[host]
        config = self._get_config(host)

        # Gradual recovery after 10 consecutive successes
        if stats.error_count > 0:
            stats.error_count = max(0, stats.error_count - 0.1)

            # Restore rate if errors cleared
            if stats.error_count == 0 and config.rate < self.default_rate:
                config.rate = min(config.rate * 1.05, self.default_rate)

    def get_stats(self, host: str | None = None) -> dict[str, Any]:
        """Get statistics for one or all hosts.

        Args:
            host: Specific host, or None for all hosts.

        Returns:
            Dictionary of statistics.
        """
        if host:
            stats = self._stats.get(host, HostStats())
            config = self._get_config(host)
            return {
                "host": host,
                "rate": config.rate,
                "burst": config.burst,
                "request_count": stats.request_count,
                "total_wait_time": stats.total_wait_time,
                "error_count": stats.error_count,
                "avg_wait": (stats.total_wait_time / stats.request_count if stats.request_count > 0 else 0.0),
            }

        return {host: self.get_stats(host) for host in self._stats}

    def reset(self, host: str | None = None) -> None:
        """Reset rate limiter state.

        Args:
            host: Specific host to reset, or None for all.
        """
        if host:
            if host in self._last_request:
                del self._last_request[host]
            if host in self._tokens:
                del self._tokens[host]
            if host in self._stats:
                self._stats[host] = HostStats()
        else:
            self._last_request.clear()
            self._tokens.clear()
            self._stats.clear()

    def clear_stale(self, max_age_seconds: float = 3600.0) -> int:
        """Remove state for hosts not accessed recently.

        Args:
            max_age_seconds: Remove hosts not accessed in this many seconds.

        Returns:
            Number of hosts cleared.
        """
        now = time.monotonic()
        stale_hosts = [host for host, stats in self._stats.items() if now - stats.last_request > max_age_seconds]

        for host in stale_hosts:
            self.reset(host)
            if host in self._locks:
                del self._locks[host]
            if host in self._configs and host not in self._configs:
                # Don't remove explicitly configured hosts
                pass

        return len(stale_hosts)


__all__ = ["HostRateLimiter", "HostConfig", "HostStats"]
