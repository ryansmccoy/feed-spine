"""Capture-spine integration operations — pure business logic.

All functions accept an :class:`~feedspine.ops.OperationContext` and return
:class:`~feedspine.ops.OperationResult`. They are transport-agnostic:
no CLI, Rich, Typer, or FastAPI imports allowed here.

Functions
---------
check_capture_health
    Check capture-spine API health.
ingest_single
    Ingest a single observation to capture-spine.
ingest_batch
    Batch ingest feedspine records to capture-spine.
get_capture_status
    Query capture-spine API status.
build_ingest_payload
    Build capture-spine ingest payload from a record.
query_records_for_batch
    Query records from storage with filters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.ops import OperationContext, OperationResult


@dataclass
class IngestPayload:
    """Payload for capture-spine ingestion."""

    content_type: str
    source_type: str
    source_id: str
    title: str
    body: str
    fingerprint: str
    format: str = "text"
    generate_summary: bool = True
    extract_entities: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SingleIngestResult:
    """Result of a single ingest operation."""

    status: str  # "accepted", "duplicate", "failed"
    record_id: str | None = None
    sighting_id: str | None = None
    is_new: bool = False
    task_id: str | None = None
    error: str | None = None


@dataclass
class BatchIngestResult:
    """Result of a batch ingest operation."""

    total: int
    accepted: int
    duplicates: int
    failed: int
    results: list[dict[str, Any]]


@dataclass
class RecordQueryResult:
    """Result of querying records for batch ingestion."""

    records: list[Any]
    total: int


def is_capture_client_available() -> bool:
    """Check if capture-spine client is available (httpx installed)."""
    try:
        from feedspine.integration import CaptureSpineClient  # noqa: F401

        return True
    except ImportError:
        return False


async def check_capture_health(
    ctx: OperationContext,
    url: str | None = None,
) -> OperationResult[bool]:
    """Check capture-spine API health.

    Args:
        ctx: Operation context.
        url: Capture-spine API URL. Defaults to ``FEEDSPINE_CAPTURE_SPINE_URL``.

    Returns:
        OperationResult with True if healthy, False if not reachable.
    """
    from feedspine.core.config import get_settings
    from feedspine.ops import OperationResult

    if url is None:
        url = get_settings().capture_spine_url

    if not is_capture_client_available():
        return OperationResult.fail(
            "Capture-spine integration requires 'httpx' package. Install with: pip install httpx"
        )

    try:
        from feedspine.integration import CaptureSpineClient

        async with CaptureSpineClient(base_url=url) as client:
            is_healthy = await client.health_check()
            return OperationResult.ok(is_healthy, metadata={"url": url})
    except Exception as e:
        return OperationResult.fail(f"Connection error: {e}")


async def ingest_single(
    ctx: OperationContext,
    payload: IngestPayload,
    url: str | None = None,
) -> OperationResult[SingleIngestResult]:
    """Ingest a single observation to capture-spine.

    Args:
        ctx: Operation context.
        payload: Ingest payload with content details.
        url: Capture-spine API URL. Defaults to ``FEEDSPINE_CAPTURE_SPINE_URL``.

    Returns:
        OperationResult with SingleIngestResult.
    """
    from feedspine.core.config import get_settings
    from feedspine.ops import OperationResult

    if url is None:
        url = get_settings().capture_spine_url

    if not is_capture_client_available():
        return OperationResult.fail("Capture-spine integration requires 'httpx' package")

    try:
        from feedspine.integration import CaptureSpineClient

        async with CaptureSpineClient(base_url=url) as client:
            result = await client.ingest(
                content_type=payload.content_type,
                source_type=payload.source_type,
                source_id=payload.source_id,
                content={
                    "title": payload.title,
                    "body": payload.body,
                    "format": payload.format,
                },
                fingerprint=payload.fingerprint,
                generate_summary=payload.generate_summary,
                extract_entities=payload.extract_entities,
            )

            ingest_result = SingleIngestResult(
                status=result.status,
                record_id=result.record_id,
                sighting_id=result.sighting_id,
                is_new=result.is_new,
                task_id=result.task_id,
                error=result.error,
            )
            return OperationResult.ok(ingest_result)
    except Exception as e:
        return OperationResult.fail(f"Ingest failed: {e}")


def load_body_from_file(body: str) -> tuple[str, str | None]:
    """Load body content from file if @filepath syntax is used.

    Args:
        body: Body string, optionally prefixed with @ for file path.

    Returns:
        Tuple of (content, file_path or None).
    """
    if body.startswith("@"):
        file_path = Path(body[1:])
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return file_path.read_text(), str(file_path)
    return body, None


async def query_records_for_batch(
    ctx: OperationContext,
    feed_name: str | None = None,
    layer: str | None = None,
    limit: int = 100,
) -> OperationResult[RecordQueryResult]:
    """Query records from storage for batch ingestion.

    Args:
        ctx: Operation context with storage.
        feed_name: Optional feed name filter.
        layer: Optional layer filter (BRONZE, SILVER, GOLD).
        limit: Maximum records to query.

    Returns:
        OperationResult with RecordQueryResult.
    """
    from feedspine.models import Layer
    from feedspine.ops import OperationResult

    try:
        query_layer = Layer(layer.upper()) if layer else None

        records = []
        async for record in ctx.storage.query(layer=query_layer, limit=limit):
            # If feed_name is specified, filter by metadata
            if feed_name:
                record_feed = record.metadata.extra.get("feed_name", record.metadata.source)
                if record_feed != feed_name:
                    continue
            records.append(record)

        return OperationResult.ok(RecordQueryResult(records=records, total=len(records)))
    except Exception as e:
        return OperationResult.fail(f"Query failed: {e}")


def build_ingest_payload(
    record: Any,
    content_type: str = "feed_item",
) -> dict[str, Any]:
    """Build capture-spine ingest payload from a feedspine record.

    Args:
        record: Feedspine record object.
        content_type: Content type for the payload.

    Returns:
        Dict payload for capture-spine ingestion.
    """
    # Extract content fields
    content_title = record.metadata.extra.get("title", record.natural_key)
    content_body = ""

    # Try to extract body from content dict
    if isinstance(record.content, dict):
        content_body = (
            record.content.get("text")
            or record.content.get("body")
            or record.content.get("content")
            or json.dumps(record.content)
        )
    elif isinstance(record.content, str):
        content_body = record.content
    else:
        content_body = str(record.content)

    return {
        "content_type": content_type,
        "source_type": record.metadata.source_type or "feedspine",
        "source_id": record.natural_key,
        "content": {
            "title": content_title,
            "body": content_body,
            "format": record.metadata.extra.get("format", "text"),
        },
        "fingerprint": f"feedspine:{record.id}",
        "metadata": {
            "source": record.metadata.source,
            "source_type": record.metadata.source_type,
            **record.metadata.extra,
            "feedspine_layer": record.layer.value,
            "feedspine_id": record.id,
        },
        "timestamps": {
            "published_at": record.published_at.isoformat(),
            "captured_at": record.captured_at.isoformat(),
        },
    }


async def ingest_batch(
    ctx: OperationContext,
    records: list[Any],
    content_type: str = "feed_item",
    url: str | None = None,
    stop_on_error: bool = False,
) -> OperationResult[BatchIngestResult]:
    """Batch ingest feedspine records to capture-spine.

    Args:
        ctx: Operation context.
        records: List of feedspine records to ingest.
        content_type: Content type for all records.
        url: Capture-spine API URL. Defaults to ``FEEDSPINE_CAPTURE_SPINE_URL``.
        stop_on_error: Stop batch on first error.

    Returns:
        OperationResult with BatchIngestResult.
    """
    from feedspine.core.config import get_settings
    from feedspine.ops import OperationResult

    if url is None:
        url = get_settings().capture_spine_url

    if not is_capture_client_available():
        return OperationResult.fail("Capture-spine integration requires 'httpx' package")

    if not records:
        return OperationResult.ok(
            BatchIngestResult(
                total=0,
                accepted=0,
                duplicates=0,
                failed=0,
                results=[],
            )
        )

    try:
        from feedspine.integration import CaptureSpineClient

        # Build payloads
        payloads = [build_ingest_payload(record, content_type) for record in records]

        async with CaptureSpineClient(base_url=url) as client:
            result = await client.ingest_batch(payloads, stop_on_error=stop_on_error)

            batch_result = BatchIngestResult(
                total=result.total,
                accepted=result.accepted,
                duplicates=result.duplicates,
                failed=result.failed,
                results=[
                    {
                        "status": r.status,
                        "record_id": r.record_id,
                        "error": r.error,
                    }
                    for r in result.results
                ],
            )
            return OperationResult.ok(batch_result)
    except Exception as e:
        return OperationResult.fail(f"Batch ingest failed: {e}")


async def get_capture_status(
    ctx: OperationContext,
    url: str | None = None,
) -> OperationResult[dict[str, Any]]:
    """Query capture-spine API status.

    Args:
        ctx: Operation context.
        url: Capture-spine API URL. Defaults to ``FEEDSPINE_CAPTURE_SPINE_URL``.

    Returns:
        OperationResult with status dict containing url and health.
    """
    from feedspine.core.config import get_settings
    from feedspine.ops import OperationResult

    if url is None:
        url = get_settings().capture_spine_url

    if not is_capture_client_available():
        return OperationResult.fail("Capture-spine integration requires 'httpx' package")

    try:
        from feedspine.integration import CaptureSpineClient

        async with CaptureSpineClient(base_url=url) as client:
            is_healthy = await client.health_check()

            return OperationResult.ok(
                {
                    "url": url,
                    "healthy": is_healthy,
                }
            )
    except Exception as e:
        return OperationResult.fail(f"Status check failed: {e}")
