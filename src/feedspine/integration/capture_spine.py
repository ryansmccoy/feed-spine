"""Capture-Spine integration client.

Provides a generic client for posting observations to the capture-spine
Content Ingestion API.

Example:
    >>> from feedspine.integration import CaptureSpineClient
    >>>
    >>> async with CaptureSpineClient("http://localhost:8000") as client:
    ...     result = await client.ingest(
    ...         content_type="sec_filing",
    ...         source_type="sec_edgar",
    ...         source_id="0000320193-25-000106",
    ...         content={"title": "AAPL 10-K", "body": "...", "format": "html"},
    ...         fingerprint="sec:0000320193:10-K:2025-11-01",
    ...     )
    ...     if result.is_new:
    ...         print(f"Created record: {result.record_id}")

API Reference:
    See capture-spine/docs/features/productivity/content-ingestion-api.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from feedspine._vendor.logging import get_logger

logger = get_logger(__name__)

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None


@dataclass
class IngestResult:
    """Result of an ingestion request.

    Attributes:
        status: "accepted", "duplicate", "updated", or "failed"
        record_id: UUID of the created/matched record
        sighting_id: UUID of the new sighting
        is_new: Whether this was a new record
        task_id: Celery task ID for async processing
        error: Error message if failed
    """

    status: Literal["accepted", "duplicate", "updated", "failed"]
    record_id: str | None = None
    sighting_id: str | None = None
    is_new: bool = False
    task_id: str | None = None
    error: str | None = None

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> IngestResult:
        """Create from API response JSON."""
        processing = data.get("processing", {})

        return cls(
            status=data.get("status", "failed"),
            record_id=data.get("record_id"),
            sighting_id=data.get("sighting_id"),
            is_new=data.get("is_new", False),
            task_id=processing.get("task_id"),
        )

    @classmethod
    def failure(cls, error: str) -> IngestResult:
        """Create a failure result."""
        return cls(status="failed", error=error)


@dataclass
class BatchIngestResult:
    """Result of a batch ingestion request.

    Attributes:
        total: Total items submitted
        accepted: Number of items accepted
        duplicates: Number of duplicate items
        failed: Number of failed items
        results: Individual results for each item
    """

    total: int = 0
    accepted: int = 0
    duplicates: int = 0
    failed: int = 0
    results: list[IngestResult] = field(default_factory=list)


class CaptureSpineClient:
    """Client for capture-spine Content Ingestion API.

    This client provides methods to POST observations to capture-spine's
    /api/v1/ingest endpoint, with support for:

    - Any content type (SEC filings, earnings, market data, etc.)
    - Batch ingestion
    - Deduplication via fingerprints

    Example:
        >>> async with CaptureSpineClient("http://localhost:8000") as client:
        ...     result = await client.ingest(
        ...         content_type="sec_filing",
        ...         source_type="sec_edgar",
        ...         source_id="0000320193-25-000106",
        ...         content={"title": "AAPL 10-K", "body": "...", "format": "html"},
        ...         fingerprint="sec:0000320193:10-K:2025-11-01",
        ...     )
        ...     results = await client.ingest_batch(payloads)

    Args:
        base_url: Base URL of capture-spine API (e.g., "http://localhost:8000")
        api_key: Optional API key for authentication
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for CaptureSpineClient. Install with: pip install httpx")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> CaptureSpineClient:
        """Enter async context manager."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def ingest(
        self,
        *,
        content_type: str,
        source_type: str,
        source_id: str,
        content: dict[str, Any],
        fingerprint: str,
        source_metadata: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        timestamps: dict[str, str] | None = None,
        generate_summary: bool = True,
        extract_todos: bool = False,
        extract_entities: bool = True,
        update_if_exists: bool = True,
    ) -> IngestResult:
        """Ingest a single observation.

        Args:
            content_type: Type of content (e.g., "sec_filing", "earnings_event")
            source_type: Source system (e.g., "sec_edgar", "polygon")
            source_id: Unique ID within source system
            content: Content payload with title, body, format keys
            fingerprint: Unique fingerprint for deduplication
            source_metadata: Additional source metadata
            metadata: Additional metadata
            timestamps: Optional created_at/published_at ISO strings
            generate_summary: Whether to generate LLM summary
            extract_todos: Whether to extract TODOs
            extract_entities: Whether to extract entities
            update_if_exists: Whether to update if duplicate found

        Returns:
            IngestResult with status and record IDs

        Example:
            >>> result = await client.ingest(
            ...     content_type="earnings_event",
            ...     source_type="polygon",
            ...     source_id="AAPL:2026-01-30",
            ...     content={"title": "AAPL Q1 2026", "body": "...", "format": "text"},
            ...     fingerprint="earnings:AAPL:2026-01-30",
            ... )
        """
        payload: dict[str, Any] = {
            "content_type": content_type,
            "source": {
                "type": source_type,
                "identifier": source_id,
                "metadata": source_metadata or {},
            },
            "content": content,
            "metadata": metadata or {},
            "processing": {
                "generate_summary": generate_summary,
                "extract_todos": extract_todos,
                "extract_entities": extract_entities,
            },
            "deduplication": {
                "unique_id": fingerprint,
                "update_if_exists": update_if_exists,
            },
        }

        if timestamps:
            payload["timestamps"] = timestamps

        return await self._post_ingest(payload)

    async def ingest_batch(
        self,
        payloads: list[dict[str, Any]],
        *,
        stop_on_error: bool = False,
    ) -> BatchIngestResult:
        """Ingest multiple observations in batch.

        Each payload dict should match the kwargs of ``ingest()``.

        Args:
            payloads: List of dicts with keys matching ingest() parameters
            stop_on_error: Whether to stop on first error

        Returns:
            BatchIngestResult with aggregate stats

        Example:
            >>> results = await client.ingest_batch([
            ...     {"content_type": "sec_filing", "source_type": "sec_edgar", ...},
            ...     {"content_type": "earnings_event", "source_type": "polygon", ...},
            ... ])
            >>> print(f"Accepted: {results.accepted}/{results.total}")
        """
        result = BatchIngestResult(total=len(payloads))

        for payload in payloads:
            try:
                item_result = await self.ingest(**payload)
                result.results.append(item_result)

                if item_result.status == "accepted":
                    result.accepted += 1
                elif item_result.status == "duplicate":
                    result.duplicates += 1
                elif item_result.status == "failed":
                    result.failed += 1
                    if stop_on_error:
                        break

            except Exception as e:
                result.failed += 1
                result.results.append(IngestResult.failure(str(e)))
                if stop_on_error:
                    break

        return result

    async def _post_ingest(self, payload: dict[str, Any]) -> IngestResult:
        """POST to the ingest endpoint.

        Args:
            payload: Request payload dict

        Returns:
            IngestResult from response
        """
        client = await self._ensure_client()

        try:
            response = await client.post("/api/v1/ingest", json=payload)

            if response.status_code == 200:
                return IngestResult.from_response(response.json())
            elif response.status_code == 201:
                data = response.json()
                data["is_new"] = True
                return IngestResult.from_response(data)
            elif response.status_code == 409:
                # Duplicate
                data = response.json()
                data["status"] = "duplicate"
                return IngestResult.from_response(data)
            else:
                return IngestResult.failure(f"HTTP {response.status_code}: {response.text}")

        except httpx.TimeoutException:
            return IngestResult.failure("Request timed out")
        except httpx.RequestError as e:
            return IngestResult.failure(f"Request error: {e}")

    async def health_check(self) -> bool:
        """Check if capture-spine API is healthy.

        Returns:
            True if API is reachable and healthy
        """
        client = await self._ensure_client()

        try:
            response = await client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.debug("CaptureSpine health check failed: %s", e)
            return False
