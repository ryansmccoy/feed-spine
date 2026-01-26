"""FeedSpine HTTP utilities.

Provides rate limiting, retry logic, and download helpers for HTTP operations.

Example:
    >>> from feedspine.http import RateLimiter, HttpClient
    >>> 
    >>> # Rate limiting
    >>> limiter = RateLimiter(rate=10.0)  # 10 requests/second
    >>> await limiter.acquire()
    >>> 
    >>> # HTTP client with rate limiting and retries
    >>> async with HttpClient(rate_limit=10.0) as client:
    ...     response = await client.get("https://example.com/api")
    ...     await client.download("https://example.com/file.txt", "local.txt")
"""

from feedspine.http.client import HttpClient
from feedspine.http.rate_limiter import RateLimiter

__all__ = [
    "HttpClient",
    "RateLimiter",
]
