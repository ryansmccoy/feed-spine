"""FeedSpine HTTP utilities.

Provides rate limiting, retry logic, and download helpers for HTTP operations.

Example:
    >>> from feedspine.http import RateLimiter, HttpClient, HostRateLimiter
    >>>
    >>> # Simple rate limiting
    >>> limiter = RateLimiter(rate=10.0)  # 10 requests/second
    >>> await limiter.acquire()
    >>>
    >>> # Per-host rate limiting
    >>> host_limiter = HostRateLimiter(default_rate=10.0)
    >>> host_limiter.set_rate("api.sec.gov", 5.0)  # SEC has strict limits
    >>> await host_limiter.acquire("https://api.sec.gov/filings")
    >>>
    >>> # HTTP client with rate limiting and retries
    >>> async with HttpClient(rate_limit=10.0) as client:
    ...     response = await client.get("https://example.com/api")
    ...     await client.download("https://example.com/file.txt", "local.txt")
"""

from feedspine.http.client import HttpClient
from feedspine.http.host_rate_limiter import HostConfig, HostRateLimiter, HostStats
from feedspine.http.rate_limiter import RateLimiter

__all__ = [
    "HttpClient",
    "RateLimiter",
    "HostRateLimiter",
    "HostConfig",
    "HostStats",
]
