"""TDD tests for enricher implementations.

Following TDD workflow:
1. Write failing tests first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor (REFACTOR)
"""

from __future__ import annotations

from datetime import datetime

import pytest

from feedspine.models.base import Layer
from feedspine.models.record import Metadata, Record
from feedspine.protocols.enricher import EnrichmentStatus

pytestmark = pytest.mark.asyncio


def make_record(
    record_id: str = "test:123",
    layer: Layer = Layer.BRONZE,
    **kwargs: object,
) -> Record:
    """Create a test record with sensible defaults."""
    return Record(
        id=record_id,
        natural_key="test:123",
        layer=layer,
        metadata=Metadata(source="test"),
        captured_at=datetime.now(),
        published_at=datetime.now(),
        **kwargs,
    )


class TestPassthroughEnricherCreation:
    """Tests for PassthroughEnricher instantiation."""

    async def test_create_enricher(self) -> None:
        """PassthroughEnricher can be instantiated."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        assert enricher is not None

    async def test_has_name_property(self) -> None:
        """PassthroughEnricher has a name property."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        assert enricher.name == "PassthroughEnricher"

    async def test_custom_name(self) -> None:
        """PassthroughEnricher can have a custom name."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher(name="CustomEnricher")
        assert enricher.name == "CustomEnricher"


class TestPassthroughEnricherCanEnrich:
    """Tests for can_enrich() method."""

    async def test_can_enrich_bronze(self) -> None:
        """PassthroughEnricher can enrich BRONZE records."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record(layer=Layer.BRONZE)

        result = await enricher.can_enrich(record)

        assert result is True

    async def test_can_enrich_silver(self) -> None:
        """PassthroughEnricher can enrich SILVER records."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record(layer=Layer.SILVER)

        result = await enricher.can_enrich(record)

        assert result is True

    async def test_cannot_enrich_gold(self) -> None:
        """PassthroughEnricher cannot enrich GOLD records (already at top)."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record(layer=Layer.GOLD)

        result = await enricher.can_enrich(record)

        assert result is False


