#!/usr/bin/env python3
"""
FeedSpine API Authentication Example

Demonstrates the API key authentication middleware:
- Configuring API key authentication
- Making authenticated requests
- Public vs protected endpoints
- Environment variable configuration

Authentication is optional and controlled by environment variables:
- FEEDSPINE_REQUIRE_AUTH=true  (enable authentication)
- FEEDSPINE_API_KEY=your-key   (the required API key)

Usage:
    python examples/04_operations/10_api_authentication.py
"""

from __future__ import annotations

import os


def main() -> None:
    """Demonstrate API authentication configuration."""
    print("=" * 60)
    print("FeedSpine API Authentication Example")
    print("=" * 60)
    print()

    # -------------------------------------------------------------------------
    # 1. Environment Configuration
    # -------------------------------------------------------------------------
    print("1. Environment variable configuration...")
    print()
    print("   To enable API authentication, set these variables:")
    print()
    print("   # In .env file or environment:")
    print("   FEEDSPINE_REQUIRE_AUTH=true")
    print("   FEEDSPINE_API_KEY=your-secure-api-key-here")
    print()

    # Show current configuration
    require_auth = os.environ.get("FEEDSPINE_REQUIRE_AUTH", "false")
    api_key = os.environ.get("FEEDSPINE_API_KEY", "")

    print("   Current configuration:")
    print(f"   FEEDSPINE_REQUIRE_AUTH = {require_auth}")
    print(f"   FEEDSPINE_API_KEY = {'[SET]' if api_key else '[NOT SET]'}")
    print()

    # -------------------------------------------------------------------------
    # 2. Public Endpoints (No Auth Required)
    # -------------------------------------------------------------------------
    print("2. Public endpoints (no authentication required)...")
    print()
    print("   These endpoints are always accessible:")
    print("   - GET  /health          Health check")
    print("   - GET  /health/live     Liveness probe")
    print("   - GET  /health/ready    Readiness probe")
    print("   - GET  /docs            OpenAPI documentation")
    print("   - GET  /redoc           ReDoc documentation")
    print("   - GET  /openapi.json    OpenAPI schema")
    print()

    # -------------------------------------------------------------------------
    # 3. Protected Endpoints
    # -------------------------------------------------------------------------
    print("3. Protected endpoints (require X-API-Key header)...")
    print()
    print("   When FEEDSPINE_REQUIRE_AUTH=true, these need authentication:")
    print("   - GET  /api/v1/records         List records")
    print("   - POST /api/v1/collect         Trigger collection")
    print("   - GET  /api/v1/stats/summary   Get statistics")
    print("   - POST /api/v1/export/parquet  Export data")
    print("   - ...and all other /api/v1/* endpoints")
    print()

    # -------------------------------------------------------------------------
    # 4. Making Authenticated Requests
    # -------------------------------------------------------------------------
    print("4. Making authenticated requests...")
    print()
    print("   Using curl:")
    print('   curl -H "X-API-Key: your-api-key" http://localhost:8300/api/v1/records')
    print()
    print("   Using Python requests:")
    print("   import requests")
    print("   headers = {'X-API-Key': 'your-api-key'}")
    print("   response = requests.get('http://localhost:8300/api/v1/records', headers=headers)")
    print()
    print("   Using httpx:")
    print("   import httpx")
    print("   client = httpx.Client(headers={'X-API-Key': 'your-api-key'})")
    print("   response = client.get('http://localhost:8300/api/v1/records')")
    print()

    # -------------------------------------------------------------------------
    # 5. Error Responses
    # -------------------------------------------------------------------------
    print("5. Authentication error responses...")
    print()
    print("   401 Unauthorized - Missing API key:")
    print('   {"detail": "X-API-Key header required"}')
    print()
    print("   403 Forbidden - Invalid API key:")
    print('   {"detail": "Invalid API key"}')
    print()

    # -------------------------------------------------------------------------
    # 6. Docker Configuration
    # -------------------------------------------------------------------------
    print("6. Docker configuration...")
    print()
    print("   In docker-compose.yml:")
    print("   services:")
    print("     api:")
    print("       environment:")
    print('         FEEDSPINE_REQUIRE_AUTH: "true"')
    print('         FEEDSPINE_API_KEY: "${FEEDSPINE_API_KEY}"')
    print()
    print("   Then set FEEDSPINE_API_KEY in your shell or .env file")
    print()

    # -------------------------------------------------------------------------
    # 7. Best Practices
    # -------------------------------------------------------------------------
    print("7. Security best practices...")
    print()
    print("   - Use a strong, random API key (32+ characters)")
    print("   - Never commit API keys to version control")
    print("   - Rotate keys periodically")
    print("   - Use HTTPS in production")
    print("   - Consider rate limiting for additional protection")
    print()

    print("=" * 60)
    print("API authentication example complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
