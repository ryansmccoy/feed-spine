"""Rate limiter for controlling request frequency.

Provides a token bucket rate limiter to ensure compliance with API rate limits.

Example:
    >>> from feedspine.http import RateLimiter
    >>> 
    >>> limiter = RateLimiter(rate=10.0)  # 10 requests per second
    >>> 
    >>> # In async code
    >>> await limiter.acquire()  # Waits if needed
    >>> # ... make request ...
"""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Token bucket rate limiter for API compliance.
    
    Uses a sliding window approach to ensure request rate stays
    within the specified limit.
    
    Example:
        >>> import asyncio
        >>> limiter = RateLimiter(rate=10.0)  # 10 requests/second
        >>> 
        >>> async def make_requests():
        ...     for i in range(100):
        ...         await limiter.acquire()
        ...         # ... make request ...
        >>> 
        >>> asyncio.run(make_requests())
    
    Attributes:
        rate: Maximum requests per second
        min_interval: Minimum interval between requests
    """
    
    def __init__(self, rate: float = 10.0):
        """Initialize rate limiter.
        
        Args:
            rate: Maximum requests per second (default: 10)
        """
        self.rate = rate
        self.min_interval = 1.0 / rate
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> float:
        """Wait until a request can be made.
        
        Returns:
            Time waited in seconds
            
        Example:
            >>> limiter = RateLimiter(rate=10.0)
            >>> await limiter.acquire()  # May wait
            >>> # ... safe to make request now ...
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            wait_time = 0.0
            
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
            
            self._last_request = time.monotonic()
            return wait_time
    
    def reset(self) -> None:
        """Reset the rate limiter state.
        
        Useful for testing or after long pauses.
        """
        self._last_request = 0.0


class BurstRateLimiter:
    """Rate limiter with burst capacity.
    
    Allows bursts of requests up to a limit, then enforces rate limiting.
    Uses a token bucket algorithm.
    
    Example:
        >>> limiter = BurstRateLimiter(rate=10.0, burst=50)
        >>> # First 50 requests go through immediately
        >>> # Then limited to 10/second
    
    Attributes:
        rate: Requests per second (token refill rate)
        burst: Maximum burst size (bucket capacity)
    """
    
    def __init__(self, rate: float = 10.0, burst: int = 50):
        """Initialize burst rate limiter.
        
        Args:
            rate: Requests per second (token refill rate)
            burst: Maximum burst size (bucket capacity)
        """
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> float:
        """Acquire a token, waiting if necessary.
        
        Returns:
            Time waited in seconds
        """
        async with self._lock:
            now = time.monotonic()
            
            # Refill tokens
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now
            
            wait_time = 0.0
            if self._tokens < 1:
                # Calculate wait time for one token
                wait_time = (1 - self._tokens) / self.rate
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1
            
            return wait_time
    
    def reset(self) -> None:
        """Reset to full burst capacity."""
        self._tokens = float(self.burst)
        self._last_update = time.monotonic()
    
    @property
    def available_tokens(self) -> float:
        """Current available tokens (approximate)."""
        elapsed = time.monotonic() - self._last_update
        return min(self.burst, self._tokens + elapsed * self.rate)


__all__ = [
    "RateLimiter",
    "BurstRateLimiter",
]
