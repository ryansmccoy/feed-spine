"""Console notifier implementation.

Provides a simple console-based notifier that prints notifications
to stdout, useful for testing and development.

Example:
    >>> from feedspine.notifier.console import ConsoleNotifier
    >>> notifier = ConsoleNotifier()
    >>> # ConsoleNotifier implements Notifier protocol
    >>> hasattr(notifier, 'send')
    True
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import TextIO

from feedspine.protocols.notification import Notification, Severity


class ConsoleNotifier:
    """Console notifier that prints to stdout/stderr.

    Formats notifications with severity indicators and timestamps.
    Can filter by minimum severity level.

    Best for: Testing, development, CLI applications.

    Example:
        >>> import asyncio
        >>> from feedspine.notifier.console import ConsoleNotifier
        >>> from feedspine.protocols.notification import Notification, Severity
        >>> notifier = ConsoleNotifier(min_severity=Severity.WARNING)
        >>> # INFO won't be shown (below WARNING)
        >>> asyncio.run(notifier.send(Notification(
        ...     title="Debug Info",
        ...     message="Low priority",
        ...     severity=Severity.DEBUG,
        ... )))
        False
    """

    # Severity indicators
    INDICATORS = {
        Severity.DEBUG: "🔍",
        Severity.INFO: "ℹ️ ",
        Severity.WARNING: "⚠️ ",
        Severity.ERROR: "❌",
        Severity.CRITICAL: "🚨",
    }

    def __init__(
        self,
        min_severity: Severity = Severity.DEBUG,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
        show_timestamp: bool = True,
        show_tags: bool = True,
    ) -> None:
        """Initialize console notifier.

        Args:
            min_severity: Minimum severity to display.
            stdout: Output stream for info/debug (default sys.stdout).
            stderr: Output stream for errors (default sys.stderr).
            show_timestamp: Include timestamp in output.
            show_tags: Include tags in output.
        """
        self._min_severity = min_severity
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr
        self._show_timestamp = show_timestamp
        self._show_tags = show_tags
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize notifier (no-op for console).

        Example:
            >>> import asyncio
            >>> from feedspine.notifier.console import ConsoleNotifier
            >>> n = ConsoleNotifier()
            >>> asyncio.run(n.initialize())
            >>> n._initialized
            True
        """
        self._initialized = True

    async def close(self) -> None:
        """Clean up resources (no-op for console)."""
        self._initialized = False

    async def send(self, notification: Notification) -> bool:
        """Send a notification to console.

        Args:
            notification: Notification to send.

        Returns:
            True if notification was displayed (met severity threshold).

        Example:
            >>> import asyncio
            >>> import io
            >>> from feedspine.notifier.console import ConsoleNotifier
            >>> from feedspine.protocols.notification import Notification, Severity
            >>> out = io.StringIO()
            >>> notifier = ConsoleNotifier(stdout=out, show_timestamp=False)
            >>> asyncio.run(notifier.send(Notification(
            ...     title="Test",
            ...     message="Hello",
            ...     severity=Severity.INFO,
            ... )))
            True
            >>> "Test" in out.getvalue()
            True
        """
        # Check severity threshold
        if not self._should_display(notification.severity):
            return False

        # Format and output
        formatted = self._format(notification)
        stream = self._get_stream(notification.severity)
        stream.write(formatted + "\n")
        stream.flush()

        return True

    def _should_display(self, severity: Severity) -> bool:
        """Check if severity meets threshold."""
        severity_order = list(Severity)
        return severity_order.index(severity) >= severity_order.index(self._min_severity)

    def _get_stream(self, severity: Severity) -> TextIO:
        """Get appropriate output stream for severity."""
        if severity in (Severity.ERROR, Severity.CRITICAL):
            return self._stderr
        return self._stdout

    def _format(self, notification: Notification) -> str:
        """Format notification for display.

        Example:
            >>> from feedspine.notifier.console import ConsoleNotifier
            >>> from feedspine.protocols.notification import Notification, Severity
            >>> n = ConsoleNotifier(show_timestamp=False, show_tags=False)
            >>> notif = Notification(title="Alert", message="Test msg", severity=Severity.WARNING)
            >>> formatted = n._format(notif)
            >>> "Alert" in formatted
            True
            >>> "Test msg" in formatted
            True
        """
        parts: list[str] = []

        # Timestamp
        if self._show_timestamp:
            ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            parts.append(f"[{ts}]")

        # Severity indicator
        indicator = self.INDICATORS.get(notification.severity, "")
        parts.append(indicator)

        # Title and message
        parts.append(f"{notification.title}:")
        parts.append(notification.message)

        # Tags
        if self._show_tags and notification.tags:
            tags_str = " ".join(f"#{tag}" for tag in notification.tags)
            parts.append(f"({tags_str})")

        return " ".join(parts)

    # --- Utility Methods ---

    def set_min_severity(self, severity: Severity) -> None:
        """Change minimum severity threshold.

        Example:
            >>> from feedspine.notifier.console import ConsoleNotifier
            >>> from feedspine.protocols.notification import Severity
            >>> n = ConsoleNotifier()
            >>> n.set_min_severity(Severity.ERROR)
            >>> n._min_severity
            <Severity.ERROR: 'error'>
        """
        self._min_severity = severity
