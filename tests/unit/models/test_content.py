"""Tests for feedspine.models.content."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import Field, ValidationError

from feedspine.models.base import Layer, Metadata
from feedspine.models.content import (
    ContentSchema,
    TypedRecord,
    clear_content_registry,
    get_content_schema,
    register_content_schema,
)
from feedspine.models.record import Record, RecordCandidate


class ArticleContent(ContentSchema):
    """Test content schema for articles."""

    title: str
    author: str = "Unknown"
    word_count: int = Field(default=0, ge=0)


class TestContentSchemaBasic:
    """Basic ContentSchema tests."""

    def test_create_minimal(self) -> None:
        """Can create with required fields only."""
        content = ArticleContent(title="Hello World")
        assert content.title == "Hello World"
        assert content.author == "Unknown"
        assert content.word_count == 0

    def test_create_full(self) -> None:
        """Can create with all fields."""
        content = ArticleContent(title="Hello", author="Alice", word_count=100)
        assert content.title == "Hello"
        assert content.author == "Alice"
        assert content.word_count == 100

    def test_extra_fields_allowed(self) -> None:
        """Extra fields are preserved."""
        content = ArticleContent(title="Test", extra_field="value")
        assert content.title == "Test"
        assert content.model_extra.get("extra_field") == "value"


class TestContentSchemaValidation:
    """ContentSchema validation tests."""

    def test_required_field_missing(self) -> None:
        """Required fields must be provided."""
        with pytest.raises(ValidationError):
            ArticleContent()  # title is required

    def test_field_validation(self) -> None:
        """Field validators work."""
        with pytest.raises(ValidationError):
            ArticleContent(title="Test", word_count=-1)  # ge=0


class TestContentSchemaConversion:
    """ContentSchema conversion tests."""

    def test_to_dict(self) -> None:
        """Can convert to dict."""
        content = ArticleContent(title="Test", author="Bob")
        d = content.to_dict()
        assert d["title"] == "Test"
        assert d["author"] == "Bob"
        assert d["word_count"] == 0

    def test_model_validate(self) -> None:
        """Can validate from dict."""
        raw = {"title": "Test", "author": "Alice", "word_count": 50}
        content = ArticleContent.model_validate(raw)
        assert content.title == "Test"
        assert content.author == "Alice"
        assert content.word_count == 50


class TestContentSchemaFromRecord:
    """Tests for ContentSchema.from_record()."""

    @pytest.fixture
    def record(self) -> Record:
        """Create a test record."""
        candidate = RecordCandidate(
            natural_key="article-1",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Test Article", "author": "Charlie", "word_count": 200},
            metadata=Metadata(source="test"),
        )
        return Record.from_candidate(candidate, "id-123")

    def test_from_record_success(self, record: Record) -> None:
        """Can extract content from record."""
        content = ArticleContent.from_record(record)
        assert content.title == "Test Article"
        assert content.author == "Charlie"
        assert content.word_count == 200

    def test_from_record_missing_required(self) -> None:
        """Raises ValidationError if required fields missing."""
        candidate = RecordCandidate(
            natural_key="article-2",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"author": "Alice"},  # missing title
            metadata=Metadata(source="test"),
        )
        record = Record.from_candidate(candidate, "id-456")
        with pytest.raises(ValidationError):
            ArticleContent.from_record(record)


class TestTypedRecordBasic:
    """Basic TypedRecord tests."""

    @pytest.fixture
    def record(self) -> Record:
        """Create a test record."""
        candidate = RecordCandidate(
            natural_key="article-1",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Typed Test", "author": "Dan", "word_count": 50},
            metadata=Metadata(source="test"),
        )
        return Record.from_candidate(candidate, "id-typed")

    def test_typed_content_access(self, record: Record) -> None:
        """Can access typed content."""
        typed = TypedRecord(record, ArticleContent)
        assert typed.content.title == "Typed Test"
        assert typed.content.author == "Dan"
        assert typed.content.word_count == 50

    def test_record_access(self, record: Record) -> None:
        """Can access underlying record."""
        typed = TypedRecord(record, ArticleContent)
        assert typed.record.id == "id-typed"
        assert typed.record.layer == Layer.BRONZE

    def test_shortcut_properties(self, record: Record) -> None:
        """Shortcut properties work."""
        typed = TypedRecord(record, ArticleContent)
        assert typed.id == "id-typed"
        assert typed.natural_key == "article-1"


class TestTypedRecordUpdate:
    """Tests for TypedRecord.update_content()."""

    @pytest.fixture
    def record(self) -> Record:
        """Create a test record."""
        candidate = RecordCandidate(
            natural_key="article-1",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            content={"title": "Original", "author": "Eve", "word_count": 100},
            metadata=Metadata(source="test"),
        )
        return Record.from_candidate(candidate, "id-update")

    def test_update_content(self, record: Record) -> None:
        """Can update content fields."""
        typed = TypedRecord(record, ArticleContent)
        updated = typed.update_content(title="Updated Title")
        assert updated.content["title"] == "Updated Title"
        assert updated.content["author"] == "Eve"  # unchanged

    def test_original_unchanged(self, record: Record) -> None:
        """Original record is unchanged."""
        typed = TypedRecord(record, ArticleContent)
        _ = typed.update_content(title="New")
        assert typed.record.content["title"] == "Original"


class TestContentRegistry:
    """Tests for content schema registry."""

    def setup_method(self) -> None:
        """Clear registry before each test."""
        clear_content_registry()

    def test_register_and_get(self) -> None:
        """Can register and retrieve schema."""
        register_content_schema("news", ArticleContent)
        schema = get_content_schema("news")
        assert schema is ArticleContent

    def test_get_unregistered(self) -> None:
        """Returns None for unregistered domain."""
        schema = get_content_schema("unknown")
        assert schema is None

    def test_clear_registry(self) -> None:
        """Can clear all registrations."""
        register_content_schema("news", ArticleContent)
        clear_content_registry()
        assert get_content_schema("news") is None
