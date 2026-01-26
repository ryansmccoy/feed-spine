"""Metrics collector for feed operations.

Provides structured metrics collection for monitoring feed collection
performance in production. Supports optional Prometheus integration.

Example:
    >>> from feedspine.metrics import CollectionMetrics
    >>> 
    >>> metrics = CollectionMetrics()
    >>> 
    >>> # Time operations
    >>> with metrics.time_operation("fetch", adapter="quarterly"):
    ...     # ... fetch operation ...
    ...     pass
    >>> 
    >>> # Record counts
    >>> metrics.record_items("quarterly", category="10-K", count=1000)
    >>> metrics.record_error("quarterly", "network_timeout")
    >>> 
    >>> # Get summary
    >>> print(metrics.summary())
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generator

logger = logging.getLogger("feedspine.metrics")


@dataclass
class MetricsSummary:
    """Summary of collected metrics.
    
    Attributes:
        total_items: Total items processed
        total_errors: Total errors encountered
        total_fetch_time: Total time spent fetching
        total_parse_time: Total time spent parsing
        items_by_source: Items grouped by source/adapter
        items_by_category: Items grouped by category
        errors_by_source: Errors grouped by source
        operation_times: Total time by operation type and source
    """
    
    total_items: int = 0
    total_errors: int = 0
    total_fetch_time: float = 0.0
    total_parse_time: float = 0.0
    items_by_source: dict[str, int] = field(default_factory=dict)
    items_by_category: dict[str, int] = field(default_factory=dict)
    errors_by_source: dict[str, int] = field(default_factory=dict)
    operation_times: dict[str, dict[str, float]] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """Format summary as human-readable string."""
        lines = [
            "📊 Collection Metrics Summary",
            "=" * 40,
            f"Total items: {self.total_items:,}",
            f"Total errors: {self.total_errors}",
            f"Total fetch time: {self.total_fetch_time:.2f}s",
            f"Total parse time: {self.total_parse_time:.2f}s",
        ]
        
        if self.items_by_source:
            lines.append("\nItems by source:")
            for source, count in sorted(self.items_by_source.items()):
                lines.append(f"  {source}: {count:,}")
        
        if self.items_by_category:
            lines.append("\nItems by category (top 10):")
            for cat, count in sorted(self.items_by_category.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"  {cat}: {count:,}")
        
        if self.errors_by_source:
            lines.append("\nErrors by source:")
            for source, count in sorted(self.errors_by_source.items()):
                lines.append(f"  {source}: {count}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary for JSON serialization."""
        return {
            "total_items": self.total_items,
            "total_errors": self.total_errors,
            "total_fetch_time": self.total_fetch_time,
            "total_parse_time": self.total_parse_time,
            "items_by_source": self.items_by_source,
            "items_by_category": self.items_by_category,
            "errors_by_source": self.errors_by_source,
        }


