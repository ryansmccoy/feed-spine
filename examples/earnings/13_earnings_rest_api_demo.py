#!/usr/bin/env python3
"""
Earnings REST API Demo
======================

Demonstrates the REST API for earnings calendar:
- RESTful endpoints
- JSON responses
- CSV export
- Swagger docs

Run with:
    python 13_earnings_rest_api_demo.py
    
Then visit:
    http://localhost:8000/docs           - Swagger UI
    http://localhost:8000/v1/earnings/today
    http://localhost:8000/v1/earnings/check/META

This demo runs a real FastAPI server with mock data.

Requirements:
    pip install fastapi uvicorn
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from enum import Enum
from io import StringIO
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import StreamingResponse, JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    print("FastAPI not installed. Install with: pip install fastapi uvicorn")
    print("\nShowing API structure instead:\n")
    
    # Print the API structure as documentation
    api_docs = """
EARNINGS REST API STRUCTURE
===========================

Base URL: http://localhost:8000/v1/earnings

Endpoints:
----------

GET /v1/earnings/calendar/{date}
    Get earnings calendar for a specific date.
    Response: { "date": "...", "count": N, "events": [...] }

GET /v1/earnings/calendar/today
    Get today's earnings calendar.
    Query params: sector, status

GET /v1/earnings/check/{ticker}
    Quick beat/miss check for a ticker.
    Response: { "ticker": "AAPL", "beat": true, "surprise": 0.063, ... }

POST /v1/earnings/compare
    Compare estimates vs actuals.
    Body: { "ticker": "AAPL", "period": "2026:Q1" }
    Response: { "eps_surprise": 0.063, "revenue_surprise": 0.027, ... }

GET /v1/earnings/releases/recent
    Get recent releases (last N hours).
    Query params: hours (default: 24)

GET /v1/earnings/export/{date}.csv
    Download calendar as CSV.

GET /v1/earnings/export/{date}.json
    Download calendar as JSON file.

Example Responses:
------------------

GET /v1/earnings/check/META
{
    "ticker": "META",
    "found": true,
    "status": "RELEASED",
    "eps_estimate": 5.25,
    "eps_actual": 5.58,
    "surprise": 0.063,
    "direction": "BEAT",
    "beat": true,
    "miss": false,
    "links": {
        "ir": "https://investor.fb.com/",
        "press_release": "https://investor.fb.com/press-releases/"
    }
}

