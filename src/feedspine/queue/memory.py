"""In-memory message queue implementation.

Provides a complete in-memory pub/sub implementation of MessageQueue,
useful for testing and single-process applications.

Example:
    >>> from feedspine.queue.memory import MemoryQueue
    >>> queue = MemoryQueue()
    >>> # MemoryQueue implements MessageQueue protocol
    >>> hasattr(queue, 'publish')
    True
    >>> hasattr(queue, 'subscribe')
    True
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from feedspine.protocols.queue import Message


class MemoryQueue:
    """In-memory message queue with pub/sub support.

    Uses asyncio queues for message delivery.
    Supports multiple subscribers per topic.

    Best for: Testing, development, single-process apps.

    Example:
        >>> import asyncio
        >>> from feedspine.queue.memory import MemoryQueue
        >>> queue = MemoryQueue()
        >>> asyncio.run(queue.initialize())
        >>> msg_id = asyncio.run(queue.publish("topic1", {"data": 1}))
        >>> len(msg_id) > 0
        True
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        """Initialize the queue.

        Args:
            max_queue_size: Maximum messages per topic queue.
        """
        self._max_size = max_queue_size
        self._topics: dict[str, list[asyncio.Queue[Message]]] = defaultdict(list)
        self._pending: dict[str, Message] = {}  # message_id -> Message (unacked)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize queue.

        Example:
            >>> import asyncio
            >>> from feedspine.queue.memory import MemoryQueue
            >>> q = MemoryQueue()
            >>> asyncio.run(q.initialize())
            >>> q._initialized
            True
        """
        self._initialized = True

    async def close(self) -> None:
        """Clean up resources."""
        for topic_queues in self._topics.values():
            for q in topic_queues:
                # Signal subscribers to stop
                await q.put(None)  # type: ignore
        self._topics.clear()
        self._pending.clear()
        self._initialized = False

    async def publish(
        self,
        topic: str,
        payload: Any,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Publish a message to a topic.

        Args:
            topic: Topic name.
            payload: Message payload.
            metadata: Optional metadata.

        Returns:
            Message ID.

        Example:
            >>> import asyncio
            >>> from feedspine.queue.memory import MemoryQueue
            >>> q = MemoryQueue()
            >>> asyncio.run(q.initialize())
            >>> msg_id = asyncio.run(q.publish("events", {"type": "created"}))
            >>> isinstance(msg_id, str)
            True
        """
        message = Message(
            message_id=str(uuid4()),
            payload=payload,
            metadata=metadata,
        )

        # Deliver to all subscriber queues
        for subscriber_queue in self._topics[topic]:
            try:
                subscriber_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop oldest message if full
                try:
                    subscriber_queue.get_nowait()
                    subscriber_queue.put_nowait(message)
                except asyncio.QueueEmpty:
                    pass

        return message.message_id

    async def subscribe(
        self,
        topic: str,
        group: str | None = None,
    ) -> AsyncIterator[Message]:
        """Subscribe to messages on a topic.

        Args:
            topic: Topic to subscribe to.
            group: Consumer group (for load balancing).

        Yields:
            Messages as they arrive.

        Example:
            >>> import asyncio
            >>> from feedspine.queue.memory import MemoryQueue
            >>> async def example():
            ...     q = MemoryQueue()
            ...     await q.initialize()
            ...     # Publish first, then subscribe would miss it
            ...     # In real usage, subscribe runs in background
            ...     return True
            >>> asyncio.run(example())
            True
        """
        queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=self._max_size)
        self._topics[topic].append(queue)

        try:
            while True:
                message = await queue.get()
                if message is None:  # Shutdown signal
                    break
                self._pending[message.message_id] = message
                yield message
        finally:
            # Cleanup on unsubscribe
            if queue in self._topics[topic]:
                self._topics[topic].remove(queue)

    async def ack(self, message: Message) -> None:
        """Acknowledge message processing.

        Args:
            message: Message to acknowledge.

        Example:
            >>> import asyncio
            >>> from feedspine.queue.memory import MemoryQueue
            >>> from feedspine.protocols.queue import Message
            >>> q = MemoryQueue()
            >>> msg = Message(message_id="m1", payload={})
            >>> q._pending["m1"] = msg
            >>> asyncio.run(q.ack(msg))
            >>> "m1" in q._pending
            False
        """
        self._pending.pop(message.message_id, None)

    async def nack(self, message: Message, requeue: bool = True) -> None:
        """Negative acknowledge - message was not processed.

        Args:
            message: Message that failed.
            requeue: Whether to requeue for redelivery.

        Example:
            >>> import asyncio
            >>> from feedspine.queue.memory import MemoryQueue
            >>> from feedspine.protocols.queue import Message
            >>> q = MemoryQueue()
            >>> asyncio.run(q.initialize())
            >>> msg = Message(message_id="m1", payload={"x": 1})
            >>> q._pending["m1"] = msg
            >>> asyncio.run(q.nack(msg, requeue=False))
            >>> "m1" in q._pending
            False
        """
        self._pending.pop(message.message_id, None)

        if requeue:
            # Re-publish with incremented attempt
            new_message = Message(
                message_id=message.message_id,
                payload=message.payload,
                metadata=message.metadata,
                attempt=message.attempt + 1,
            )
            # Find original topic (simplified - in real impl, track this)
            for _topic, queues in self._topics.items():
                for q in queues:
                    try:
                        q.put_nowait(new_message)
                        return
                    except asyncio.QueueFull:
                        pass

    # --- Utility Methods ---

    def topic_count(self) -> int:
        """Return number of active topics.

        Example:
            >>> from feedspine.queue.memory import MemoryQueue
            >>> q = MemoryQueue()
            >>> q.topic_count()
            0
        """
        return len([t for t, subs in self._topics.items() if subs])

    def pending_count(self) -> int:
        """Return number of unacknowledged messages.

        Example:
            >>> from feedspine.queue.memory import MemoryQueue
            >>> q = MemoryQueue()
            >>> q.pending_count()
            0
        """
        return len(self._pending)
