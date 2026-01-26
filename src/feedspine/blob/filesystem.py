"""Filesystem blob storage implementation.

Provides local filesystem storage for binary files,
using content-addressed storage with configurable organization.

Example:
    >>> from feedspine.blob.filesystem import FilesystemBlob
    >>> blob = FilesystemBlob()
    >>> # FilesystemBlob implements BlobStorage protocol
    >>> hasattr(blob, 'put')
    True
    >>> hasattr(blob, 'get')
    True
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from feedspine.protocols.blob import BlobInfo


class FilesystemBlob:
    """Local filesystem blob storage.

    Stores files in a directory structure with content-based
    deduplication using SHA-256 hashes.

    Best for: Development, single-server deployments.

    Example:
        >>> import asyncio
        >>> import tempfile
        >>> from feedspine.blob.filesystem import FilesystemBlob
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     blob = FilesystemBlob(root=tmpdir)
        ...     asyncio.run(blob.initialize())
        ...     info = asyncio.run(blob.put("test.txt", b"hello world"))
        ...     info.size
        11
    """

    def __init__(
        self,
        root: str | Path = "./data/blobs",
        create_dirs: bool = True,
    ) -> None:
        """Initialize filesystem blob storage.

        Args:
            root: Root directory for blob storage.
            create_dirs: Create directories if they don't exist.
        """
        self._root = Path(root)
        self._create_dirs = create_dirs
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize blob storage, creating directories.

        Example:
            >>> import asyncio
            >>> import tempfile
            >>> from feedspine.blob.filesystem import FilesystemBlob
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     blob = FilesystemBlob(root=tmpdir)
            ...     asyncio.run(blob.initialize())
            ...     blob._initialized
            True
        """
        if self._create_dirs:
            self._root.mkdir(parents=True, exist_ok=True)
        self._initialized = True

    async def close(self) -> None:
        """Clean up resources (no-op for filesystem)."""
        self._initialized = False

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> BlobInfo:
        """Store a blob.

        Args:
            key: Blob key (used as path).
            data: Binary data to store.
            content_type: MIME type.
            metadata: Optional metadata (stored in .meta file).

        Returns:
            BlobInfo with storage details.

        Example:
            >>> import asyncio
            >>> import tempfile
            >>> from feedspine.blob.filesystem import FilesystemBlob
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     blob = FilesystemBlob(root=tmpdir)
            ...     asyncio.run(blob.initialize())
            ...     info = asyncio.run(blob.put("docs/file.txt", b"content"))
            ...     info.content_type
            'application/octet-stream'
        """
        path = self._key_to_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write data
        path.write_bytes(data)

        # Calculate hash
        etag = hashlib.sha256(data).hexdigest()

        # Store metadata if provided
        if metadata:
            meta_path = path.with_suffix(path.suffix + ".meta")
            meta_content = "\n".join(f"{k}={v}" for k, v in metadata.items())
            meta_path.write_text(meta_content)

        return BlobInfo(
            key=key,
            size=len(data),
            content_type=content_type,
            created_at=datetime.now(UTC).isoformat(),
            etag=etag,
            metadata=metadata,
        )

    async def get(self, key: str) -> bytes | None:
        """Get blob contents.

        Args:
            key: Blob key.

        Returns:
            Binary data or None if not found.

        Example:
            >>> import asyncio
            >>> import tempfile
            >>> from feedspine.blob.filesystem import FilesystemBlob
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     blob = FilesystemBlob(root=tmpdir)
            ...     asyncio.run(blob.initialize())
            ...     asyncio.run(blob.put("test", b"data"))  # doctest: +ELLIPSIS
            ...     asyncio.run(blob.get("test"))
            BlobInfo(...)
            b'data'
        """
        path = self._key_to_path(key)
        if not path.exists():
            return None
        return path.read_bytes()

    async def delete(self, key: str) -> bool:
        """Delete a blob.

        Args:
            key: Blob key.

        Returns:
            True if blob existed and was deleted.

        Example:
            >>> import asyncio
            >>> import tempfile
            >>> from feedspine.blob.filesystem import FilesystemBlob
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     blob = FilesystemBlob(root=tmpdir)
            ...     asyncio.run(blob.initialize())
            ...     asyncio.run(blob.put("del", b"x"))  # doctest: +ELLIPSIS
            ...     asyncio.run(blob.delete("del"))
            BlobInfo(...)
            True
        """
        path = self._key_to_path(key)
        if not path.exists():
            return False

        path.unlink()

        # Also delete metadata file if exists
        meta_path = path.with_suffix(path.suffix + ".meta")
        if meta_path.exists():
            meta_path.unlink()

        return True

    async def exists(self, key: str) -> bool:
        """Check if blob exists.

        Args:
            key: Blob key.

        Returns:
            True if blob exists.

        Example:
            >>> import asyncio
            >>> import tempfile
            >>> from feedspine.blob.filesystem import FilesystemBlob
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     blob = FilesystemBlob(root=tmpdir)
            ...     asyncio.run(blob.initialize())
            ...     asyncio.run(blob.exists("missing"))
            False
        """
        path = self._key_to_path(key)
        return path.exists()

    async def info(self, key: str) -> BlobInfo | None:
        """Get blob metadata.

        Args:
            key: Blob key.

        Returns:
            BlobInfo or None if not found.

        Example:
            >>> import asyncio
            >>> import tempfile
            >>> from feedspine.blob.filesystem import FilesystemBlob
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     blob = FilesystemBlob(root=tmpdir)
            ...     asyncio.run(blob.initialize())
            ...     asyncio.run(blob.put("info_test", b"abc"))  # doctest: +ELLIPSIS
            ...     info = asyncio.run(blob.info("info_test"))
            ...     info.size
            BlobInfo(...)
            3
        """
        path = self._key_to_path(key)
        if not path.exists():
            return None

        stat = path.stat()
        data = path.read_bytes()
        etag = hashlib.sha256(data).hexdigest()

        # Load metadata if exists
        metadata: dict[str, str] | None = None
        meta_path = path.with_suffix(path.suffix + ".meta")
        if meta_path.exists():
            metadata = {}
            for line in meta_path.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    metadata[k] = v

        return BlobInfo(
            key=key,
            size=stat.st_size,
            content_type=self._guess_content_type(key),
            created_at=datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat(),
            etag=etag,
            metadata=metadata,
        )

    async def list(self, prefix: str = "") -> AsyncIterator[BlobInfo]:
        """List blobs with optional prefix.

        Args:
            prefix: Filter by key prefix.

        Yields:
            BlobInfo for each matching blob.

        Example:
            >>> import asyncio
            >>> import tempfile
            >>> from feedspine.blob.filesystem import FilesystemBlob
            >>> async def list_example():
            ...     with tempfile.TemporaryDirectory() as tmpdir:
            ...         blob = FilesystemBlob(root=tmpdir)
            ...         await blob.initialize()
            ...         await blob.put("a/1.txt", b"1")
            ...         await blob.put("a/2.txt", b"2")
            ...         await blob.put("b/1.txt", b"3")
            ...         count = 0
            ...         async for info in blob.list("a/"):
            ...             count += 1
            ...         return count
            >>> asyncio.run(list_example())
            2
        """
        search_path = self._root / prefix if prefix else self._root

        if not search_path.exists():
            return

        # Find all files (not directories, not .meta files)
        if search_path.is_file():
            # Exact match
            if not str(search_path).endswith(".meta"):
                info = await self.info(prefix)
                if info:
                    yield info
        else:
            # Directory scan
            for path in search_path.rglob("*"):
                if path.is_file() and not str(path).endswith(".meta"):
                    key = str(path.relative_to(self._root)).replace(os.sep, "/")
                    if key.startswith(prefix):
                        info = await self.info(key)
                        if info:
                            yield info

    def _key_to_path(self, key: str) -> Path:
        """Convert key to filesystem path."""
        # Normalize path separators
        normalized = key.replace("/", os.sep)
        return self._root / normalized

    def _guess_content_type(self, key: str) -> str:
        """Guess content type from file extension."""
        ext = Path(key).suffix.lower()
        content_types = {
            ".txt": "text/plain",
            ".html": "text/html",
            ".htm": "text/html",
            ".json": "application/json",
            ".xml": "application/xml",
            ".pdf": "application/pdf",
            ".csv": "text/csv",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
        }
        return content_types.get(ext, "application/octet-stream")

    # --- Utility Methods ---

    def __len__(self) -> int:
        """Return approximate blob count (non-recursive check)."""
        if not self._root.exists():
            return 0
        return sum(1 for _ in self._root.rglob("*") if _.is_file() and not str(_).endswith(".meta"))
