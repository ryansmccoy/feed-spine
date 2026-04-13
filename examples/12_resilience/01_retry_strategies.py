#!/usr/bin/env python3
"""
Retry Strategies & Resilient Collection
========================================

This example demonstrates FeedSpine's **retry utilities** for building
fault-tolerant feed collection pipelines.

What You'll Learn:
    1. Configuring RetryConfig (attempts, delays, backoff, jitter)
    2. Using with_retry() for any async operation
    3. Selective retry (which errors to retry vs. fail fast)
    4. Callbacks for monitoring retry behavior

Key Concepts:
    - RetryConfig: Dataclass controlling retry behavior
    - Exponential backoff: Delays grow exponentially (1s, 2s, 4s, 8s...)
    - Jitter: Random variance prevents thundering herd
    - Selective retry: Only retry transient errors, not auth failures

Usage:
    python examples/12_resilience/01_retry_strategies.py

Expected Output:
    Shows retry behavior with simulated failures, backoff timing,
    and selective retry vs. fast-fail based on exception type.
"""

import asyncio
import random

from feedspine.utils.retry import RetryConfig, with_retry


# ============================================================================
# Simulated Failures
# ============================================================================

class TransientError(Exception):
    """Temporary failure — should be retried."""
    pass


class AuthError(Exception):
    """Permanent failure — should NOT be retried."""
    pass


async def flaky_api_call(fail_count: list[int], max_fails: int = 2) -> dict:
    """Simulates an API that fails transiently then succeeds."""
    fail_count[0] += 1
    if fail_count[0] <= max_fails:
        raise TransientError(f"Connection timeout (attempt {fail_count[0]})")
    return {"status": "ok", "data": [1, 2, 3]}


async def always_auth_fail() -> dict:
    """Simulates a permanent auth failure."""
    raise AuthError("Invalid API key")


async def main() -> None:
    # =========================================================================
    # EXAMPLE 1: Basic Retry with Exponential Backoff
    # =========================================================================
    print("=" * 60)
    print("EXAMPLE 1: Basic Retry (Exponential Backoff)")
    print("=" * 60)

    config = RetryConfig(
        max_attempts=5,       # Try up to 5 times total
        base_delay=0.1,       # Start with 0.1s delay (short for demo)
        max_delay=2.0,        # Never wait more than 2s
        exponential_base=2.0, # Double the delay each time
        jitter=0.1,           # ±10% random variance
    )

    # Show what the delays look like
    print("\nBackoff schedule:")
    for attempt in range(1, config.max_attempts + 1):
        delay = config.calculate_delay(attempt)
        print(f"  Attempt {attempt}: {delay:.3f}s delay")

    # Run with simulated failures
    fail_counter = [0]
    print("\nExecuting with 2 transient failures...")
    result = await with_retry(lambda: flaky_api_call(fail_counter, max_fails=2), config)
    print(f"  Success on attempt {fail_counter[0]}: {result}")

    # =========================================================================
    # EXAMPLE 2: Retry with Monitoring Callback
    # =========================================================================
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Retry with Monitoring Callback")
    print("=" * 60)

    retry_log: list[str] = []

    def on_retry(exc: Exception, attempt: int, delay: float) -> None:
        """Called before each retry — log, alert, increment metrics."""
        msg = f"  ⚠ Retry {attempt}: {exc} (waiting {delay:.2f}s)"
        print(msg)
        retry_log.append(msg)

    config_monitored = RetryConfig(
        max_attempts=4,
        base_delay=0.05,
        jitter=0.0,  # No jitter for predictable demo output
        on_retry=on_retry,
    )

    fail_counter = [0]
    result = await with_retry(
        lambda: flaky_api_call(fail_counter, max_fails=2),
        config_monitored,
    )
    print(f"\n  Succeeded after {len(retry_log)} retries")

    # =========================================================================
    # EXAMPLE 3: Selective Retry (Transient vs. Permanent)
    # =========================================================================
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Selective Retry")
    print("=" * 60)

    config_selective = RetryConfig(
        max_attempts=5,
        base_delay=0.05,
        retry_on=(TransientError,),     # ONLY retry these
        no_retry_on=(AuthError,),       # NEVER retry these
    )

    # Transient error → retried and succeeds
    fail_counter = [0]
    print("\n  Transient error (should retry and succeed):")
    result = await with_retry(
        lambda: flaky_api_call(fail_counter, max_fails=1),
        config_selective,
    )
    print(f"    ✓ Succeeded: {result}")

    # Auth error → fails immediately (no retry)
    print("\n  Auth error (should fail immediately, no retry):")
    try:
        await with_retry(always_auth_fail, config_selective)
    except AuthError as e:
        print(f"    ✗ Failed fast: {e} (no retries wasted)")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("RETRY STRATEGY GUIDE")
    print("=" * 60)
    print("""
When to use each strategy:

  AGGRESSIVE (fast retry, many attempts):
    RetryConfig(max_attempts=10, base_delay=0.5, max_delay=10)
    Use for: Internal services, local databases

  CONSERVATIVE (slow backoff, fewer attempts):
    RetryConfig(max_attempts=3, base_delay=5.0, max_delay=300)
    Use for: External APIs, rate-limited services

  SELECTIVE (only retry transient errors):
    RetryConfig(retry_on=(TimeoutError, ConnectionError),
                no_retry_on=(AuthError, ValueError))
    Use for: APIs where some errors are permanent

  WITH MONITORING (callback for observability):
    RetryConfig(on_retry=lambda exc, attempt, delay: log(exc))
    Use for: Production pipelines with alerting
    """)


if __name__ == "__main__":
    asyncio.run(main())
