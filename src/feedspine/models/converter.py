"""Record converter registry for domain model conversion.

This module provides a registry for converting FeedSpine Records to
domain-specific models (e.g., Filing, Article, Product). This eliminates
the need for repeated _record_to_filing() helper functions across codebases.

Example:
    >>> from feedspine.models.converter import RecordConverter, converter_registry
    >>> from feedspine.models.record import Record, RecordCandidate
    >>> from feedspine.models.base import Metadata, Layer
    >>> from datetime import datetime, timezone
    >>> from dataclasses import dataclass
    >>>
    >>> @dataclass
    ... class Article:
    ...     id: str
    ...     title: str
    ...     author: str
    >>>
    >>> class ArticleConverter(RecordConverter[Article]):
    ...     domain = "news"
    ...     def convert(self, record: Record) -> Article:
    ...         return Article(
    ...             id=record.id,
    ...             title=record.content.get("title", ""),
    ...             author=record.content.get("author", "Unknown"),
    ...         )
    >>>
    >>> converter_registry.register(ArticleConverter())
    >>> # Now any code can convert records to Articles
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from feedspine.models.record import Record

# Type variable for domain models
T = TypeVar("T")


class RecordConverter(ABC, Generic[T]):
    """Base class for record to domain model converters.

    Implement this class to define how Records are converted to
    your domain-specific models (Filing, Article, Product, etc.).

    Example:
        >>> from feedspine.models.converter import RecordConverter
        >>> from feedspine.models.record import Record
        >>> from dataclasses import dataclass
        >>>
        >>> @dataclass
        ... class Product:
        ...     sku: str
        ...     name: str
        ...     price: float
        >>>
        >>> class ProductConverter(RecordConverter[Product]):
        ...     domain = "ecommerce"
        ...     def convert(self, record: Record) -> Product:
        ...         return Product(
        ...             sku=record.natural_key,
        ...             name=record.content.get("name", ""),
        ...             price=record.content.get("price", 0.0),
        ...         )
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """The domain identifier this converter handles.

        Examples: 'sec', 'news', 'ecommerce', 'healthcare'.
        """
        ...

    @abstractmethod
    def convert(self, record: Record) -> T:
        """Convert a Record to the domain model.

        Args:
            record: The FeedSpine Record to convert.

        Returns:
            An instance of the domain model.

        Raises:
            ValueError: If the record cannot be converted.
        """
        ...

    def can_convert(self, record: Record) -> bool:
        """Check if this converter can handle the given record.

        Override this for custom validation logic. Default checks
        if the record's metadata.source_type matches the domain.

        Args:
            record: The record to check.

        Returns:
            True if this converter can handle the record.

        Example:
            >>> from feedspine.models.converter import RecordConverter
            >>> from feedspine.models.record import Record
            >>>
            >>> class MyConverter(RecordConverter[dict]):
            ...     domain = "test"
            ...     def convert(self, record: Record) -> dict:
            ...         return record.content
            ...     def can_convert(self, record: Record) -> bool:
            ...         return "required_field" in record.content
        """
        # Default: check if source_type starts with domain
        source_type = record.metadata.source_type or ""
        return source_type.startswith(self.domain)

    def convert_many(self, records: list[Record]) -> list[T]:
        """Convert multiple records to domain models.

        Override for batch-optimized conversion.

        Args:
            records: List of records to convert.

        Returns:
            List of domain models.

        Example:
            >>> from feedspine.models.converter import RecordConverter
            >>> from feedspine.models.record import Record
            >>>
            >>> class MyConverter(RecordConverter[dict]):
            ...     domain = "test"
            ...     def convert(self, record: Record) -> dict:
            ...         return {"id": record.id}
            ...     def convert_many(self, records: list[Record]) -> list[dict]:
            ...         # Could batch database lookups here
            ...         return [self.convert(r) for r in records]
        """
        return [self.convert(r) for r in records]


