"""Typed content schemas for domain-specific record content.

This module provides a type-safe way to work with record content
instead of raw dict[str, Any] access. It supports Pydantic models
as content schemas with automatic validation and serialization.

Example:
    >>> from feedspine.models.content import ContentSchema, TypedRecord
    >>> from pydantic import Field
    >>>
    >>> class ArticleContent(ContentSchema):
    ...     title: str
    ...     author: str
    ...     body: str
    ...     word_count: int = Field(default=0)
    ...
    >>> # Validate raw content
    >>> raw = {"title": "Hello", "author": "Alice", "body": "World"}
    >>> article = ArticleContent.model_validate(raw)
    >>> article.title
    'Hello'
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from feedspine.models.record import Record

# TypeVar for content schema generics
T = TypeVar("T", bound="ContentSchema")


class ContentSchema(BaseModel):
    """Base class for typed content schemas.

    Extend this class to define domain-specific content structures.
    Provides automatic validation when loading from raw dicts.

    Example:
        >>> from feedspine.models.content import ContentSchema
        >>> from pydantic import Field
        >>>
        >>> class SECFilingContent(ContentSchema):
        ...     form_type: str
        ...     cik: str
        ...     company_name: str
        ...     filing_date: str
        ...     accession_number: str
        ...
        >>> raw = {
        ...     "form_type": "10-K",
        ...     "cik": "0001234567",
        ...     "company_name": "Example Corp",
        ...     "filing_date": "2024-01-15",
        ...     "accession_number": "0001234567-24-000001",
        ... }
        >>> filing = SECFilingContent.model_validate(raw)
        >>> filing.form_type
        '10-K'
    """

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields from raw content
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    @classmethod
    def from_record(cls: type[T], record: Record) -> T:
        """Create typed content from a Record's content dict.

        Args:
            record: The record containing content to validate.

        Returns:
            A validated instance of the content schema.

        Raises:
            ValidationError: If the content doesn't match the schema.

        Example:
            >>> from feedspine.models.content import ContentSchema
            >>> from feedspine.models.record import Record, RecordCandidate
            >>> from feedspine.models.base import Metadata
            >>> from datetime import datetime, timezone
            >>>
            >>> class MyContent(ContentSchema):
            ...     value: int
            ...
            >>> meta = Metadata(source="test")
            >>> candidate = RecordCandidate(
            ...     natural_key="test-1",
            ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...     content={"value": 42},
            ...     metadata=meta,
            ... )
            >>> record = Record.from_candidate(candidate, "id-1")
            >>> content = MyContent.from_record(record)
            >>> content.value
            42
        """
        return cls.model_validate(record.content)

    def to_dict(self) -> dict[str, Any]:
        """Convert content back to a dict for storage.

        Returns:
            Dictionary representation of the content.

        Example:
            >>> from feedspine.models.content import ContentSchema
            >>> class MyContent(ContentSchema):
            ...     value: int
            ...
            >>> c = MyContent(value=42)
            >>> c.to_dict()
            {'value': 42}
        """
        return self.model_dump()


class TypedRecord(Generic[T]):
    """Wrapper providing typed access to a Record's content.

    Combines a Record with its typed content schema for convenient access.

    Example:
        >>> from feedspine.models.content import ContentSchema, TypedRecord
        >>> from feedspine.models.record import Record, RecordCandidate
        >>> from feedspine.models.base import Metadata
        >>> from datetime import datetime, timezone
        >>>
        >>> class MyContent(ContentSchema):
        ...     value: int
        ...
        >>> meta = Metadata(source="test")
        >>> candidate = RecordCandidate(
        ...     natural_key="test-1",
        ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ...     content={"value": 42},
        ...     metadata=meta,
        ... )
        >>> record = Record.from_candidate(candidate, "id-1")
        >>> typed = TypedRecord(record, MyContent)
        >>> typed.content.value
        42
        >>> typed.record.id
        'id-1'
    """

    __slots__ = ("_record", "_content")

    def __init__(self, record: Record, schema: type[T]) -> None:
        """Initialize typed record wrapper.

        Args:
            record: The underlying Record instance.
            schema: The ContentSchema class to use for validation.
        """
        self._record = record
        self._content = schema.from_record(record)

    @property
    def record(self) -> Record:
        """Get the underlying Record."""
        return self._record

    @property
    def content(self) -> T:
        """Get the typed content."""
        return self._content

    @property
    def id(self) -> str:
        """Shortcut to record.id."""
        return self._record.id

    @property
    def natural_key(self) -> str:
        """Shortcut to record.natural_key."""
        return self._record.natural_key

    def update_content(self, **updates: Any) -> Record:
        """Create a new record with updated content.

        Args:
            **updates: Fields to update in the content.

        Returns:
            A new Record with the updated content.

        Example:
            >>> from feedspine.models.content import ContentSchema, TypedRecord
            >>> from feedspine.models.record import Record, RecordCandidate
            >>> from feedspine.models.base import Metadata
            >>> from datetime import datetime, timezone
            >>>
            >>> class MyContent(ContentSchema):
            ...     value: int
            ...
            >>> meta = Metadata(source="test")
            >>> candidate = RecordCandidate(
            ...     natural_key="test-1",
            ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...     content={"value": 42},
            ...     metadata=meta,
            ... )
            >>> record = Record.from_candidate(candidate, "id-1")
            >>> typed = TypedRecord(record, MyContent)
            >>> updated = typed.update_content(value=100)
            >>> updated.content["value"]
            100
        """
        new_content = {**self._record.content, **updates}
        return self._record.model_copy(update={"content": new_content})


# Registry for domain content schemas
_content_registry: dict[str, type[ContentSchema]] = {}


def register_content_schema(domain: str, schema: type[ContentSchema]) -> None:
    """Register a content schema for a domain.

    Args:
        domain: Domain identifier (e.g., 'sec', 'news').
        schema: ContentSchema subclass for this domain.

    Example:
        >>> from feedspine.models.content import ContentSchema, register_content_schema
        >>>
        >>> class NewsContent(ContentSchema):
        ...     headline: str
        ...     source: str
        ...
        >>> register_content_schema("news", NewsContent)
    """
    _content_registry[domain] = schema


def get_content_schema(domain: str) -> type[ContentSchema] | None:
    """Get the registered content schema for a domain.

    Args:
        domain: Domain identifier.

    Returns:
        The registered ContentSchema subclass, or None if not registered.

    Example:
        >>> from feedspine.models.content import get_content_schema
        >>> schema = get_content_schema("unknown")
        >>> schema is None
        True
    """
    return _content_registry.get(domain)


def clear_content_registry() -> None:
    """Clear all registered content schemas. Useful for testing."""
    _content_registry.clear()
