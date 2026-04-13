"""Tests for feedspine.utils.transforms module.

Tests KeyTransform hierarchy — pure data transformations.
"""

from __future__ import annotations

from datetime import date

from feedspine.utils.transforms import (
    Chain,
    Concat,
    DatePart,
    JsonPath,
    Lower,
    RegexExtract,
    Split,
    Strip,
)

# ---------------------------------------------------------------------------
# JsonPath
# ---------------------------------------------------------------------------


class TestJsonPath:
    """Tests for JsonPath transform."""

    def test_extracts_top_level_key(self):
        t = JsonPath("name")
        assert t({"name": "Alice"}) == "Alice"

    def test_nested_path(self):
        t = JsonPath("a.b")
        result = t({"a": {"b": 42}})
        assert result == 42

    def test_missing_key_returns_default(self):
        t = JsonPath("missing", default="N/A")
        assert t({"name": "Alice"}) == "N/A"


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------


class TestSplit:
    """Tests for Split transform."""

    def test_split_first(self):
        t = Split("_", index=0)
        assert t("hello_world") == "hello"

    def test_split_last(self):
        t = Split("_", index=-1)
        assert t("a_b_c") == "c"

    def test_no_separator(self):
        t = Split("_", index=0)
        assert t("nosep") == "nosep"


# ---------------------------------------------------------------------------
# RegexExtract
# ---------------------------------------------------------------------------


class TestRegexExtract:
    """Tests for RegexExtract transform."""

    def test_extracts_group(self):
        t = RegexExtract(r"(\d+)", group=1)
        assert t("item-42") == "42"

    def test_no_match_returns_default(self):
        t = RegexExtract(r"(\d+)", default="none")
        assert t("no-digits") == "none"


# ---------------------------------------------------------------------------
# DatePart
# ---------------------------------------------------------------------------


class TestDatePart:
    """Tests for DatePart transform."""

    def test_year(self):
        t = DatePart("year")
        assert t(date(2026, 3, 15)) == 2026

    def test_month(self):
        t = DatePart("month")
        assert t(date(2026, 3, 15)) == 3

    def test_quarter(self):
        t = DatePart("quarter")
        result = t(date(2026, 3, 15))
        assert result == 1  # March → Q1

    def test_day(self):
        t = DatePart("day")
        assert t(date(2026, 3, 15)) == 15


# ---------------------------------------------------------------------------
# Concat
# ---------------------------------------------------------------------------


class TestConcat:
    """Tests for Concat transform."""

    def test_concatenates_fields(self):
        t = Concat("first", "last", separator=" ")
        result = t({"first": "John", "last": "Doe"})
        assert result == "John Doe"

    def test_custom_separator(self):
        t = Concat("a", "b", separator="-")
        result = t({"a": "x", "b": "y"})
        assert result == "x-y"


# ---------------------------------------------------------------------------
# Lower / Strip
# ---------------------------------------------------------------------------


class TestLower:
    """Tests for Lower transform."""

    def test_lowercases(self):
        t = Lower()
        assert t("HELLO") == "hello"


class TestStrip:
    """Tests for Strip transform."""

    def test_strips_whitespace(self):
        t = Strip()
        assert t("  hello  ") == "hello"

    def test_strips_custom_chars(self):
        t = Strip("*")
        assert t("**hello**") == "hello"


# ---------------------------------------------------------------------------
# Chain
# ---------------------------------------------------------------------------


class TestChain:
    """Tests for Chain transform."""

    def test_chains_transforms(self):
        t = Chain(Lower(), Strip())
        assert t("  HELLO  ") == "hello"

    def test_single_transform(self):
        t = Chain(Lower())
        assert t("TEST") == "test"
