"""Tests for models/enrichment_batch.py — EnrichmentBatch projection."""

from __future__ import annotations

import json

import pytest

from feedspine.models.enrichment_batch import EnrichmentBatch


def _item(state: str = "QUEUED", enricher: str = "test-enricher", created_at: str = "2025-01-01T00:00:00") -> dict:
    """Helper to build a work-item dict."""
    return {
        "state": state,
        "params_json": json.dumps({"enricher": enricher, "record_id": "r1"}),
        "created_at": created_at,
    }


class TestEnrichmentBatchStatus:
    def test_empty(self):
        b = EnrichmentBatch(
            batch_id="b1",
            enricher="e",
            total=0,
            succeeded=0,
            queued=0,
            leased=0,
            dead_lettered=0,
        )
        assert b.status == "EMPTY"

    def test_all_queued(self):
        b = EnrichmentBatch(
            batch_id="b1",
            enricher="e",
            total=3,
            succeeded=0,
            queued=3,
            leased=0,
            dead_lettered=0,
        )
        assert b.status == "QUEUED"

    def test_in_progress(self):
        b = EnrichmentBatch(
            batch_id="b1",
            enricher="e",
            total=3,
            succeeded=0,
            queued=1,
            leased=2,
            dead_lettered=0,
        )
        assert b.status == "IN_PROGRESS"

    def test_completed(self):
        b = EnrichmentBatch(
            batch_id="b1",
            enricher="e",
            total=3,
            succeeded=3,
            queued=0,
            leased=0,
            dead_lettered=0,
        )
        assert b.status == "COMPLETED"

    def test_completed_with_failures(self):
        b = EnrichmentBatch(
            batch_id="b1",
            enricher="e",
            total=3,
            succeeded=2,
            queued=0,
            leased=0,
            dead_lettered=1,
        )
        assert b.status == "COMPLETED_WITH_FAILURES"

    def test_partial_success(self):
        b = EnrichmentBatch(
            batch_id="b1",
            enricher="e",
            total=3,
            succeeded=1,
            queued=2,
            leased=0,
            dead_lettered=0,
        )
        assert b.status == "PARTIAL_SUCCESS"

    def test_cancelled(self):
        b = EnrichmentBatch(
            batch_id="b1",
            enricher="e",
            total=3,
            succeeded=0,
            queued=0,
            leased=0,
            dead_lettered=0,
            cancelled=3,
        )
        assert b.status == "CANCELLED"


class TestEnrichmentBatchFromWorkItems:
    def test_builds_from_items(self):
        items = [
            _item("SUCCEEDED"),
            _item("QUEUED"),
            _item("DEAD_LETTERED"),
        ]
        b = EnrichmentBatch.from_work_items("batch-1", items)
        assert b.batch_id == "batch-1"
        assert b.enricher == "test-enricher"
        assert b.total == 3
        assert b.succeeded == 1
        assert b.queued == 1
        assert b.dead_lettered == 1

    def test_empty_items(self):
        b = EnrichmentBatch.from_work_items("batch-1", [])
        assert b.total == 0
        assert b.enricher == "unknown"
        assert b.status == "EMPTY"

    def test_enricher_from_string_params(self):
        items = [{"state": "QUEUED", "params_json": '{"enricher": "foo"}', "created_at": "2025-01-01"}]
        b = EnrichmentBatch.from_work_items("b1", items)
        assert b.enricher == "foo"

    def test_enricher_from_dict_params(self):
        items = [{"state": "QUEUED", "params_json": {"enricher": "bar"}, "created_at": "2025-01-01"}]
        b = EnrichmentBatch.from_work_items("b1", items)
        assert b.enricher == "bar"

    def test_created_at_is_earliest(self):
        items = [
            _item(created_at="2025-01-03T00:00:00"),
            _item(created_at="2025-01-01T00:00:00"),
            _item(created_at="2025-01-02T00:00:00"),
        ]
        b = EnrichmentBatch.from_work_items("b1", items)
        assert b.created_at == "2025-01-01T00:00:00"

    def test_frozen(self):
        b = EnrichmentBatch.from_work_items("b1", [_item()])
        with pytest.raises(AttributeError):
            b.total = 99  # type: ignore[misc]
