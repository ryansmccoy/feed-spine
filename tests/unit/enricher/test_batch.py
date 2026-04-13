"""Tests for enricher/batch.py — create_enrichment_work_items."""

from __future__ import annotations

import pytest

pytest.importorskip("spine", reason="spine-core not installed")

import sqlite3

from feedspine.enricher.batch import create_enrichment_work_items


def _make_store():
    """Create an in-memory SQLite work-item store for testing."""
    from spine.core.schema_loader import apply_schema
    from spine.data.stores.sqlite.work_item_store import SqliteWorkItemStore

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    apply_schema(conn)
    return SqliteWorkItemStore(conn)


class TestCreateEnrichmentWorkItems:
    def test_creates_items_for_each_record(self):
        store = _make_store()
        batch_id, ids = create_enrichment_work_items(
            store,
            "metadata",
            ["rec-1", "rec-2", "rec-3"],
        )
        assert len(ids) == 3
        assert batch_id  # non-empty

    def test_items_have_correct_domain_workflow(self):
        store = _make_store()
        _, ids = create_enrichment_work_items(
            store,
            "metadata",
            ["rec-1"],
        )
        item = store.get_by_id(ids[0])
        assert item["domain"] == "feed-spine"
        assert item["workflow"] == "feed.enrich"
        assert item["execution_mode"] == "runner_dispatch"

    def test_params_json_contains_enricher_and_record_id(self):
        import json

        store = _make_store()
        batch_id, ids = create_enrichment_work_items(
            store,
            "sec-metadata",
            ["rec-abc"],
        )
        item = store.get_by_id(ids[0])
        params = json.loads(item["params_json"])
        assert params["record_id"] == "rec-abc"
        assert params["enricher"] == "sec-metadata"
        assert params["source_layer"] == "BRONZE"
        assert params["target_layer"] == "SILVER"
        assert params["batch_id"] == batch_id

    def test_custom_batch_id(self):
        store = _make_store()
        batch_id, _ = create_enrichment_work_items(
            store,
            "metadata",
            ["rec-1"],
            batch_id="my-batch-42",
        )
        assert batch_id == "my-batch-42"

    def test_custom_layers(self):
        import json

        store = _make_store()
        _, ids = create_enrichment_work_items(
            store,
            "gold-enricher",
            ["rec-1"],
            source_layer="SILVER",
            target_layer="GOLD",
        )
        item = store.get_by_id(ids[0])
        params = json.loads(item["params_json"])
        assert params["source_layer"] == "SILVER"
        assert params["target_layer"] == "GOLD"

    def test_group_key_set(self):
        store = _make_store()
        _, ids = create_enrichment_work_items(
            store,
            "my-enricher",
            ["rec-1"],
        )
        item = store.get_by_id(ids[0])
        assert item["group_key"] == "feed-spine:enrich:my-enricher"

    def test_batch_id_on_work_item(self):
        store = _make_store()
        batch_id, ids = create_enrichment_work_items(
            store,
            "metadata",
            ["rec-1", "rec-2"],
        )
        for item_id in ids:
            item = store.get_by_id(item_id)
            assert item["batch_id"] == batch_id

    def test_list_by_batch(self):
        store = _make_store()
        batch_id, ids = create_enrichment_work_items(
            store,
            "metadata",
            ["rec-1", "rec-2", "rec-3"],
        )
        items = store.list_by_batch(batch_id)
        assert len(items) == 3

    def test_empty_record_ids(self):
        store = _make_store()
        batch_id, ids = create_enrichment_work_items(
            store,
            "metadata",
            [],
        )
        assert ids == []
        assert batch_id  # still generated
