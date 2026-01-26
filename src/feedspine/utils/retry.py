"""Retry utilities for FeedSpine.

Provides configurable retry logic with exponential backoff for handling
transient failures in feed collection.

Example:
    >>> from feedspine.utils.retry import with_retry, RetryConfig
    >>> 
    >>> config = RetryConfig(max_attempts=3, base_delay=1.0)
    >>> result = await with_retry(fetch_data, config)
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger("feedspine.retry")

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior.
    
    Attributes:
        max_attempts: Maximum total attempts (including first try)
        base_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay between retries
        exponential_base: Multiplier for exponential backoff (default: 2)
        jitter: Random jitter factor (0-1) to prevent thundering herd
        retry_on: Exception types that should trigger retry
        no_retry_on: Exception types that should NOT retry
        on_retry: Callback called on each retry (exception, attempt, delay)
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1
    retry_on: tuple[type[Exception], ...] = (Exception,)
    no_retry_on: tuple[type[Exception], ...] = ()
    on_retry: Callable[[Exception, int, float], None] | None = None
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.
        
        Uses exponential backoff with jitter.
        
        Args:
            attempt: Current attempt number (1-indexed)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter
        if self.jitter > 0:
            jitter_amount = delay * self.jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def should_retry(self, exc: Exception, attempt: int) -> bool:
        """Determine if we should retry after an exception.
        
        Args:
            exc: The exception that occurred
            attempt: Current attempt number
            
        Returns:
            True if we should retry
        """
        # Check if we have attempts remaining
        if attempt >= self.max_attempts:
            return False
        
        # Check no_retry_on first (takes precedence)
        if self.no_retry_on and isinstance(exc, self.no_retry_on):
            return False
        
        # Check retry_on
        return isinstance(exc, self.retry_on)


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""
    
    def __init__(self, last_error: Exception, attempts: int):
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(
            f"All {attempts} retry attempts exhausted. Last error: {last_error}"
        )


@dataclass
class RetryResult:
    """Result of a retry operation.
    
    Attributes:
        success: Whether the operation succeeded
        result: The result value (if success)
        attempts: Number of attempts made
        total_delay: Total time spent waiting between retries
        errors: List of errors encountered
    """
    success: bool
    result: T | None = None
    attempts: int = 1
    total_delay: float = 0.0
    errors: list[Exception] = field(default_factory=list)


async def with_retry(
    func: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
) -> T:
    """Execute an async function with retry logic.
    
    Args:
        func: Async function to execute
        config: Retry configuration (default: 3 attempts)
        
    Returns:
        The result of the function
        
    Raises:
        RetryExhausted: If all retry attempts fail
        
    Example:
        >>> async def flaky_fetch():
        ...     response = await client.get(url)
        ...     return response.json()
        >>> 
        >>> config = RetryConfig(max_attempts=3, base_delay=1.0)
        >>> result = await with_retry(flaky_fetch, config)
    """
    config = config or RetryConfig()
    last_error: Exception | None = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func()
        except Exception as e:
            last_error = e
            
            if not config.should_retry(e, attempt):
                logger.debug(f"Not retrying {type(e).__name__} on attempt {attempt}")
                raise
            
            delay = config.calculate_delay(attempt)
            
            logger.warning(
                f"Attempt {attempt}/{config.max_attempts} failed: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            
            # Call the on_retry callback if provided
            if config.on_retry:
                config.on_retry(e, attempt, delay)
            
            await asyncio.sleep(delay)
    
    # All retries exhausted
    raise RetryExhausted(last_error or Exception("Unknown error"), config.max_attempts)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for retry logic.
    
    Args:
        max_attempts: Maximum total attempts
        base_delay: Initial delay before retry
        max_delay: Maximum delay between retries
        exponential_base: Multiplier for backoff
        retry_on: Exception types to retry on
        
    Example:
        >>> @retry(max_attempts=3, retry_on=(ConnectionError,))
        ... async def fetch_data():
        ...     return await client.get(url)
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        retry_on=retry_on,
    )
    
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs) -> T:
            async def _call() -> T:
                return await func(*args, **kwargs)
            return await with_retry(_call, config)
        return wrapper
    
    return decorator


__all__ = [
    "RetryConfig",
    "RetryExhausted",
    "RetryResult",
    "with_retry",
    "retry",
]
