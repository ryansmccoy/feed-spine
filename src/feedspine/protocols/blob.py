"""Blob storage protocol.

Defines the interface for binary/blob storage backends (S3, GCS, local filesystem).

Example:
    >>> from feedspine.protocols.blob import BlobInfo
    >>> info = BlobInfo(
    ...     key="files/doc.pdf",
    ...     size=1024,
    ...     content_type="application/pdf",
    ...     created_at="2024-01-15T10:00:00Z",
    ... )
    >>> info.size
    1024
    >>> info.content_type
    'application/pdf'
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class BlobInfo:
    """Metadata about a stored blob.

    Example:
        >>> from feedspine.protocols.blob import BlobInfo
        >>> blob = BlobInfo(
        ...     key="data/file.json",
        ...     size=256,
        ...     content_type="application/json",
        ...     created_at="2024-01-01T00:00:00Z",
        ...     etag="abc123",
        ... )
        >>> blob.key
        'data/file.json'
        >>> blob.etag
        'abc123'
    """

    key: str
    size: int
    content_type: str
    created_at: str
    etag: str | None = None
    metadata: dict[str, str] | None = field(default=None)


@runtime_checkable
class BlobStorage(Protocol):
    """Blob storage protocol for binary files."""

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> BlobInfo:
        """Store a blob."""
        ...

    async def get(self, key: str) -> bytes | None:
        """Get blob contents."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete a blob."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if blob exists."""
        ...

    async def info(self, key: str) -> BlobInfo | None:
        """Get blob metadata."""
        ...

    async def list(self, prefix: str = "") -> AsyncIterator[BlobInfo]:
        """List blobs with optional prefix."""
        ...

    async def initialize(self) -> None:
        """Initialize blob storage."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