GET /v1/earnings/calendar/today?sector=Technology
{
    "date": "2026-01-30",
    "count": 4,
    "events": [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "report_date": "2026-01-30",
            "report_time": "AMC",
            "status": "SCHEDULED",
            "eps_estimate": 2.35,
            "links": { "ir": "https://investor.apple.com/" }
        },
        ...
    ]
}
"""
    print(api_docs)
    exit(0)


# =============================================================================
# MODELS
# =============================================================================


class ReportTime(str, Enum):
    BMO = "BMO"
    AMC = "AMC"
    UNKNOWN = "UNK"


class EventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    RELEASED = "RELEASED"
    DELAYED = "DELAYED"


class SurpriseDirection(str, Enum):
    BEAT = "BEAT"
    MISS = "MISS"
    INLINE = "INLINE"


class EventLinks(BaseModel):
    """Links associated with an earnings event."""
    ir: Optional[str] = None
    press_release: Optional[str] = None
    sec_filing: Optional[str] = None


class EarningsEventResponse(BaseModel):
    """API response for a single earnings event."""
    ticker: str
    company_name: str
    report_date: str
    report_time: ReportTime
    status: EventStatus
    sector: str = "Unknown"
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    eps_surprise: Optional[float] = None
    revenue_estimate_mm: Optional[float] = None
    revenue_actual_mm: Optional[float] = None
    revenue_surprise: Optional[float] = None
    links: EventLinks = EventLinks()


class CalendarResponse(BaseModel):
    """API response for calendar query."""
    date: str
    count: int
    events: list[EarningsEventResponse]


class CheckResponse(BaseModel):
    """API response for beat/miss check."""
    ticker: str
    found: bool
    status: Optional[EventStatus] = None
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    surprise: Optional[float] = None
    direction: Optional[SurpriseDirection] = None
    beat: bool = False
    miss: bool = False
    inline: bool = False
    links: EventLinks = EventLinks()


class CompareRequest(BaseModel):
    """Request body for compare endpoint."""
    ticker: str
    period: str = Field(default="2026:Q1", description="Period in format YYYY:QN")


class CompareResponse(BaseModel):
    """API response for comparison."""
    ticker: str
    period: str
    eps_estimate: float
    eps_actual: float
    eps_surprise: float
    revenue_estimate_mm: Optional[float] = None
    revenue_actual_mm: Optional[float] = None
    revenue_surprise: Optional[float] = None
    beat: bool
    miss: bool


# =============================================================================
# MOCK DATA
# =============================================================================


def _mock_events() -> list[EarningsEventResponse]:
    """Generate mock events."""
    events = [
        EarningsEventResponse(
            ticker="AAPL", company_name="Apple Inc.", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.SCHEDULED, sector="Technology",
            eps_estimate=2.35, revenue_estimate_mm=124500,
            links=EventLinks(ir="https://investor.apple.com/")
        ),
        EarningsEventResponse(
            ticker="META", company_name="Meta Platforms, Inc.", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.RELEASED, sector="Technology",
            eps_estimate=5.25, eps_actual=5.58, eps_surprise=0.063,
            revenue_estimate_mm=40100, revenue_actual_mm=41200, revenue_surprise=0.027,
            links=EventLinks(ir="https://investor.fb.com/", press_release="https://investor.fb.com/press-releases/")
        ),
        EarningsEventResponse(
            ticker="MSFT", company_name="Microsoft Corporation", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.SCHEDULED, sector="Technology",
            eps_estimate=2.78, revenue_estimate_mm=62800,
            links=EventLinks(ir="https://www.microsoft.com/investor/")
        ),
        EarningsEventResponse(
            ticker="NVDA", company_name="NVIDIA Corporation", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.RELEASED, sector="Technology",
            eps_estimate=4.12, eps_actual=4.65, eps_surprise=0.129,
            revenue_estimate_mm=28500, revenue_actual_mm=30800, revenue_surprise=0.081,
            links=EventLinks(ir="https://investor.nvidia.com/")
        ),
        EarningsEventResponse(
            ticker="JPM", company_name="JPMorgan Chase", report_date="2026-01-30",
            report_time=ReportTime.BMO, status=EventStatus.RELEASED, sector="Financial",
            eps_estimate=4.50, eps_actual=4.42, eps_surprise=-0.018,
            revenue_estimate_mm=42000, revenue_actual_mm=41500, revenue_surprise=-0.012,
            links=EventLinks(ir="https://www.jpmorganchase.com/ir/")
        ),
        EarningsEventResponse(
            ticker="TSLA", company_name="Tesla, Inc.", report_date="2026-01-30",
            report_time=ReportTime.AMC, status=EventStatus.SCHEDULED, sector="Consumer",
            eps_estimate=0.85, revenue_estimate_mm=25500,
            links=EventLinks(ir="https://ir.tesla.com/")
        ),
    ]
    return events


# =============================================================================
# FASTAPI APP
# =============================================================================


app = FastAPI(
    title="Earnings API",
    description="Earnings calendar and estimates vs actuals comparison",
    version="1.0.0",
)


@app.get("/")
async def root():
    """API root - show available endpoints."""
    return {
        "api": "Earnings API v1",
        "endpoints": {
            "calendar_today": "/v1/earnings/calendar/today",
            "calendar_date": "/v1/earnings/calendar/{date}",
            "check": "/v1/earnings/check/{ticker}",
            "compare": "POST /v1/earnings/compare",
            "recent": "/v1/earnings/releases/recent",
            "export_csv": "/v1/earnings/export/{date}.csv",
            "docs": "/docs",
        }
    }


@app.get("/v1/earnings/calendar/today", response_model=CalendarResponse)
async def calendar_today(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    status: Optional[EventStatus] = Query(None, description="Filter by status"),
):
    """Get today's earnings calendar."""
    date = datetime.now().strftime("%Y-%m-%d")
    events = _mock_events()
    
    if sector:
        events = [e for e in events if e.sector.lower() == sector.lower()]
    if status:
        events = [e for e in events if e.status == status]
    
    return CalendarResponse(date=date, count=len(events), events=events)


@app.get("/v1/earnings/calendar/{date}", response_model=CalendarResponse)
async def calendar_date(
    date: str,
    sector: Optional[str] = Query(None, description="Filter by sector"),
    status: Optional[EventStatus] = Query(None, description="Filter by status"),
):
    """Get earnings calendar for a specific date."""
    events = _mock_events()
    
    if sector:
        events = [e for e in events if e.sector.lower() == sector.lower()]
    if status:
        events = [e for e in events if e.status == status]
    
    return CalendarResponse(date=date, count=len(events), events=events)


