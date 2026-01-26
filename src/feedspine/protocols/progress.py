"""Progress reporting protocol for FeedSpine.

This module defines the ProgressReporter protocol that allows monitoring
long-running collection operations.

Example:
    >>> from feedspine.protocols.progress import ProgressReporter, ProgressEvent
    >>> 
    >>> class MyReporter(ProgressReporter):
    ...     def report(self, event: ProgressEvent) -> None:
    ...         print(f"{event.stage}: {event.current}/{event.total}")
    ... 
    >>> spine = FeedSpine(storage=storage, progress=MyReporter())
    >>> await spine.collect()  # Progress events emitted
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ProgressStage(Enum):
    """Stages of the collection pipeline."""
    PLANNING = "planning"
    FETCHING = "fetching"
    PARSING = "parsing"
    DEDUPLICATING = "deduplicating"
    STORING = "storing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ProgressEvent:
    """A progress event emitted during collection.
    
    Attributes:
        stage: Current pipeline stage
        adapter_name: Name of the adapter being processed
        current: Current item number (0-indexed)
        total: Total items expected (may be estimate)
        message: Human-readable status message
        records_new: Count of new records so far
        records_duplicate: Count of duplicates so far
        bytes_downloaded: Bytes downloaded so far
        started_at: When this stage started
        metadata: Additional adapter-specific metadata
    """
    stage: ProgressStage
    adapter_name: str = ""
    current: int = 0
    total: int = 0
    message: str = ""
    records_new: int = 0
    records_duplicate: int = 0
    bytes_downloaded: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def progress_percent(self) -> float:
        """Progress as percentage (0-100)."""
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100)
    
    @property
    def elapsed_seconds(self) -> float:
        """Seconds since stage started."""
        return (datetime.now() - self.started_at).total_seconds()
    
    @property
    def records_per_second(self) -> float:
        """Processing rate in records/second."""
        elapsed = self.elapsed_seconds
        if elapsed <= 0:
            return 0.0
        total_records = self.records_new + self.records_duplicate
        return total_records / elapsed
    
    @property
    def eta_seconds(self) -> float | None:
        """Estimated seconds remaining, or None if unknown."""
        if self.total <= 0 or self.current <= 0:
            return None
        elapsed = self.elapsed_seconds
        remaining = self.total - self.current
        rate = self.current / elapsed
        if rate <= 0:
            return None
        return remaining / rate


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for progress reporting implementations.
    
    Implement this protocol to receive progress events during collection.
    
    Example:
        >>> class LoggingReporter:
        ...     def report(self, event: ProgressEvent) -> None:
        ...         logger.info(f"{event.stage.value}: {event.message}")
        ...     
        ...     def start(self) -> None:
        ...         logger.info("Collection started")
        ...     
        ...     def finish(self, success: bool) -> None:
        ...         logger.info(f"Collection {'succeeded' if success else 'failed'}")
    """
    
    def report(self, event: ProgressEvent) -> None:
        """Report a progress event.
        
        Called whenever progress changes (new stage, new records, etc.)
        
        Args:
            event: The progress event with current state
        """
        ...
    
    def start(self) -> None:
        """Called when collection begins.
        
        Use this to initialize progress UI (e.g., create progress bar).
        """
        ...
    
    def finish(self, success: bool) -> None:
        """Called when collection ends.
        
        Args:
            success: True if collection completed without errors
        """
        ...


class NullProgressReporter:
    """No-op progress reporter (default when none specified)."""
    
    def report(self, event: ProgressEvent) -> None:
        """Discard event."""
        pass
    
    def start(self) -> None:
        """No-op."""
        pass
    
    def finish(self, success: bool) -> None:
        """No-op."""
        pass


class CallbackProgressReporter:
    """Progress reporter that calls a callback function.
    
    Useful for simple integrations where you just want a callback.
    
    Example:
        >>> def my_callback(event: ProgressEvent):
        ...     print(f"{event.progress_percent:.0f}%")
        >>> 
        >>> reporter = CallbackProgressReporter(my_callback)
    """
    
    def __init__(
        self,
        on_progress: callable | None = None,
        on_start: callable | None = None,
        on_finish: callable | None = None,
    ):
        self._on_progress = on_progress
        self._on_start = on_start
        self._on_finish = on_finish
    
    def report(self, event: ProgressEvent) -> None:
        if self._on_progress:
            self._on_progress(event)
    
    def start(self) -> None:
        if self._on_start:
            self._on_start()
    
    def finish(self, success: bool) -> None:
        if self._on_finish:
            self._on_finish(success)


__all__ = [
    "ProgressStage",
    "ProgressEvent",
    "ProgressReporter",
    "NullProgressReporter",
    "CallbackProgressReporter",
]
