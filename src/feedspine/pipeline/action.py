"""ProcessAction - Record processing outcome classification.

Provides the ProcessAction enum that classifies the three possible
outcomes when a feed candidate is processed.
"""

from __future__ import annotations

from enum import StrEnum


class ProcessAction(StrEnum):
    """Action classification for record processing outcomes.

    Three possible outcomes when a candidate is processed:

    - **CREATED** — first observation of this natural_key.
    - **DUPLICATE** — exact match (same key + same content hash).
    - **UPDATED** — same key but content_hash changed.

    Example:
        >>> from feedspine.pipeline import ProcessAction
        >>> ProcessAction.CREATED.value
        'created'
    """

    CREATED = "created"  # New record stored
    DUPLICATE = "duplicate"  # Exact duplicate (same natural_key + same content_hash)
    UPDATED = "updated"  # Same natural_key, different content_hash
