"""Typed content schemas for domain-specific record content.

Provides ``ContentSchema`` (Pydantic base) and ``TypedRecord`` wrapper
for type-safe access to record content instead of raw ``dict[str, Any]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from feedspine.models.record import Record

# TypeVar for content schema generics
T = TypeVar("T", bound="ContentSchema")


class ContentSchema(BaseModel):
    """Base class for typed content schemas.

    Extend this to define domain-specific content structures with
    automatic Pydantic validation when loading from raw dicts.

    Example:
        >>> from feedspine.models.content import ContentSchema
        >>> class SECFilingContent(ContentSchema):
        ...     form_type: str
        ...     cik: str
        >>> filing = SECFilingContent.model_validate({"form_type": "10-K", "cik": "0001234567"})
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
        """
        return cls.model_validate(record.content)

    def to_dict(self) -> dict[str, Any]:
        """Convert content back to a dict for storage."""
        return self.model_dump()


class TypedRecord[T: "ContentSchema"]:
    """Wrapper providing typed access to a Record's content.

    Combines a Record with its typed ``ContentSchema`` for type-safe access.
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
        """Create a new record with updated content fields."""
        new_content = {**self._record.content, **updates}
        return self._record.model_copy(update={"content": new_content})


# Registry for domain content schemas
_content_registry: dict[str, type[ContentSchema]] = {}


def register_content_schema(domain: str, schema: type[ContentSchema]) -> None:
    """Register a content schema for a domain.

    Args:
        domain: Domain identifier (e.g., 'sec', 'news').
        schema: ContentSchema subclass for this domain.
    """
    _content_registry[domain] = schema


def get_content_schema(domain: str) -> type[ContentSchema] | None:
    """Get the registered content schema for a domain.

    Args:
        domain: Domain identifier.

    Returns:
        The registered ContentSchema subclass, or None if not registered.
    """
    return _content_registry.get(domain)


def clear_content_registry() -> None:
    """Clear all registered content schemas. Useful for testing."""
    _content_registry.clear()
