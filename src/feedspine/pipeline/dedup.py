"""Cross-feed deduplication index.

Maintains a content-hash → record-id mapping to detect duplicate
content arriving through different feeds with distinct natural keys.
Per-feed dedup (via ``natural_key``) is handled separately in ``stages.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DedupMatch:
    """Result of a dedup check."""

    is_duplicate: bool
    existing_record_id: str | None = None
    content_hash: str = ""


class DedupIndex:
    """In-memory content-hash index for cross-feed deduplication.

    Maintains a ``{content_hash: record_id}`` mapping for the lifetime
    of the index (typically one application run). Thread-unsafe —
    designed for single-event-loop async usage.
    """

    def __init__(self) -> None:
        self._index: dict[str, str] = {}

    def check(self, content_hash: str) -> DedupMatch:
        """Look up a content hash in the index.

        Args:
            content_hash: SHA-256 prefix from ``RecordCandidate.content_hash``.

        Returns:
            DedupMatch indicating whether this content was already seen.
        """
        existing_id = self._index.get(content_hash)
        if existing_id is not None:
            return DedupMatch(
                is_duplicate=True,
                existing_record_id=existing_id,
                content_hash=content_hash,
            )
        return DedupMatch(is_duplicate=False, content_hash=content_hash)

    def register(self, content_hash: str, record_id: str) -> None:
        """Register a content hash after a record is stored.

        Args:
            content_hash: The content hash of the stored record.
            record_id: The UUID of the stored record.
        """
        self._index[content_hash] = record_id

    @property
    def size(self) -> int:
        """Number of entries in the index."""
        return len(self._index)

    def clear(self) -> None:
        """Reset the index."""
        self._index.clear()


@dataclass
class DedupStats:
    """Aggregated cross-feed dedup statistics."""

    checked: int = 0
    cross_feed_duplicates: int = 0
    registered: int = 0

    @property
    def duplicate_rate(self) -> float:
        """Fraction of checked candidates that were cross-feed duplicates."""
        return self.cross_feed_duplicates / self.checked if self.checked else 0.0
