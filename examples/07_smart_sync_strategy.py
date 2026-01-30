#!/usr/bin/env python3
"""
FeedSpine Example 07: Smart Sync Strategy Pattern

This example demonstrates how to implement intelligent collection strategies
that minimize HTTP requests by choosing the optimal data source for each
portion of a date range.

Use Cases:
- SEC EDGAR: Quarterly > Monthly > Daily > RSS feeds
- News: Archive API > Recent API > Live WebSocket
- Social Media: Historical API > Search API > Streaming API
- E-Commerce: Bulk catalog > Delta updates > Real-time prices
- DevOps: Log archives > Recent logs > Live tail

The Strategy Pattern:
1. Analyze the requested date range
2. For each portion, calculate the "cost" of different sources
3. Choose the most efficient source that covers those dates
4. Return an optimized plan with minimal total requests

Run:
    python examples/07_smart_sync_strategy.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import IntEnum
from typing import Iterator, Literal

from feedspine.protocols import (
    BaseCollectionStrategy,
    CollectionPlan,
    DateRange,
    SourceFetch,
    SourcePriority,
)


# =============================================================================
# Generic Smart Sync Strategy
# =============================================================================

@dataclass
class SourceConfig:
    """Configuration for a data source.
    
    Attributes:
        name: Source identifier
        priority: Lower = more efficient (prefer for bulk)
        coverage_days: How many days one request covers
        estimated_records: Records per request
        min_days_threshold: Minimum days needed to use this source
        max_staleness_days: Source not available for recent N days
    """
    name: str
    priority: int
    coverage_days: int
    estimated_records: int
    min_days_threshold: int = 1
    max_staleness_days: int = 0  # 0 = available for today


class GenericSmartSyncStrategy:
    """Generic strategy that works with any domain's source configuration.
    
    Example:
        >>> # SEC EDGAR sources
        >>> sources = [
        ...     SourceConfig("quarterly", 1, 90, 100_000, min_days_threshold=60),
        ...     SourceConfig("monthly", 2, 30, 35_000, min_days_threshold=15, max_staleness_days=30),
        ...     SourceConfig("daily", 3, 1, 4_000, min_days_threshold=1),
        ...     SourceConfig("rss", 4, 1, 100, max_staleness_days=0),  # Real-time only
        ... ]
        >>> strategy = GenericSmartSyncStrategy(sources)
        >>> plan = strategy.plan(date(2024, 1, 1), date(2024, 6, 30))
    """
    
    def __init__(self, sources: list[SourceConfig]):
        """Initialize with source configurations, sorted by priority."""
        self.sources = sorted(sources, key=lambda s: s.priority)
        self.realtime_source = next(
            (s for s in self.sources if s.max_staleness_days == 0 and s.coverage_days == 1),
            None
        )
    
    def plan(
        self,
        start_date: date,
        end_date: date,
    ) -> list[tuple[str, date, date]]:
        """Create optimized plan for date range.
        
        Returns list of (source_name, start, end) tuples.
        """
        today = date.today()
        
        # Handle future dates
        if start_date > today:
            if self.realtime_source:
                return [(self.realtime_source.name, today, today)]
            return []
        
        # Clamp end to today
        effective_end = min(end_date, today)
        
        # Track uncovered ranges
        uncovered: list[tuple[date, date]] = [(start_date, effective_end)]
        plan: list[tuple[str, date, date]] = []
        
        # Try each source in priority order (most efficient first)
        for source in self.sources:
            if not uncovered:
                break
            
            new_uncovered = []
            
            for range_start, range_end in uncovered:
                # Check staleness constraint
                freshest_available = today - timedelta(days=source.max_staleness_days)
                if range_end > freshest_available and source.max_staleness_days > 0:
                    # This source can't cover recent dates
                    if range_start <= freshest_available:
                        # Partial coverage possible
                        covered = self._try_cover_range(
                            source, range_start, freshest_available, plan
                        )
                        if covered:
                            new_uncovered.append((covered + timedelta(days=1), range_end))
                        else:
                            new_uncovered.append((range_start, range_end))
                    else:
                        new_uncovered.append((range_start, range_end))
                    continue
                
                # Try to cover this range
                covered = self._try_cover_range(source, range_start, range_end, plan)
                if covered:
                    if covered < range_end:
                        new_uncovered.append((covered + timedelta(days=1), range_end))
                else:
                    new_uncovered.append((range_start, range_end))
            
            uncovered = new_uncovered
        
        # Any remaining uncovered goes to most granular source
        if uncovered and self.sources:
            finest = self.sources[-1]  # Lowest priority = most granular
            for start, end in uncovered:
                plan.append((finest.name, start, end))
        
        return sorted(plan, key=lambda x: x[1])  # Sort by start date
    
    def _try_cover_range(
        self,
        source: SourceConfig,
        start: date,
        end: date,
        plan: list[tuple[str, date, date]],
    ) -> date | None:
        """Try to cover a range with this source.
        
        Returns the last date covered, or None if source not applicable.
        """
        days_needed = (end - start).days + 1
        
        # Check minimum threshold
        if days_needed < source.min_days_threshold:
            return None
        
        # For sources with fixed coverage periods (e.g., quarterly, monthly)
        # we need to align to period boundaries
        if source.coverage_days >= 30:
            return self._cover_with_periods(source, start, end, plan)
        else:
            # Granular source - just cover the range
            plan.append((source.name, start, end))
            return end
    
    def _cover_with_periods(
        self,
        source: SourceConfig,
        start: date,
        end: date,
        plan: list[tuple[str, date, date]],
    ) -> date | None:
        """Cover range with period-based source (quarterly, monthly)."""
        covered_end = None
        current = start
        
        while current <= end:
            # Determine period boundaries
            if source.coverage_days >= 90:
                # Quarterly
                q = (current.month - 1) // 3
                period_start = date(current.year, q * 3 + 1, 1)
                if q == 3:
                    period_end = date(current.year + 1, 1, 1) - timedelta(days=1)
                else:
                    period_end = date(current.year, (q + 1) * 3 + 1, 1) - timedelta(days=1)
            else:
                # Monthly
                period_start = date(current.year, current.month, 1)
                if current.month == 12:
                    period_end = date(current.year + 1, 1, 1) - timedelta(days=1)
                else:
                    period_end = date(current.year, current.month + 1, 1) - timedelta(days=1)
            
            # Calculate overlap
            overlap_start = max(start, period_start)
            overlap_end = min(end, period_end)
            overlap_days = (overlap_end - overlap_start).days + 1
            
            # Only use if we need enough days from this period
            if overlap_days >= source.min_days_threshold:
                plan.append((source.name, period_start, period_end))
                covered_end = period_end
            
            # Move to next period
            current = period_end + timedelta(days=1)
        
        return covered_end


# =============================================================================
# Domain-Specific Examples
# =============================================================================

def create_sec_edgar_strategy() -> GenericSmartSyncStrategy:
    """Create strategy for SEC EDGAR feeds."""
    return GenericSmartSyncStrategy([
        SourceConfig("quarterly", 1, 90, 100_000, min_days_threshold=60),
        SourceConfig("monthly", 2, 30, 35_000, min_days_threshold=15, max_staleness_days=30),
        SourceConfig("daily", 3, 1, 4_000, min_days_threshold=1),
        SourceConfig("rss", 4, 1, 100, max_staleness_days=0),
    ])


def create_news_strategy() -> GenericSmartSyncStrategy:
    """Create strategy for news aggregation.
    
    Archive API: Historical data, bulk access
    Recent API: Last 30 days, rate limited
    Live: WebSocket or polling, real-time
    """
    return GenericSmartSyncStrategy([
        SourceConfig("archive", 1, 30, 50_000, min_days_threshold=15, max_staleness_days=7),
        SourceConfig("recent", 2, 1, 5_000, min_days_threshold=1, max_staleness_days=0),
        SourceConfig("live", 3, 1, 100, max_staleness_days=0),
    ])


def create_ecommerce_strategy() -> GenericSmartSyncStrategy:
    """Create strategy for e-commerce price monitoring.
    
    Catalog dump: Nightly full export
    Delta: Hourly changes
    Real-time: Price alerts
    """
    return GenericSmartSyncStrategy([
        SourceConfig("catalog", 1, 1, 1_000_000, min_days_threshold=1, max_staleness_days=1),
        SourceConfig("delta", 2, 1, 10_000, min_days_threshold=1, max_staleness_days=0),
        SourceConfig("realtime", 3, 1, 100, max_staleness_days=0),
    ])


def create_social_media_strategy() -> GenericSmartSyncStrategy:
    """Create strategy for social media intelligence.
    
    Historical: Full archive access (expensive)
    Search: Last 7 days, rate limited
    Stream: Real-time firehose
    """
    return GenericSmartSyncStrategy([
        SourceConfig("historical", 1, 30, 100_000, min_days_threshold=7, max_staleness_days=0),
        SourceConfig("search", 2, 1, 10_000, min_days_threshold=1, max_staleness_days=0),
        SourceConfig("stream", 3, 1, 1_000, max_staleness_days=0),
    ])


# =============================================================================
# Demo
# =============================================================================

def demo_strategy(name: str, strategy: GenericSmartSyncStrategy, start: date, end: date) -> None:
    """Run and display a strategy plan."""
    print(f"\n{'='*60}")
    print(f"{name}: {start} to {end}")
    print('='*60)
    
    plan = strategy.plan(start, end)
    
    if not plan:
        print("  (empty plan)")
        return
    
    # Group by source
    by_source: dict[str, list[tuple[date, date]]] = {}
    for source, s, e in plan:
        by_source.setdefault(source, []).append((s, e))
    
    total_requests = 0
    for source, ranges in sorted(by_source.items()):
        count = len(ranges)
        total_requests += count
        if count == 1:
            s, e = ranges[0]
            days = (e - s).days + 1
            print(f"  {source}: {s} to {e} ({days} days)")
        else:
            print(f"  {source}: {count} fetches")
            for s, e in ranges[:3]:
                days = (e - s).days + 1
                print(f"    - {s} to {e} ({days} days)")
            if len(ranges) > 3:
                print(f"    - ... and {len(ranges) - 3} more")
    
    print(f"  {'-'*30}")
    print(f"  Total requests: {total_requests}")


def main() -> None:
    """Demonstrate smart sync strategies across domains."""
    print("\n" + "="*60)
    print(" SMART SYNC STRATEGY EXAMPLES")
    print("="*60)
    
    today = date.today()
    
    # SEC EDGAR Examples
    print("\n" + "="*60)
    print(" SEC EDGAR STRATEGY")
    print("="*60)
    sec = create_sec_edgar_strategy()
    
    demo_strategy(
        "3-Year Backfill",
        sec,
        date(2023, 1, 1),
        today,
    )
    
    demo_strategy(
        "Mid-Year Range (Mar-Dec 2023)",
        sec,
        date(2023, 3, 1),
        date(2023, 12, 31),
    )
    
    demo_strategy(
        "Last 30 Days",
        sec,
        today - timedelta(days=30),
        today,
    )
    
    # News Examples
    print("\n" + "="*60)
    print(" NEWS AGGREGATION STRATEGY")
    print("="*60)
    news = create_news_strategy()
    
    demo_strategy(
        "Last 60 Days of News",
        news,
        today - timedelta(days=60),
        today,
    )
    
    demo_strategy(
        "Last Week",
        news,
        today - timedelta(days=7),
        today,
    )
    
    # E-Commerce Examples
    print("\n" + "="*60)
    print(" E-COMMERCE PRICE MONITORING")
    print("="*60)
    ecom = create_ecommerce_strategy()
    
    demo_strategy(
        "Today's Prices",
        ecom,
        today,
        today,
    )
    
    demo_strategy(
        "Last 3 Days",
        ecom,
        today - timedelta(days=3),
        today,
    )
    
    # Summary
    print("\n" + "="*60)
    print(" STRATEGY PATTERN BENEFITS")
    print("="*60)
    print("""
    1. EFFICIENCY: Choose optimal source for each date range
    2. FLEXIBILITY: Different domains, same pattern
    3. TESTABILITY: Pure functions, easy to unit test
    4. OBSERVABILITY: Plan is inspectable before execution
    5. COST CONTROL: Minimize expensive API calls
    
    The key insight: Data sources have different trade-offs:
    - Bulk sources: Efficient but stale
    - Recent sources: Fresh but expensive  
    - Real-time: Freshest but most expensive
    
    Smart strategies balance these trade-offs automatically!
    """)


if __name__ == "__main__":
    main()