class TestPassthroughEnricherEnrich:
    """Tests for enrich() method."""

    async def test_enrich_returns_result(self) -> None:
        """enrich() returns an EnrichmentResult."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record()

        result = await enricher.enrich(record)

        assert result.record_id == record.id
        assert result.enricher_name == "PassthroughEnricher"

    async def test_enrich_success_status(self) -> None:
        """enrich() returns SUCCESS status for valid records."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record(layer=Layer.BRONZE)

        result = await enricher.enrich(record)

        assert result.status == EnrichmentStatus.SUCCESS

    async def test_enrich_promotes_bronze_to_silver(self) -> None:
        """enrich() promotes BRONZE to SILVER."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record(layer=Layer.BRONZE)

        result = await enricher.enrich(record)

        assert result.source_layer == Layer.BRONZE
        assert result.target_layer == Layer.SILVER
        assert record.layer == Layer.SILVER  # Record is modified

    async def test_enrich_promotes_silver_to_gold(self) -> None:
        """enrich() promotes SILVER to GOLD."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record(layer=Layer.SILVER)

        result = await enricher.enrich(record)

        assert result.source_layer == Layer.SILVER
        assert result.target_layer == Layer.GOLD
        assert record.layer == Layer.GOLD

    async def test_enrich_skips_gold(self) -> None:
        """enrich() skips GOLD records (cannot promote further)."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record(layer=Layer.GOLD)

        result = await enricher.enrich(record)

        assert result.status == EnrichmentStatus.SKIPPED
        assert record.layer == Layer.GOLD  # Unchanged

    async def test_enrich_has_duration(self) -> None:
        """enrich() includes duration_ms in result."""
        from feedspine.enricher import PassthroughEnricher

        enricher = PassthroughEnricher()
        record = make_record()

        result = await enricher.enrich(record)

        assert result.duration_ms >= 0


class TestMetadataEnricher:
    """Tests for MetadataEnricher that adds specific fields."""

    async def test_create_metadata_enricher(self) -> None:
        """MetadataEnricher can be instantiated with fields to add."""
        from feedspine.enricher import MetadataEnricher

        enricher = MetadataEnricher(fields={"processed": True, "version": "1.0"})
        assert enricher is not None

    async def test_metadata_enricher_name(self) -> None:
        """MetadataEnricher has a configurable name."""
        from feedspine.enricher import MetadataEnricher

        enricher = MetadataEnricher(
            name="CustomMeta",
            fields={"processed": True},
        )
        assert enricher.name == "CustomMeta"

    async def test_adds_metadata_fields(self) -> None:
        """MetadataEnricher adds specified fields to record metadata."""
        from feedspine.enricher import MetadataEnricher

        enricher = MetadataEnricher(fields={"processed": True, "version": "1.0"})
        record = make_record()

        result = await enricher.enrich(record)

        assert result.status == EnrichmentStatus.SUCCESS
        assert record.metadata.extra["processed"] is True
        assert record.metadata.extra["version"] == "1.0"
        assert result.fields_added == ["processed", "version"]

    async def test_can_enrich_any_layer(self) -> None:
        """MetadataEnricher can enrich records at any layer."""
        from feedspine.enricher import MetadataEnricher

        enricher = MetadataEnricher(fields={"tag": "test"})

        for layer in [Layer.BRONZE, Layer.SILVER, Layer.GOLD]:
            record = make_record(layer=layer)
            assert await enricher.can_enrich(record) is True

    async def test_does_not_promote(self) -> None:
        """MetadataEnricher adds fields but does not promote layer."""
        from feedspine.enricher import MetadataEnricher

        enricher = MetadataEnricher(fields={"tag": "test"})
        record = make_record(layer=Layer.BRONZE)

        result = await enricher.enrich(record)

        assert record.layer == Layer.BRONZE  # Unchanged
        assert result.source_layer == Layer.BRONZE
        assert result.target_layer == Layer.BRONZE  # Same layer

    async def test_updates_existing_fields(self) -> None:
        """MetadataEnricher updates existing fields if they exist."""
        from feedspine.enricher import MetadataEnricher

        enricher = MetadataEnricher(fields={"version": "2.0"})
        record = make_record()
        record.metadata.extra["version"] = "1.0"  # Pre-existing

        result = await enricher.enrich(record)

        assert record.metadata.extra["version"] == "2.0"
        assert result.fields_updated == ["version"]
        assert "version" not in result.fields_added


class TestEnricherProtocolCompliance:
    """Tests that enrichers implement the Enricher protocol."""

    async def test_passthrough_implements_protocol(self) -> None:
        """PassthroughEnricher implements the Enricher protocol."""
        from feedspine.enricher import PassthroughEnricher
        from feedspine.protocols.enricher import Enricher

        enricher = PassthroughEnricher()
        assert isinstance(enricher, Enricher)

    async def test_metadata_implements_protocol(self) -> None:
        """MetadataEnricher implements the Enricher protocol."""
        from feedspine.enricher import MetadataEnricher
        from feedspine.protocols.enricher import Enricher

        enricher = MetadataEnricher(fields={})
        assert isinstance(enricher, Enricher)


class TestEnrichmentResultDataclass:
    """Tests for EnrichmentResult dataclass."""

    def test_create_result(self) -> None:
        """EnrichmentResult can be created with minimal args."""
        from feedspine.protocols.enricher import EnrichmentResult

        result = EnrichmentResult(
            record_id="test:123",
            status=EnrichmentStatus.SUCCESS,
            enricher_name="TestEnricher",
        )

        assert result.record_id == "test:123"
        assert result.status == EnrichmentStatus.SUCCESS
        assert result.enricher_name == "TestEnricher"
        assert result.fields_added == []
        assert result.fields_updated == []

    def test_result_with_all_fields(self) -> None:
        """EnrichmentResult can be created with all optional fields."""
        from feedspine.protocols.enricher import EnrichmentResult

        result = EnrichmentResult(
            record_id="test:123",
            status=EnrichmentStatus.SUCCESS,
            enricher_name="TestEnricher",
            source_layer=Layer.BRONZE,
            target_layer=Layer.SILVER,
            fields_added=["field1", "field2"],
            fields_updated=["field3"],
            duration_ms=50.5,
            metadata={"extra": "data"},
        )

        assert result.source_layer == Layer.BRONZE
        assert result.target_layer == Layer.SILVER
        assert len(result.fields_added) == 2
        assert result.duration_ms == 50.5


class TestEnrichmentStatusEnum:
    """Tests for EnrichmentStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """All expected statuses are defined."""
        assert EnrichmentStatus.SUCCESS.value == "success"
        assert EnrichmentStatus.SKIPPED.value == "skipped"
        assert EnrichmentStatus.FAILED.value == "failed"
        assert EnrichmentStatus.PARTIAL.value == "partial"
