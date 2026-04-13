"""Event bus re-exports — backward compatibility aliases.

Feed-spine's original ``MessageQueue`` protocol duplicated spine-core's
``EventBus``.  This module provides backward-compatible aliases so
existing ``from feedspine.protocols.queue import …`` imports work.
"""

try:
    from spine.events import Event as Message  # noqa: F401
    from spine.events import EventBus as MessageQueue  # noqa: F401
except ImportError:
    from feedspine._vendor.events import Event as Message  # noqa: F401
    from feedspine._vendor.events import EventBus as MessageQueue  # noqa: F401

__all__ = ["Message", "MessageQueue"]
