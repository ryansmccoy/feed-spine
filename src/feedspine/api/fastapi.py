"""FastAPI integration for FeedSpine.

Provides a REST API for FeedSpine with:
- Record CRUD operations
- Search endpoints
- Collection triggers
- Statistics and health checks
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

try:
    from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
except ImportError as e:
    raise ImportError(
        "FastAPI is required for the API module. Install with: pip install feedspine[api]"
    ) from e

from feedspine.models.base import Layer
from feedspine.protocols.search import SearchBackend, SearchType
from feedspine.protocols.storage import StorageBackend


def create_app(
    storage: StorageBackend,
    search: SearchBackend | None = None,
    title: str = "FeedSpine API",
    version: str = "0.1.0",
    description: str = "Storage-agnostic feed capture framework API",
) -> FastAPI:
    """Create a FastAPI application for FeedSpine.

    Args:
        storage: Storage backend instance.
        search: Optional search backend instance.
        title: API title for OpenAPI docs.
        version: API version.
        description: API description for docs.

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

    # Store backends in app state
    app.state.storage = storage
    app.state.search = search

    # =========================================================================
    # Lifecycle Events
    # =========================================================================

    @app.on_event("startup")
    async def startup() -> None:
        """Initialize backends on startup."""
        await app.state.storage.initialize()
        if app.state.search:
            await app.state.search.initialize()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        """Clean up backends on shutdown."""
        await app.state.storage.close()
        if app.state.search:
            await app.state.search.close()

    # =========================================================================
    # Health & Info Endpoints
    # =========================================================================

    @app.get("/")
    async def root() -> dict[str, Any]:
        """API root with basic info."""
        return {
            "name": title,
            "version": version,
            "description": description,
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    # =========================================================================
    # Records Endpoints
    # =========================================================================

    @app.get("/api/v1/records")
    async def list_records(
        layer: str | None = Query(None, description="Filter by layer"),
        limit: int = Query(100, le=1000, description="Max records to return"),
        offset: int = Query(0, ge=0, description="Skip records"),
    ) -> list[dict[str, Any]]:
        """List records with optional filtering."""
        layer_filter = Layer(layer) if layer else None

        records = []
        async for record in app.state.storage.query(
            layer=layer_filter,
            limit=limit,
            offset=offset,
        ):
            records.append(record.model_dump(mode="json"))

        return records

    @app.get("/api/v1/records/{record_id}")
    async def get_record(record_id: str) -> dict[str, Any]:
        """Get a record by ID."""
        record = await app.state.storage.get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        result: dict[str, Any] = record.model_dump(mode="json")
        return result

    @app.get("/api/v1/records/by-key/{natural_key:path}")
    async def get_record_by_key(natural_key: str) -> dict[str, Any]:
        """Get a record by natural key."""
        record = await app.state.storage.get_by_natural_key(natural_key)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        result: dict[str, Any] = record.model_dump(mode="json")
        return result

    # =========================================================================
    # Search Endpoints
    # =========================================================================

    @app.get("/api/v1/search")
    async def search_records(
        q: str = Query(..., description="Search query"),
        limit: int = Query(10, le=100, description="Max results"),
        offset: int = Query(0, ge=0, description="Skip results"),
    ) -> dict[str, Any]:
        """Search indexed records."""
        if not app.state.search:
            raise HTTPException(
                status_code=501,
                detail="Search not configured",
            )

        response = await app.state.search.search(
            query=q,
            search_type=SearchType.FULLTEXT,
            limit=limit,
            offset=offset,
        )

        return {
            "results": [
                {
                    "record_id": r.record_id,
                    "score": r.score,
                    "highlights": r.highlights,
                }
                for r in response.results
            ],
            "total_count": response.total_count,
            "query_time_ms": response.query_time_ms,
        }

    # =========================================================================
    # Statistics Endpoints
    # =========================================================================

    @app.get("/api/v1/stats")
    async def get_stats() -> dict[str, Any]:
        """Get storage statistics."""
        total = await app.state.storage.count()

        # Count per layer
        layer_counts = {}
        for layer in Layer:
            count = await app.state.storage.count(layer=layer)
            layer_counts[layer.value] = count

        return {
            "total_records": total,
            "by_layer": layer_counts,
        }

    # =========================================================================
    # Collection Endpoints
    # =========================================================================

    @app.post("/api/v1/collect", status_code=202)
    async def trigger_collection(
        background_tasks: BackgroundTasks,
    ) -> dict[str, str]:
        """Trigger feed collection in background.

        Returns immediately with 202 Accepted.
        Collection runs asynchronously.
        """
        # In a real implementation, this would trigger FeedSpine collection
        # For now, we just return that collection was started
        # background_tasks.add_task(run_collection)

        return {"status": "collection_started"}

    return app


# Default app instance for uvicorn
# Usage: uvicorn feedspine.api.fastapi:app
# Note: This requires setting up storage/search externally
def _create_default_app() -> FastAPI:
    """Create app with memory backends for development."""
    from feedspine.search.memory import MemorySearch
    from feedspine.storage.memory import MemoryStorage

    return create_app(
        storage=MemoryStorage(),
        search=MemorySearch(),
    )


app = _create_default_app()
