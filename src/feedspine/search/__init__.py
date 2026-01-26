"""Search implementations."""

from feedspine.search.memory import MemorySearch

__all__ = ["MemorySearch"]

# Optional: Elasticsearch search (requires elasticsearch)
try:
    from feedspine.search.elasticsearch import ElasticsearchSearch as _ElasticsearchSearch

    ElasticsearchSearch = _ElasticsearchSearch
    __all__.append("ElasticsearchSearch")
except ImportError:
    ElasticsearchSearch = None  # type: ignore[misc,assignment]
