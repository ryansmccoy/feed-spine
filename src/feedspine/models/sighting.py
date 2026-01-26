"""Sighting model - tracks when records are seen.

Sightings provide the audit trail for feed data:
- Track first-seen vs. subsequent observations
- Enable deduplication across feeds
- Support feed health monitoring

Example:
    >>> from feedspine.models.sighting import Sighting
    >>> s = Sighting(
    ...     id="sight-1",
    ...     natural_key="article-123",
    ...     source="rss-feed",
    ...     is_new=True,
    ... )
    >>> s.is_new
    True
    >>> s.natural_key
    'article-123'
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from feedspine.models.base import FeedSpineModel


class Sighting(FeedSpineModel):
    """Records each time we see a natural_key.

    Used for:
    - Deduplication (is this new?)
    - Tracking feed health (when did we last see updates?)
    - Audit trail (provenance)

    Example:
        >>> from feedspine.models.sighting import Sighting
        >>> s = Sighting(
        ...     id="s1",
        ...     natural_key="key-abc",
        ...     source="feed-x",
        ...     is_new=False,
        ...     record_id="rec-123",
        ... )
        >>> s.record_id
        'rec-123'
        >>> s.is_new
        False
    """

    id: str = Field(..., description="Sighting ID")
    natural_key: str = Field(..., description="The key that was sighted")
    record_id: str | None = Field(default=None, description="Associated record ID if stored")
    source: str = Field(..., description="Which feed/source reported this")
    seen_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this sighting occurred",
    )
    is_new: bool = Field(..., description="True if this was the first sighting")
    raw_data_hash: str | None = Field(
        default=None,
        description="Hash of raw data for change detection",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
