"""Message queue protocol.

Defines the interface for message queues and pub/sub systems.

Example:
    >>> from feedspine.protocols.queue import Message
    >>> msg = Message(message_id="msg-1", payload={"action": "process"})
    >>> msg.payload
    {'action': 'process'}
    >>> msg.attempt
    1
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class Message:
    """A message in the queue.

    Example:
        >>> from feedspine.protocols.queue import Message
        >>> m = Message(
        ...     message_id="m123",
        ...     payload={"key": "value"},
        ...     attempt=2,
        ... )
        >>> m.message_id
        'm123'
        >>> m.attempt
        2
    """

    message_id: str
    payload: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempt: int = 1
    metadata: dict[str, Any] | None = None


@runtime_checkable
class MessageQueue(Protocol):
    """Message queue protocol."""

    async def publish(
        self,
        topic: str,
        payload: Any,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Publish a message. Returns message ID."""
        ...

    async def subscribe(
        self,
        topic: str,
        group: str | None = None,
    ) -> AsyncIterator[Message]:
        """Subscribe to messages."""
        ...

    async def ack(self, message: Message) -> None:
        """Acknowledge message."""
        ...

    async def nack(self, message: Message, requeue: bool = True) -> None:
        """Negative acknowledge."""
        ...

    async def initialize(self) -> None:
        """Initialize queue."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
