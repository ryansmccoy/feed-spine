"""FetchContext model for HTTP conditional fetching.

Tracks ETag, Last-Modified, and other HTTP caching state per endpoint
to support conditional fetching (If-None-Match, If-Modified-Since).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import Field, computed_field

from feedspine.models.base import FeedSpineModel


class FetchContext(FeedSpineModel):
    """HTTP caching state for a single endpoint.

    Stores ETag and Last-Modified values from HTTP responses to enable
    conditional fetching on subsequent requests. Also tracks fetch statistics
    for monitoring and health assessment.

    Attributes:
        endpoint_url: The URL being fetched.
        etag: ETag value from last response (for If-None-Match).
        last_modified: Last-Modified value from last response (for If-Modified-Since).
        last_fetch_at: When the last fetch attempt occurred.
        last_success_at: When the last successful (2xx) response was received.
        last_content_at: When we last received actual content (not 304).
        consecutive_failures: Count of consecutive failed fetches.
        total_fetches: Total fetch attempts for this endpoint.
        total_304s: Count of 304 Not Modified responses received.
        http_status: Status code from last response.
        content_hash: Hash of last received content (for local change detection).

    Example:
        >>> ctx = FetchContext(endpoint_url="https://example.com/feed.xml")
        >>> ctx.is_fresh
        False
        >>> ctx = ctx.update_from_response(etag='"v1"', status=200)
        >>> ctx.etag
        '"v1"'
    """

    endpoint_url: str = Field(..., description="The URL being fetched")
    etag: str | None = Field(default=None, description="ETag value from last response")
    last_modified: str | None = Field(default=None, description="Last-Modified header value")
    last_fetch_at: datetime | None = Field(default=None, description="When last fetch occurred")
    last_success_at: datetime | None = Field(default=None, description="When last success occurred")
    last_content_at: datetime | None = Field(default=None, description="When last content received")
    consecutive_failures: int = Field(default=0, description="Count of consecutive failures")
    total_fetches: int = Field(default=0, description="Total fetch attempts")
    total_304s: int = Field(default=0, description="Count of 304 responses")
    http_status: int | None = Field(default=None, description="Last HTTP status code")
    content_hash: str | None = Field(default=None, description="Hash of last content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> str:
        """Unique identifier based on URL hash.

        Example:
            >>> ctx = FetchContext(endpoint_url="https://example.com/feed")
            >>> len(ctx.id)
            16
        """
        return hashlib.sha256(self.endpoint_url.encode()).hexdigest()[:16]

    @property
    def is_fresh(self) -> bool:
        """Whether we have caching headers to use.

        Example:
            >>> ctx = FetchContext(endpoint_url="https://example.com/feed")
            >>> ctx.is_fresh
            False
            >>> ctx = ctx.update_from_response(etag='"v1"', status=200)
            >>> ctx.is_fresh
            True
        """
        return self.etag is not None or self.last_modified is not None

    @property
    def is_healthy(self) -> bool:
        """Whether the endpoint appears healthy (no recent failures).

        Example:
            >>> ctx = FetchContext(endpoint_url="https://example.com/feed")
            >>> ctx.is_healthy
            True
            >>> ctx = ctx.record_failure(status=500)
            >>> ctx.is_healthy
            True  # One failure is OK
            >>> for _ in range(5):
            ...     ctx = ctx.record_failure(status=500)
            >>> ctx.is_healthy
            False
        """
        return self.consecutive_failures < 5

    @property
    def cache_hit_rate(self) -> float:
        """Ratio of 304 responses to total fetches.

        Example:
            >>> ctx = FetchContext(
            ...     endpoint_url="https://example.com/feed",
            ...     total_fetches=100,
            ...     total_304s=80,
            ... )
            >>> ctx.cache_hit_rate
            0.8
        """
        if self.total_fetches == 0:
            return 0.0
        return self.total_304s / self.total_fetches

    def make_conditional_headers(self) -> dict[str, str]:
        """Create HTTP headers for conditional request.

        Returns headers dict with If-None-Match and/or If-Modified-Since
        if we have cached values. Empty dict if no cached state.

        Returns:
            Dictionary of HTTP headers for conditional fetching.

        Example:
            >>> ctx = FetchContext(
            ...     endpoint_url="https://example.com/feed",
            ...     etag='"abc123"',
            ...     last_modified="Sat, 01 Feb 2026 00:00:00 GMT",
            ... )
            >>> headers = ctx.make_conditional_headers()
            >>> headers["If-None-Match"]
            '"abc123"'
            >>> headers["If-Modified-Since"]
            'Sat, 01 Feb 2026 00:00:00 GMT'
        """
        headers: dict[str, str] = {}

        if self.etag:
            headers["If-None-Match"] = self.etag

        if self.last_modified:
            headers["If-Modified-Since"] = self.last_modified

        return headers

    def update_from_response(
        self,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        status: int,
        content_hash: str | None = None,
    ) -> FetchContext:
        """Create updated context from HTTP response.

        Call this after receiving an HTTP response to update caching state.
        Handles both successful responses (2xx) and 304 Not Modified.

        Args:
            etag: ETag header value from response (if present).
            last_modified: Last-Modified header value from response (if present).
            status: HTTP status code.
            content_hash: Hash of response content (for change detection).

        Returns:
            New FetchContext with updated state.

        Example:
            >>> ctx = FetchContext(endpoint_url="https://example.com/feed")
            >>> ctx = ctx.update_from_response(
            ...     etag='"v1"',
            ...     status=200,
            ...     content_hash="abc123",
            ... )
            >>> ctx.etag
            '"v1"'
            >>> ctx.http_status
            200
        """
        now = datetime.now(UTC)
        is_success = 200 <= status < 400
        is_304 = status == 304

        return self.model_copy(
            update={
                "etag": etag if etag else self.etag,
                "last_modified": last_modified if last_modified else self.last_modified,
                "last_fetch_at": now,
                "last_success_at": now if is_success else self.last_success_at,
                "last_content_at": now if (is_success and not is_304) else self.last_content_at,
                "consecutive_failures": 0 if is_success else self.consecutive_failures,
                "total_fetches": self.total_fetches + 1,
                "total_304s": self.total_304s + (1 if is_304 else 0),
                "http_status": status,
                "content_hash": content_hash if content_hash else self.content_hash,
            }
        )

    def record_failure(
        self,
        *,
        status: int | None = None,
        error: str | None = None,
    ) -> FetchContext:
        """Record a failed fetch attempt.

        Args:
            status: HTTP status code (if available).
            error: Error message (stored in metadata).

        Returns:
            New FetchContext with incremented failure count.

        Example:
            >>> ctx = FetchContext(endpoint_url="https://example.com/feed")
            >>> ctx = ctx.record_failure(status=500, error="Server Error")
            >>> ctx.consecutive_failures
            1
            >>> ctx.metadata.get("last_error")
            'Server Error'
        """
        now = datetime.now(UTC)
        metadata = {**self.metadata}

        if error:
            metadata["last_error"] = error
            metadata["last_error_at"] = now.isoformat()

        return self.model_copy(
            update={
                "last_fetch_at": now,
                "consecutive_failures": self.consecutive_failures + 1,
                "total_fetches": self.total_fetches + 1,
                "http_status": status,
                "metadata": metadata,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage.

        Returns:
            Dictionary representation suitable for JSON serialization.

        Example:
            >>> ctx = FetchContext(endpoint_url="https://example.com/feed")
            >>> d = ctx.to_dict()
            >>> d["endpoint_url"]
            'https://example.com/feed'
        """
        data = self.model_dump(mode="json")
        data["id"] = self.id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FetchContext:
        """Deserialize from dictionary.

        Args:
            data: Dictionary with FetchContext fields.

        Returns:
            New FetchContext instance.

        Example:
            >>> data = {"endpoint_url": "https://example.com/feed", "etag": '"v1"'}
            >>> ctx = FetchContext.from_dict(data)
            >>> ctx.etag
            '"v1"'
        """
        # Remove computed field if present
        data = {k: v for k, v in data.items() if k != "id"}
        return cls.model_validate(data)


__all__ = ["FetchContext"]
