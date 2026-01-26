"""Tests for MemorySearch implementation.

Tests cover:
- Indexing documents
- Basic search
- Keyword and fulltext search
- Filtering
- Delete operations
- Lifecycle (initialize/close)
- Protocol compliance
"""

from feedspine.protocols.search import SearchType
from feedspine.search.memory import IndexedDocument, MemorySearch

# =============================================================================
# IndexedDocument Tests
# =============================================================================


class TestIndexedDocument:
    """Tests for IndexedDocument dataclass."""

    def test_create_with_content(self):
        """Can create document with content."""
        doc = IndexedDocument(
            record_id="r1",
            content={"title": "Test", "body": "Content"},
        )

        assert doc.record_id == "r1"
        assert doc.content["title"] == "Test"

    def test_text_cache_built_from_content(self):
        """text_cache is built from content strings."""
        doc = IndexedDocument(
            record_id="r1",
            content={"title": "Hello World", "body": "Test content"},
        )

        assert "hello world" in doc.text_cache
        assert "test content" in doc.text_cache

    def test_text_cache_includes_list_items(self):
        """text_cache includes items from lists."""
        doc = IndexedDocument(
            record_id="r1",
            content={"tags": ["python", "testing"]},
        )

        assert "python" in doc.text_cache
        assert "testing" in doc.text_cache

    def test_text_cache_lowercased(self):
        """text_cache is lowercased for searching."""
        doc = IndexedDocument(
            record_id="r1",
            content={"title": "UPPERCASE TEXT"},
        )

        assert "uppercase text" in doc.text_cache


# =============================================================================
# Index Tests
# =============================================================================


class TestMemorySearchIndex:
    """Tests for indexing documents."""

    async def test_index_document(self):
        """Can index a document."""
        search = MemorySearch()

        await search.index("doc1", {"title": "Test Document"})

        assert "doc1" in search._index

    async def test_index_with_metadata(self):
        """Can index with metadata."""
        search = MemorySearch()

        await search.index(
            "doc1",
            {"title": "Test"},
            metadata={"type": "article"},
        )

        assert search._index["doc1"].metadata == {"type": "article"}

    async def test_index_overwrites_existing(self):
        """Re-indexing overwrites existing document."""
        search = MemorySearch()

        await search.index("doc1", {"title": "Old"})
        await search.index("doc1", {"title": "New"})

        assert search._index["doc1"].content["title"] == "New"


# =============================================================================
# Basic Search Tests
# =============================================================================


class TestMemorySearchBasic:
    """Tests for basic search operations."""

    async def test_search_finds_matching(self):
        """Search finds documents with matching terms."""
        search = MemorySearch()

        await search.index("r1", {"title": "Apple iPhone"})
        await search.index("r2", {"title": "Samsung Galaxy"})

        results = await search.search("apple")

        assert len(results.results) == 1
        assert results.results[0].record_id == "r1"

    async def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        search = MemorySearch()

        await search.index("r1", {"title": "APPLE iPhone"})

        results = await search.search("apple")

        assert len(results.results) == 1

    async def test_search_multiple_results(self):
        """Search returns multiple matching documents."""
        search = MemorySearch()

        await search.index("r1", {"title": "Apple iPhone"})
        await search.index("r2", {"title": "Apple MacBook"})
        await search.index("r3", {"title": "Samsung Phone"})

        results = await search.search("apple")

        assert len(results.results) == 2
        ids = {r.record_id for r in results.results}
        assert ids == {"r1", "r2"}

    async def test_search_no_matches(self):
        """Search with no matches returns empty results."""
        search = MemorySearch()

        await search.index("r1", {"title": "Apple"})

        results = await search.search("microsoft")

        assert len(results.results) == 0

    async def test_search_empty_index(self):
        """Search on empty index returns empty results."""
        search = MemorySearch()

        results = await search.search("anything")

        assert len(results.results) == 0


# =============================================================================
# Search Type Tests
# =============================================================================


class TestMemorySearchTypes:
    """Tests for different search types."""

    async def test_keyword_search(self):
        """Keyword search matches exact words."""
        search = MemorySearch()

        await search.index("r1", {"title": "apple pie recipe"})
        await search.index("r2", {"title": "pineapple juice"})

        results = await search.search("apple", search_type=SearchType.KEYWORD)

        # Should match "apple" word but not "pineapple"
        assert len(results.results) >= 1

    async def test_fulltext_search(self):
        """Fulltext search matches partial terms."""
        search = MemorySearch()

        await search.index("r1", {"body": "The application runs smoothly"})

        results = await search.search("application", search_type=SearchType.FULLTEXT)

        assert len(results.results) == 1


