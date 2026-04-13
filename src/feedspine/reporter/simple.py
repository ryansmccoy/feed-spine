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

from datetime import UTC, datetime
from logging import INFO, Logger
from typing import Any

from feedspine._vendor.logging import get_logger

from feedspine.protocols.progress import (
    ProgressEvent,
)

_default_logger = get_logger("feedspine.progress")


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
        logger: Logger | None = None,
        log_level: int = INFO,
    ):
        """Initialize the reporter.

        Args:
            logger: Stdlib logger to use (default: structlog feedspine.progress)
            log_level: Logging level for progress messages (used with stdlib loggers)
        """
        self._logger: Any = logger or _default_logger
        self._log_level = log_level
        self._use_stdlib = logger is not None
        self._stats: dict[str, Any] = {}

    def _log(self, message: str) -> None:
        """Log a message via stdlib .log() or structlog .info()."""
        if self._use_stdlib:
            self._logger.log(self._log_level, message)
        else:
            self._logger.info(message)

    def start(self) -> None:
        """Mark the start of collection."""
        self._stats = {
            "started_at": datetime.now(UTC),
            "records_new": 0,
            "records_duplicate": 0,
        }
        self._log("[STARTED] Feed collection")

    def report(self, event: ProgressEvent) -> None:
        """Report a progress event.

        Args:
            event: Progress event from feed collection
        """
        self._stats["records_new"] = event.records_new
        self._stats["records_duplicate"] = event.records_duplicate

        if event.total > 0:
            self._log(
                f"[{event.stage.value.upper()}] {event.adapter_name}: "
                f"{event.current:,}/{event.total:,} ({event.progress_percent:.0f}%)",
            )
        else:
            self._log(
                f"[{event.stage.value.upper()}] {event.adapter_name}: {event.message}",
            )

    def finish(self, success: bool) -> None:
        """Mark the end of collection.

        Args:
            success: Whether collection completed successfully
        """
        elapsed = (datetime.now(UTC) - self._stats["started_at"]).total_seconds()
        status = "COMPLETE" if success else "FAILED"
        self._log(
            f"[{status}] New: {self._stats['records_new']:,}, "
            f"Duplicates: {self._stats['records_duplicate']:,}, "
            f"Duration: {elapsed:.1f}s",
        )


__all__ = ["SimpleProgressReporter"]
