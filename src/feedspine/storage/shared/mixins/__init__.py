"""Memory storage mixins for in-memory implementations.

These mixins provide in-memory implementations of storage protocols
that can be composed into a complete storage backend.

Example:
    >>> class MyStorage(RecordStorageMixin, FetchContextMixin, RunLogMixin):
    ...     def __init__(self):
    ...         RecordStorageMixin.__init__(self)
    ...         FetchContextMixin.__init__(self)
    ...         RunLogMixin.__init__(self)
"""

from feedspine.storage.shared.mixins.fetch_context import FetchContextMixin
from feedspine.storage.shared.mixins.records import RecordStorageMixin
from feedspine.storage.shared.mixins.run_log import RunLogMixin

__all__ = [
    "RecordStorageMixin",
    "FetchContextMixin",
    "RunLogMixin",
]
