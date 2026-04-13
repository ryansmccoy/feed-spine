"""Rate limiter for feed adapters.

Extracted from BaseFeedAdapter to be composable, testable, and swappable.

Example:
    >>> from feedspine.adapter.rate_limiter import AdapterRateLimiter
    >>> limiter = AdapterRateLimiter(requests_per_second=2.0)
    >>> limiter.requests_per_second
    2.0
"""

from __future__ import annotations

import asyncio
import time


class AdapterRateLimiter:
    """Simple rate limiter enforcing a per-second request quota.

    Args:
        requests_per_second: Maximum requests per second. 0 disables limiting.
    """

    def __init__(self, requests_per_second: float = 1.0) -> None:
        self._requests_per_second = requests_per_second
        self._last_request_time: float = 0.0

    @property
    def requests_per_second(self) -> float:
        """Configured rate limit."""
        return self._requests_per_second

    async def acquire(self) -> None:
        """Wait until a request is allowed under the rate limit."""
        if self._last_request_time > 0 and self._requests_per_second > 0:
            min_interval = 1.0 / self._requests_per_second
            elapsed = time.time() - self._last_request_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

        self._last_request_time = time.time()
