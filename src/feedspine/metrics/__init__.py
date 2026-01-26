"""FeedSpine metrics and observability.

Provides structured metrics collection for monitoring feed collection
performance. Supports optional Prometheus integration.

Example:
    >>> from feedspine.metrics import CollectionMetrics
    >>> 
    >>> metrics = CollectionMetrics()
    >>> 
    >>> # Record operations
    >>> with metrics.time_operation("fetch", adapter="quarterly"):
    ...     # ... fetch operation ...
    ...     pass
    >>> 
    >>> metrics.record_items("quarterly", category="10-K", count=1000)
    >>> metrics.record_error("quarterly", "network_timeout")
    >>> 
    >>> # Get summary
    >>> print(metrics.summary())
"""

from feedspine.metrics.collector import CollectionMetrics, MetricsSummary

__all__ = [
    "CollectionMetrics",
    "MetricsSummary",
]
