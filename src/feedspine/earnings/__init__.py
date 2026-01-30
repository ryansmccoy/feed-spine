"""
Earnings Domain - Professional API for earnings calendar and estimates vs actuals.

This module provides the main public API for earnings operations:
- EarningsCalendarService: Full-featured service with all customization
- Convenience functions: fetch_calendar(), watch_releases()
- Models: CalendarEvent, CalendarResult, SurpriseResult

Architecture:
- Follows spine-core Pipeline/Workflow patterns
- Integrates with EntitySpine for entity resolution
- Uses FeedSpine observation storage
- Connectors for SEC, Finnhub, and other sources

Quick Start:
    from feedspine.earnings import fetch_calendar, watch_releases
    from datetime import date
    
    # Fetch today's calendar
    result = await fetch_calendar(date.today())
    
    # With customization
    result = await fetch_calendar(
        date(2026, 1, 30),
        sources=["sec", "finnhub"],
        tickers=["AAPL", "MSFT"],
        include_estimates=True,
    )
    
    # Watch for releases
    async for event in watch_releases(tickers=["AAPL"]):
        print(f"🔔 {event.ticker} released!")

Full Service API:
    from feedspine.earnings import EarningsCalendarService
    
    service = EarningsCalendarService(
        connectors=[...],  # Custom connectors
        cache_ttl_minutes=30,
    )
    
    # All methods with full parameter customization
    result = await service.fetch_calendar(...)
    result = await service.compute_surprise(...)
    async for event in service.watch_releases(...):
        ...
"""

from feedspine.earnings.service import (
    # Service
    EarningsCalendarService,
    get_service,
    
    # Convenience functions
    fetch_calendar,
    watch_releases,
    
    # Models
    CalendarEvent,
    CalendarResult,
    SurpriseResult,
    StoreResult,
    EventLinks,
    
    # Enums
    EventStatus,
    ReportTime,
    SurpriseDirection,
    
    # Base classes (for custom connectors)
    BaseConnector,
)

__all__ = [
    # Service
    "EarningsCalendarService",
    "get_service",
    
    # Convenience functions
    "fetch_calendar",
    "watch_releases",
    
    # Models
    "CalendarEvent",
    "CalendarResult",
    "SurpriseResult",
    "StoreResult",
    "EventLinks",
    
    # Enums
    "EventStatus",
    "ReportTime",
    "SurpriseDirection",
    
    # Base classes
    "BaseConnector",
]
