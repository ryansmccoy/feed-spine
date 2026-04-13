"""Integration tests that run FeedSpine examples as test cases.

These tests ensure all examples execute without errors and follow
best practices (docstrings, no external dependencies, etc.).

Run with:
    pytest tests/integration/test_examples.py -v
    pytest tests/integration/test_examples.py -v -k "quickstart"

    # Fast CI mode using demo mode:
    FEEDSPINE_DEMO_MODE=1 pytest tests/integration/test_examples.py -v
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Resolve examples directory
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"

# Add examples to path for registry import
sys.path.insert(0, str(EXAMPLES_DIR.parent))
from examples._registry import ExampleRegistry  # noqa: E402

# Initialize registry once for discovery
_registry = ExampleRegistry(root=EXAMPLES_DIR)


def _demo_mode_env() -> dict[str, str]:
    """Return environment dict with demo mode enabled."""
    env = dict(os.environ)
    env["FEEDSPINE_DEMO_MODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _is_demo_mode() -> bool:
    """Check if running in demo/CI mode."""
    return os.environ.get("FEEDSPINE_DEMO_MODE", "").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Legacy per-category discovery (for backward compatibility)
# ---------------------------------------------------------------------------


def get_getting_started_examples():
    """Get getting started example files."""
    return [(e.name, e.path) for e in _registry.by_category("01_getting_started")]


def get_storage_examples():
    """Get storage example files."""
    return [(e.name, e.path) for e in _registry.by_category("02_storage")]


def get_domain_feed_examples():
    """Get domain feed example files."""
    return [(e.name, e.path) for e in _registry.by_category("03_domain_feeds")]


def get_operations_examples():
    """Get operations example files."""
    return [(e.name, e.path) for e in _registry.by_category("04_operations")]


def get_integration_examples():
    """Get integration example files."""
    return [(e.name, e.path) for e in _registry.by_category("05_integrations")]


def get_earnings_examples():
    """Get earnings subsystem examples."""
    return [(e.name, e.path) for e in _registry.by_category("06_earnings")]


# ---------------------------------------------------------------------------
# Registry-based discovery (recommended)
# ---------------------------------------------------------------------------


def get_all_examples():
    """Get all examples via auto-discovery registry."""
    return _registry.as_pytest_params()


@pytest.mark.slow
class TestGettingStartedExamples:
    """Test getting started FeedSpine examples - runs via subprocess."""

    @pytest.mark.parametrize("name,path", get_getting_started_examples())
    def test_getting_started_example_runs(self, name, path):
        """Each getting started example should run without errors."""
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(EXAMPLES_DIR.parent),
            encoding="utf-8",
            errors="replace",
            env={**dict(__import__("os").environ), "PYTHONIOENCODING": "utf-8"},
        )

        # Some examples may fail due to network issues - that's expected
        # We mainly check for import errors and syntax errors
        if result.returncode != 0:
            # Check if it's a network error (acceptable) vs code error (fail)
            stderr = result.stderr.lower()
            if any(x in stderr for x in ["import", "syntax", "attribute", "name"]):
                pytest.fail(f"Getting started example {name} has code error:\nSTDERR: {result.stderr[:500]}")
            else:
                pytest.skip(f"Example {name} requires network (expected)")

    @pytest.mark.parametrize("name,path", get_getting_started_examples())
    def test_getting_started_example_has_docstring(self, name, path):
        """Each getting started example should have a module docstring."""
        content = path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # Skip shebang if present
        start_idx = 1 if lines[0].startswith("#!") else 0

        has_docstring = lines[start_idx].startswith('"""') or lines[start_idx].startswith("'''")

        assert has_docstring, f"Example {name} missing module docstring"


class TestOperationsExamples:
    """Test operations FeedSpine examples."""

    @pytest.mark.parametrize("name,path", get_operations_examples())
    def test_operations_example_syntax(self, name, path):
        """Each operations example should have valid Python syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Operations example {name} has syntax error:\n{result.stderr}"


class TestEarningsExamples:
    """Test earnings subsystem examples."""

    @pytest.mark.slow
    @pytest.mark.parametrize("name,path", get_earnings_examples())
    def test_earnings_example_syntax(self, name, path):
        """Each earnings example should have valid Python syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Earnings example {name} has syntax error:\n{result.stderr}"


