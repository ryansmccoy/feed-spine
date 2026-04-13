"""PipelineStats - Aggregated statistics from a pipeline run.

Provides the PipelineStats dataclass for capturing complete metrics
from processing a feed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class PipelineStats:
    """Aggregated statistics from a pipeline run.

    Captures counts of new records, duplicates, updates, and errors,
    plus timing information.  Use ``dedup_rate`` and ``update_rate``
    properties for quick insight into feed characteristics.

    Example:
        >>> from feedspine.pipeline import PipelineStats
        >>> stats = PipelineStats(
        ...     feed_name="sec_rss",
        ...     processed=100,
        ...     new=80,
        ...     duplicates=15,
        ...     updated=5,
        ... )
        >>> stats.dedup_rate
        0.15
    """

    feed_name: str
    processed: int = 0
    new: int = 0
    duplicates: int = 0
    updated: int = 0  # Count of same-ID-changed-content updates
    errors: int = 0
    duration_ms: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def dedup_rate(self) -> float:
        """Calculate deduplication rate (0.0 to 1.0).

        Example:
            >>> from feedspine.pipeline import PipelineStats
            >>> stats = PipelineStats("test", processed=100, duplicates=25)
            >>> stats.dedup_rate
            0.25
        """
        if self.processed == 0:
            return 0.0
        return self.duplicates / self.processed

    @property
    def update_rate(self) -> float:
        """Calculate update rate (0.0 to 1.0).

        Example:
            >>> from feedspine.pipeline import PipelineStats
            >>> stats = PipelineStats("test", processed=100, updated=10)
            >>> stats.update_rate
            0.1
        """
        if self.processed == 0:
            return 0.0
        return self.updated / self.processed
