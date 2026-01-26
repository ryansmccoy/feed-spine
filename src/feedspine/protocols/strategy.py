"""Collection strategy protocol for optimized multi-source data collection.

This module defines protocols for implementing intelligent collection strategies
that optimize data fetching across multiple sources with different characteristics
(efficiency, freshness, coverage).

The pattern supports scenarios where:
- Multiple data sources exist with different trade-offs
- Bulk sources are more efficient but less fresh
- Real-time sources are fresh but expensive
- Intelligent planning minimizes total requests

Example domain implementations:
- SEC EDGAR: Quarterly (bulk) > Daily (medium) > RSS (real-time)
- News: Archive API > Recent API > Live WebSocket
- Social Media: Historical API > Search API > Streaming API

Usage:
    >>> # Define domain-specific source priorities
    >>> class MySourcePriority(SourcePriority):
    ...     ARCHIVE = 1   # Most efficient
    ...     RECENT = 2    # Medium
    ...     LIVE = 3      # Least efficient but real-time
    ...
    >>> # Implement collection strategy
    >>> class MyStrategy:
    ...     def plan(self, start_date, end_date) -> CollectionPlan:
    ...         # Return optimized plan for the date range
    ...         ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Generic, Iterator, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from feedspine.protocols.feed import FeedAdapter


class SourcePriority(IntEnum):
    """Base class for source priority ordering.
    
    Lower values = more efficient (prefer bulk operations).
    Higher values = more fresh (real-time, streaming).
    
    Domains should subclass this with their specific sources:
    
        class SECSourcePriority(SourcePriority):
            QUARTERLY = 1  # ~100K filings per request
            DAILY = 2      # ~4K filings per day
            RSS = 3        # Real-time, ~100 filings
    """
    pass


@dataclass(frozen=True)
class DateRange:
    """A date range for collection.
    
    Supports both date-only ranges and precise datetime ranges.
    """
    start: date | datetime
    end: date | datetime
    
    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(f"start ({self.start}) must be <= end ({self.end})")
    
    @property
    def days(self) -> int:
        """Number of days in range (inclusive)."""
        start_date = self.start.date() if isinstance(self.start, datetime) else self.start
        end_date = self.end.date() if isinstance(self.end, datetime) else self.end
        return (end_date - start_date).days + 1
    
    def overlaps(self, other: DateRange) -> bool:
        """Check if this range overlaps with another."""
        return self.start <= other.end and other.start <= self.end
    
    def contains(self, d: date | datetime) -> bool:
        """Check if a date/datetime is within this range."""
        return self.start <= d <= self.end


# Type variable for domain-specific source identifiers
SourceT = TypeVar("SourceT", bound=str)


@dataclass
class SourceFetch(Generic[SourceT]):
    """A single fetch operation from a source.
    
    Represents one request to a data source with its expected characteristics.
    
    Attributes:
        source_id: Identifier for the source (e.g., "quarterly_2024_q1", "daily_2024_03_15")
        source_type: Type/category of source (e.g., "quarterly", "daily", "rss")
        date_range: Date range this fetch covers
        url: Optional URL for the fetch
        estimated_records: Estimated number of records
        metadata: Additional source-specific metadata
    """
    source_id: str
    source_type: SourceT
    date_range: DateRange
    url: str | None = None
    estimated_records: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"{self.source_type}:{self.source_id} ({self.date_range.start} to {self.date_range.end})"


@dataclass
class CollectionPlan(Generic[SourceT]):
    """An optimized plan for collecting data from multiple sources.
    
    Contains the breakdown of which sources to use for which date ranges,
    ordered by efficiency (bulk sources first, real-time last).
    
    Attributes:
        fetches: List of fetch operations, ordered by efficiency
        include_realtime: Whether to include real-time/streaming source
        target_range: The original requested date range
    """
    fetches: list[SourceFetch[SourceT]] = field(default_factory=list)
    include_realtime: bool = False
    target_range: DateRange | None = None
    
    @property
    def total_requests(self) -> int:
        """Total number of fetch operations."""
        count = len(self.fetches)
        if self.include_realtime:
            count += 1
        return count
    
    @property
    def estimated_records(self) -> int:
        """Total estimated records across all fetches."""
        return sum(f.estimated_records for f in self.fetches)
    
    def by_source_type(self, source_type: SourceT) -> list[SourceFetch[SourceT]]:
        """Get all fetches for a specific source type."""
        return [f for f in self.fetches if f.source_type == source_type]
    
    def iter_fetches(self) -> Iterator[SourceFetch[SourceT]]:
        """Iterate through fetches in execution order."""
        yield from self.fetches
    
    def summary(self) -> str:
        """Human-readable summary of the plan."""
        lines = ["📋 Collection Plan:"]
        
        # Group by source type
        by_type: dict[str, list[SourceFetch[SourceT]]] = {}
        for fetch in self.fetches:
            by_type.setdefault(fetch.source_type, []).append(fetch)
        
        for source_type, type_fetches in by_type.items():
            total_records = sum(f.estimated_records for f in type_fetches)
            lines.append(f"  📊 {source_type}: {len(type_fetches)} fetches (~{total_records:,} records)")
        
        if self.include_realtime:
            lines.append("  📡 Real-time: enabled")
        
        lines.append(f"  ─────────────────────────────")
        lines.append(f"  Total requests: ~{self.total_requests}")
        lines.append(f"  Estimated records: ~{self.estimated_records:,}")
        
        return "\n".join(lines)


@runtime_checkable
class CollectionStrategy(Protocol[SourceT]):
    """Protocol for collection strategies that optimize multi-source fetching.
    
    Implementations analyze the requested date range and determine the optimal
    mix of data sources to minimize requests while maximizing coverage.
    
    Example:
        >>> class MyStrategy:
        ...     def plan(
        ...         self,
        ...         *,
        ...         start_date: date | None = None,
        ...         end_date: date | None = None,
        ...         days: int | None = None,
        ...     ) -> CollectionPlan:
        ...         # Analyze range and return optimal plan
        ...         ...
    """
    
    def plan(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        days: int | None = None,
    ) -> CollectionPlan[SourceT]:
        """Create an optimized collection plan for the requested date range.
        
        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive, default: today)
            days: Alternative to start_date - number of days back from end_date
            
        Returns:
            CollectionPlan with optimized fetch operations
            
        Note:
            Either start_date or days should be provided.
            If neither is provided, implementation should use a sensible default.
        """
        ...


@runtime_checkable  
class IncrementalStrategy(Protocol[SourceT]):
    """Protocol for strategies that support incremental updates.
    
    Extends CollectionStrategy with support for efficient incremental syncs
    from a known last-sync point.
    """
    
    def plan_incremental(
        self,
        last_sync: date | datetime,
    ) -> CollectionPlan[SourceT]:
        """Plan an incremental sync from last sync point to now.
        
        Optimized for regular updates - typically uses only recent/real-time sources.
        
        Args:
            last_sync: Date/datetime of last successful sync
            
        Returns:
            CollectionPlan for incremental update
        """
        ...


class BaseCollectionStrategy(ABC, Generic[SourceT]):
    """Abstract base class for implementing collection strategies.
    
    Provides common utilities and enforces the protocol interface.
    Subclass this for domain-specific strategy implementations.
    
    Example:
        >>> from datetime import date, timedelta
        >>>
        >>> class MyStrategy(BaseCollectionStrategy[str]):
        ...     def _build_plan(
        ...         self,
        ...         start_date: date,
        ...         end_date: date,
        ...     ) -> CollectionPlan[str]:
        ...         plan = CollectionPlan(target_range=DateRange(start_date, end_date))
        ...         # Add fetches based on date analysis
        ...         return plan
    """
    
    def __init__(
        self,
        *,
        default_days: int = 7,
        enable_realtime: bool = True,
    ):
        """Initialize strategy.
        
        Args:
            default_days: Default number of days if no range specified
            enable_realtime: Whether to include real-time source in plans
        """
        self.default_days = default_days
        self.enable_realtime = enable_realtime
    
    def plan(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        days: int | None = None,
    ) -> CollectionPlan[SourceT]:
        """Create an optimized collection plan for the requested date range."""
        today = date.today()
        
        # Resolve date range
        if end_date is None:
            end_date = today
        
        if start_date is None:
            if days is not None:
                start_date = end_date - timedelta(days=days)
            else:
                start_date = end_date - timedelta(days=self.default_days)
        
        return self._build_plan(start_date, end_date)
    
    @abstractmethod
    def _build_plan(
        self,
        start_date: date,
        end_date: date,
    ) -> CollectionPlan[SourceT]:
        """Build the collection plan for a resolved date range.
        
        Subclasses must implement this with domain-specific logic.
        
        Args:
            start_date: Start of date range (resolved, not None)
            end_date: End of date range (resolved, not None)
            
        Returns:
            Optimized CollectionPlan for the date range
        """
        ...


# Convenience type aliases for common use cases
from datetime import timedelta  # noqa: E402 - import after class definitions


def date_range_days(days: int, end_date: date | None = None) -> DateRange:
    """Create a DateRange for the last N days.
    
    Args:
        days: Number of days back from end_date
        end_date: End of range (default: today)
        
    Returns:
        DateRange from (end_date - days) to end_date
    """
    if end_date is None:
        end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return DateRange(start=start_date, end=end_date)