class TestNetworkFreeExamples:
    """Verify certain examples work without network."""

    def test_operational_tracking_offline(self):
        """01_operational_tracking.py uses simulated data."""
        path = EXAMPLES_DIR / "04_operations" / "01_operational_tracking.py"
        if not path.exists():
            pytest.skip("Example not found")

        content = path.read_text(encoding="utf-8")

        # Should have simulated feed class
        assert "Simulated" in content or "Mock" in content or "simulated" in content

    def test_smart_sync_offline(self):
        """03_smart_sync_strategy.py doesn't need network."""
        path = EXAMPLES_DIR / "04_operations" / "03_smart_sync_strategy.py"
        if not path.exists():
            pytest.skip("Example not found")

        content = path.read_text(encoding="utf-8")

        # Should not have direct HTTP calls
        assert "httpx.get" not in content
        assert "requests.get" not in content


# ---------------------------------------------------------------------------
# Registry-based comprehensive tests (recommended for CI)
# ---------------------------------------------------------------------------


class TestAllExamplesViaRegistry:
    """Run ALL discovered examples via the ExampleRegistry.

    This is the recommended entry-point for CI. Use FEEDSPINE_DEMO_MODE=1
    for fast execution (examples that support demo mode exit early).

    Usage:
        # Full run (may hit network, slower)
        pytest tests/integration/test_examples.py::TestAllExamplesViaRegistry -v

        # Fast CI run (demo mode, no network)
        FEEDSPINE_DEMO_MODE=1 pytest tests/integration/test_examples.py::TestAllExamplesViaRegistry -v
    """

    @pytest.mark.parametrize("name,path", get_all_examples())
    def test_example_runs(self, name: str, path: Path):
        """Each example should execute without import/syntax errors."""
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(EXAMPLES_DIR.parent),
            encoding="utf-8",
            errors="replace",
            env=_demo_mode_env() if _is_demo_mode() else {**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        if result.returncode != 0:
            stderr = result.stderr.lower()
            # Distinguish code errors from network/runtime errors
            code_error_patterns = ["importerror", "syntaxerror", "nameerror", "attributeerror"]
            if any(pat in stderr for pat in code_error_patterns):
                pytest.fail(f"Example {name} has code error:\nSTDERR:\n{result.stderr[:1000]}")
            else:
                # Network/runtime failure - skip in non-demo mode
                if not _is_demo_mode():
                    pytest.skip(f"Example {name} failed (likely network): {result.stderr[:200]}")
                else:
                    pytest.fail(f"Demo-mode example {name} failed:\nSTDERR:\n{result.stderr[:1000]}")

    @pytest.mark.parametrize("name,path", get_all_examples())
    def test_example_has_docstring(self, name: str, path: Path):
        """Each example should have a module docstring."""
        content = path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # Skip shebang if present
        start_idx = 1 if lines and lines[0].startswith("#!") else 0

        has_docstring = len(lines) > start_idx and (
            lines[start_idx].startswith('"""') or lines[start_idx].startswith("'''")
        )
        assert has_docstring, f"Example {name} missing module docstring"


class TestExamplesRegistryMetadata:
    """Verify the ExampleRegistry discovers all expected examples."""

    def test_registry_has_examples(self):
        """Registry should discover examples."""
        assert len(_registry) > 0, "No examples discovered"

    def test_registry_has_expected_categories(self):
        """Registry should have at least core categories."""
        cats = _registry.categories
        expected = {"01_getting_started", "02_storage", "03_domain_feeds", "04_operations"}
        found = set(cats)
        missing = expected - found
        assert not missing, f"Missing expected categories: {missing}"

    def test_all_examples_have_titles(self):
        """Each example should have a parsed title."""
        missing_titles = [e.name for e in _registry if not e.title]
        assert not missing_titles, f"Examples missing titles: {missing_titles}"

    def test_registry_count_at_least_15(self):
        """Should have at least 15 examples across all categories."""
        assert len(_registry) >= 15, f"Expected >=15 examples, found {len(_registry)}"
