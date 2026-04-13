"""Tests for FilesystemBlob implementation.

Tests cover:
- Put/get/delete operations
- Content-based hashing
- Metadata storage
- Exists and info operations
- Directory creation
- Lifecycle (initialize/close)
- Protocol compliance
"""

import tempfile
from pathlib import Path

import pytest

from feedspine.blob.filesystem import FilesystemBlob

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for blob storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
async def blob_store(temp_dir):
    """Create an initialized FilesystemBlob."""
    store = FilesystemBlob(root=temp_dir)
    await store.initialize()
    yield store
    await store.close()


# =============================================================================
# Put Tests
# =============================================================================


class TestFilesystemBlobPut:
    """Tests for storing blobs."""

    async def test_put_creates_file(self, temp_dir):
        """put creates the file on disk."""
        blob = FilesystemBlob(root=temp_dir)
        await blob.initialize()

        await blob.put("test.txt", b"hello world")

        file_path = Path(temp_dir) / "test.txt"
        assert file_path.exists()
        assert file_path.read_bytes() == b"hello world"

    async def test_put_returns_blob_info(self, blob_store):
        """put returns BlobInfo with details."""
        info = await blob_store.put("doc.txt", b"content")

        assert info.key == "doc.txt"
        assert info.size == 7  # len("content")
        assert info.etag is not None

    async def test_put_with_content_type(self, blob_store):
        """Can specify content type."""
        info = await blob_store.put(
            "image.png",
            b"fake image",
            content_type="image/png",
        )

        assert info.content_type == "image/png"

    async def test_put_with_metadata(self, blob_store):
        """Can store metadata."""
        info = await blob_store.put(
            "data.json",
            b"{}",
            metadata={"source": "api", "version": "1"},
        )

        assert info.metadata == {"source": "api", "version": "1"}

    async def test_put_creates_subdirectories(self, blob_store, temp_dir):
        """put creates necessary subdirectories."""
        await blob_store.put("deep/nested/path/file.txt", b"data")

        file_path = Path(temp_dir) / "deep/nested/path/file.txt"
        assert file_path.exists()

    async def test_put_calculates_etag(self, blob_store):
        """etag is SHA-256 hash of content."""
        import hashlib

        content = b"test content"
        expected_hash = hashlib.sha256(content).hexdigest()

        info = await blob_store.put("test", content)

        assert info.etag == expected_hash

    async def test_put_overwrites_existing(self, blob_store):
        """put overwrites existing file."""
        await blob_store.put("file.txt", b"old content")
        await blob_store.put("file.txt", b"new content")

        content = await blob_store.get("file.txt")
        assert content == b"new content"


# =============================================================================
# Get Tests
# =============================================================================


class TestFilesystemBlobGet:
    """Tests for retrieving blobs."""

    async def test_get_existing(self, blob_store):
        """get returns file contents."""
        await blob_store.put("test.txt", b"hello world")

        content = await blob_store.get("test.txt")

        assert content == b"hello world"

    async def test_get_nonexistent(self, blob_store):
        """get returns None for missing file."""
        content = await blob_store.get("missing.txt")

        assert content is None

    async def test_get_binary_data(self, blob_store):
        """Can store and retrieve binary data."""
        binary_data = bytes(range(256))

        await blob_store.put("binary.dat", binary_data)
        content = await blob_store.get("binary.dat")

        assert content == binary_data


# =============================================================================
# Delete Tests
# =============================================================================


class TestFilesystemBlobDelete:
    """Tests for deleting blobs."""

    async def test_delete_existing(self, blob_store, temp_dir):
        """delete removes file and returns True."""
        await blob_store.put("test.txt", b"data")

        result = await blob_store.delete("test.txt")

        assert result is True
        assert not (Path(temp_dir) / "test.txt").exists()

    async def test_delete_nonexistent(self, blob_store):
        """delete returns False for missing file."""
        result = await blob_store.delete("missing.txt")

        assert result is False

    async def test_delete_removes_metadata_file(self, blob_store, temp_dir):
        """delete also removes .meta file."""
        await blob_store.put("test.txt", b"data", metadata={"key": "value"})

        await blob_store.delete("test.txt")

        meta_path = Path(temp_dir) / "test.txt.meta"
        assert not meta_path.exists()


