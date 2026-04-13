"""Strongly-typed identifiers for feed-spine (CS-14).

Using ``NewType`` prevents accidental swaps between identifiers that
are all plain ``str`` at runtime.  Static type checkers (mypy, pyright)
will flag misuse; at runtime the wrappers are erased — zero overhead.

Example:
    >>> from feedspine.types import FeedName, JobId
    >>> name = FeedName("sec-rss")
    >>> type(name) is str
    True
"""

from __future__ import annotations

from typing import NewType

FeedName = NewType("FeedName", str)
"""Unique human-readable name of a feed adapter (e.g. ``"sec-rss"``)."""

RecordId = NewType("RecordId", str)
"""Globally unique identifier for a stored record (UUID or similar)."""

SourceId = NewType("SourceId", str)
"""Identifier for a data source origin."""

JobId = NewType("JobId", str)
"""Identifier for an enrichment job."""
