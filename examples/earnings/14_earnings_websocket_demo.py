#!/usr/bin/env python3
"""
Earnings WebSocket Demo
=======================

Demonstrates real-time earnings alerts via WebSocket:
- Subscribe to release notifications
- Filter by ticker, sector, or market cap
- Receive instant alerts when earnings drop

Run server:
    python 14_earnings_websocket_demo.py server
    
Run client (in another terminal):
    python 14_earnings_websocket_demo.py client

Or use wscat:
    wscat -c ws://localhost:8000/v1/ws/earnings

Requirements:
    pip install fastapi uvicorn websockets
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from enum import Enum
from typing import Optional, Set
from dataclasses import dataclass, field

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from pydantic import BaseModel
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


# =============================================================================
# MODELS
# =============================================================================


class SurpriseDirection(str, Enum):
    BEAT = "BEAT"
    MISS = "MISS"
    INLINE = "INLINE"


@dataclass
class EarningsRelease:
    """An earnings release event."""
    ticker: str
    company_name: str
    eps_estimate: float
    eps_actual: float
    eps_surprise: float
    direction: SurpriseDirection
    revenue_surprise: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "type": "release",
            "ticker": self.ticker,
            "company_name": self.company_name,
            "eps_estimate": self.eps_estimate,
            "eps_actual": self.eps_actual,
            "eps_surprise": self.eps_surprise,
            "direction": self.direction.value,
            "revenue_surprise": self.revenue_surprise,
            "timestamp": self.timestamp,
        }


# =============================================================================
# CONNECTION MANAGER
# =============================================================================


class ConnectionManager:
    """Manage WebSocket connections and subscriptions."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.subscriptions: dict[WebSocket, dict] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = {"tickers": None, "min_surprise": None}
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to earnings stream. Send 'subscribe' to start receiving alerts.",
            "available_commands": {
                "subscribe": {"channel": "releases", "filters": {"tickers": ["AAPL"], "min_surprise": 0.05}},
                "unsubscribe": {},
                "ping": {},
            }
        })
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
    
    def update_subscription(self, websocket: WebSocket, filters: dict):
        self.subscriptions[websocket] = filters
    
    async def broadcast(self, release: EarningsRelease):
        """Broadcast release to all matching subscribers."""
        for connection in self.active_connections:
            filters = self.subscriptions.get(connection, {})
            
            # Check ticker filter
            tickers = filters.get("tickers")
            if tickers and release.ticker not in tickers:
                continue
            
            # Check minimum surprise filter
            min_surprise = filters.get("min_surprise")
            if min_surprise and abs(release.eps_surprise) < min_surprise:
                continue
            
            try:
                await connection.send_json(release.to_dict())
            except Exception:
                pass


manager = ConnectionManager()


# =============================================================================
# SIMULATED RELEASE STREAM
# =============================================================================


async def simulate_releases():
    """Simulate earnings releases arriving in real-time."""
    releases = [
        EarningsRelease(
            ticker="META", company_name="Meta Platforms", 
            eps_estimate=5.25, eps_actual=5.58, eps_surprise=0.063,
            direction=SurpriseDirection.BEAT, revenue_surprise=0.027
        ),
        EarningsRelease(
            ticker="NVDA", company_name="NVIDIA Corporation",
            eps_estimate=4.12, eps_actual=4.65, eps_surprise=0.129,
            direction=SurpriseDirection.BEAT, revenue_surprise=0.081
        ),
        EarningsRelease(
            ticker="JPM", company_name="JPMorgan Chase",
            eps_estimate=4.50, eps_actual=4.42, eps_surprise=-0.018,
            direction=SurpriseDirection.MISS, revenue_surprise=-0.012
        ),
        EarningsRelease(
            ticker="MSFT", company_name="Microsoft Corporation",
            eps_estimate=2.78, eps_actual=2.95, eps_surprise=0.061,
            direction=SurpriseDirection.BEAT, revenue_surprise=0.033
        ),
        EarningsRelease(
            ticker="AAPL", company_name="Apple Inc.",
            eps_estimate=2.35, eps_actual=2.42, eps_surprise=0.030,
            direction=SurpriseDirection.BEAT, revenue_surprise=0.015
        ),
    ]
    
    # Send releases with delays to simulate real-time
    for release in releases:
        await asyncio.sleep(5)  # 5 seconds between releases
        release.timestamp = datetime.now().isoformat()
        await manager.broadcast(release)


# =============================================================================
# WEBSOCKET SERVER (FastAPI)
# =============================================================================


