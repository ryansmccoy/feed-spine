"""Tests for enricher/worker.py — FeedEnrichmentWorker."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

pytest.importorskip("spine", reason="spine-core not installed")
from spine.ports.dispatch_config import DispatchConfig

from feedspine.enricher.worker import FeedEnrichmentWorker
from feedspine.protocols.enricher import EnrichmentResult, EnrichmentStatus

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class FakeRecord:
    id: str
    natural_key: str = ""
    content: dict = field(default_factory=dict)


class FakeStorage:
    """In-memory storage that supports get/store."""

    def __init__(self, records: dict[str, FakeRecord] | None = None):
        self._records = dict(records) if records else {}

    async def get(self, record_id: str, layer=None):
        return self._records.get(record_id)

    async def store(self, record):
        self._records[record.id] = record


class SuccessEnricher:
    """Enricher that always succeeds."""

    name = "success-enricher"

    async def can_enrich(self, record):
        return True

    async def enrich(self, record):
        return EnrichmentResult(
            record_id=record.id,
            status=EnrichmentStatus.SUCCESS,
            enricher_name=self.name,
            fields_added=["enriched"],
        )


class FailEnricher:
    """Enricher that always fails."""

    name = "fail-enricher"

    async def can_enrich(self, record):
        return True

    async def enrich(self, record):
        return EnrichmentResult(
            record_id=record.id,
            status=EnrichmentStatus.FAILED,
            enricher_name=self.name,
            error_message="Enrichment error",
        )


class SkipEnricher:
    """Enricher that always skips."""

    name = "skip-enricher"

    async def can_enrich(self, record):
        return False

    async def enrich(self, record):
        return EnrichmentResult(
            record_id=record.id,
            status=EnrichmentStatus.SKIPPED,
            enricher_name=self.name,
        )


class ExplodingEnricher:
    """Enricher that raises."""

    name = "explode-enricher"

    async def can_enrich(self, record):
        return True

    async def enrich(self, record):
        raise RuntimeError("boom")


def _create_work_item(record_id: str, enricher: str = "success-enricher"):
    return {
        "id": 1,
        "params_json": {
            "record_id": record_id,
            "enricher": enricher,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFeedEnrichmentWorker:
    @pytest.mark.asyncio
    async def test_processes_single_item(self):
        storage = FakeStorage({"rec-1": FakeRecord(id="rec-1")})
        item = _create_work_item("rec-1")

        worker = FeedEnrichmentWorker(
            storage,
            {"success-enricher": SuccessEnricher()},
        )

        config = DispatchConfig(type="feed.enrich")
        result = await worker.dispatch(config, item)

        assert result.success is True
        assert result.status_code == 200

        res_body = json.loads(result.response_body)
        assert res_body["status"] == "success"

    @pytest.mark.asyncio
    async def test_failed_enrichment_fails_item(self):
        storage = FakeStorage({"rec-1": FakeRecord(id="rec-1")})
        item = _create_work_item("rec-1", "fail-enricher")

        worker = FeedEnrichmentWorker(
            storage,
            {"fail-enricher": FailEnricher()},
        )
        config = DispatchConfig(type="feed.enrich")
        result = await worker.dispatch(config, item)

        assert result.success is False
        assert "Enrichment error" in result.error

    @pytest.mark.asyncio
    async def test_skipped_enrichment_completes(self):
        storage = FakeStorage({"rec-1": FakeRecord(id="rec-1")})
        item = _create_work_item("rec-1", "skip-enricher")

        worker = FeedEnrichmentWorker(
            storage,
            {"skip-enricher": SkipEnricher()},
        )
        config = DispatchConfig(type="feed.enrich")
        result = await worker.dispatch(config, item)

        assert result.success is True
        assert result.status_code == 200

        res_body = json.loads(result.response_body)
        assert res_body["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_unknown_enricher_returns_failure(self):
        storage = FakeStorage({"rec-1": FakeRecord(id="rec-1")})
        item = _create_work_item("rec-1", "nonexistent")

        worker = FeedEnrichmentWorker(
            storage,
            {"success-enricher": SuccessEnricher()},
        )
        config = DispatchConfig(type="feed.enrich")
        result = await worker.dispatch(config, item)

        assert result.success is False
        assert "Unknown enricher" in result.error

    @pytest.mark.asyncio
    async def test_missing_record_returns_failure(self):
        storage = FakeStorage()  # empty
        item = _create_work_item("rec-missing")

        worker = FeedEnrichmentWorker(
            storage,
            {"success-enricher": SuccessEnricher()},
        )
        config = DispatchConfig(type="feed.enrich")
        result = await worker.dispatch(config, item)

        assert result.success is False
        assert "Record not found" in result.error

    @pytest.mark.asyncio
    async def test_exception_in_enricher_fails_item(self):
        storage = FakeStorage({"rec-1": FakeRecord(id="rec-1")})
        item = _create_work_item("rec-1", "explode-enricher")

        worker = FeedEnrichmentWorker(
            storage,
            {"explode-enricher": ExplodingEnricher()},
        )
        config = DispatchConfig(type="feed.enrich")
        result = await worker.dispatch(config, item)

        assert result.success is False
        assert "Unhandled exception" in result.error
