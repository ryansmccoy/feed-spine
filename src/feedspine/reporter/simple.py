"""Simple logging-based progress reporter.

Provides a text-based progress reporter that uses Python logging,
suitable for scripts, CI/CD pipelines, or when Rich is not available.

Example:
    >>> from feedspine.reporter import SimpleProgressReporter
    >>> 
    >>> reporter = SimpleProgressReporter()
    >>> reporter.start()
    >>> # ... feed.collect() reports progress events ...
    >>> reporter.finish(success=True)
    
    # Output in logs:
    # [STARTED] Feed collection
    # [PROGRESS] adapter.name: 45/100 (45%)
    # [COMPLETE] New: 102,345, Duplicates: 1,234
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from feedspine.protocols.progress import (
    ProgressEvent,
    ProgressStage,
)


class SimpleProgressReporter:
    """Simple text-based progress reporter using logging.
    
    Prints progress to a logger without fancy formatting.
    Good for scripts, CI/CD, or when Rich is not available.
    
    Example:
        >>> reporter = SimpleProgressReporter()
        >>> reporter.start()
        >>> # ... during collection ...
        >>> reporter.report(event)
        >>> reporter.finish(success=True)
        
        # Output:
        # [STARTED] Feed collection
        # [PROGRESS] quarterly.2025Q1: 45/100 (45%)
        # [PROGRESS] quarterly.2025Q1: 100/100 (100%)
        # [COMPLETE] New: 102,345, Duplicates: 1,234
    
    Attributes:
        logger: The logger instance to use
    """
    
    def __init__(
        self,
        logger: logging.Logger | None = None,
        log_level: int = logging.INFO,
    ):
        """Initialize the reporter.
        
        Args:
            logger: Logger to use (default: feedspine.progress logger)
            log_level: Logging level for progress messages
        """
        self._logger = logger or logging.getLogger("feedspine.progress")
        self._log_level = log_level
        self._stats: dict[str, Any] = {}
    
    def start(self) -> None:
        """Mark the start of collection."""
        self._stats = {
            "started_at": datetime.now(),
            "records_new": 0,
            "records_duplicate": 0,
        }
        self._logger.log(self._log_level, "[STARTED] Feed collection")
    
    def report(self, event: ProgressEvent) -> None:
        """Report a progress event.
        
        Args:
            event: Progress event from feed collection
        """
        self._stats["records_new"] = event.records_new
        self._stats["records_duplicate"] = event.records_duplicate
        
        if event.total > 0:
            self._logger.log(
                self._log_level,
                f"[{event.stage.value.upper()}] {event.adapter_name}: "
                f"{event.current:,}/{event.total:,} ({event.progress_percent:.0f}%)"
            )
        else:
            self._logger.log(
                self._log_level,
                f"[{event.stage.value.upper()}] {event.adapter_name}: {event.message}"
            )
    
    def finish(self, success: bool) -> None:
        """Mark the end of collection.
        
        Args:
            success: Whether collection completed successfully
        """
        elapsed = (datetime.now() - self._stats["started_at"]).total_seconds()
        status = "COMPLETE" if success else "FAILED"
        self._logger.log(
            self._log_level,
            f"[{status}] New: {self._stats['records_new']:,}, "
            f"Duplicates: {self._stats['records_duplicate']:,}, "
            f"Duration: {elapsed:.1f}s"
        )


__all__ = ["SimpleProgressReporter"]
