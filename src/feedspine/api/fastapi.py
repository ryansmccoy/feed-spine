"""FastAPI integration for FeedSpine.

Provides a REST API for FeedSpine with:
- Record CRUD operations
- Search endpoints
- Collection triggers
- Statistics and health checks
- Feed management
- Run history
- Sightings and observations
- OpenAPI documentation

Example:
    >>> from feedspine.api.fastapi import create_app
    >>> from feedspine.storage.memory import MemoryStorage
    >>> from feedspine.search.memory import MemorySearch
    >>>
    >>> storage = MemoryStorage()
    >>> search = MemorySearch()
    >>> app = create_app(storage=storage, search=search)
    >>>
    >>> # Run with: uvicorn feedspine.api.fastapi:app

Note:
    Requires the `api` optional dependency:
    ``pip install feedspine[api]``
"""

from __future__ import annotations

from typing import Any

from spine.core.logging import get_logger

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as e:
    raise ImportError("FastAPI is required for the API module. Install with: pip install feedspine[api]") from e

from feedspine.api.route_registry import include_all_routers
from feedspine.core.config import get_settings
from feedspine.protocols.search import SearchBackend
from feedspine.protocols.storage import StorageBackend

logger = get_logger(__name__)


async def _seed_demo_data_if_empty(storage: StorageBackend) -> None:
    """Seed demo feed configs if storage supports it and tables are empty.

    Called at startup so the API has sample data on first run.
    No-op for backends that don't support feed-config operations (e.g. MemoryStorage).
    """
    if not hasattr(storage, "store_feed_config") or not hasattr(storage, "list_feed_configs"):
        return

    try:
        existing = await storage.list_feed_configs()
        if existing:
            return  # already has data

        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        demo_feeds = [
            {
                "id": "feed-sec-press",
                "name": "SEC Press Releases",
                "adapter_type": "rss",
                "url": "https://www.sec.gov/news/pressreleases.rss",
                "enabled": True,
                "config": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "feed-sec-speeches",
                "name": "SEC Speeches",
                "adapter_type": "rss",
                "url": "https://www.sec.gov/news/speeches.rss",
                "enabled": True,
                "config": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "feed-sec-filings",
                "name": "SEC EDGAR Filings",
                "adapter_type": "sec_edgar",
                "url": "https://efts.sec.gov/LATEST/search-index?q=%22annual%20report%22",
                "enabled": True,
                "config": {"filing_types": ["10-K", "10-Q"]},
                "created_at": now,
                "updated_at": now,
            },
        ]
        for feed in demo_feeds:
            await storage.store_feed_config(feed)
        logger.info("Seeded %d demo feed configs", len(demo_feeds))
    except Exception as exc:
        logger.warning("Failed to seed demo data: %s", exc)


def _configure_cors(app: FastAPI, cors_origins: list[str] | None) -> None:
    """Set up CORS middleware on *app*."""
    _default_origins = [
        "http://localhost:3010",
        "http://localhost:5173",
        "http://127.0.0.1:3010",
        "http://127.0.0.1:5173",
    ]
    if cors_origins is None:
        settings = get_settings()
        cors_origins = settings.cors_origins_list if settings.cors_origins else _default_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _configure_auth(app: FastAPI) -> None:
    """Add API-key auth middleware if settings require it."""
    from feedspine.api.middleware import APIKeyMiddleware

    settings = get_settings()
    if settings.require_auth and settings.api_key:
        app.add_middleware(
            APIKeyMiddleware,
            api_key=settings.api_key,
            required=True,
        )
        logger.info("API authentication enabled")


def _attach_health(app: FastAPI, search: SearchBackend | None, version: str) -> None:
    """Attach health-check endpoints (spine-core or inline fallback)."""
    try:
        from spine.infra.health import HealthCheck, create_health_router

        checks: list[HealthCheck] = []

        async def _check_db() -> bool:
            await app.state.storage.count()
            return True

        checks.append(HealthCheck(name="database", check_fn=_check_db))

        if search is not None:

            async def _check_search() -> bool:
                await app.state.search.count()
                return True

            checks.append(HealthCheck(name="search", check_fn=_check_search, required=False))

        app.include_router(create_health_router(service_name="feedspine", version=version, checks=checks))
    except ImportError:
        from feedspine.api.models import HealthResponse

        @app.get("/health", response_model=HealthResponse)
        async def health() -> dict[str, str]:
            return {"status": "healthy"}


