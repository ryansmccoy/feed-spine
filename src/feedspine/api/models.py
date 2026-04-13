"""Pydantic response models for the FeedSpine REST API.

Provides typed response schemas for all API endpoints, enabling:
- OpenAPI documentation auto-generation
- Response validation
- Client code generation
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Enrichment responses (enrich.py)
# =============================================================================


class EnrichmentStatsResponse(BaseModel):
    """Response for GET /api/v1/enrich/stats."""

    total_records: int
    by_layer: dict[str, int]
    enrichers_available: int


# =============================================================================
# Metrics responses (metrics.py)
# =============================================================================


class StorageStatsResponse(BaseModel):
    """Response for GET /api/v1/stats."""

    total_records: int
    by_layer: dict[str, int]


class MetricsJsonResponse(BaseModel):
    """Response for GET /api/v1/metrics/json."""

    total_records: int
    by_layer: dict[str, int]
    storage_backend: str
    search_enabled: bool


class FeedRunInfo(BaseModel):
    """A single feed run entry in feed stats."""

    feed_name: str
    started_at: str | None = None
    completed_at: str | None = None
    status: str
    fetched_count: int = 0
    new_count: int = 0
    error_count: int = 0
    duration_seconds: float | None = None


class FeedStatsResponse(BaseModel):
    """Response for GET /api/v1/stats/feeds."""

    feed_name: str | None = None
    runs: list[FeedRunInfo] = Field(default_factory=list)
    total_runs: int = 0
    error: str | None = None
    supported_backends: list[str] = Field(default_factory=list)


# =============================================================================
# Record responses (records.py)
# =============================================================================


class RecordCreate(BaseModel):
    """Request body for POST /api/v1/records."""

    natural_key: str = Field(..., min_length=1, max_length=1024, description="Unique natural key")
    layer: str = Field(default="bronze", description="Medallion layer: bronze, silver, gold")
    content: dict[str, Any] = Field(default_factory=dict, description="Record payload")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")
    source: str = Field(default="api", description="Source identifier")


class RecordUpdate(BaseModel):
    """Request body for PATCH /api/v1/records/{record_id}."""

    content: dict[str, Any] | None = Field(None, description="Updated content (merged)")
    metadata: dict[str, Any] | None = Field(None, description="Updated metadata (merged)")
    layer: str | None = Field(None, description="New layer")


class RecordResponse(BaseModel):
    """A single record returned by the API.

    Uses ``model_config`` to allow arbitrary fields since record content
    varies by feed.
    """

    model_config = {"extra": "allow"}

    id: str
    natural_key: str
    layer: str
    content: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class RecordVersionInfo(BaseModel):
    """Version metadata for a single record version."""

    version: int
    record_id: str
    natural_key: str
    layer: str
    captured_at: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    seen_count: int = 1


class RecordVersionsResponse(BaseModel):
    """Response for GET /api/v1/records/{record_id}/versions."""

    record_id: str
    current_version: int
    versions: list[RecordVersionInfo]
    total_versions: int
    note: str


# =============================================================================
# Search responses (search.py)
# =============================================================================


class SearchHit(BaseModel):
    """A single search result."""

    record_id: str
    score: float
    highlights: Any = None


class SearchResponse(BaseModel):
    """Response for GET /api/v1/search."""

    results: list[SearchHit]
    total_count: int
    query_time_ms: float


# =============================================================================
# Stats responses (stats.py)
# =============================================================================


class RecordStatsResponse(BaseModel):
    """Response for GET /api/v1/stats/records."""

    total: int
    by_layer: dict[str, int]


class ObservationStatsResponse(BaseModel):
    """Response for GET /api/v1/stats/observations."""

    total: int
    note: str | None = None


# =============================================================================
# Storage responses (storage.py)
# =============================================================================


class StorageHealthResponse(BaseModel):
    """Response for GET /api/v1/storage/health."""

    status: str
    backend: str
    record_count: int = 0
    error: str | None = None


# =============================================================================
# Timeline responses (timeline.py)
# =============================================================================


class FeedSourceInfo(BaseModel):
    """A single feed source entry."""

    name: str
    total_records: int = 0
    last_run_at: str | None = None
    status: str = "unknown"


class FeedSourcesResponse(BaseModel):
    """Response for GET /api/v1/feed/sources."""

    sources: list[FeedSourceInfo]
    count: int
    note: str | None = None


# =============================================================================
# Root / Health / Export status responses
# =============================================================================


class RootInfoResponse(BaseModel):
    """Response for GET / (API root)."""

    name: str
    version: str
    description: str


class HealthResponse(BaseModel):
    """Minimal health response (fallback when spine-core health router unavailable)."""

    status: str


class ExportFormatInfo(BaseModel):
    """Describes availability of a single export format."""

    available: bool
    description: str


class ExportStatusResponse(BaseModel):
    """Response for GET /api/v1/export/status."""

    backend: str
    formats: dict[str, ExportFormatInfo]
