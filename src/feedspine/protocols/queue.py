"""Event bus re-exports from spine-core.

Feed-spine's original ``MessageQueue`` protocol duplicated spine-core's
``EventBus``.  This module now re-exports spine-core's canonical event
types so existing ``from feedspine.protocols.queue import …`` imports
continue to work.

For fan-out pub/sub use :class:`spine.events.EventBus`.
For competing-consumer task dispatch use :class:`spine.ports.work_item_store.WorkItemStore`.
"""

from spine.events import Event as Message  # noqa: F401 — backward compat alias
from spine.events import EventBus as MessageQueue  # noqa: F401 — backward compat alias

__all__ = ["Message", "MessageQueue"]
