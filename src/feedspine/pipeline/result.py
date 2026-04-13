"""ProcessResult - Structured result from processing a record candidate.

Provides the ProcessResult dataclass that encapsulates the outcome
of processing a RecordCandidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from feedspine.pipeline.action import ProcessAction

if TYPE_CHECKING:
    from feedspine.models.record import Record


@dataclass
class ProcessResult:
    """Structured result from processing a single record candidate.

    Attributes:
        action: The ProcessAction taken (CREATED/DUPLICATE/UPDATED).
        record: The stored Record, if any.
        previous_content_hash: Old hash when content changed (UPDATED only).

    Convenience properties ``is_new``, ``is_duplicate``, ``is_update``
    provide boolean accessors for the action.

    Example:
        >>> result = ProcessResult(action=ProcessAction.CREATED, record=None)
        >>> result.is_new
        True
    """

    action: ProcessAction
    record: Record | None = None
    previous_content_hash: str | None = None  # For updates, what the hash was before

    @property
    def is_new(self) -> bool:
        """Whether this was a new record."""
        return self.action == ProcessAction.CREATED

    @property
    def is_duplicate(self) -> bool:
        """Whether this was an exact duplicate."""
        return self.action == ProcessAction.DUPLICATE

    @property
    def is_update(self) -> bool:
        """Whether this was an update to existing content."""
        return self.action == ProcessAction.UPDATED
