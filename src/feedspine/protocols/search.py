"""Search backend protocol.

Defines the interface for search backends (full-text, semantic, etc.)
and associated data structures.

Example:
    >>> from feedspine.protocols.search import SearchResult, SearchType
    >>> result = SearchResult(record_id="rec-1", score=0.95)
    >>> result.score
    0.95
    >>> SearchType.FULLTEXT.value
    'fulltext'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class SearchType(str, Enum):
    """Type of search to perform.

    Example:
        >>> from feedspine.protocols.search import SearchType
        >>> SearchType.SEMANTIC.value
        'semantic'
        >>> list(SearchType)  # doctest: +NORMALIZE_WHITESPACE
        [<SearchType.KEYWORD: 'keyword'>, <SearchType.FULLTEXT: 'fulltext'>,
         <SearchType.SEMANTIC: 'semantic'>, <SearchType.HYBRID: 'hybrid'>]
    """

    KEYWORD = "keyword"
    FULLTEXT = "fulltext"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class SearchResult:
    """A single search result.

    Example:
        >>> from feedspine.protocols.search import SearchResult
        >>> r = SearchResult(
        ...     record_id="rec-123",
        ...     score=0.87,
        ...     highlights={"title": ["match here"]},
        ... )
        >>> r.record_id
        'rec-123'
        >>> r.highlights
        {'title': ['match here']}
    """

    record_id: str
    score: float
    highlights: dict[str, list[str]] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class SearchResponse:
    """Search response with results and metadata.

    Example:
        >>> from feedspine.protocols.search import SearchResponse, SearchResult
        >>> resp = SearchResponse(
        ...     results=[SearchResult(record_id="r1", score=0.9)],
        ...     total_count=1,
        ...     query_time_ms=15.5,
        ... )
        >>> len(resp.results)
        1
        >>> resp.total_count
        1
    """

    results: list[SearchResult] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: float = 0.0
    search_type: SearchType = SearchType.FULLTEXT


@runtime_checkable
class SearchBackend(Protocol):
    """Search backend protocol."""

    async def index(
        self,
        record_id: str,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index a record for searching."""
        ...

    async def delete(self, record_id: str) -> bool:
        """Remove from index."""
        ...

    async def search(
        self,
        query: str,
        search_type: SearchType = SearchType.FULLTEXT,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> SearchResponse:
        """Search indexed records."""
        ...

    async def initialize(self) -> None:
        """Initialize search backend."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
