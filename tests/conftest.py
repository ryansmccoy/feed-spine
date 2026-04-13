"""
Pytest configuration and fixtures for feedspine tests.

This conftest.py is shared across all test directories.

Provides:
- Auto-markers based on directory location
- Environment isolation (prevents .env leakage between tests)
- Common test data fixtures
- Path fixtures
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# =============================================================================
# Environment Isolation
# =============================================================================

# Variables that feedspine reads from the environment (FEEDSPINE_ prefix).
# Captured at import time so we can restore them after each test.
_FEEDSPINE_ENV_PREFIX = "FEEDSPINE_"


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent environment variable leakage between tests.

    Removes all FEEDSPINE_* vars before each test and restores the original
    environment afterwards (monkeypatch handles teardown automatically).
    """
    for key in list(os.environ):
        if key.startswith(_FEEDSPINE_ENV_PREFIX):
            monkeypatch.delenv(key, raising=False)


# =============================================================================
# Auto-Marking (ecosystem standard)
# =============================================================================


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-mark tests based on directory location."""
    for item in items:
        try:
            test_path = Path(item.fspath).relative_to(Path(__file__).parent)
        except ValueError:
            continue

        path_str = str(test_path)
        if "integration" in path_str:
            item.add_marker(pytest.mark.integration)
        if "e2e" in path_str:
            item.add_marker(pytest.mark.e2e)
        if "performance" in path_str:
            item.add_marker(pytest.mark.slow)

        # Auto-mark unmarked tests as unit
        markers = {mark.name for mark in item.iter_markers()}
        if not markers.intersection({"unit", "integration", "slow", "e2e", "examples"}):
            item.add_marker(pytest.mark.unit)


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture
def project_root() -> Path:
    """Return the feed-spine project root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the test fixtures directory."""
    return Path(__file__).resolve().parent / "fixtures"


# =============================================================================
# Common Test Data
# =============================================================================


@pytest.fixture
def sample_earnings_data() -> dict:
    """Sample earnings data matching Polygon demo format."""
    return {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "report_date": "2026-01-30",
        "report_time": "amc",
        "fiscal_year": 2026,
        "fiscal_quarter": 1,
        "fiscal_period": "Q1",
        "eps_estimate": 2.35,
        "eps_actual": 2.42,
        "revenue_estimate": 119000000000,
        "revenue_actual": 121000000000,
        "is_released": True,
        "source_vendor": "polygon",
        "source_feed": "reference/earnings",
    }


@pytest.fixture
def sample_miss_data() -> dict:
    """Sample earnings miss data."""
    return {
        "ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "report_date": "2026-01-30",
        "report_time": "amc",
        "fiscal_year": 2026,
        "fiscal_quarter": 2,
        "fiscal_period": "Q2",
        "eps_estimate": 2.80,
        "eps_actual": 2.50,
        "is_released": True,
        "source_vendor": "polygon",
    }
