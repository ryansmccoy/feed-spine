"""Tests for feedspine.utils.retry module.

Tests retry configuration, delay calculation, and the retry decorator.
"""

from __future__ import annotations

import asyncio

import pytest

from feedspine.utils.retry import RetryConfig, RetryResult, with_retry

# ---------------------------------------------------------------------------
# RetryConfig
# ---------------------------------------------------------------------------


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self):
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay > 0

    def test_calculate_delay_increases(self):
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.0)
        d1 = config.calculate_delay(1)
        d2 = config.calculate_delay(2)
        assert d2 > d1

    def test_calculate_delay_respects_max(self):
        config = RetryConfig(base_delay=1.0, max_delay=5.0, exponential_base=10.0, jitter=0.0)
        delay = config.calculate_delay(10)
        assert delay <= 5.0

    def test_should_retry_on_matching_exception(self):
        config = RetryConfig(max_attempts=3, retry_on=(ValueError,))
        assert config.should_retry(ValueError("test"), attempt=1) is True

    def test_should_retry_exhausted(self):
        config = RetryConfig(max_attempts=3)
        assert config.should_retry(ValueError("test"), attempt=3) is False

    def test_should_retry_excluded_exception(self):
        config = RetryConfig(no_retry_on=(KeyError,))
        assert config.should_retry(KeyError("test"), attempt=1) is False


# ---------------------------------------------------------------------------
# RetryResult
# ---------------------------------------------------------------------------


class TestRetryResult:
    """Tests for RetryResult dataclass."""

    def test_success_result(self):
        r = RetryResult(success=True, result=42, attempts=1, total_delay=0.0, errors=[])
        assert r.success is True
        assert r.result == 42

    def test_failure_result(self):
        r = RetryResult(success=False, result=None, attempts=3, total_delay=3.0, errors=[ValueError("x")])
        assert r.success is False
        assert len(r.errors) == 1


# ---------------------------------------------------------------------------
# with_retry
# ---------------------------------------------------------------------------


class TestWithRetry:
    """Tests for the with_retry async function."""

    def test_succeeds_first_try(self):
        async def ok():
            return 42

        result = asyncio.run(with_retry(ok))
        assert result == 42

    def test_retries_then_succeeds(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "done"

        config = RetryConfig(max_attempts=5, base_delay=0.01, max_delay=0.02)
        result = asyncio.run(with_retry(flaky, config=config))
        assert result == "done"
        assert call_count == 3

    def test_exhausts_retries(self):
        async def always_fail():
            raise ValueError("permanent")

        config = RetryConfig(max_attempts=2, base_delay=0.01, max_delay=0.02)
        # should_retry returns False on the last attempt → original error is re-raised
        with pytest.raises(ValueError, match="permanent"):
            asyncio.run(with_retry(always_fail, config=config))
