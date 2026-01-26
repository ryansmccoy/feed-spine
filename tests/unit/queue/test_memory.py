"""Tests for MemoryQueue implementation.

Tests cover:
- Publish/subscribe basics
- Message delivery
- Multiple subscribers
- Acknowledgment
- Lifecycle (initialize/close)
- Protocol compliance
"""

import asyncio

from feedspine.queue.memory import MemoryQueue

# =============================================================================
# Basic Publish Tests
# =============================================================================


class TestMemoryQueuePublish:
    """Tests for message publishing."""

    async def test_publish_returns_message_id(self):
        """Publishing returns a message ID."""
        queue = MemoryQueue()
        await queue.initialize()

        msg_id = await queue.publish("topic1", {"data": 1})

        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    async def test_publish_unique_ids(self):
        """Each message gets a unique ID."""
        queue = MemoryQueue()
        await queue.initialize()

        id1 = await queue.publish("topic", "msg1")
        id2 = await queue.publish("topic", "msg2")
        id3 = await queue.publish("topic", "msg3")

        assert len({id1, id2, id3}) == 3

    async def test_publish_with_metadata(self):
        """Can publish with metadata."""
        queue = MemoryQueue()
        await queue.initialize()

        msg_id = await queue.publish(
            "topic",
            {"content": "test"},
            metadata={"priority": "high"},
        )

        assert msg_id is not None


# =============================================================================
# Subscribe Tests
# =============================================================================


class TestMemoryQueueSubscribe:
    """Tests for message subscription."""

    async def test_subscriber_receives_messages(self):
        """Subscriber receives published messages."""
        queue = MemoryQueue()
        await queue.initialize()

        received = []

        async def subscriber():
            async for msg in queue.subscribe("events"):
                received.append(msg)
                if len(received) >= 2:
                    break

        # Start subscriber in background
        task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.01)  # Let subscriber start

        # Publish messages
        await queue.publish("events", {"id": 1})
        await queue.publish("events", {"id": 2})

        await asyncio.wait_for(task, timeout=1.0)

        assert len(received) == 2
        assert received[0].payload == {"id": 1}
        assert received[1].payload == {"id": 2}

    async def test_multiple_subscribers_same_topic(self):
        """Multiple subscribers all receive messages."""
        queue = MemoryQueue()
        await queue.initialize()

        received1 = []
        received2 = []

        async def sub1():
            async for msg in queue.subscribe("news"):
                received1.append(msg)
                if len(received1) >= 1:
                    break

        async def sub2():
            async for msg in queue.subscribe("news"):
                received2.append(msg)
                if len(received2) >= 1:
                    break

        task1 = asyncio.create_task(sub1())
        task2 = asyncio.create_task(sub2())
        await asyncio.sleep(0.01)

        await queue.publish("news", "breaking")

        await asyncio.wait_for(asyncio.gather(task1, task2), timeout=1.0)

        assert len(received1) == 1
        assert len(received2) == 1
        assert received1[0].payload == "breaking"
        assert received2[0].payload == "breaking"

    async def test_different_topics_isolated(self):
        """Messages on different topics are isolated."""
        queue = MemoryQueue()
        await queue.initialize()

        received_a = []
        received_b = []

        async def sub_a():
            async for msg in queue.subscribe("topic_a"):
                received_a.append(msg)
                break

        async def sub_b():
            async for msg in queue.subscribe("topic_b"):
                received_b.append(msg)
                break

        task_a = asyncio.create_task(sub_a())
        task_b = asyncio.create_task(sub_b())
        await asyncio.sleep(0.01)

        await queue.publish("topic_a", "message_a")
        await queue.publish("topic_b", "message_b")

        await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=1.0)

        assert received_a[0].payload == "message_a"
        assert received_b[0].payload == "message_b"


# =============================================================================
# Message Tests
# =============================================================================


