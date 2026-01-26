"""Feed adapter module."""

from feedspine.adapter.base import BaseFeedAdapter, FeedAdapter, FeedError
from feedspine.adapter.file import (
    DiffableFileFeedAdapter,
    FileFeedAdapter,
    FileSnapshot,
    SnapshotDiff,
)
from feedspine.adapter.json import JSONFeedAdapter
from feedspine.adapter.rss import RSSFeedAdapter

__all__ = [
    "BaseFeedAdapter",
    "FeedAdapter",
    "FeedError",
    "JSONFeedAdapter",
    "RSSFeedAdapter",
    "FileFeedAdapter",
    "DiffableFileFeedAdapter",
    "FileSnapshot",
    "SnapshotDiff",
]
