"""In-memory search implementation.

Provides a simple linear search implementation for testing
and development. Production should use Elasticsearch or similar.

Example:
    >>> from feedspine.search.memory import MemorySearch
    >>> search = MemorySearch()
    >>> # MemorySearch implements SearchBackend protocol
    >>> hasattr(search, 'index')
    True
    >>> hasattr(search, 'search')
    True
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from feedspine.protocols.search import SearchResponse, SearchResult, SearchType


@dataclass
class IndexedDocument:
    """A document in the search index.

    Example:
        >>> from feedspine.search.memory import IndexedDocument
        >>> doc = IndexedDocument(
        ...     record_id="r1",
        ...     content={"title": "Test Document"},
        ...     metadata={"type": "article"},
        ... )
        >>> doc.record_id
        'r1'
    """

    record_id: str
    content: dict[str, Any]
    metadata: dict[str, Any] | None = None
    text_cache: str = field(default="")

    def __post_init__(self) -> None:
        """Build text cache for searching."""
        self.text_cache = self._build_text_cache()

    def _build_text_cache(self) -> str:
        """Flatten content into searchable text."""
        parts: list[str] = []
        for _key, value in self.content.items():
            if isinstance(value, str):
                parts.append(value.lower())
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        parts.append(item.lower())
        return " ".join(parts)


class MemorySearch:
    """In-memory search using linear scan.

    Supports basic keyword and fulltext search.
    Not suitable for large datasets or production use.

    Best for: Testing, development, small datasets.

    Example:
        >>> import asyncio
        >>> from feedspine.search.memory import MemorySearch
        >>> search = MemorySearch()
        >>> asyncio.run(search.index("r1", {"title": "Apple Inc", "body": "Tech company"}))
        >>> asyncio.run(search.index("r2", {"title": "Microsoft", "body": "Software"}))
        >>> results = asyncio.run(search.search("apple"))
        >>> len(results.results)
        1
        >>> results.results[0].record_id
        'r1'
    """

    def __init__(self) -> None:
        self._index: dict[str, IndexedDocument] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize search backend.

        Example:
            >>> import asyncio
            >>> from feedspine.search.memory import MemorySearch
            >>> s = MemorySearch()
            >>> asyncio.run(s.initialize())
            >>> s._initialized
            True
        """
        self._initialized = True

    async def close(self) -> None:
        """Clean up resources."""
        self._index.clear()
        self._initialized = False

    async def index(
        self,
        record_id: str,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index a record for searching.

        Args:
            record_id: Unique record identifier.
            content: Searchable content fields.
            metadata: Optional metadata for filtering.

        Example:
            >>> import asyncio
            >>> from feedspine.search.memory import MemorySearch
            >>> s = MemorySearch()
            >>> asyncio.run(s.index("doc1", {"title": "Hello World"}))
            >>> len(s._index)
            1
        """
        self._index[record_id] = IndexedDocument(
            record_id=record_id,
            content=content,
            metadata=metadata,
        )

    async def delete(self, record_id: str) -> bool:
        """Remove document from index.

        Returns:
            True if document existed and was deleted.

        Example:
            >>> import asyncio
            >>> from feedspine.search.memory import MemorySearch
            >>> s = MemorySearch()
            >>> asyncio.run(s.index("d1", {"text": "test"}))
            >>> asyncio.run(s.delete("d1"))
            True
            >>> asyncio.run(s.delete("d1"))
            False
        """
        if record_id in self._index:
            del self._index[record_id]
            return True
        return False

    async def search(
        self,
        query: str,
        search_type: SearchType = SearchType.FULLTEXT,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> SearchResponse:
        """Search indexed records.

        Args:
            query: Search query string.
            search_type: Type of search (keyword, fulltext).
            filters: Metadata filters.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            SearchResponse with matching results.

        Example:
            >>> import asyncio
            >>> from feedspine.search.memory import MemorySearch
            >>> s = MemorySearch()
            >>> asyncio.run(s.index("r1", {"title": "Python Guide"}))
            >>> asyncio.run(s.index("r2", {"title": "Java Tutorial"}))
            >>> resp = asyncio.run(s.search("python"))
            >>> resp.total_count
            1
        """
        start_time = time.perf_counter()
        query_lower = query.lower()
        query_terms = query_lower.split()

        results: list[SearchResult] = []

        for doc in self._index.values():
            # Apply metadata filters
            if filters and not self._matches_filters(doc, filters):
                continue

            # Score document
            score = self._score_document(doc, query_terms, search_type)
            if score > 0:
                highlights = self._extract_highlights(doc, query_terms)
                results.append(
                    SearchResult(
                        record_id=doc.record_id,
                        score=score,
                        highlights=highlights,
                        metadata=doc.metadata,
                    )
                )

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        total_count = len(results)

        # Paginate
        results = results[offset : offset + limit]

        query_time_ms = (time.perf_counter() - start_time) * 1000

        return SearchResponse(
            results=results,
            total_count=total_count,
            query_time_ms=query_time_ms,
            search_type=search_type,
        )

    def _matches_filters(
        self,
        doc: IndexedDocument,
        filters: dict[str, Any],
    ) -> bool:
        """Check if document matches all filters."""
        if not doc.metadata:
            return False

        for key, value in filters.items():
            if key not in doc.metadata:
                return False
            if doc.metadata[key] != value:
                return False
        return True

    def _score_document(
        self,
        doc: IndexedDocument,
        query_terms: list[str],
        search_type: SearchType,
    ) -> float:
        """Calculate relevance score for document."""
        if not query_terms:
            return 0.0

        text = doc.text_cache
        matches = 0
        total_terms = len(query_terms)

        for term in query_terms:
            if search_type == SearchType.KEYWORD:
                # Exact word match
                pattern = r"\b" + re.escape(term) + r"\b"
                if re.search(pattern, text):
                    matches += 1
            else:
                # Substring match (fulltext)
                if term in text:
                    matches += 1

        if matches == 0:
            return 0.0

        # Simple TF-like score
        return matches / total_terms

    def _extract_highlights(
        self,
        doc: IndexedDocument,
        query_terms: list[str],
    ) -> dict[str, list[str]]:
        """Extract highlighted snippets around matches."""
        highlights: dict[str, list[str]] = {}

        for field_name, value in doc.content.items():
            if not isinstance(value, str):
                continue

            value_lower = value.lower()
            field_highlights = []

            for term in query_terms:
                if term in value_lower:
                    # Find context around match
                    idx = value_lower.find(term)
                    start = max(0, idx - 30)
                    end = min(len(value), idx + len(term) + 30)
                    snippet = value[start:end]
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(value):
                        snippet = snippet + "..."
                    field_highlights.append(snippet)

            if field_highlights:
                highlights[field_name] = field_highlights

        return highlights

    # --- Utility Methods ---

    def __len__(self) -> int:
        """Return number of indexed documents.

        Example:
            >>> import asyncio
            >>> from feedspine.search.memory import MemorySearch
            >>> s = MemorySearch()
            >>> len(s)
            0
            >>> asyncio.run(s.index("r1", {"text": "test"}))
            >>> len(s)
            1
        """
        return len(self._index)
