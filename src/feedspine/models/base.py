"""Base models and shared types.

This module provides the foundational models and enums used throughout FeedSpine.

Example:
    >>> from feedspine.models.base import Layer, Metadata
    >>> Layer.BRONZE.value
    'bronze'
    >>> meta = Metadata(source="test-feed")
    >>> meta.source
    'test-feed'
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Layer(str, Enum):
    """Medallion architecture layer for data quality tiers.

    Records progress through layers as they are validated and enriched:
    BRONZE (raw) → SILVER (clean) → GOLD (enriched).

    Example:
        >>> Layer.BRONZE.value
        'bronze'
        >>> list(Layer)
        [<Layer.BRONZE: 'bronze'>, <Layer.SILVER: 'silver'>, <Layer.GOLD: 'gold'>]
    """

    BRONZE = "bronze"  # Raw, as-captured
    SILVER = "silver"  # Validated, deduplicated
    GOLD = "gold"  # Enriched, analytics-ready


class FeedSpineModel(BaseModel):
    """Base model with standard configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )


class Metadata(FeedSpineModel):
    """Common metadata fields."""

    source: str = Field(..., min_length=1, description="Origin of the data")
    source_type: str = Field(default="", description="Type of source (e.g., 'sec.rss', 'sec.daily_index')")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When data was captured",
    )
    extra: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
