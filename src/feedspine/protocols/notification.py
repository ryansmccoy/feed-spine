"""Notification protocol.

Defines the interface for sending notifications (Slack, email, webhooks, etc.).

Example:
    >>> from feedspine.protocols.notification import Notification, Severity
    >>> n = Notification(
    ...     title="Feed Complete",
    ...     message="Processed 100 records",
    ...     severity=Severity.INFO,
    ... )
    >>> n.severity.value
    'info'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class Severity(str, Enum):
    """Notification severity level.

    Example:
        >>> from feedspine.protocols.notification import Severity
        >>> Severity.WARNING.value
        'warning'
        >>> list(Severity)  # doctest: +NORMALIZE_WHITESPACE
        [<Severity.DEBUG: 'debug'>, <Severity.INFO: 'info'>,
         <Severity.WARNING: 'warning'>, <Severity.ERROR: 'error'>,
         <Severity.CRITICAL: 'critical'>]
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Notification:
    """A notification to send.

    Example:
        >>> from feedspine.protocols.notification import Notification, Severity
        >>> n = Notification(
        ...     title="Error Alert",
        ...     message="Connection failed",
        ...     severity=Severity.ERROR,
        ...     tags=["database", "urgent"],
        ... )
        >>> n.title
        'Error Alert'
        >>> n.tags
        ['database', 'urgent']
    """

    title: str
    message: str
    severity: Severity = Severity.INFO
    data: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)


@runtime_checkable
class Notifier(Protocol):
    """Notification backend protocol."""

    async def send(self, notification: Notification) -> bool:
        """Send a notification. Returns True if successful."""
        ...

    async def initialize(self) -> None:
        """Initialize notifier."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
