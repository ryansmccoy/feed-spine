"""Tests for feedspine.utils.versioning module.

Covers VersionedRecord lifecycle, MemoryVersionStore CRUD,
content_hash determinism, and ChangeType semantics.
"""

from __future__ import annotations

import pytest

from feedspine.utils.versioning import (
    ChangeType,
    MemoryVersionStore,
    PipelineVersion,
    VersionedRecord,
    content_hash,
)

# ── content_hash ────────────────────────────────────────────────


class TestContentHash:
    """Tests for the content_hash function."""

    def test_deterministic_dict(self):
        h1 = content_hash({"a": 1, "b": 2})
        h2 = content_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = content_hash({"a": 1})
        h2 = content_hash({"a": 2})
        assert h1 != h2

    def test_string_content(self):
        h = content_hash("hello world")
        assert isinstance(h, str)
        assert len(h) == 16

    def test_bytes_content(self):
        h = content_hash(b"binary data")
        assert isinstance(h, str)
        assert len(h) == 16

    def test_key_order_independent(self):
        h1 = content_hash({"z": 1, "a": 2})
        h2 = content_hash({"a": 2, "z": 1})
        assert h1 == h2


# ── VersionedRecord ─────────────────────────────────────────────


class TestVersionedRecord:
    """Tests for VersionedRecord creation and versioning."""

    def test_create_first_version(self):
        v = VersionedRecord.create(key="doc:1", content={"title": "Draft"}, source="editor")
        assert v.version == 1
        assert v.change_type == ChangeType.CREATED
        assert v.parent_version is None
        assert v.content_hash is not None

    def test_new_version_increments(self):
        v1 = VersionedRecord.create(key="doc:1", content={"v": 1}, source="s")
        v2 = v1.new_version(content={"v": 2})
        assert v2.version == 2
        assert v2.parent_version == 1
        assert v2.change_type == ChangeType.UPDATED

    def test_same_content_marks_reprocessed(self):
        v1 = VersionedRecord.create(key="doc:1", content={"v": 1}, source="s")
        v2 = v1.new_version(content={"v": 1})  # same content
        assert v2.change_type == ChangeType.REPROCESSED

    def test_mark_deleted(self):
        v1 = VersionedRecord.create(key="doc:1", content={"v": 1}, source="s")
        v2 = v1.mark_deleted(reason="Obsolete")
        assert v2.is_deleted is True
        assert v2.change_type == ChangeType.DELETED
        assert v2.content is None

    def test_version_id_format(self):
        v = VersionedRecord.create(key="my-key", content={}, source="test")
        assert v.version_id == "my-key@v1"

    def test_metadata_merge_on_new_version(self):
        v1 = VersionedRecord.create(key="k", content="a", source="s", metadata={"model": "v1"})
        v2 = v1.new_version(content="b", metadata={"model": "v2", "extra": True})
        assert v2.metadata["model"] == "v2"
        assert v2.metadata["extra"] is True

    def test_explicit_change_type_overrides(self):
        v1 = VersionedRecord.create(key="k", content="a", source="s")
        v2 = v1.new_version(
            content="a",  # same content
            change_type=ChangeType.UPDATED,
        )
        assert v2.change_type == ChangeType.UPDATED  # overridden

    def test_repr(self):
        v = VersionedRecord.create(key="doc:1", content={}, source="s")
        r = repr(v)
        assert "doc:1" in r
        assert "v1" in r


# ── MemoryVersionStore ──────────────────────────────────────────


class TestMemoryVersionStore:
    """Tests for the in-memory version store."""

    @pytest.fixture
    def store(self):
        return MemoryVersionStore()

    def test_save_and_get_latest(self, store):
        v = VersionedRecord.create(key="k1", content="data", source="s")
        store.save(v)
        latest = store.get_latest("k1")
        assert latest is not None
        assert latest.key == "k1"
        assert latest.version == 1

    def test_get_latest_nonexistent(self, store):
        assert store.get_latest("nonexistent") is None

    def test_get_specific_version(self, store):
        v1 = VersionedRecord.create(key="k", content="a", source="s")
        store.save(v1)
        v2 = v1.new_version(content="b")
        store.save(v2)

        assert store.get_version("k", 1).content == "a"
        assert store.get_version("k", 2).content == "b"
        assert store.get_version("k", 99) is None

    def test_get_versions_ordered(self, store):
        v1 = VersionedRecord.create(key="k", content="a", source="s")
        store.save(v1)
        v2 = v1.new_version(content="b")
        store.save(v2)
        v3 = v2.new_version(content="c")
        store.save(v3)

        versions = store.get_versions("k")
        assert len(versions) == 3
        assert [v.version for v in versions] == [1, 2, 3]

    def test_get_versions_empty(self, store):
        assert store.get_versions("missing") == []

    def test_keys(self, store):
        store.save(VersionedRecord.create(key="a", content=1, source="s"))
        store.save(VersionedRecord.create(key="b", content=2, source="s"))
        assert sorted(store.keys()) == ["a", "b"]

    def test_stats(self, store):
        v1 = VersionedRecord.create(key="doc", content="v1", source="s")
        store.save(v1)
        v2 = v1.new_version(content="v2")
        store.save(v2)

        stats = store.stats()
        assert stats["total_keys"] == 1
        assert stats["total_versions"] == 2
        assert stats["avg_versions_per_key"] == 2.0

    def test_save_if_changed_new_record(self, store):
        v = VersionedRecord.create(key="new", content="data", source="s")
        saved, record = store.save_if_changed(v)
        assert saved is True
        assert record.version == 1

    def test_save_if_changed_no_change(self, store):
        v = VersionedRecord.create(key="k", content="same", source="s")
        store.save(v)

        v2 = VersionedRecord.create(key="k", content="same", source="s")
        saved, record = store.save_if_changed(v2)
        assert saved is False
        assert record.version == 1  # still the original

    def test_save_if_changed_with_change(self, store):
        v = VersionedRecord.create(key="k", content="old", source="s")
        store.save(v)

        v2 = VersionedRecord.create(key="k", content="new", source="s")
        saved, record = store.save_if_changed(v2)
        assert saved is True
        assert record.version == 2


# ── ChangeType ──────────────────────────────────────────────────


class TestChangeType:
    """Tests for the ChangeType enum."""

    def test_all_values(self):
        assert ChangeType.CREATED.value == "created"
        assert ChangeType.UPDATED.value == "updated"
        assert ChangeType.DELETED.value == "deleted"
        assert ChangeType.REPROCESSED.value == "reprocessed"


# ── PipelineVersion ────────────────────────────────────────────


class TestPipelineVersion:
    """Tests for ML/LLM pipeline version tracking."""

    def test_to_metadata(self):
        pv = PipelineVersion(
            pipeline_name="embed",
            pipeline_version="1.0",
            model_name="gpt-4",
        )
        meta = pv.to_metadata()
        assert meta["pipeline_name"] == "embed"
        assert meta["model_name"] == "gpt-4"

    def test_from_metadata_roundtrip(self):
        pv = PipelineVersion(
            pipeline_name="extract",
            pipeline_version="2.0",
            model_name="claude-3",
            model_version="sonnet",
        )
        meta = pv.to_metadata()
        restored = PipelineVersion.from_metadata(meta)
        assert restored is not None
        assert restored.pipeline_name == "extract"
        assert restored.model_version == "sonnet"

    def test_from_metadata_missing(self):
        assert PipelineVersion.from_metadata({}) is None
