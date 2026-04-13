"""Feed-spine workflow layer — spine-core Runtime implementations.

Workflows bridge spine-core's execution engine to feed-spine's
domain service layer:

- ``FeedCollectionRuntime``: implements ``Runtime`` for ``feed.collect``
  work items dispatched by the Runner.
"""

from __future__ import annotations

from feedspine.workflows.collect import FeedCollectionRuntime

__all__ = [
    "FeedCollectionRuntime",
]
