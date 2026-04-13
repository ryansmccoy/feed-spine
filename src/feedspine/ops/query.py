"""Query operations — pure business logic.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`.  They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Export operations have been extracted to :mod:`feedspine.ops.export`.

Functions
---------
execute_search
    Run a full-text / keyword search.
fetch_records
    Retrieve stored records with layer filtering and pagination.
fetch_record_history
    Retrieve version history for a record by natural key.
fetch_sightings
    List sighting (observation) events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.ops import OperationContext, OperationResult


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


async def execute_search(
    ctx: OperationContext,
    query: str,
    search_type: str,
    limit: int = 10,
    offset: int = 0,
) -> OperationResult[dict[str, Any]]:
    """Run a search query against the configured search backend.

    Args:
        ctx: Operation context (must have ``search`` set).
        query: Search query string.
        search_type: One of ``keyword``, ``fulltext``.
        limit: Maximum results to return.
        offset: Number of results to skip.

    Returns:
        OperationResult with data containing ``query``, ``search_type``,
        ``total_count``, ``query_time_ms``, and ``results`` list.
    """
    from feedspine.ops import OperationResult
    from feedspine.protocols.search import SearchType as SearchTypeEnum

    type_map = {
        "keyword": SearchTypeEnum.KEYWORD,
        "fulltext": SearchTypeEnum.FULLTEXT,
    }
    resolved_type = type_map.get(search_type.lower())
    if resolved_type is None:
        return OperationResult.fail(f"Unknown search type: {search_type}. Valid types: {', '.join(type_map)}")

    if ctx.search is None:
        return OperationResult.fail("No search backend configured")

    response = await ctx.search.search(
        query,
        search_type=resolved_type,
        limit=limit,
        offset=offset,
    )

    data = {
        "query": query,
        "search_type": search_type,
        "total_count": response.total_count,
        "query_time_ms": response.query_time_ms,
        "results": [
            {
                "record_id": r.record_id,
                "score": r.score,
                "highlights": r.highlights,
                "metadata": r.metadata,
            }
            for r in response.results
        ],
    }
    return OperationResult.ok(data)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


async def fetch_records(
    ctx: OperationContext,
    layer: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> OperationResult[list[dict[str, Any]]]:
    """Fetch stored records with optional layer filtering and pagination.

    Args:
        ctx: Operation context with storage backend.
        layer: Optional layer filter (``bronze``, ``silver``, ``gold``).
        limit: Maximum records to return.
        offset: Number of records to skip.

    Returns:
        OperationResult with data containing a list of record dicts.
    """
    from feedspine.models.base import Layer as LayerEnum
    from feedspine.ops import OperationResult

    layer_filter = LayerEnum(layer) if layer else None
    records = []
    async for record in ctx.storage.query(layer=layer_filter, limit=limit, offset=offset):
        records.append(record)

    data = [r.model_dump(mode="json") for r in records]
    return OperationResult.ok(data, metadata={"offset": offset, "count": len(data)})


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


async def fetch_record_history(
    ctx: OperationContext,
    natural_key: str,
    limit: int = 20,
) -> OperationResult[list[dict[str, Any]]]:
    """Retrieve version history for a record.

    Requires a storage backend with SQLAlchemy session support.

    Args:
        ctx: Operation context with storage backend.
        natural_key: Natural key of the record.
        limit: Maximum versions to return.

    Returns:
        OperationResult with a list of version dicts.
    """
    from feedspine.ops import OperationResult

    if not (hasattr(ctx.storage, "session_factory") and ctx.storage.session_factory):
        return OperationResult.fail("Version history requires SQLAlchemy storage backend")

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from feedspine.storage.models import RecordVersionModel

    async with ctx.storage.session_factory() as session:
        session: AsyncSession
        stmt = (
            select(RecordVersionModel)
            .where(RecordVersionModel.record_key == natural_key)
            .order_by(RecordVersionModel.version.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        versions = result.scalars().all()

        if not versions:
            return OperationResult.ok([])

        version_dicts = [
            {
                "id": v.id,
                "record_key": v.record_key,
                "version": v.version,
                "content_hash": v.content_hash,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "source": v.source,
                "change_type": v.change_type,
                "change_reason": v.change_reason,
                "parent_version": v.parent_version,
            }
            for v in versions
        ]
        return OperationResult.ok(version_dicts)


# ---------------------------------------------------------------------------
# Sightings
# ---------------------------------------------------------------------------


async def fetch_sightings(
    ctx: OperationContext,
    natural_key: str | None = None,
    limit: int = 50,
    source: str | None = None,
) -> OperationResult[list[dict[str, Any]]]:
    """List record sightings (observation events).

    Requires a storage backend with SQLAlchemy session support.

    Args:
        ctx: Operation context with storage backend.
        natural_key: Optional filter by natural key.
        limit: Maximum sightings to return.
        source: Optional filter by source name.

    Returns:
        OperationResult with a list of sighting dicts.
    """
    from feedspine.ops import OperationResult

    if not (hasattr(ctx.storage, "session_factory") and ctx.storage.session_factory):
        return OperationResult.fail("Sightings list requires SQLAlchemy storage backend")

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from feedspine.storage.models import SightingModel

    async with ctx.storage.session_factory() as session:
        session: AsyncSession
        stmt = select(SightingModel).order_by(SightingModel.seen_at.desc()).limit(limit)

        if natural_key:
            stmt = stmt.where(SightingModel.natural_key == natural_key)
        if source:
            stmt = stmt.where(SightingModel.source == source)

        result = await session.execute(stmt)
        sightings = result.scalars().all()

        if not sightings:
            return OperationResult.ok([])

        sighting_dicts = [
            {
                "id": s.id,
                "natural_key": s.natural_key,
                "record_id": s.record_id,
                "source": s.source,
                "seen_at": s.seen_at.isoformat() if s.seen_at else None,
                "is_new": s.is_new,
                "raw_data_hash": s.raw_data_hash,
            }
            for s in sightings
        ]
        return OperationResult.ok(sighting_dicts)
