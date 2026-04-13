"""Integration modules for external systems.

This package provides clients for integrating FeedSpine observations
with external systems like capture-spine.

Example:
    >>> from feedspine.integration import CaptureSpineClient
    >>> client = CaptureSpineClient(base_url="http://localhost:8000")
    >>> result = await client.ingest(
    ...     content_type="sec_filing",
    ...     source_type="sec_edgar",
    ...     source_id="0000320193-25-000106",
    ...     content={"title": "AAPL 10-K", "body": "...", "format": "html"},
    ...     fingerprint="sec:0000320193:10-K:2025-11-01",
    ... )
"""

from feedspine.integration.capture_spine import CaptureSpineClient, IngestResult

__all__ = [
    "CaptureSpineClient",
    "IngestResult",
]
