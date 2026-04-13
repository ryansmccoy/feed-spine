"""Tests for feedspine.models.converter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from feedspine.models.base import Metadata
from feedspine.models.converter import (
    ConverterRegistry,
    RecordConverter,
    converter_registry,
)
from feedspine.models.record import Record, RecordCandidate


@dataclass
class Article:
    """Test domain model."""

    id: str
    title: str
    author: str


class ArticleConverter(RecordConverter[Article]):
    """Test converter for articles."""

    @property
    def domain(self) -> str:
        return "news"

    def convert(self, record: Record) -> Article:
        return Article(
            id=record.id,
            title=record.content.get("title", ""),
            author=record.content.get("author", "Unknown"),
        )


class ArticleConverterWithCanConvert(RecordConverter[Article]):
    """Test converter with custom can_convert."""

    @property
    def domain(self) -> str:
        return "news_custom"

    def convert(self, record: Record) -> Article:
        return Article(
            id=record.id,
            title=record.content.get("title", ""),
            author=record.content.get("author", "Unknown"),
        )

    def can_convert(self, record: Record) -> bool:
        return "title" in record.content


class TestRecordConverterBasic:
    """Basic RecordConverter tests."""

    @pytest.fixture
    def record(self) -> Record:
        """Create a test record."""
        candidate = RecordCandidate(
            natural_key="article-1",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Test Title", "author": "Alice"},
            metadata=Metadata(source="test", source_type="news.rss"),
        )
        return Record.from_candidate(candidate, "id-1")

    def test_convert(self, record: Record) -> None:
        """Can convert record to domain model."""
        converter = ArticleConverter()
        article = converter.convert(record)
        assert article.id == "id-1"
        assert article.title == "Test Title"
        assert article.author == "Alice"

    def test_domain_property(self) -> None:
        """Domain property returns domain name."""
        converter = ArticleConverter()
        assert converter.domain == "news"

    def test_can_convert_default(self, record: Record) -> None:
        """Default can_convert checks source_type."""
        converter = ArticleConverter()
        assert converter.can_convert(record) is True

    def test_convert_many(self, record: Record) -> None:
        """Can convert multiple records."""
        converter = ArticleConverter()
        records = [record, record]
        articles = converter.convert_many(records)
        assert len(articles) == 2
        assert all(a.title == "Test Title" for a in articles)


class TestRecordConverterCanConvert:
    """Tests for custom can_convert."""

    @pytest.fixture
    def converter(self) -> ArticleConverterWithCanConvert:
        return ArticleConverterWithCanConvert()

    def test_can_convert_true(self, converter: ArticleConverterWithCanConvert) -> None:
        """Returns True when content has required field."""
        candidate = RecordCandidate(
            natural_key="article-1",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Has Title"},
            metadata=Metadata(source="test"),
        )
        record = Record.from_candidate(candidate, "id-1")
        assert converter.can_convert(record) is True

    def test_can_convert_false(self, converter: ArticleConverterWithCanConvert) -> None:
        """Returns False when content missing required field."""
        candidate = RecordCandidate(
            natural_key="article-2",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"body": "No title here"},
            metadata=Metadata(source="test"),
        )
        record = Record.from_candidate(candidate, "id-2")
        assert converter.can_convert(record) is False


class TestConverterRegistryBasic:
    """Basic ConverterRegistry tests."""

    @pytest.fixture
    def registry(self) -> ConverterRegistry:
        """Create a fresh registry."""
        return ConverterRegistry()

    def test_register_and_get(self, registry: ConverterRegistry) -> None:
        """Can register and retrieve converter."""
        converter = ArticleConverter()
        registry.register(converter)
        assert registry.get("news") is converter

    def test_get_unregistered(self, registry: ConverterRegistry) -> None:
        """Returns None for unregistered domain."""
        assert registry.get("unknown") is None

    def test_has_registered(self, registry: ConverterRegistry) -> None:
        """has() returns True for registered domain."""
        registry.register(ArticleConverter())
        assert registry.has("news") is True

    def test_has_unregistered(self, registry: ConverterRegistry) -> None:
        """has() returns False for unregistered domain."""
        assert registry.has("unknown") is False

    def test_domains(self, registry: ConverterRegistry) -> None:
        """domains() returns list of registered domains."""
        registry.register(ArticleConverter())
        assert "news" in registry.domains()

    def test_unregister(self, registry: ConverterRegistry) -> None:
        """Can unregister a converter."""
        registry.register(ArticleConverter())
        assert registry.unregister("news") is True
        assert registry.has("news") is False

    def test_unregister_missing(self, registry: ConverterRegistry) -> None:
        """unregister returns False for missing domain."""
        assert registry.unregister("unknown") is False

    def test_clear(self, registry: ConverterRegistry) -> None:
        """Can clear all converters."""
        registry.register(ArticleConverter())
        registry.clear()
        assert registry.domains() == []


class TestConverterRegistryConvert:
    """Tests for ConverterRegistry.convert()."""

    @pytest.fixture
    def registry(self) -> ConverterRegistry:
        """Create registry with converter."""
        reg = ConverterRegistry()
        reg.register(ArticleConverter())
        return reg

    @pytest.fixture
    def record(self) -> Record:
        """Create a test record."""
        candidate = RecordCandidate(
            natural_key="article-1",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Test", "author": "Bob"},
            metadata=Metadata(source="test"),
        )
        return Record.from_candidate(candidate, "id-1")

    def test_convert(self, registry: ConverterRegistry, record: Record) -> None:
        """Can convert using registry."""
        article = registry.convert("news", record)
        assert article.title == "Test"
        assert article.author == "Bob"

    def test_convert_unknown_domain(self, registry: ConverterRegistry, record: Record) -> None:
        """Raises KeyError for unknown domain."""
        with pytest.raises(KeyError, match="unknown"):
            registry.convert("unknown", record)

    def test_convert_many(self, registry: ConverterRegistry, record: Record) -> None:
        """Can convert multiple records."""
        articles = registry.convert_many("news", [record, record])
        assert len(articles) == 2


class TestConverterRegistryAutoConvert:
    """Tests for ConverterRegistry.auto_convert()."""

    @pytest.fixture
    def registry(self) -> ConverterRegistry:
        """Create registry with converter that uses custom can_convert."""
        reg = ConverterRegistry()
        reg.register(ArticleConverterWithCanConvert())
        return reg

    def test_auto_convert_match(self, registry: ConverterRegistry) -> None:
        """auto_convert finds matching converter."""
        candidate = RecordCandidate(
            natural_key="article-1",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Has Title"},
            metadata=Metadata(source="test"),
        )
        record = Record.from_candidate(candidate, "id-1")
        article = registry.auto_convert(record)
        assert article.title == "Has Title"

    def test_auto_convert_no_match(self, registry: ConverterRegistry) -> None:
        """auto_convert raises ValueError when no converter matches."""
        candidate = RecordCandidate(
            natural_key="no-title",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"body": "No title"},
            metadata=Metadata(source="test"),
        )
        record = Record.from_candidate(candidate, "id-2")
        with pytest.raises(ValueError, match="No converter found"):
            registry.auto_convert(record)


class TestGlobalConverterRegistry:
    """Tests for global converter_registry."""

    def setup_method(self) -> None:
        """Clear global registry before each test."""
        converter_registry.clear()

    def test_global_registry_exists(self) -> None:
        """Global registry is available."""
        assert isinstance(converter_registry, ConverterRegistry)

    def test_global_registry_usable(self) -> None:
        """Can use global registry."""
        converter_registry.register(ArticleConverter())
        assert converter_registry.has("news")
