"""Record converter registry for domain model conversion.

Provides a registry for converting FeedSpine Records to
domain-specific models (e.g., Filing, Article, Product).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from feedspine.models.record import Record

# Type variable for domain models
T = TypeVar("T")


class RecordConverter[T](ABC):
    """Base class for record to domain model converters.

    Implement ``domain`` and ``convert()`` to define how Records are
    converted to your domain-specific models.

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

        Override for custom validation. Default checks if the record's
        ``metadata.source_type`` starts with ``self.domain``.
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
        """
        return [self.convert(r) for r in records]


class ConverterRegistry:
    """Registry for domain model converters.

    Central place to register and lookup converters for different domains.
    """

    def __init__(self) -> None:
        """Initialize an empty converter registry."""
        self._converters: dict[str, RecordConverter[Any]] = {}

    def register(self, converter: RecordConverter[Any]) -> None:
        """Register a converter for a domain.

        Args:
            converter: The converter instance to register.
        """
        self._converters[converter.domain] = converter

    def unregister(self, domain: str) -> bool:
        """Remove a converter. Returns True if one was removed."""
        if domain in self._converters:
            del self._converters[domain]
            return True
        return False

    def get(self, domain: str) -> RecordConverter[Any] | None:
        """Get the converter for a domain, or None."""
        return self._converters.get(domain)

    def has(self, domain: str) -> bool:
        """Check if a converter is registered for a domain."""
        return domain in self._converters

    def domains(self) -> list[str]:
        """Get all registered domain names."""
        return list(self._converters.keys())

    def convert(self, domain: str, record: Record) -> Any:
        """Convert a record using the registered converter.

        Raises:
            KeyError: If no converter is registered for the domain.
            ValueError: If the record cannot be converted.
        """
        converter = self._converters.get(domain)
        if converter is None:
            raise KeyError(f"No converter registered for domain: {domain}")
        return converter.convert(record)

    def convert_many(self, domain: str, records: list[Record]) -> list[Any]:
        """Convert multiple records. Raises KeyError if domain not found."""
        converter = self._converters.get(domain)
        if converter is None:
            raise KeyError(f"No converter registered for domain: {domain}")
        return converter.convert_many(records)

    def auto_convert(self, record: Record) -> Any:
        """Convert a record using the first matching converter.

        Raises:
            ValueError: If no converter can handle the record.
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