if HAS_FASTAPI:
    app = FastAPI(title="Earnings WebSocket Demo")
    
    @app.get("/")
    async def root():
        return {"message": "Earnings WebSocket Server", "ws_endpoint": "/v1/ws/earnings"}
    
    @app.websocket("/v1/ws/earnings")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "subscribe":
                    filters = data.get("filters", {})
                    manager.update_subscription(websocket, filters)
                    await websocket.send_json({
                        "type": "subscribed",
                        "filters": filters,
                        "message": "Subscribed to earnings releases"
                    })
                
                elif action == "unsubscribe":
                    manager.update_subscription(websocket, {})
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "message": "Unsubscribed from earnings releases"
                    })
                
                elif action == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })
                    
        except WebSocketDisconnect:
            manager.disconnect(websocket)
    
    @app.on_event("startup")
    async def startup_event():
        # Start simulating releases in the background
        asyncio.create_task(simulate_releases())


# =============================================================================
# WEBSOCKET CLIENT
# =============================================================================


async def run_client():
    """Run a demo WebSocket client."""
    if not HAS_WEBSOCKETS:
        print("websockets not installed. Install with: pip install websockets")
        return
    
    print("=" * 60)
    print("  📡 EARNINGS WEBSOCKET CLIENT")
    print("=" * 60)
    print("\nConnecting to ws://localhost:8000/v1/ws/earnings...")
    
    try:
        async with websockets.connect("ws://localhost:8000/v1/ws/earnings") as websocket:
            # Receive connection message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✅ {data.get('message', 'Connected')}\n")
            
            # Subscribe to all releases
            print("📬 Subscribing to releases...")
            await websocket.send(json.dumps({
                "action": "subscribe",
                "filters": {}  # No filters = all releases
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✅ {data.get('message', 'Subscribed')}\n")
            
            print("👀 Watching for earnings releases...")
            print("   (Press Ctrl+C to stop)\n")
            print("-" * 60)
            
            # Listen for releases
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                if data.get("type") == "release":
                    ticker = data["ticker"]
                    company = data["company_name"]
                    direction = data["direction"]
                    surprise = data["eps_surprise"]
                    actual = data["eps_actual"]
                    estimate = data["eps_estimate"]
                    
                    symbol = "✅" if direction == "BEAT" else "❌" if direction == "MISS" else "➡️"
                    
                    print(f"\n🔔 EARNINGS ALERT [{datetime.now().strftime('%H:%M:%S')}]")
                    print(f"   {ticker} - {company}")
                    print(f"   {symbol} {direction}: ${actual:.2f} vs ${estimate:.2f} ({surprise:+.1%})")
                    
    except ConnectionRefusedError:
        print("❌ Could not connect. Make sure the server is running:")
        print("   python 14_earnings_websocket_demo.py server")
    except KeyboardInterrupt:
        print("\n\n👋 Client stopped.")


# =============================================================================
# MAIN
# =============================================================================


def print_server_info():
    print("=" * 60)
    print("  🌐 EARNINGS WEBSOCKET SERVER")
    print("=" * 60)
    print("""
Starting WebSocket server...

Connect with:
    
    # Python client
    python 14_earnings_websocket_demo.py client
    
    # wscat
    wscat -c ws://localhost:8000/v1/ws/earnings
    
    # JavaScript
    const ws = new WebSocket("ws://localhost:8000/v1/ws/earnings");
    ws.onmessage = (e) => console.log(JSON.parse(e.data));
    ws.send(JSON.stringify({action: "subscribe", filters: {}}));

Protocol:
    
    → Send:  {"action": "subscribe", "filters": {"tickers": ["AAPL"]}}
    ← Recv:  {"type": "subscribed", "message": "..."}
    ← Recv:  {"type": "release", "ticker": "AAPL", "direction": "BEAT", ...}

Simulated releases will arrive every 5 seconds.
Press Ctrl+C to stop.
""")


def main():
    if len(sys.argv) < 2:
        print("Usage: python 14_earnings_websocket_demo.py [server|client]")
        print()
        print("  server  - Start WebSocket server on ws://localhost:8000/v1/ws/earnings")
        print("  client  - Connect to server and display releases")
        return
    
    mode = sys.argv[1].lower()
    
    if mode == "server":
        if not HAS_FASTAPI:
            print("FastAPI not installed. Install with: pip install fastapi uvicorn")
            return
        print_server_info()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    
    elif mode == "client":
        asyncio.run(run_client())
    
    else:
        print(f"Unknown mode: {mode}")
        print("Use 'server' or 'client'")


if __name__ == "__main__":
    main()