# =============================================================================
# Exists Tests
# =============================================================================


class TestFilesystemBlobExists:
    """Tests for checking blob existence."""

    async def test_exists_for_existing(self, blob_store):
        """exists returns True for existing file."""
        await blob_store.put("test.txt", b"data")

        assert await blob_store.exists("test.txt") is True

    async def test_exists_for_missing(self, blob_store):
        """exists returns False for missing file."""
        assert await blob_store.exists("missing.txt") is False


# =============================================================================
# Info Tests
# =============================================================================


class TestFilesystemBlobInfo:
    """Tests for getting blob info."""

    async def test_info_for_existing(self, blob_store):
        """info returns BlobInfo for existing file."""
        await blob_store.put("test.txt", b"content")

        info = await blob_store.info("test.txt")

        assert info is not None
        assert info.key == "test.txt"
        assert info.size == 7

    async def test_info_for_missing(self, blob_store):
        """info returns None for missing file."""
        info = await blob_store.info("missing.txt")

        assert info is None


# =============================================================================
# List Tests
# =============================================================================


class TestFilesystemBlobList:
    """Tests for listing blobs."""

    async def test_list_all(self, blob_store):
        """list returns all blobs."""
        await blob_store.put("a.txt", b"1")
        await blob_store.put("b.txt", b"2")
        await blob_store.put("c.txt", b"3")

        keys = []
        async for info in blob_store.list():
            keys.append(info.key)

        assert len(keys) == 3

    async def test_list_with_prefix(self, blob_store):
        """list can filter by prefix."""
        await blob_store.put("docs/a.txt", b"1")
        await blob_store.put("docs/b.txt", b"2")
        await blob_store.put("images/c.png", b"3")

        keys = []
        async for info in blob_store.list(prefix="docs/"):
            keys.append(info.key)

        assert len(keys) == 2
        assert all("docs/" in k for k in keys)

    async def test_list_empty_store(self, blob_store):
        """list on empty store returns nothing."""
        keys = []
        async for info in blob_store.list():
            keys.append(info.key)

        assert keys == []


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestFilesystemBlobLifecycle:
    """Tests for initialize/close lifecycle."""

    async def test_initialize_creates_directory(self, temp_dir):
        """initialize creates root directory."""
        root = Path(temp_dir) / "blobs" / "data"
        blob = FilesystemBlob(root=str(root))

        await blob.initialize()

        assert root.exists()
        assert blob._initialized is True

    async def test_initialize_with_existing_directory(self, temp_dir):
        """initialize works with existing directory."""
        blob = FilesystemBlob(root=temp_dir)

        await blob.initialize()

        assert blob._initialized is True

    async def test_close_clears_flag(self, temp_dir):
        """close clears _initialized flag."""
        blob = FilesystemBlob(root=temp_dir)
        await blob.initialize()

        await blob.close()

        assert blob._initialized is False

    async def test_close_idempotent(self, temp_dir):
        """Multiple closes are safe."""
        blob = FilesystemBlob(root=temp_dir)
        await blob.initialize()

        await blob.close()
        await blob.close()

        assert blob._initialized is False


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestFilesystemBlobProtocol:
    """Tests for BlobStorage protocol compliance."""

    def test_has_required_methods(self, temp_dir):
        """FilesystemBlob has all required BlobStorage methods."""
        blob = FilesystemBlob(root=temp_dir)

        assert hasattr(blob, "initialize")
        assert hasattr(blob, "close")
        assert hasattr(blob, "put")
        assert hasattr(blob, "get")
        assert hasattr(blob, "delete")
        assert hasattr(blob, "exists")
        assert hasattr(blob, "info")
        assert hasattr(blob, "list")

    def test_methods_are_async(self, temp_dir):
        """All I/O methods are async."""
        import inspect

        blob = FilesystemBlob(root=temp_dir)

        assert inspect.iscoroutinefunction(blob.initialize)
        assert inspect.iscoroutinefunction(blob.close)
        assert inspect.iscoroutinefunction(blob.put)
        assert inspect.iscoroutinefunction(blob.get)
        assert inspect.iscoroutinefunction(blob.delete)
        assert inspect.iscoroutinefunction(blob.exists)
        assert inspect.iscoroutinefunction(blob.info)
        assert inspect.isasyncgenfunction(blob.list)
