"""Feed adapter module."""

from feedspine.adapter.base import BaseFeedAdapter, FeedAdapter, FeedError
from feedspine.adapter.csv_adapter import CSVFeedAdapter
from feedspine.adapter.file import (
    DiffableFileFeedAdapter,
    FileFeedAdapter,
    FileSnapshot,
    SnapshotDiff,
)
from feedspine.adapter.json import JSONFeedAdapter
from feedspine.adapter.polygon_earnings import (
    PolygonEarningsAdapter,
    PolygonEstimateHistoryAdapter,
)
from feedspine.adapter.rss import RSSFeedAdapter
from feedspine.adapter.sec_edgar import SECEdgarFilingAdapter

__all__ = [
    "BaseFeedAdapter",
    "CSVFeedAdapter",
    "DiffableFileFeedAdapter",
    "FeedAdapter",
    "FeedError",
    "FileFeedAdapter",
    "FileSnapshot",
    "JSONFeedAdapter",
    "PolygonEarningsAdapter",
    "PolygonEstimateHistoryAdapter",
    "RSSFeedAdapter",
    "SECEdgarFilingAdapter",
    "SnapshotDiff",
]