class ConverterRegistry:
    """Registry for domain model converters.

    Provides a central place to register and lookup converters
    for different domains. This eliminates duplicate conversion
    functions scattered across codebases.

    Example:
        >>> from feedspine.models.converter import ConverterRegistry, RecordConverter
        >>> from feedspine.models.record import Record
        >>>
        >>> registry = ConverterRegistry()
        >>>
        >>> class MyConverter(RecordConverter[dict]):
        ...     domain = "myapp"
        ...     def convert(self, record: Record) -> dict:
        ...         return record.content
        >>>
        >>> registry.register(MyConverter())
        >>> registry.has("myapp")
        True
    """

    def __init__(self) -> None:
        """Initialize an empty converter registry."""
        self._converters: dict[str, RecordConverter[Any]] = {}

    def register(self, converter: RecordConverter[Any]) -> None:
        """Register a converter for a domain.

        Args:
            converter: The converter instance to register.

        Example:
            >>> from feedspine.models.converter import ConverterRegistry, RecordConverter
            >>> from feedspine.models.record import Record
            >>> registry = ConverterRegistry()
            >>> class TestConverter(RecordConverter[dict]):
            ...     domain = "test"
            ...     def convert(self, record: Record) -> dict:
            ...         return {}
            >>> registry.register(TestConverter())
            >>> registry.has("test")
            True
        """
        self._converters[converter.domain] = converter

    def unregister(self, domain: str) -> bool:
        """Remove a converter from the registry.

        Args:
            domain: The domain to remove.

        Returns:
            True if a converter was removed.

        Example:
            >>> from feedspine.models.converter import ConverterRegistry
            >>> registry = ConverterRegistry()
            >>> registry.unregister("missing")
            False
        """
        if domain in self._converters:
            del self._converters[domain]
            return True
        return False

    def get(self, domain: str) -> RecordConverter[Any] | None:
        """Get the converter for a domain.

        Args:
            domain: The domain identifier.

        Returns:
            The registered converter, or None if not found.

        Example:
            >>> from feedspine.models.converter import ConverterRegistry
            >>> registry = ConverterRegistry()
            >>> registry.get("unknown") is None
            True
        """
        return self._converters.get(domain)

    def has(self, domain: str) -> bool:
        """Check if a converter is registered for a domain.

        Args:
            domain: The domain identifier.

        Returns:
            True if a converter is registered.

        Example:
            >>> from feedspine.models.converter import ConverterRegistry
            >>> registry = ConverterRegistry()
            >>> registry.has("missing")
            False
        """
        return domain in self._converters

    def domains(self) -> list[str]:
        """Get all registered domain names.

        Returns:
            List of registered domain identifiers.

        Example:
            >>> from feedspine.models.converter import ConverterRegistry
            >>> registry = ConverterRegistry()
            >>> registry.domains()
            []
        """
        return list(self._converters.keys())

    def convert(self, domain: str, record: Record) -> Any:
        """Convert a record using the registered converter.

        Args:
            domain: The domain to convert to.
            record: The record to convert.

        Returns:
            The converted domain model.

        Raises:
            KeyError: If no converter is registered for the domain.
            ValueError: If the record cannot be converted.

        Example:
            >>> from feedspine.models.converter import ConverterRegistry, RecordConverter
            >>> from feedspine.models.record import Record, RecordCandidate
            >>> from feedspine.models.base import Metadata
            >>> from datetime import datetime, timezone
            >>> registry = ConverterRegistry()
            >>> class TestConverter(RecordConverter[dict]):
            ...     domain = "test"
            ...     def convert(self, record: Record) -> dict:
            ...         return {"id": record.id}
            >>> registry.register(TestConverter())
            >>> meta = Metadata(source="test")
            >>> candidate = RecordCandidate(
            ...     natural_key="key1",
            ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...     metadata=meta,
            ... )
            >>> record = Record.from_candidate(candidate, "id-1")
            >>> result = registry.convert("test", record)
            >>> result["id"]
            'id-1'
        """
        converter = self._converters.get(domain)
        if converter is None:
            raise KeyError(f"No converter registered for domain: {domain}")
        return converter.convert(record)

    def convert_many(self, domain: str, records: list[Record]) -> list[Any]:
        """Convert multiple records using the registered converter.

        Args:
            domain: The domain to convert to.
            records: The records to convert.

        Returns:
            List of converted domain models.

        Raises:
            KeyError: If no converter is registered for the domain.
        """
        converter = self._converters.get(domain)
        if converter is None:
            raise KeyError(f"No converter registered for domain: {domain}")
        return converter.convert_many(records)

    def auto_convert(self, record: Record) -> Any:
        """Automatically convert a record using matching converter.

        Tries each registered converter's can_convert() method.

        Args:
            record: The record to convert.

        Returns:
            The converted domain model.

        Raises:
            ValueError: If no converter can handle the record.

        Example:
            >>> from feedspine.models.converter import ConverterRegistry, RecordConverter
            >>> from feedspine.models.record import Record, RecordCandidate
            >>> from feedspine.models.base import Metadata
            >>> from datetime import datetime, timezone
            >>> registry = ConverterRegistry()
            >>> class TestConverter(RecordConverter[dict]):
            ...     domain = "test"
            ...     def convert(self, record: Record) -> dict:
            ...         return {"id": record.id}
            ...     def can_convert(self, record: Record) -> bool:
            ...         return True  # Accept all records
            >>> registry.register(TestConverter())
            >>> meta = Metadata(source="test")
            >>> candidate = RecordCandidate(
            ...     natural_key="key1",
            ...     published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ...     metadata=meta,
            ... )
            >>> record = Record.from_candidate(candidate, "id-1")
            >>> result = registry.auto_convert(record)
            >>> result["id"]
            'id-1'
        """
        for converter in self._converters.values():
            if converter.can_convert(record):
                return converter.convert(record)
        raise ValueError(f"No converter found for record: {record.id}")

    def __iter__(self) -> Iterator[tuple[str, RecordConverter[Any]]]:
        """Iterate over registered converters.

        Yields:
            Tuples of (domain, converter).
        """
        yield from self._converters.items()

    def clear(self) -> None:
        """Remove all registered converters. Useful for testing."""
        self._converters.clear()


# Global converter registry instance
converter_registry = ConverterRegistry()
