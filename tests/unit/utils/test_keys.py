"""Tests for feedspine.utils.keys module.

Covers generate_content_key, CompositeKeyBuilder, URLKeyExtractor,
AutoKeyGenerator, and auto_key helper.
"""

from __future__ import annotations

from datetime import date

from feedspine.utils.keys import (
    AutoKeyGenerator,
    CompositeKeyBuilder,
    URLKeyExtractor,
    auto_key,
    generate_content_key,
)

# ── generate_content_key ────────────────────────────────────────


class TestGenerateContentKey:
    """Tests for content-hash key generation."""

    def test_returns_prefixed_string(self):
        key = generate_content_key({"title": "Hello"})
        assert key.startswith("ch_")

    def test_deterministic(self):
        data = {"title": "News", "body": "Content"}
        k1 = generate_content_key(data)
        k2 = generate_content_key(data)
        assert k1 == k2

    def test_different_content_different_key(self):
        k1 = generate_content_key({"title": "A"})
        k2 = generate_content_key({"title": "B"})
        assert k1 != k2

    def test_custom_prefix(self):
        key = generate_content_key({"x": 1}, prefix="fp")
        assert key.startswith("fp_")

    def test_custom_hash_length(self):
        key = generate_content_key({"x": 1}, hash_length=8)
        # prefix + underscore + 8 hex chars
        assert len(key) == 2 + 1 + 8

    def test_field_filter(self):
        data = {"title": "Same", "noise": "A"}
        k1 = generate_content_key(data, fields=["title"])
        data2 = {"title": "Same", "noise": "B"}
        k2 = generate_content_key(data2, fields=["title"])
        assert k1 == k2

    def test_empty_dict(self):
        key = generate_content_key({})
        assert isinstance(key, str)
        assert len(key) > 0

    def test_nested_content_is_stable(self):
        data = {"items": [{"id": 1}, {"id": 2}]}
        k1 = generate_content_key(data)
        k2 = generate_content_key(data)
        assert k1 == k2

    def test_key_order_independent(self):
        """Dict key order should not affect hash."""
        k1 = generate_content_key({"a": 1, "b": 2})
        k2 = generate_content_key({"b": 2, "a": 1})
        assert k1 == k2


# ── CompositeKeyBuilder ─────────────────────────────────────────


class TestCompositeKeyBuilder:
    """Tests for composite key construction."""

    def test_basic_build(self):
        builder = CompositeKeyBuilder(["source", "date"])
        key = builder.build({"source": "Reuters", "date": "2024-01-15"})
        assert "::" in key
        assert "reuters" in key  # normalized

    def test_missing_field_uses_placeholder(self):
        builder = CompositeKeyBuilder(["a", "b"], missing_value="MISSING")
        key = builder.build({"a": "hello"})
        assert "MISSING" in key

    def test_no_normalize(self):
        builder = CompositeKeyBuilder(["x"], normalize=False)
        key = builder.build({"x": "MixedCase"})
        assert "MixedCase" in key

    def test_custom_separator(self):
        builder = CompositeKeyBuilder(["a", "b"], separator="|")
        key = builder.build({"a": "1", "b": "2"})
        assert "|" in key
        assert "::" not in key

    def test_date_values_normalized(self):
        builder = CompositeKeyBuilder(["d"])
        key = builder.build({"d": date(2024, 6, 15)})
        assert "2024-06-15" in key

    def test_deterministic(self):
        builder = CompositeKeyBuilder(["x", "y"])
        data = {"x": "alpha", "y": "beta"}
        assert builder.build(data) == builder.build(data)


# ── URLKeyExtractor ──────────────────────────────────────────────


class TestURLKeyExtractor:
    """Tests for URL-based key extraction."""

    def test_regex_pattern(self):
        extractor = URLKeyExtractor(pattern=r"/article/(\d+)")
        key = extractor.extract("https://news.com/article/12345")
        assert key == "12345"

    def test_path_fallback(self):
        extractor = URLKeyExtractor(use_path=True)
        key = extractor.extract("https://example.com/posts/my-article")
        assert key == "my-article"

    def test_query_param(self):
        extractor = URLKeyExtractor(use_query_param="id")
        key = extractor.extract("https://api.com/search?id=abc123&q=test")
        assert key == "abc123"

    def test_no_match_returns_none(self):
        extractor = URLKeyExtractor(pattern=r"/missing/(\d+)", use_path=False)
        key = extractor.extract("https://example.com/other")
        assert key is None

    def test_empty_path(self):
        extractor = URLKeyExtractor(use_path=True)
        key = extractor.extract("https://example.com/")
        assert key is None or key == ""


# ── AutoKeyGenerator ────────────────────────────────────────────


class TestAutoKeyGenerator:
    """Tests for automatic key generation with fallback strategies."""

    def test_uses_id_field(self):
        gen = AutoKeyGenerator(id_fields=["id", "guid"])
        key = gen.generate({"id": "123", "title": "Hello"})
        assert key == "123"

    def test_falls_through_to_url(self):
        gen = AutoKeyGenerator(
            id_fields=["id"],
            url_field="link",
            url_pattern=r"/post/(\d+)",
        )
        key = gen.generate({"link": "https://x.com/post/456"})
        assert key == "456"

    def test_falls_through_to_composite(self):
        gen = AutoKeyGenerator(
            id_fields=["id"],
            composite_fields=["author", "title"],
        )
        key = gen.generate({"author": "John", "title": "Hello"})
        assert "::" in key

    def test_falls_through_to_content_hash(self):
        gen = AutoKeyGenerator(id_fields=["id"])
        key = gen.generate({"body": "Some content"})
        assert key.startswith("ch_")

    def test_source_prefix(self):
        gen = AutoKeyGenerator(id_fields=["id"], source_prefix="src")
        key = gen.generate({"id": "42"})
        assert key.startswith("src")


# ── auto_key ────────────────────────────────────────────────────


class TestAutoKey:
    """Tests for the auto_key convenience function."""

    def test_with_id_fields(self):
        key = auto_key({"id": "x1"}, id_fields=["id"])
        assert key == "x1"

    def test_content_hash_fallback(self):
        key = auto_key({"data": "value"})
        assert isinstance(key, str)
        assert len(key) > 0
