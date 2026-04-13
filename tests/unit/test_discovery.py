"""Tests for feedspine.discovery module.

Covers adapter discovery, registration, listing, and cache clearing.
"""

from __future__ import annotations

import pytest

from feedspine.discovery import (
    clear_cache,
    discover_adapters,
    get_adapter,
    list_adapters,
    register_adapter,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """Clear adapter cache between tests."""
    clear_cache()
    yield
    clear_cache()


class TestDiscoverAdapters:
    """Tests for entry-point-based adapter discovery."""

    def test_returns_dict(self):
        adapters = discover_adapters()
        assert isinstance(adapters, dict)

    def test_cached(self):
        """Second call returns the same object (cached)."""
        a1 = discover_adapters()
        a2 = discover_adapters()
        assert a1 is a2

    def test_reload_refreshes_cache(self):
        discover_adapters()
        # reload should not raise
        discover_adapters(reload=True)


class TestRegisterAdapter:
    """Tests for manual adapter registration."""

    def test_register_and_retrieve(self):
        class MyAdapter:
            pass

        register_adapter("test-adapter", MyAdapter)
        assert get_adapter("test-adapter") is MyAdapter

    def test_register_overwrites(self):
        class A:
            pass

        class B:
            pass

        register_adapter("x", A)
        register_adapter("x", B)
        assert get_adapter("x") is B


class TestGetAdapter:
    """Tests for get_adapter lookup."""

    def test_nonexistent_returns_none(self):
        assert get_adapter("does-not-exist") is None

    def test_returns_registered(self):
        class Stub:
            pass

        register_adapter("stub", Stub)
        assert get_adapter("stub") is Stub


class TestListAdapters:
    """Tests for list_adapters metadata."""

    def test_returns_list(self):
        result = list_adapters()
        assert isinstance(result, list)

    def test_registered_adapter_appears(self):
        class Doc:
            """My adapter docs."""

        register_adapter("doc-adapter", Doc)
        infos = list_adapters()
        names = {i["name"] for i in infos}
        assert "doc-adapter" in names

    def test_info_has_required_keys(self):
        class A:
            pass

        register_adapter("a", A)
        info = next(i for i in list_adapters() if i["name"] == "a")
        assert "name" in info
        assert "class" in info
        assert "docstring" in info
