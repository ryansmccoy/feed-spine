"""Elasticsearch search backend for full-text search at scale.

Elasticsearch provides distributed, scalable full-text search with:
- Full-text search with relevance scoring
- Aggregations and analytics
- Real-time indexing
- Highlight support
- Filtering capabilities

Example:
    >>> from feedspine.search.elasticsearch import ElasticsearchSearch
    >>> search = ElasticsearchSearch(hosts=["http://localhost:9200"])
    >>> await search.initialize()
    >>> await search.index("rec-1", {"title": "Hello World"})
    >>> results = await search.search("hello")

Note:
    Requires the `elasticsearch` optional dependency:
    ``pip install feedspine[elasticsearch]``
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

try:
    from elasticsearch import AsyncElasticsearch, NotFoundError
except ImportError as e:
    raise ImportError(
        "Elasticsearch is required for ElasticsearchSearch. "
        "Install with: pip install feedspine[elasticsearch]"
    ) from e

from feedspine.protocols.search import SearchResponse, SearchResult, SearchType


class ElasticsearchSearch:
    """Elasticsearch search backend for scalable full-text search.

    Provides distributed search with relevance scoring, highlighting,
    filtering, and aggregation capabilities.

    Best for: Production search, large datasets, complex queries.

    Args:
        hosts: List of Elasticsearch host URLs.
        index: Index name for storing documents.
        **client_kwargs: Additional kwargs for AsyncElasticsearch client.

    Example:
        >>> import asyncio
        >>> from feedspine.search.elasticsearch import ElasticsearchSearch
        >>> # Create with default settings
        >>> search = ElasticsearchSearch(hosts=["http://localhost:9200"])
        >>> # Or with custom index
        >>> search = ElasticsearchSearch(
        ...     hosts=["http://localhost:9200"],
        ...     index="my-feedspine-index",
        ... )
    """

    def __init__(
        self,
        hosts: list[str],
        index: str = "feedspine",
        **client_kwargs: Any,
    ) -> None:
        self._hosts = hosts
        self._index = index
        self._client_kwargs = client_kwargs
        self._client: AsyncElasticsearch | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize client and create index if needed.

        Creates the index with appropriate mappings for search if it
        doesn't already exist.

        Example:
            >>> import asyncio
            >>> from feedspine.search.elasticsearch import ElasticsearchSearch
            >>> search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            >>> asyncio.run(search.initialize())
        """
        self._client = AsyncElasticsearch(hosts=self._hosts, **self._client_kwargs)

        # Create index if it doesn't exist
        exists = await self._client.indices.exists(index=self._index)
        if not exists:
            await self._client.indices.create(
                index=self._index,
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "analysis": {
                            "analyzer": {
                                "default": {
                                    "type": "standard",
                                }
                            }
                        },
                    },
                    "mappings": {
                        "properties": {
                            "content": {
                                "type": "object",
                                "dynamic": True,
                            },
                            "metadata": {
                                "type": "object",
                                "dynamic": True,
                            },
                            "indexed_at": {
                                "type": "date",
                            },
                        }
                    },
                },
            )

        self._initialized = True

    async def close(self) -> None:
        """Close Elasticsearch client connection.

        Example:
            >>> import asyncio
            >>> from feedspine.search.elasticsearch import ElasticsearchSearch
            >>> search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            >>> asyncio.run(search.initialize())
            >>> asyncio.run(search.close())
        """
        if self._client:
            await self._client.close()
            self._client = None
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
            >>> from feedspine.search.elasticsearch import ElasticsearchSearch
            >>> search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            >>> asyncio.run(search.initialize())
            >>> asyncio.run(search.index(
            ...     "rec-1",
            ...     {"title": "Test", "body": "Content here"},
            ...     {"source": "test-feed"},
            ... ))
        """
        assert self._client is not None, "Search not initialized"

        document = {
            "content": content,
            "metadata": metadata or {},
            "indexed_at": datetime.now(UTC).isoformat(),
        }

        await self._client.index(
            index=self._index,
            id=record_id,
            document=document,
            refresh=True,  # Make immediately searchable
        )

    async def delete(self, record_id: str) -> bool:
        """Remove document from index.

        Args:
            record_id: Record ID to delete.

        Returns:
            True if document existed and was deleted, False if not found.

        Example:
            >>> import asyncio
            >>> from feedspine.search.elasticsearch import ElasticsearchSearch
            >>> search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            >>> asyncio.run(search.initialize())
            >>> # Returns False if not found
            >>> asyncio.run(search.delete("nonexistent"))
            False
        """
        assert self._client is not None, "Search not initialized"

        try:
            await self._client.delete(
                index=self._index,
                id=record_id,
                refresh=True,
            )
            return True
        except NotFoundError:
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
            search_type: Type of search to perform.
            filters: Optional filters to apply.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            SearchResponse with results and metadata.

        Example:
            >>> import asyncio
            >>> from feedspine.search.elasticsearch import ElasticsearchSearch
            >>> search = ElasticsearchSearch(hosts=["http://localhost:9200"])
            >>> asyncio.run(search.initialize())
            >>> response = asyncio.run(search.search("test query"))
            >>> len(response.results)
            0
        """
        assert self._client is not None, "Search not initialized"

        # Build query based on search type
        es_query = self._build_query(query, search_type, filters)

        # Execute search
        response = await self._client.search(
            index=self._index,
            query=es_query,
            highlight={
                "fields": {
                    "content.*": {},
                }
            },
            size=limit,
            from_=offset,
        )

        # Parse results
        hits = response["hits"]["hits"]
        total = response["hits"]["total"]["value"]
        took_ms = response["took"]

        results = [
            SearchResult(
                record_id=hit["_id"],
                score=hit["_score"] or 0.0,
                highlights=hit.get("highlight"),
                metadata=hit["_source"].get("metadata"),
            )
            for hit in hits
        ]

        return SearchResponse(
            results=results,
            total_count=total,
            query_time_ms=took_ms,
            search_type=search_type,
        )

    def _build_query(
        self,
        query: str,
        search_type: SearchType,
        filters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build Elasticsearch query DSL.

        Args:
            query: User query string.
            search_type: Type of search.
            filters: Optional filters.

        Returns:
            Elasticsearch query DSL dictionary.
        """
        # Build the main query based on type
        if search_type == SearchType.KEYWORD:
            main_query: dict[str, Any] = {
                "match_phrase": {
                    "content.*": query,
                }
            }
        else:
            # FULLTEXT is default - use multi_match
            main_query = {
                "multi_match": {
                    "query": query,
                    "fields": ["content.*"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }

        # Wrap in bool query if filters present
        if filters:
            filter_clauses = []
            for field, value in filters.items():
                filter_clauses.append({"term": {f"metadata.{field}": value}})

            return {
                "bool": {
                    "must": [main_query],
                    "filter": filter_clauses,
                }
            }

        return main_query
