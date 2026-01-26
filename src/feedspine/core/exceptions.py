"""Custom exceptions.

FeedSpine uses a hierarchy of exceptions to provide clear error handling:

Example:
    >>> from feedspine.core.exceptions import StorageError, NotFoundError
    >>> isinstance(StorageError("db error"), FeedSpineError)
    True
    >>> try:
    ...     raise NotFoundError("record not found")
    ... except FeedSpineError as e:
    ...     print(f"Caught: {type(e).__name__}")
    Caught: NotFoundError
"""

from __future__ import annotations


class FeedSpineError(Exception):
    """Base exception for FeedSpine.

    Example:
        >>> from feedspine.core.exceptions import FeedSpineError
        >>> e = FeedSpineError("something went wrong")
        >>> str(e)
        'something went wrong'
    """


class StorageError(FeedSpineError):
    """Storage operation failed.

    Example:
        >>> from feedspine.core.exceptions import StorageError
        >>> raise StorageError("connection lost")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        StorageError: connection lost
    """


class FeedError(FeedSpineError):
    """Feed operation failed.

    Example:
        >>> from feedspine.core.exceptions import FeedError
        >>> raise FeedError("feed unavailable")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        FeedError: feed unavailable
    """


class ValidationError(FeedSpineError):
    """Data validation failed.

    Example:
        >>> from feedspine.core.exceptions import ValidationError
        >>> raise ValidationError("invalid format")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        ValidationError: invalid format
    """


class ConfigurationError(FeedSpineError):
    """Configuration is invalid.

    Example:
        >>> from feedspine.core.exceptions import ConfigurationError
        >>> raise ConfigurationError("missing key")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        ConfigurationError: missing key
    """


class NotFoundError(FeedSpineError):
    """Requested resource not found.

    Example:
        >>> from feedspine.core.exceptions import NotFoundError
        >>> raise NotFoundError("record abc")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        NotFoundError: record abc
    """


class DuplicateError(FeedSpineError):
    """Duplicate record detected.

    Example:
        >>> from feedspine.core.exceptions import DuplicateError
        >>> raise DuplicateError("key exists")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        DuplicateError: key exists
    """
