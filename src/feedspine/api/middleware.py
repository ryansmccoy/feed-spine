"""API authentication middleware.

Provides API key authentication for protected endpoints.
"""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.types import ASGIApp
    from starlette.responses import Response


# Endpoints that bypass authentication
PUBLIC_PATHS = frozenset(
    {
        "/",
        "/health",
        "/health/live",
        "/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
    }
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that validates X-API-Key header for protected endpoints.

    When authentication is required:
    - Requests to public endpoints (health, docs, metrics) are allowed
    - Other requests must include a valid X-API-Key header
    - Invalid or missing keys return 401/403 errors

    Usage:
        app.add_middleware(
            APIKeyMiddleware,
            api_key=os.environ["API_SECRET_KEY"],
            required=True,
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        api_key: str | None = None,
        required: bool = False,
    ) -> None:
        """Initialize middleware.

        Args:
            app: The ASGI application.
            api_key: The valid API key.
            required: Whether authentication is required.
        """
        super().__init__(app)
        self.api_key = api_key
        self.required = required

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and validate authentication."""
        # Check if path should bypass auth
        path = request.url.path.rstrip("/")
        if not path:
            path = "/"

        # Allow public endpoints
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # If auth not required, allow all
        if not self.required or not self.api_key:
            return await call_next(request)

        # Validate API key
        provided_key = request.headers.get("X-API-Key")

        if not provided_key:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Missing X-API-Key header",
                    "error": "authentication_required",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if not hmac.compare_digest(provided_key, self.api_key):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Invalid API key",
                    "error": "invalid_credentials",
                },
            )

        return await call_next(request)
