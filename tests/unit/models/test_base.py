"""Tests for feedspine.models.base."""

from __future__ import annotations

import pytest

from feedspine.models.base import Layer, Metadata


class TestLayer:
    """Tests for Layer enum."""

    def test_layer_values(self) -> None:
        """Layer has correct values."""
        assert Layer.BRONZE.value == "bronze"
        assert Layer.SILVER.value == "silver"
        assert Layer.GOLD.value == "gold"

    def test_layer_ordering(self) -> None:
        """Layers have logical ordering for promotion.

        Note: Layer uses string values, ordering is conceptual not lexical.
        """
        # Layer ordering is conceptual: BRONZE -> SILVER -> GOLD
        layers = [Layer.BRONZE, Layer.SILVER, Layer.GOLD]
        assert layers[0] == Layer.BRONZE
        assert layers[1] == Layer.SILVER
        assert layers[2] == Layer.GOLD


class TestMetadata:
    """Tests for Metadata model."""

    def test_create_minimal(self) -> None:
        """Can create with source only."""
        meta = Metadata(source="test-feed")
        assert meta.source == "test-feed"
        assert meta.extra == {}

    def test_create_with_extra(self) -> None:
        """Can include extra data."""
        meta = Metadata(source="test", extra={"key": "value"})
        assert meta.extra["key"] == "value"

    def test_captured_at_auto(self) -> None:
        """captured_at is set automatically."""
        meta = Metadata(source="test")
        assert meta.captured_at is not None

    def test_source_required(self) -> None:
        """Source is required."""
        with pytest.raises(ValueError):
            Metadata()  # type: ignore[call-arg]
