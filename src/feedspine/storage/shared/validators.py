"""Shared input validation helpers for FeedSpine storage backends.

This module provides reusable validation functions to ensure data integrity
before database operations.

By extracting validation, we ensure consistent behavior across all backends
and reduce duplication of validation logic.
"""

from __future__ import annotations

import re
from typing import Any

from feedspine.core.exceptions import ValidationError
from feedspine.models.base import Layer
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting

# Valid order_by columns (to prevent SQL injection)
VALID_ORDER_COLUMNS = frozenset(
    {
        "id",
        "natural_key",
        "layer",
        "published_at",
        "captured_at",
        "updated_at",
        "version",
        "first_seen_at",
        "last_seen_at",
        "seen_count",
    }
)


def validate_record(record: Record) -> None:
    """Validate a Record before storage.

    Args:
        record: Record to validate

    Raises:
        ValidationError: If validation fails
    """
    if not record.id:
        raise ValidationError("Record ID is required")

    if not record.natural_key:
        raise ValidationError("Record natural_key is required")

    if not isinstance(record.layer, Layer):
        raise ValidationError(f"Invalid layer: {record.layer}")

    if not isinstance(record.content, dict):
        raise ValidationError("Record content must be a dictionary")


def validate_sighting(sighting: Sighting) -> None:
    """Validate a Sighting before storage.

    Args:
        sighting: Sighting to validate

    Raises:
        ValidationError: If validation fails
    """
    if not sighting.id:
        raise ValidationError("Sighting ID is required")

    if not sighting.natural_key:
        raise ValidationError("Sighting natural_key is required")

    if not sighting.source:
        raise ValidationError("Sighting source is required")


def validate_layer(layer: str | Layer | None) -> Layer | None:
    """Validate and normalize layer value.

    Args:
        layer: Layer value (string or Layer enum)

    Returns:
        Layer enum or None

    Raises:
        ValidationError: If layer is invalid
    """
    if layer is None:
        return None

    if isinstance(layer, Layer):
        return layer

    try:
        return Layer(layer)
    except ValueError as err:
        valid_layers = [lyr.value for lyr in Layer]
        raise ValidationError(f"Invalid layer '{layer}'. Valid layers: {valid_layers}") from err


def validate_natural_key(natural_key: str) -> str:
    """Validate and normalize natural key.

    Args:
        natural_key: Natural key to validate

    Returns:
        Normalized natural key

    Raises:
        ValidationError: If natural key is invalid
    """
    if not natural_key:
        raise ValidationError("Natural key is required")

    if not isinstance(natural_key, str):
        raise ValidationError("Natural key must be a string")

    # Normalize (strip whitespace)
    normalized = natural_key.strip()

    if not normalized:
        raise ValidationError("Natural key cannot be empty or whitespace")

    # Maximum length check
    if len(normalized) > 512:
        raise ValidationError("Natural key exceeds maximum length of 512 characters")

    return normalized


def sanitize_order_by(order_by: str | None) -> str | None:
    """Sanitize order_by parameter to prevent SQL injection.

    Args:
        order_by: Order by clause (column name, optionally prefixed with -)

    Returns:
        Sanitized order_by or None

    Raises:
        ValidationError: If order_by contains invalid characters
    """
    if not order_by:
        return None

    # Handle descending prefix
    is_desc = order_by.startswith("-")
    column = order_by[1:] if is_desc else order_by

    # Validate column name
    if column not in VALID_ORDER_COLUMNS:
        # Allow JSON path syntax (e.g., content.title)
        if column.startswith("content."):
            json_path = column.replace("content.", "")
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", json_path):
                raise ValidationError(f"Invalid JSON path in order_by: {json_path}")
        else:
            raise ValidationError(f"Invalid order_by column: {column}. Valid columns: {sorted(VALID_ORDER_COLUMNS)}")

    return order_by


def validate_filters(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate filter dictionary.

    Args:
        filters: Filter dictionary

    Returns:
        Validated filters or None

    Raises:
        ValidationError: If filters are invalid
    """
    if filters is None:
        return None

    if not isinstance(filters, dict):
        raise ValidationError("Filters must be a dictionary")

    validated = {}

    for key, value in filters.items():
        if not isinstance(key, str):
            raise ValidationError(f"Filter key must be string, got {type(key)}")

        # Validate key format (prevent SQL injection)
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", key):
            raise ValidationError(f"Invalid filter key: {key}")

        validated[key] = value

    return validated


def validate_limit_offset(limit: int | None, offset: int) -> tuple[int | None, int]:
    """Validate limit and offset parameters.

    Args:
        limit: Maximum rows to return
        offset: Number of rows to skip

    Returns:
        Validated (limit, offset) tuple

    Raises:
        ValidationError: If values are invalid
    """
    if limit is not None:
        if not isinstance(limit, int) or limit < 0:
            raise ValidationError(f"Limit must be a non-negative integer, got {limit}")
        if limit > 100000:
            raise ValidationError("Limit exceeds maximum of 100,000")

    if not isinstance(offset, int) or offset < 0:
        raise ValidationError(f"Offset must be a non-negative integer, got {offset}")

    return limit, offset


def validate_batch_size(batch_size: int) -> int:
    """Validate batch size for bulk operations.

    Args:
        batch_size: Batch size to validate

    Returns:
        Validated batch size

    Raises:
        ValidationError: If batch size is invalid
    """
    if not isinstance(batch_size, int) or batch_size < 1:
        raise ValidationError(f"Batch size must be a positive integer, got {batch_size}")

    if batch_size > 10000:
        raise ValidationError("Batch size exceeds maximum of 10,000")

    return batch_size


def validate_record_id(record_id: str) -> str:
    """Validate record ID.

    Args:
        record_id: Record ID to validate

    Returns:
        Validated record ID

    Raises:
        ValidationError: If record ID is invalid
    """
    if not record_id:
        raise ValidationError("Record ID is required")

    if not isinstance(record_id, str):
        raise ValidationError("Record ID must be a string")

    normalized = record_id.strip()

    if not normalized:
        raise ValidationError("Record ID cannot be empty or whitespace")

    if len(normalized) > 256:
        raise ValidationError("Record ID exceeds maximum length of 256 characters")

    return normalized
