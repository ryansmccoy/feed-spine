"""Tests for EntityEnricher — cross-feed entity resolution enrichment.

Covers:
- Initialization and protocol compliance
- CIK-based resolution (highest confidence)
- Ticker-based resolution
- Name-based fuzzy resolution with configurable threshold
- Skipping already-enriched records
- Layer promotion
- Conditional import guard (no hard entityspine dependency)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from feedspine.enricher.entity_enricher import EntityEnricher, EntityStoreProtocol
from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record
from feedspine.protocols.enricher import EnrichmentStatus

# ── Mock entity store ────────────────────────────────────────────────────────


@dataclass
class FakeEntity:
    """Minimal entity matching EntitySpine contract."""

    entity_id: str
    primary_name: str
    source_id: str | None = None


class FakeEntityStore:
    """In-memory entity store satisfying EntityStoreProtocol."""

    def __init__(self, entities: dict[str, FakeEntity] | None = None) -> None:
        self._by_cik: dict[str, list[FakeEntity]] = {}
        self._all: list[FakeEntity] = []
        for e in (entities or {}).values():
            self._all.append(e)
            if e.source_id:
                self._by_cik.setdefault(e.source_id, []).append(e)

    def add(self, entity: FakeEntity, cik: str | None = None) -> None:
        self._all.append(entity)
        key = cik or entity.source_id
        if key:
            self._by_cik.setdefault(key, []).append(entity)

    def get_entities_by_cik(self, cik: str) -> list[FakeEntity]:
        return self._by_cik.get(cik, [])

    def search_entities(self, query: str, limit: int = 10) -> list[tuple[FakeEntity, float]]:
        results: list[tuple[FakeEntity, float]] = []
        q = query.lower()
        for e in self._all:
            name = e.primary_name.lower()
            if q == name:
                results.append((e, 1.0))
            elif q in name or name in q:
                results.append((e, 0.85))
        return sorted(results, key=lambda x: x[1], reverse=True)[:limit]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_record(
    content: dict[str, Any] | None = None,
    layer: Layer = Layer.BRONZE,
    record_id: str = "rec-001",
) -> Record:
    return Record(
        id=record_id,
        natural_key="test-key",
        layer=layer,
        published_at=datetime(2024, 6, 1, tzinfo=UTC),
        captured_at=datetime(2024, 6, 1, tzinfo=UTC),
        content=content or {},
        metadata=Metadata(source="test"),
    )


def _make_store_with_apple() -> FakeEntityStore:
    store = FakeEntityStore()
    apple = FakeEntity(entity_id="E-AAPL", primary_name="Apple Inc.", source_id="0000320193")
    store.add(apple, cik="0000320193")
    return store


# ── Protocol compliance ──────────────────────────────────────────────────────


class TestEntityStoreProtocol:
    def test_fake_store_satisfies_protocol(self):
        store = FakeEntityStore()
        assert isinstance(store, EntityStoreProtocol)


# ── Initialization ───────────────────────────────────────────────────────────


class TestEntityEnricherInit:
    def test_default_name(self):
        enricher = EntityEnricher(FakeEntityStore())
        assert enricher.name == "EntityEnricher"

    def test_custom_name(self):
        enricher = EntityEnricher(FakeEntityStore(), name="CustomResolver")
        assert enricher.name == "CustomResolver"


# ── can_enrich ───────────────────────────────────────────────────────────────


class TestCanEnrich:
    async def test_record_with_cik(self):
        enricher = EntityEnricher(FakeEntityStore())
        record = _make_record(content={"cik": "0000320193"})
        assert await enricher.can_enrich(record) is True

    async def test_record_with_ticker(self):
        enricher = EntityEnricher(FakeEntityStore())
        record = _make_record(content={"ticker": "AAPL"})
        assert await enricher.can_enrich(record) is True

    async def test_record_with_company_name(self):
        enricher = EntityEnricher(FakeEntityStore())
        record = _make_record(content={"company_name": "Apple Inc."})
        assert await enricher.can_enrich(record) is True

    async def test_record_with_name(self):
        enricher = EntityEnricher(FakeEntityStore())
        record = _make_record(content={"name": "Apple Inc."})
        assert await enricher.can_enrich(record) is True

    async def test_record_without_identifiers(self):
        enricher = EntityEnricher(FakeEntityStore())
        record = _make_record(content={"title": "Some report"})
        assert await enricher.can_enrich(record) is False

    async def test_already_enriched_record_skipped(self):
        enricher = EntityEnricher(FakeEntityStore())
        record = _make_record(content={"cik": "0000320193"})
        record.metadata.extra["entity_id"] = "E-AAPL"
        assert await enricher.can_enrich(record) is False

    async def test_gold_layer_skipped_when_promote_enabled(self):
        enricher = EntityEnricher(FakeEntityStore(), promote_layer=True)
        record = _make_record(content={"cik": "0000320193"}, layer=Layer.GOLD)
        assert await enricher.can_enrich(record) is False

    async def test_gold_layer_allowed_when_promote_disabled(self):
        enricher = EntityEnricher(FakeEntityStore(), promote_layer=False)
        record = _make_record(content={"cik": "0000320193"}, layer=Layer.GOLD)
        assert await enricher.can_enrich(record) is True


# ── enrich — CIK resolution ─────────────────────────────────────────────────


class TestEnrichByCik:
    async def test_resolves_by_cik(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store)
        record = _make_record(content={"cik": "0000320193"})

        result = await enricher.enrich(record)

        assert result.status == EnrichmentStatus.SUCCESS
        assert result.enricher_name == "EntityEnricher"
        assert "entity_id" in result.fields_added
        assert result.metadata["entity_name"] == "Apple Inc."
        assert result.metadata["resolution_method"] == "cik"
        assert result.metadata["resolution_score"] == 1.0

    async def test_cik_added_to_record_metadata(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store)
        record = _make_record(content={"cik": "0000320193"})

        await enricher.enrich(record)

        assert record.metadata.extra["entity_id"] == "E-AAPL"
        assert record.metadata.extra["entity_name"] == "Apple Inc."

    async def test_cik_leading_zeros_normalized(self):
        """CIK '320193' should be zero-padded to '0000320193'."""
        store = _make_store_with_apple()
        enricher = EntityEnricher(store)
        record = _make_record(content={"cik": "320193"})

        result = await enricher.enrich(record)
        assert result.status == EnrichmentStatus.SUCCESS


# ── enrich — Name resolution ────────────────────────────────────────────────


class TestEnrichByName:
    async def test_resolves_by_name(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store)
        record = _make_record(content={"name": "Apple Inc."})

        result = await enricher.enrich(record)

        assert result.status == EnrichmentStatus.SUCCESS
        assert result.metadata["resolution_method"] == "name"

    async def test_below_confidence_threshold_skipped(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store, min_confidence=0.99)
        # Partial match that yields 0.85 score from FakeEntityStore
        record = _make_record(content={"name": "Apple"})

        result = await enricher.enrich(record)
        assert result.status == EnrichmentStatus.SKIPPED

    async def test_no_match_skipped(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store)
        record = _make_record(content={"name": "UnknownCorp"})

        result = await enricher.enrich(record)
        assert result.status == EnrichmentStatus.SKIPPED


# ── Layer promotion ──────────────────────────────────────────────────────────


class TestLayerPromotion:
    async def test_bronze_promoted_to_silver(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store, promote_layer=True)
        record = _make_record(content={"cik": "0000320193"}, layer=Layer.BRONZE)

        result = await enricher.enrich(record)

        assert result.source_layer == Layer.BRONZE
        assert result.target_layer == Layer.SILVER
        assert record.layer == Layer.SILVER

    async def test_silver_promoted_to_gold(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store, promote_layer=True)
        record = _make_record(content={"cik": "0000320193"}, layer=Layer.SILVER)

        result = await enricher.enrich(record)

        assert result.target_layer == Layer.GOLD
        assert record.layer == Layer.GOLD

    async def test_no_promotion_when_disabled(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store, promote_layer=False)
        record = _make_record(content={"cik": "0000320193"}, layer=Layer.BRONZE)

        result = await enricher.enrich(record)

        assert result.target_layer == Layer.BRONZE
        assert record.layer == Layer.BRONZE


# ── Duration tracking ────────────────────────────────────────────────────────


class TestDuration:
    async def test_duration_recorded(self):
        store = _make_store_with_apple()
        enricher = EntityEnricher(store)
        record = _make_record(content={"cik": "0000320193"})

        result = await enricher.enrich(record)
        assert result.duration_ms >= 0.0

    async def test_skipped_duration_recorded(self):
        enricher = EntityEnricher(FakeEntityStore())
        record = _make_record(content={"name": "Nobody"})

        result = await enricher.enrich(record)
        assert result.status == EnrichmentStatus.SKIPPED
        assert result.duration_ms >= 0.0


# ── Conditional import guard ─────────────────────────────────────────────────


class TestConditionalImport:
    def test_entity_enricher_importable_from_module(self):
        """EntityEnricher can be imported directly without entityspine installed."""
        from feedspine.enricher.entity_enricher import EntityEnricher as EE

        assert EE is not None

    def test_enricher_init_exports(self):
        """EntityEnricher is conditionally in enricher __all__."""
        import feedspine.enricher as mod

        # It should be in __all__ since entity_enricher.py doesn't
        # require entityspine at import time (only at runtime via store)
        assert "EntityEnricher" in mod.__all__