@app.get("/v1/earnings/check/{ticker}", response_model=CheckResponse)
async def check_ticker(ticker: str):
    """
    Quick check if a ticker beat or missed earnings.
    
    Returns beat/miss status with surprise percentage.
    """
    events = _mock_events()
    event = next((e for e in events if e.ticker.upper() == ticker.upper()), None)
    
    if event is None:
        return CheckResponse(ticker=ticker.upper(), found=False)
    
    direction = None
    beat = miss = inline = False
    if event.eps_surprise is not None:
        if event.eps_surprise > 0.01:
            direction = SurpriseDirection.BEAT
            beat = True
        elif event.eps_surprise < -0.01:
            direction = SurpriseDirection.MISS
            miss = True
        else:
            direction = SurpriseDirection.INLINE
            inline = True
    
    return CheckResponse(
        ticker=event.ticker,
        found=True,
        status=event.status,
        eps_estimate=event.eps_estimate,
        eps_actual=event.eps_actual,
        surprise=event.eps_surprise,
        direction=direction,
        beat=beat,
        miss=miss,
        inline=inline,
        links=event.links,
    )


@app.post("/v1/earnings/compare", response_model=CompareResponse)
async def compare_earnings(request: CompareRequest):
    """
    Compare estimates vs actuals for a ticker.
    
    Returns detailed comparison including EPS and revenue surprises.
    """
    events = _mock_events()
    event = next(
        (e for e in events if e.ticker.upper() == request.ticker.upper() and e.status == EventStatus.RELEASED),
        None
    )
    
    if event is None:
        raise HTTPException(status_code=404, detail=f"No released earnings found for {request.ticker}")
    
    return CompareResponse(
        ticker=event.ticker,
        period=request.period,
        eps_estimate=event.eps_estimate or 0.0,
        eps_actual=event.eps_actual or 0.0,
        eps_surprise=event.eps_surprise or 0.0,
        revenue_estimate_mm=event.revenue_estimate_mm,
        revenue_actual_mm=event.revenue_actual_mm,
        revenue_surprise=event.revenue_surprise,
        beat=(event.eps_surprise or 0) > 0.01,
        miss=(event.eps_surprise or 0) < -0.01,
    )


@app.get("/v1/earnings/releases/recent")
async def recent_releases(
    hours: int = Query(24, description="Hours to look back")
):
    """Get recent earnings releases."""
    events = _mock_events()
    released = [e for e in events if e.status == EventStatus.RELEASED]
    return {
        "hours": hours,
        "count": len(released),
        "releases": released,
    }


@app.get("/v1/earnings/export/{date}.csv")
async def export_csv(date: str):
    """Export earnings calendar as CSV."""
    events = _mock_events()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ticker", "company", "date", "time", "status", "sector",
        "eps_estimate", "eps_actual", "eps_surprise",
        "revenue_estimate_mm", "revenue_actual_mm",
        "ir_url", "pr_url"
    ])
    
    for e in events:
        writer.writerow([
            e.ticker, e.company_name, e.report_date, e.report_time.value,
            e.status.value, e.sector,
            e.eps_estimate, e.eps_actual, e.eps_surprise,
            e.revenue_estimate_mm, e.revenue_actual_mm,
            e.links.ir, e.links.press_release
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=earnings_{date}.csv"}
    )


@app.get("/v1/earnings/export/{date}.json")
async def export_json(date: str):
    """Export earnings calendar as JSON file."""
    events = _mock_events()
    return JSONResponse(
        content={
            "date": date,
            "exported_at": datetime.now().isoformat(),
            "count": len(events),
            "events": [e.model_dump() for e in events],
        },
        headers={"Content-Disposition": f"attachment; filename=earnings_{date}.json"}
    )


# =============================================================================
# DEMO OUTPUT
# =============================================================================


def print_demo_info():
    """Print demo information."""
    print("=" * 70)
    print("  🌐 EARNINGS REST API DEMO")
    print("=" * 70)
    print("""
Starting FastAPI server...

Endpoints available:
    
    GET  /v1/earnings/calendar/today       Today's calendar
    GET  /v1/earnings/calendar/{date}      Calendar for date
    GET  /v1/earnings/check/{ticker}       Beat/miss check
    POST /v1/earnings/compare              Detailed comparison
    GET  /v1/earnings/releases/recent      Recent releases
    GET  /v1/earnings/export/{date}.csv    Export as CSV
    GET  /v1/earnings/export/{date}.json   Export as JSON

Try these:
    
    curl http://localhost:8000/v1/earnings/calendar/today
    curl http://localhost:8000/v1/earnings/check/META
    curl -X POST http://localhost:8000/v1/earnings/compare \\
         -H "Content-Type: application/json" \\
         -d '{"ticker": "NVDA", "period": "2026:Q1"}'

Interactive docs:
    http://localhost:8000/docs        (Swagger UI)
    http://localhost:8000/redoc       (ReDoc)

Press Ctrl+C to stop.
""")


# =============================================================================
# MAIN
# =============================================================================


if __name__ == "__main__":
    print_demo_info()
    uvicorn.run(app, host="0.0.0.0", port=8000)
