"""Shared type conversion logic for FeedSpine storage backends.

This module contains converters that work across all backends:
- Row → Record domain model
- Record → Row dictionary
- Row → Sighting domain model
- Sighting → Row dictionary
- DateTime parsing/serialization

By extracting these converters, we eliminate ~150 lines of duplication
per backend (~600 lines total).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from feedspine.models.base import Layer, Metadata
from feedspine.models.record import Record
from feedspine.models.sighting import Sighting

# =============================================================================
# JSON Serialization Helpers
# =============================================================================


def json_serial(obj: Any) -> str:
    """JSON serializer for objects not serializable by default.

    Handles:
    - datetime objects
    - date objects

    Args:
        obj: Object to serialize

    Returns:
        ISO format string for datetime/date

    Raises:
        TypeError: If object type is not serializable
    """
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def parse_datetime(val: Any) -> datetime:
    """Parse datetime from various formats.

    Handles:
    - datetime objects (with or without timezone)
    - ISO format strings
    - None (returns current UTC time)

    Args:
        val: Value to parse

    Returns:
        Timezone-aware datetime (UTC)
    """
    if val is None:
        return datetime.now(UTC)
    if isinstance(val, datetime):
        return val.replace(tzinfo=UTC) if val.tzinfo is None else val
    if isinstance(val, str):
        dt = datetime.fromisoformat(val)
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
    # Fallback: convert to string and parse
    return datetime.fromisoformat(str(val)).replace(tzinfo=UTC)


def serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO format string.

    Args:
        dt: Datetime to serialize

    Returns:
        ISO format string
    """
    return dt.isoformat()


# =============================================================================
# Record Converters
# =============================================================================


def row_to_record(row: dict[str, Any] | tuple[Any, ...], column_map: dict[str, int] | None = None) -> Record | None:
    """Convert database row to Record domain model.

    Works with rows from any backend (dict-like or tuple access).

    Args:
        row: Database row (dict or tuple)
        column_map: For tuple rows, maps column name to index

    Returns:
        Record domain model, or None if row is None/empty

    Example:
        >>> # With dict-like row (SQLite, Postgres asyncpg)
        >>> record = row_to_record({"id": "1", "natural_key": "test", ...})

        >>> # With tuple row (DuckDB)
        >>> cols = {"id": 0, "natural_key": 1, "layer": 2, ...}
        >>> record = row_to_record(row_tuple, column_map=cols)
    """
    if row is None:
        return None

    # Handle dict-like rows
    if isinstance(row, dict) or hasattr(row, "__getitem__") and hasattr(row, "keys"):
        return _dict_row_to_record(row)

    # Handle tuple rows with column map
    if column_map is not None:
        return _tuple_row_to_record(row, column_map)

    # Default tuple column order (standard FeedSpine schema)
    default_cols = {
        "id": 0,
        "natural_key": 1,
        "layer": 2,
        "content": 3,
        "metadata": 4,
        "published_at": 5,
        "captured_at": 6,
        "updated_at": 7,
        "version": 8,
        "first_seen_at": 9,
        "last_seen_at": 10,
        "seen_count": 11,
    }
    return _tuple_row_to_record(row, default_cols)


def _dict_row_to_record(row: dict[str, Any]) -> Record:
    """Convert dict-like row to Record."""
    content = row["content"]
    if isinstance(content, str):
        content = json.loads(content)

    metadata_raw = row.get("metadata")
    if isinstance(metadata_raw, str) and metadata_raw:
        metadata_raw = json.loads(metadata_raw)

    metadata = None
    if metadata_raw:
        metadata = Metadata(**metadata_raw) if isinstance(metadata_raw, dict) else metadata_raw

    return Record(
        id=row["id"],
        natural_key=row["natural_key"],
        layer=Layer(row["layer"]) if isinstance(row["layer"], str) else row["layer"],
        content=content,
        metadata=metadata,
        published_at=parse_datetime(row["published_at"]),
        captured_at=parse_datetime(row["captured_at"]),
        updated_at=parse_datetime(row.get("updated_at", row["captured_at"])),
        version=row.get("version", 1),
        first_seen_at=parse_datetime(row.get("first_seen_at", row["captured_at"])),
        last_seen_at=parse_datetime(row.get("last_seen_at", row["captured_at"])),
        seen_count=row.get("seen_count", 1),
    )


