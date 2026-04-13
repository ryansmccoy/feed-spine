"""Tests for feedspine.storage.shared.validators module.

Pure validation functions — no I/O, no external services.
"""

from __future__ import annotations

import pytest

from feedspine.storage.shared.validators import (
    ValidationError,
    sanitize_order_by,
    validate_batch_size,
    validate_filters,
    validate_layer,
    validate_limit_offset,
    validate_natural_key,
    validate_record_id,
)

# ---------------------------------------------------------------------------
# validate_natural_key
# ---------------------------------------------------------------------------


class TestValidateNaturalKey:
    """Tests for validate_natural_key."""

    def test_valid_key_returned(self):
        assert validate_natural_key("item-001") == "item-001"

    def test_whitespace_stripped(self):
        result = validate_natural_key("  key  ")
        assert result == result.strip()

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError):
            validate_natural_key("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            validate_natural_key("   ")

    def test_none_raises(self):
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            validate_natural_key(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_layer
# ---------------------------------------------------------------------------


class TestValidateLayer:
    """Tests for validate_layer."""

    def test_none_returns_none(self):
        assert validate_layer(None) is None

    def test_valid_layer_string(self):
        result = validate_layer("bronze")
        assert result is not None

    @pytest.mark.parametrize("layer", ["bronze", "silver", "gold"])
    def test_medallion_layers(self, layer: str):
        result = validate_layer(layer)
        assert result is not None


# ---------------------------------------------------------------------------
# sanitize_order_by
# ---------------------------------------------------------------------------


class TestSanitizeOrderBy:
    """Tests for sanitize_order_by."""

    def test_none_returns_none(self):
        assert sanitize_order_by(None) is None

    def test_valid_column_accepted(self):
        result = sanitize_order_by("captured_at")
        assert result is not None

    def test_invalid_column_raises(self):
        with pytest.raises(ValidationError):
            sanitize_order_by("DROP TABLE records; --")


# ---------------------------------------------------------------------------
# validate_filters
# ---------------------------------------------------------------------------


class TestValidateFilters:
    """Tests for validate_filters."""

    def test_none_returns_none(self):
        assert validate_filters(None) is None

    def test_empty_dict_returns_none_or_empty(self):
        result = validate_filters({})
        assert result is None or result == {}

    def test_valid_filter(self):
        result = validate_filters({"source": "test"})
        assert result is not None


# ---------------------------------------------------------------------------
# validate_limit_offset
# ---------------------------------------------------------------------------


class TestValidateLimitOffset:
    """Tests for validate_limit_offset."""

    def test_none_limit_zero_offset(self):
        limit, offset = validate_limit_offset(None, 0)
        assert limit is None
        assert offset == 0

    def test_positive_limit(self):
        limit, offset = validate_limit_offset(50, 0)
        assert limit == 50

    def test_negative_limit_raises(self):
        with pytest.raises((ValidationError, ValueError)):
            validate_limit_offset(-1, 0)

    def test_negative_offset_raises(self):
        with pytest.raises((ValidationError, ValueError)):
            validate_limit_offset(10, -1)


# ---------------------------------------------------------------------------
# validate_batch_size
# ---------------------------------------------------------------------------


class TestValidateBatchSize:
    """Tests for validate_batch_size."""

    def test_valid_batch_size(self):
        assert validate_batch_size(100) == 100

    def test_one_is_valid(self):
        assert validate_batch_size(1) == 1

    def test_zero_raises(self):
        with pytest.raises((ValidationError, ValueError)):
            validate_batch_size(0)

    def test_negative_raises(self):
        with pytest.raises((ValidationError, ValueError)):
            validate_batch_size(-5)


# ---------------------------------------------------------------------------
# validate_record_id
# ---------------------------------------------------------------------------


class TestValidateRecordId:
    """Tests for validate_record_id."""

    def test_valid_id(self):
        assert validate_record_id("abc-123") == "abc-123"

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            validate_record_id("")
