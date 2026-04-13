"""MCP transport for feedspine — re-exports server entry points."""

from feedspine.transports.mcp.server import create_server, mcp, run

__all__ = ["create_server", "mcp", "run"]
