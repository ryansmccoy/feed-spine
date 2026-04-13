"""Tests for feedspine.models.sighting."""

from __future__ import annotations

import pytest

from feedspine.models.sighting import Sighting


class TestSightingCreation:
    """Tests for Sighting creation."""

    def test_create_minimal(self) -> None:
        """Can create with required fields."""
        sighting = Sighting(
            id="sight-1",
            natural_key="key-123",
            source="test-feed",
            is_new=True,
        )
        assert sighting.id == "sight-1"
        assert sighting.natural_key == "key-123"
        assert sighting.is_new is True

    def test_create_with_record_id(self) -> None:
        """Can include record_id."""
        sighting = Sighting(
            id="sight-1",
            natural_key="key-123",
            source="test-feed",
            is_new=False,
            record_id="rec-456",
        )
        assert sighting.record_id == "rec-456"

    def test_seen_at_auto(self) -> None:
        """seen_at is set automatically."""
        sighting = Sighting(
            id="sight-1",
            natural_key="key-123",
            source="test-feed",
            is_new=True,
        )
        assert sighting.seen_at is not None

    def test_with_hash(self) -> None:
        """Can include raw data hash."""
        sighting = Sighting(
            id="sight-1",
            natural_key="key-123",
            source="test-feed",
            is_new=True,
            raw_data_hash="abc123hash",
        )
        assert sighting.raw_data_hash == "abc123hash"


class TestSightingValidation:
    """Tests for Sighting validation."""

    def test_natural_key_required(self) -> None:
        """natural_key is required."""
        with pytest.raises(ValueError):
            Sighting(
                id="sight-1",
                source="test-feed",
                is_new=True,
            )  # type: ignore[call-arg]

    def test_source_required(self) -> None:
        """source is required."""
        with pytest.raises(ValueError):
            Sighting(
                id="sight-1",
                natural_key="key-123",
                is_new=True,
            )  # type: ignore[call-arg]
