"""Custom exceptions for FeedSpine.

Hierarchy::

    FeedSpineError (base)
    ├── StorageError
    ├── FeedError (with source attribution)
    ├── PipelineError
    ├── ValidationError
    ├── ConfigurationError
    ├── NotFoundError
    └── DuplicateError
"""

from __future__ import annotations


class FeedSpineError(Exception):
    """Base exception for all FeedSpine errors."""


class StorageError(FeedSpineError):
    """Storage/database operation failed."""


class FeedError(FeedSpineError):
    """Error during feed fetch operation with source attribution."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.cause = cause


class PipelineError(FeedSpineError):
    """Pipeline execution failed."""


class ValidationError(FeedSpineError, ValueError):
    """Data validation failed."""


class ConfigurationError(FeedSpineError):
    """Configuration is invalid or incomplete."""


class NotFoundError(FeedSpineError):
    """Requested resource not found."""


class DuplicateError(FeedSpineError):
    """Duplicate record detected."""