def create_app(
    storage: StorageBackend,
    search: SearchBackend | None = None,
    title: str = "FeedSpine API",
    version: str = "0.1.0",
    description: str = "Storage-agnostic feed capture framework API",
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create a FastAPI application for FeedSpine.

    Args:
        storage: Storage backend instance.
        search: Optional search backend instance.
        title: API title for OpenAPI docs.
        version: API version.
        description: API description for docs.
        cors_origins: Allowed CORS origins. Defaults to env var FEEDSPINE_CORS_ORIGINS
            (comma-separated) or common localhost origins.

    Returns:
        Configured FastAPI application.

    Example:
        >>> from feedspine.api.fastapi import create_app
        >>> from feedspine.storage.memory import MemoryStorage
        >>> storage = MemoryStorage()
        >>> app = create_app(storage=storage)
        >>> app.title
        'FeedSpine API'
    """
    app = FastAPI(
        title=title,
        version=version,
        description=description,
    )

    _configure_cors(app, cors_origins)
    _configure_auth(app)

    # ── Telemetry sink (vendor-neutral observability) ────────────────
    try:
        from spine.observability.factory import TelemetrySettings, make_telemetry_sink

        _ts = TelemetrySettings.from_env()
        _ts.service_name = "feed-spine"
        app.state.telemetry = make_telemetry_sink(_ts)
    except ImportError:
        app.state.telemetry = None

    # ── Webhook router (mountable factory) ────────────────────────────
    try:
        from uuid import uuid4

        from fastapi import Request
        from spine.api.routers.webhook_factory import make_webhook_router
        from spine.runtime.requests import CallableRequest  # noqa: TC002 — guarded by try/except
        from spine.runtime.webhook_registry import MemoryWebhookRegistry, WebhookRegistration
        from spine.runtime.webhook_submitter import WebhookResult

        _webhook_registry = MemoryWebhookRegistry()

        class _FeedWebhookSubmitter:
            """Adapts StorageBackend to WebhookSubmitter protocol for webhook dispatch."""

            def __init__(self, storage: StorageBackend, search: SearchBackend | None) -> None:
                self._storage = storage
                self._search = search

            async def submit(self, request: CallableRequest) -> WebhookResult:
                """Route webhook to the appropriate feed-spine operation."""
                handler = request.handler or ""
                params = request.envelope.params if request.envelope else {}

                if handler == "feed.ingest":
                    record = params.get("record")
                    if record is None:
                        raise RuntimeError("feed.ingest requires a 'record' param")
                    await self._storage.store(record)
                    if self._search is not None:
                        try:
                            await self._search.index(record)
                        except Exception:
                            logger.warning(
                                "webhook: search index failed for feed.ingest",
                                exc_info=True,
                            )
                elif handler == "feed.checkpoint":
                    count = await self._storage.count()
                    return WebhookResult(execution_id=f"checkpoint:{count}")
                else:
                    raise RuntimeError(f"Unknown feed webhook handler: {handler!r}")

                return WebhookResult(execution_id=str(uuid4()))

        def _get_feed_webhook_submitter(request: Request) -> _FeedWebhookSubmitter | None:
            """FastAPI dependency: returns the feed webhook submitter adapter."""
            storage = getattr(request.app.state, "storage", None)
            if storage is None:
                return None
            search = getattr(request.app.state, "search", None)
            return _FeedWebhookSubmitter(storage, search)

        # Register feed-spine webhook targets
        for _target in ("feed.ingest", "feed.checkpoint"):
            _webhook_registry.put(WebhookRegistration(name=_target, kind="operation"))
            logger.info("webhook.registered name=%s", _target)

        _wh_router = make_webhook_router(
            registry=_webhook_registry,
            engine_dep=_get_feed_webhook_submitter,
        )
        app.include_router(_wh_router, prefix="/webhooks", tags=["webhooks"])
    except ImportError:
        logger.debug("spine.api.routers.webhook_factory not available - webhook router disabled")

    # Store backends in app state
    app.state.storage = storage
    app.state.search = search

    # Export registry for two-phase export endpoints
    from feedspine.api.routes.export import ExportRegistry

    app.state.export_registry = ExportRegistry()

    # Include routers (centralised in route_registry)
    include_all_routers(app)

    # =========================================================================
    # Lifecycle Events
    # =========================================================================

    @app.on_event("startup")
    async def startup() -> None:
        """Initialize backends on startup."""
        await app.state.storage.initialize()
        if app.state.search:
            await app.state.search.initialize()
        await _seed_demo_data_if_empty(app.state.storage)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        """Clean up backends on shutdown."""
        if app.state.telemetry is not None:
            app.state.telemetry.emit_event("app.stopped", {"service": "feed-spine"})
        await app.state.storage.close()
        if app.state.search:
            await app.state.search.close()

    # =========================================================================
    # Info endpoint
    # =========================================================================

    from feedspine.api.models import RootInfoResponse

    @app.get("/", response_model=RootInfoResponse)
    async def root() -> dict[str, Any]:
        """API root with basic info."""
        return {"name": title, "version": version, "description": description}

    _attach_health(app, search, version)

    return app


# Default app instance for uvicorn
# Usage: uvicorn feedspine.api.fastapi:app
# Note: This requires setting up storage/search externally
def _create_default_app() -> FastAPI:
    """Create app with backends configured from environment.

    Environment variables:
        FEEDSPINE_STORAGE: Storage backend type (memory|sqlite|duckdb|postgresql).
            Defaults to 'memory'.
        FEEDSPINE_STORAGE_CONNECTION: Connection string for database backends.
            Defaults to in-memory for the chosen backend.
        FEEDSPINE_CORS_ORIGINS: Comma-separated allowed CORS origins.
            Defaults to localhost dev origins.
    """
    settings = get_settings()
    storage_type = settings.storage.lower()

    if storage_type == "memory":
        from feedspine.storage.memory import MemoryStorage

        storage: StorageBackend = MemoryStorage()
    else:
        from feedspine.storage.factory import create_storage

        storage = create_storage(storage_type=storage_type, connection_string=settings.storage_connection)

    search: SearchBackend | None = None
    try:
        from feedspine.search.memory import MemorySearch

        search = MemorySearch()
    except Exception as e:
        logger.debug("Search backend not available: %s", e)

    return create_app(
        storage=storage,
        search=search,
    )


app = _create_default_app()
