"""Tests for feedspine.utils.constraints module.

Tests UniqueConstraint key generation and duplicate detection.
"""

from __future__ import annotations

import pytest

from feedspine.utils.constraints import UniqueConstraint


class TestUniqueConstraint:
    """Tests for UniqueConstraint."""

    def test_single_column_key(self):
        uc = UniqueConstraint("id")
        key = uc.key({"id": "abc"})
        assert isinstance(key, str)
        assert len(key) > 0

    def test_multi_column_key(self):
        uc = UniqueConstraint("source", "item_id")
        key = uc.key({"source": "rss", "item_id": "001"})
        assert isinstance(key, str)

    def test_same_record_same_key(self):
        """Deterministic: same data → same key."""
        uc = UniqueConstraint("source", "id")
        record = {"source": "test", "id": "x"}
        assert uc.key(record) == uc.key(record)

    def test_different_records_different_keys(self):
        uc = UniqueConstraint("id")
        k1 = uc.key({"id": "a"})
        k2 = uc.key({"id": "b"})
        assert k1 != k2

    def test_is_duplicate_true(self):
        uc = UniqueConstraint("id")
        assert uc.is_duplicate({"id": "same"}, {"id": "same"}) is True

    def test_is_duplicate_false(self):
        uc = UniqueConstraint("id")
        assert uc.is_duplicate({"id": "a"}, {"id": "b"}) is False

    def test_case_insensitive_by_default(self):
        uc = UniqueConstraint("name", case_sensitive=False)
        assert uc.is_duplicate({"name": "ABC"}, {"name": "abc"}) is True

    def test_case_sensitive(self):
        uc = UniqueConstraint("name", case_sensitive=True)
        assert uc.is_duplicate({"name": "ABC"}, {"name": "abc"}) is False

    def test_no_columns_raises(self):
        with pytest.raises(ValueError):
            UniqueConstraint()

    def test_null_value_handling(self):
        """Missing keys should use null_value sentinel."""
        uc = UniqueConstraint("source", "id")
        key = uc.key({"source": "test"})  # id missing
        assert isinstance(key, str)

    def test_repr(self):
        uc = UniqueConstraint("a", "b", name="test_uc")
        r = repr(uc)
        assert "test_uc" in r or "UniqueConstraint" in r