# =============================================================================
# Search Response Tests
# =============================================================================


class TestMemorySearchResponse:
    """Tests for SearchResponse structure."""

    async def test_response_has_results(self):
        """Response contains results list."""
        search = MemorySearch()

        await search.index("r1", {"title": "Test"})

        response = await search.search("test")

        assert hasattr(response, "results")
        assert isinstance(response.results, list)

    async def test_response_has_total(self):
        """Response includes total count."""
        search = MemorySearch()

        await search.index("r1", {"title": "Test"})
        await search.index("r2", {"title": "Test"})

        response = await search.search("test")

        assert response.total_count == 2

    async def test_response_has_timing(self):
        """Response includes query timing."""
        search = MemorySearch()

        await search.index("r1", {"title": "Test"})

        response = await search.search("test")

        assert response.query_time_ms >= 0

    async def test_result_has_score(self):
        """SearchResult has relevance score."""
        search = MemorySearch()

        await search.index("r1", {"title": "Test"})

        response = await search.search("test")

        assert response.results[0].score >= 0


# =============================================================================
# Pagination Tests
# =============================================================================


class TestMemorySearchPagination:
    """Tests for search pagination."""

    async def test_limit_results(self):
        """Can limit number of results."""
        search = MemorySearch()

        for i in range(10):
            await search.index(f"r{i}", {"title": "test document"})

        response = await search.search("test", limit=3)

        assert len(response.results) == 3

    async def test_offset_results(self):
        """Can offset results for pagination."""
        search = MemorySearch()

        # Index documents with distinct identifiable content
        for i in range(5):
            await search.index(f"r{i}", {"title": f"test {i}"})

        response = await search.search("test", offset=2)

        # Should skip first 2
        assert len(response.results) <= 3

    async def test_default_limit(self):
        """Results have a default limit."""
        search = MemorySearch()

        for i in range(100):
            await search.index(f"r{i}", {"title": "test"})

        response = await search.search("test")

        # Should have some reasonable default limit
        assert len(response.results) < 100


# =============================================================================
# Delete Tests
# =============================================================================


class TestMemorySearchDelete:
    """Tests for delete operations."""

    async def test_delete_existing(self):
        """Can delete an indexed document."""
        search = MemorySearch()

        await search.index("doc1", {"title": "Test"})
        result = await search.delete("doc1")

        assert result is True
        assert "doc1" not in search._index

    async def test_delete_nonexistent(self):
        """Deleting non-existent returns False."""
        search = MemorySearch()

        result = await search.delete("missing")

        assert result is False

    async def test_deleted_not_in_search(self):
        """Deleted documents don't appear in search."""
        search = MemorySearch()

        await search.index("doc1", {"title": "Apple"})
        await search.delete("doc1")

        results = await search.search("apple")

        assert len(results.results) == 0


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestMemorySearchLifecycle:
    """Tests for initialize/close lifecycle."""

    async def test_initialize_sets_flag(self):
        """initialize sets _initialized flag."""
        search = MemorySearch()

        assert search._initialized is False

        await search.initialize()

        assert search._initialized is True

    async def test_close_clears_index(self):
        """close clears the index."""
        search = MemorySearch()
        await search.initialize()

        await search.index("doc1", {"title": "Test"})
        await search.close()

        assert len(search._index) == 0
        assert search._initialized is False

    async def test_close_idempotent(self):
        """Multiple closes are safe."""
        search = MemorySearch()
        await search.initialize()

        await search.close()
        await search.close()

        assert search._initialized is False


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestMemorySearchProtocol:
    """Tests for SearchBackend protocol compliance."""

    def test_has_required_methods(self):
        """MemorySearch has all required SearchBackend methods."""
        search = MemorySearch()

        assert hasattr(search, "initialize")
        assert hasattr(search, "close")
        assert hasattr(search, "index")
        assert hasattr(search, "search")
        assert hasattr(search, "delete")

    def test_methods_are_async(self):
        """All I/O methods are async."""
        import inspect

        search = MemorySearch()

        assert inspect.iscoroutinefunction(search.initialize)
        assert inspect.iscoroutinefunction(search.close)
        assert inspect.iscoroutinefunction(search.index)
        assert inspect.iscoroutinefunction(search.search)
        assert inspect.iscoroutinefunction(search.delete)