class CollectionMetrics:
    """Collects metrics for feed collection operations.
    
    Thread-safe metrics collection with optional Prometheus export.
    
    Example:
        >>> metrics = CollectionMetrics()
        >>> metrics.start()
        >>> 
        >>> # Record items
        >>> metrics.record_items("quarterly", category="10-K", count=1000)
        >>> metrics.record_items("daily", category="8-K", count=500)
        >>> 
        >>> # Time operations
        >>> with metrics.time_operation("fetch", adapter="quarterly"):
        ...     # ... fetch ...
        ...     pass
        >>> 
        >>> print(metrics.summary())
    
    Attributes:
        prometheus_enabled: Whether Prometheus metrics are enabled
    """
    
    def __init__(
        self,
        enable_prometheus: bool = False,
        prometheus_prefix: str = "feedspine",
    ):
        """Initialize metrics collector.
        
        Args:
            enable_prometheus: If True, also export to Prometheus
                              (requires prometheus_client package)
            prometheus_prefix: Prefix for Prometheus metric names
        """
        self._items_by_source: dict[str, int] = defaultdict(int)
        self._items_by_category: dict[str, int] = defaultdict(int)
        self._errors_by_source: dict[str, int] = defaultdict(int)
        self._operation_times: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._start_time: datetime | None = None
        self._prometheus_enabled = False
        self._prometheus_prefix = prometheus_prefix
        
        if enable_prometheus:
            self._init_prometheus()
    
    @property
    def prometheus_enabled(self) -> bool:
        """Whether Prometheus metrics are enabled."""
        return self._prometheus_enabled
    
    def _init_prometheus(self) -> None:
        """Initialize Prometheus metrics if available."""
        try:
            from prometheus_client import Counter, Histogram
            
            prefix = self._prometheus_prefix
            
            self._prom_items = Counter(
                f"{prefix}_items_processed_total",
                "Total items processed",
                ["source", "category"],
            )
            
            self._prom_errors = Counter(
                f"{prefix}_errors_total",
                "Total errors",
                ["source", "error_type"],
            )
            
            self._prom_fetch_duration = Histogram(
                f"{prefix}_fetch_duration_seconds",
                "Time to fetch data",
                ["source"],
                buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
            )
            
            self._prom_parse_duration = Histogram(
                f"{prefix}_parse_duration_seconds",
                "Time to parse data",
                ["source"],
                buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
            )
            
            self._prometheus_enabled = True
            logger.info("Prometheus metrics enabled")
            
        except ImportError:
            logger.warning(
                "prometheus_client not installed. "
                "Install with: pip install prometheus-client"
            )
    
    def start(self) -> None:
        """Mark the start of a collection operation."""
        self._start_time = datetime.now()
    
    def record_items(
        self,
        source: str,
        category: str = "default",
        count: int = 1,
    ) -> None:
        """Record processed items.
        
        Args:
            source: Source adapter name (e.g., "quarterly", "daily")
            category: Item category (e.g., form type, content type)
            count: Number of items processed
        """
        self._items_by_source[source] += count
        self._items_by_category[category] += count
        
        if self._prometheus_enabled:
            self._prom_items.labels(source=source, category=category).inc(count)
    
    def record_error(
        self,
        source: str,
        error_type: str = "unknown",
    ) -> None:
        """Record an error.
        
        Args:
            source: Source adapter name
            error_type: Type of error (e.g., "network", "parse", "validation")
        """
        self._errors_by_source[source] += 1
        
        if self._prometheus_enabled:
            self._prom_errors.labels(source=source, error_type=error_type).inc()
        
        logger.warning(f"Error in {source}: {error_type}")
    
    @contextmanager
    def time_operation(
        self,
        operation: str,
        adapter: str = "default",
    ) -> Generator[None, None, None]:
        """Context manager to time an operation.
        
        Args:
            operation: Operation type ("fetch", "parse", "store", etc.)
            adapter: Adapter/source name
            
        Example:
            >>> metrics = CollectionMetrics()
            >>> with metrics.time_operation("fetch", adapter="quarterly"):
            ...     # ... fetch operation ...
            ...     pass
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self._operation_times[operation][adapter].append(duration)
            
            if self._prometheus_enabled:
                if operation == "fetch":
                    self._prom_fetch_duration.labels(source=adapter).observe(duration)
                elif operation == "parse":
                    self._prom_parse_duration.labels(source=adapter).observe(duration)
    
    def summary(self) -> MetricsSummary:
        """Get metrics summary.
        
        Returns:
            MetricsSummary with aggregated metrics
        """
        # Calculate operation times
        fetch_times = self._operation_times.get("fetch", {})
        parse_times = self._operation_times.get("parse", {})
        
        total_fetch = sum(sum(times) for times in fetch_times.values())
        total_parse = sum(sum(times) for times in parse_times.values())
        
        operation_totals = {}
        for op, adapters in self._operation_times.items():
            operation_totals[op] = {
                adapter: sum(times) for adapter, times in adapters.items()
            }
        
        return MetricsSummary(
            total_items=sum(self._items_by_source.values()),
            total_errors=sum(self._errors_by_source.values()),
            total_fetch_time=total_fetch,
            total_parse_time=total_parse,
            items_by_source=dict(self._items_by_source),
            items_by_category=dict(self._items_by_category),
            errors_by_source=dict(self._errors_by_source),
            operation_times=operation_totals,
        )
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._items_by_source.clear()
        self._items_by_category.clear()
        self._errors_by_source.clear()
        self._operation_times.clear()
        self._start_time = None
    
    def to_dict(self) -> dict[str, Any]:
        """Export metrics as dictionary."""
        return self.summary().to_dict()


# Global metrics instance for convenience
_global_metrics: CollectionMetrics | None = None


def get_metrics() -> CollectionMetrics:
    """Get global metrics instance.
    
    Returns:
        Global CollectionMetrics instance (created on first call)
    """
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = CollectionMetrics()
    return _global_metrics


def reset_metrics() -> None:
    """Reset global metrics."""
    global _global_metrics
    if _global_metrics is not None:
        _global_metrics.reset()


__all__ = [
    "CollectionMetrics",
    "MetricsSummary",
    "get_metrics",
    "reset_metrics",
]
