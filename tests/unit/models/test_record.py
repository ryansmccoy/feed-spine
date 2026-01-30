"""Tests for feedspine.models.record."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record, RecordCandidate


class TestRecordCandidateCreation:
    """Tests for RecordCandidate creation."""

    def test_create_minimal(self) -> None:
        """Can create with required fields only."""
        candidate = RecordCandidate(
            natural_key="test-123",
            published_at=datetime.now(UTC),
            metadata=Metadata(source="test-feed"),
        )
        assert candidate.natural_key == "test-123"
        assert candidate.content == {}

    def test_create_with_content(self) -> None:
        """Can include content."""
        candidate = RecordCandidate(
            natural_key="test-123",
            published_at=datetime.now(UTC),
            content={"title": "Test Title", "body": "Test body"},
            metadata=Metadata(source="test"),
        )
        assert candidate.content["title"] == "Test Title"


class TestRecordCandidateValidation:
    """Tests for RecordCandidate validation."""

    def test_natural_key_normalized(self) -> None:
        """Natural key is normalized (lowercase, stripped)."""
        candidate = RecordCandidate(
            natural_key="  TEST-123  ",
            published_at=datetime.now(UTC),
            metadata=Metadata(source="test"),
        )
        assert candidate.natural_key == "test-123"

    def test_natural_key_required(self) -> None:
        """Natural key cannot be empty."""
        with pytest.raises(ValueError):
            RecordCandidate(
                natural_key="",
                published_at=datetime.now(UTC),
                metadata=Metadata(source="test"),
            )

    def test_published_at_required(self) -> None:
        """published_at is required."""
        with pytest.raises(ValueError):
            RecordCandidate(
                natural_key="test",
                metadata=Metadata(source="test"),
            )  # type: ignore[call-arg]


class TestRecordCreation:
    """Tests for Record creation."""

    @pytest.fixture
    def candidate(self) -> RecordCandidate:
        """Create a test candidate."""
        return RecordCandidate(
            natural_key="test-123",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Test"},
            metadata=Metadata(source="test-feed"),
        )

    def test_from_candidate(self, candidate: RecordCandidate) -> None:
        """Can create Record from RecordCandidate."""
        record = Record.from_candidate(candidate, record_id="uuid-123")

        assert record.id == "uuid-123"
        assert record.natural_key == candidate.natural_key
        assert record.layer == Layer.BRONZE
        assert record.content == candidate.content
        assert record.version == 1

    def test_from_candidate_preserves_metadata(self, candidate: RecordCandidate) -> None:
        """Metadata is preserved from candidate."""
        record = Record.from_candidate(candidate, record_id="uuid-123")
        assert record.metadata.source == "test-feed"


class TestRecordPromotion:
    """Tests for Record promotion through layers."""

    @pytest.fixture
    def bronze_record(self) -> Record:
        """Create a bronze record."""
        candidate = RecordCandidate(
            natural_key="test-123",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Test"},
            metadata=Metadata(source="test-feed"),
        )
        return Record.from_candidate(candidate, record_id="uuid-123")

    def test_promote_to_silver(self, bronze_record: Record) -> None:
        """Can promote from BRONZE to SILVER."""
        promoted = bronze_record.promote(Layer.SILVER, {"validated": True})

        assert promoted.layer == Layer.SILVER
        assert promoted.content["validated"] is True
        assert promoted.content["title"] == "Test"  # Original preserved
        assert promoted.version == 2
        assert promoted.id == bronze_record.id

    def test_promote_to_gold(self, bronze_record: Record) -> None:
        """Can promote from SILVER to GOLD."""
        silver = bronze_record.promote(Layer.SILVER)
        gold = silver.promote(Layer.GOLD, {"enriched": True})

        assert gold.layer == Layer.GOLD
        assert gold.version == 3

    def test_cannot_demote(self, bronze_record: Record) -> None:
        """Cannot promote to same or lower layer."""
        silver = bronze_record.promote(Layer.SILVER)

        with pytest.raises(ValueError):
            silver.promote(Layer.BRONZE)

    def test_cannot_promote_to_same_layer(self, bronze_record: Record) -> None:
        """Cannot promote to same layer."""
        with pytest.raises(ValueError):
            bronze_record.promote(Layer.BRONZE)

    def test_promote_without_enrichments(self, bronze_record: Record) -> None:
        """Can promote without adding enrichments."""
        promoted = bronze_record.promote(Layer.SILVER)
        assert promoted.layer == Layer.SILVER
        assert promoted.content == bronze_record.content


class TestRecordSightingTracking:
    """Tests for Record sighting tracking fields (optimized storage)."""

    @pytest.fixture
    def record(self) -> Record:
        """Create a test record."""
        candidate = RecordCandidate(
            natural_key="test-123",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Test"},
            metadata=Metadata(source="test-feed"),
        )
        return Record.from_candidate(candidate, record_id="uuid-123")

    def test_default_sighting_fields(self, record: Record) -> None:
        """New records have default sighting tracking fields."""
        assert record.first_seen_at is not None
        assert record.last_seen_at is not None
        assert record.seen_count == 1

    def test_record_sighting_increments_count(self, record: Record) -> None:
        """record_sighting() increments seen_count."""
        updated = record.record_sighting()
        assert updated.seen_count == 2
        # Original unchanged
        assert record.seen_count == 1

    def test_record_sighting_updates_last_seen(self, record: Record) -> None:
        """record_sighting() updates last_seen_at."""
        import time
        time.sleep(0.01)  # Ensure time difference
        updated = record.record_sighting()
        assert updated.last_seen_at >= record.last_seen_at

    def test_record_sighting_preserves_first_seen(self, record: Record) -> None:
        """record_sighting() does not change first_seen_at."""
        updated = record.record_sighting()
        assert updated.first_seen_at == record.first_seen_at

    def test_multiple_sightings(self, record: Record) -> None:
        """Multiple sightings accumulate correctly."""
        r1 = record.record_sighting()
        r2 = r1.record_sighting()
        r3 = r2.record_sighting()
        assert r3.seen_count == 4
        assert r3.first_seen_at == record.first_seen_at
        assert r3.last_seen_at >= r2.last_seen_at

    def test_record_sighting_with_custom_time(self, record: Record) -> None:
        """record_sighting() accepts custom seen_at time."""
        custom_time = datetime(2025, 6, 15, tzinfo=UTC)
        updated = record.record_sighting(seen_at=custom_time)
        assert updated.last_seen_at == custom_time