class TestMemoryQueueMessage:
    """Tests for Message structure."""

    async def test_message_has_id(self):
        """Messages have a message_id."""
        queue = MemoryQueue()
        await queue.initialize()

        received = []

        async def sub():
            async for msg in queue.subscribe("topic"):
                received.append(msg)
                break

        task = asyncio.create_task(sub())
        await asyncio.sleep(0.01)

        published_id = await queue.publish("topic", "test")
        await asyncio.wait_for(task, timeout=1.0)

        assert received[0].message_id == published_id

    async def test_message_has_payload(self):
        """Messages contain the published payload."""
        queue = MemoryQueue()
        await queue.initialize()

        received = []

        async def sub():
            async for msg in queue.subscribe("topic"):
                received.append(msg)
                break

        task = asyncio.create_task(sub())
        await asyncio.sleep(0.01)

        await queue.publish("topic", {"key": "value"})
        await asyncio.wait_for(task, timeout=1.0)

        assert received[0].payload == {"key": "value"}

    async def test_message_has_metadata(self):
        """Messages include metadata when provided."""
        queue = MemoryQueue()
        await queue.initialize()

        received = []

        async def sub():
            async for msg in queue.subscribe("topic"):
                received.append(msg)
                break

        task = asyncio.create_task(sub())
        await asyncio.sleep(0.01)

        await queue.publish("topic", "data", metadata={"source": "test"})
        await asyncio.wait_for(task, timeout=1.0)

        assert received[0].metadata == {"source": "test"}


# =============================================================================
# Acknowledgment Tests
# =============================================================================


class TestMemoryQueueAcknowledge:
    """Tests for message acknowledgment."""

    async def test_ack_message(self):
        """Can acknowledge a message."""
        queue = MemoryQueue()
        await queue.initialize()

        received = []

        async def sub():
            async for msg in queue.subscribe("topic"):
                received.append(msg)
                break

        task = asyncio.create_task(sub())
        await asyncio.sleep(0.01)

        await queue.publish("topic", "test")
        await asyncio.wait_for(task, timeout=1.0)

        # Acknowledge should not raise (pass Message object, not string)
        await queue.ack(received[0])

    async def test_nack_message(self):
        """Can negative-acknowledge a message."""
        queue = MemoryQueue()
        await queue.initialize()

        received = []

        async def sub():
            async for msg in queue.subscribe("topic"):
                received.append(msg)
                break

        task = asyncio.create_task(sub())
        await asyncio.sleep(0.01)

        await queue.publish("topic", "test")
        await asyncio.wait_for(task, timeout=1.0)

        # Nack should not raise (pass Message object, not string)
        await queue.nack(received[0])


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestMemoryQueueLifecycle:
    """Tests for initialize/close lifecycle."""

    async def test_initialize_sets_flag(self):
        """initialize sets _initialized flag."""
        queue = MemoryQueue()

        assert queue._initialized is False

        await queue.initialize()

        assert queue._initialized is True

    async def test_close_clears_state(self):
        """close clears topics and pending."""
        queue = MemoryQueue()
        await queue.initialize()

        await queue.publish("topic", "msg")

        await queue.close()

        assert queue._initialized is False
        assert len(queue._topics) == 0

    async def test_close_idempotent(self):
        """Multiple closes are safe."""
        queue = MemoryQueue()
        await queue.initialize()

        await queue.close()
        await queue.close()

        assert queue._initialized is False

    async def test_max_queue_size(self):
        """Queue respects max size configuration."""
        queue = MemoryQueue(max_queue_size=5)

        assert queue._max_size == 5


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestMemoryQueueProtocol:
    """Tests for MessageQueue protocol compliance."""

    def test_has_required_methods(self):
        """MemoryQueue has all required MessageQueue methods."""
        queue = MemoryQueue()

        assert hasattr(queue, "initialize")
        assert hasattr(queue, "close")
        assert hasattr(queue, "publish")
        assert hasattr(queue, "subscribe")
        assert hasattr(queue, "ack")
        assert hasattr(queue, "nack")

    def test_methods_are_async(self):
        """All I/O methods are async."""
        import inspect

        queue = MemoryQueue()

        assert inspect.iscoroutinefunction(queue.initialize)
        assert inspect.iscoroutinefunction(queue.close)
        assert inspect.iscoroutinefunction(queue.publish)
        assert inspect.isasyncgenfunction(queue.subscribe)
        assert inspect.iscoroutinefunction(queue.ack)
        assert inspect.iscoroutinefunction(queue.nack)