def _tuple_row_to_record(row: tuple[Any, ...], column_map: dict[str, int]) -> Record:
    """Convert tuple row to Record using column map."""

    def get(name: str, default: Any = None) -> Any:
        idx = column_map.get(name)
        if idx is not None and idx < len(row):
            return row[idx]
        return default

    content = get("content")
    if isinstance(content, str):
        content = json.loads(content)

    metadata_raw = get("metadata")
    if isinstance(metadata_raw, str) and metadata_raw:
        metadata_raw = json.loads(metadata_raw)

    metadata = None
    if metadata_raw:
        metadata = Metadata(**metadata_raw) if isinstance(metadata_raw, dict) else metadata_raw

    captured_at = parse_datetime(get("captured_at"))

    return Record(
        id=get("id"),
        natural_key=get("natural_key"),
        layer=Layer(get("layer")) if isinstance(get("layer"), str) else get("layer"),
        content=content,
        metadata=metadata,
        published_at=parse_datetime(get("published_at")),
        captured_at=captured_at,
        updated_at=parse_datetime(get("updated_at", captured_at)),
        version=get("version", 1),
        first_seen_at=parse_datetime(get("first_seen_at", captured_at)),
        last_seen_at=parse_datetime(get("last_seen_at", captured_at)),
        seen_count=get("seen_count", 1),
    )


def record_to_row(record: Record) -> dict[str, Any]:
    """Convert Record to database row dict.

    Args:
        record: Record domain model

    Returns:
        Dictionary ready for database insertion
    """
    return {
        "id": record.id,
        "natural_key": record.natural_key,
        "layer": record.layer.value,
        "content": json.dumps(record.content, default=json_serial),
        "metadata": json.dumps(record.metadata.model_dump(), default=json_serial) if record.metadata else None,
        "published_at": serialize_datetime(record.published_at),
        "captured_at": serialize_datetime(record.captured_at),
        "updated_at": serialize_datetime(record.updated_at),
        "version": record.version,
        "first_seen_at": serialize_datetime(record.first_seen_at),
        "last_seen_at": serialize_datetime(record.last_seen_at),
        "seen_count": record.seen_count,
    }


# =============================================================================
# Sighting Converters
# =============================================================================


def row_to_sighting(row: dict[str, Any] | tuple[Any, ...], column_map: dict[str, int] | None = None) -> Sighting:
    """Convert database row to Sighting domain model.

    Args:
        row: Database row (dict or tuple)
        column_map: For tuple rows, maps column name to index

    Returns:
        Sighting domain model
    """
    # Handle dict-like rows
    if isinstance(row, dict) or hasattr(row, "__getitem__") and hasattr(row, "keys"):
        return _dict_row_to_sighting(row)

    # Handle tuple rows with column map
    if column_map is not None:
        return _tuple_row_to_sighting(row, column_map)

    # Default tuple column order
    default_cols = {
        "id": 0,
        "natural_key": 1,
        "record_id": 2,
        "source": 3,
        "seen_at": 4,
        "is_new": 5,
        "raw_data_hash": 6,
        "metadata": 7,
    }
    return _tuple_row_to_sighting(row, default_cols)


def _dict_row_to_sighting(row: dict[str, Any]) -> Sighting:
    """Convert dict-like row to Sighting."""
    metadata = row.get("metadata")
    if isinstance(metadata, str) and metadata:
        metadata = json.loads(metadata)
    if metadata is None:
        metadata = {}

    is_new = row["is_new"]
    if isinstance(is_new, int):
        is_new = bool(is_new)

    return Sighting(
        id=row["id"],
        natural_key=row["natural_key"],
        record_id=row.get("record_id"),
        source=row["source"],
        seen_at=parse_datetime(row["seen_at"]),
        is_new=is_new,
        raw_data_hash=row.get("raw_data_hash"),
        metadata=metadata,
    )


def _tuple_row_to_sighting(row: tuple[Any, ...], column_map: dict[str, int]) -> Sighting:
    """Convert tuple row to Sighting using column map."""

    def get(name: str, default: Any = None) -> Any:
        idx = column_map.get(name)
        if idx is not None and idx < len(row):
            return row[idx]
        return default

    metadata = get("metadata")
    if isinstance(metadata, str) and metadata:
        metadata = json.loads(metadata)
    if metadata is None:
        metadata = {}

    is_new = get("is_new", False)
    if isinstance(is_new, int):
        is_new = bool(is_new)

    return Sighting(
        id=get("id"),
        natural_key=get("natural_key"),
        record_id=get("record_id"),
        source=get("source"),
        seen_at=parse_datetime(get("seen_at")),
        is_new=is_new,
        raw_data_hash=get("raw_data_hash"),
        metadata=metadata,
    )


def sighting_to_row(sighting: Sighting) -> dict[str, Any]:
    """Convert Sighting to database row dict.

    Args:
        sighting: Sighting domain model

    Returns:
        Dictionary ready for database insertion
    """
    return {
        "id": sighting.id,
        "natural_key": sighting.natural_key,
        "record_id": sighting.record_id,
        "source": sighting.source,
        "seen_at": serialize_datetime(sighting.seen_at),
        "is_new": sighting.is_new,
        "raw_data_hash": sighting.raw_data_hash,
        "metadata": json.dumps(sighting.metadata) if sighting.metadata else None,
    }
