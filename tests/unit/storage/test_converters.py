"""Tests for feedspine.storage.shared.converters module.

Pure conversion functions — no I/O, no external services.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from feedspine.storage.shared.converters import (
    json_serial,
    parse_datetime,
    serialize_datetime,
)

# ---------------------------------------------------------------------------
# json_serial
# ---------------------------------------------------------------------------


class TestJsonSerial:
    """Tests for json_serial helper."""

    def test_serializes_datetime(self):
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = json_serial(dt)
        assert isinstance(result, str)
        assert "2026" in result

    def test_serializes_date(self):
        from datetime import date

        d = date(2026, 1, 15)
        result = json_serial(d)
        assert isinstance(result, str)
        assert "2026" in result

    def test_non_serializable_raises(self):
        with pytest.raises(TypeError):
            json_serial(object())


# ---------------------------------------------------------------------------
# parse_datetime
# ---------------------------------------------------------------------------


class TestParseDatetime:
    """Tests for parse_datetime."""

    def test_parses_iso_string(self):
        result = parse_datetime("2026-01-15T12:00:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_parses_datetime_object(self):
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = parse_datetime(dt)
        assert result == dt

    def test_result_is_utc_aware(self):
        result = parse_datetime("2026-01-15T12:00:00Z")
        assert result.tzinfo is not None

    def test_none_handling(self):
        """None input should return a datetime or raise."""
        result = parse_datetime(None)
        # Implementation accepts None gracefully
        assert result is None or isinstance(result, datetime)


# ---------------------------------------------------------------------------
# serialize_datetime
# ---------------------------------------------------------------------------


class TestSerializeDatetime:
    """Tests for serialize_datetime."""

    def test_returns_iso_string(self):
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = serialize_datetime(dt)
        assert isinstance(result, str)
        assert "2026-01-15" in result

    def test_roundtrip(self):
        """parse(serialize(dt)) should equal dt."""
        dt = datetime(2026, 6, 15, 8, 30, 0, tzinfo=UTC)
        result = parse_datetime(serialize_datetime(dt))
        assert result == dt
