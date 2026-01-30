"""
FeedSpine Adapter Discovery.

Auto-discovers feed adapters from installed packages via entry points.

Usage:
    from feedspine.discovery import discover_adapters, get_adapter
    
    # Discover all adapters
    adapters = discover_adapters()
    # {'sec-rss': <class SecRssFeedAdapter>, ...}
    
    # Get specific adapter
    SecRssAdapter = get_adapter("sec-rss")
    adapter = SecRssAdapter(form_types=["10-K"])

Entry Point Registration:
    # In pyproject.toml:
    [project.entry-points."feedspine.adapters"]
    sec-rss = "py_sec_edgar.adapters.sec_feeds:SecRssFeedAdapter"
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from feedspine.adapter.base import FeedAdapter

logger = logging.getLogger(__name__)

# Cache for discovered adapters
_adapter_cache: dict[str, type] | None = None


def discover_adapters(reload: bool = False) -> dict[str, type]:
    """
    Discover adapters from installed packages via entry points.
    
    Looks for entry points in the "feedspine.adapters" group.
    
    Args:
        reload: If True, re-discover adapters even if cached.
    
    Returns:
        Dictionary mapping adapter names to adapter classes.
    
    Example:
        >>> adapters = discover_adapters()
        >>> print(adapters.keys())
        dict_keys(['sec-rss', 'sec-daily', 'sec-quarterly'])
        
        >>> SecRssAdapter = adapters['sec-rss']
        >>> adapter = SecRssAdapter(form_types=["10-K"])
    """
    global _adapter_cache
    
    if _adapter_cache is not None and not reload:
        return _adapter_cache
    
    adapters = {}
    
    try:
        # Python 3.10+ style
        eps = entry_points(group="feedspine.adapters")
    except TypeError:
        # Python 3.9 fallback
        all_eps = entry_points()
        eps = all_eps.get("feedspine.adapters", [])
    
    for ep in eps:
        try:
            adapter_class = ep.load()
            adapters[ep.name] = adapter_class
            logger.debug(f"Discovered adapter: {ep.name} -> {adapter_class}")
        except Exception as e:
            logger.warning(f"Failed to load adapter {ep.name}: {e}")
    
    _adapter_cache = adapters
    return adapters


def get_adapter(name: str) -> type | None:
    """
    Get a specific adapter class by name.
    
    Args:
        name: Adapter name (e.g., "sec-rss")
    
    Returns:
        Adapter class, or None if not found.
    
    Example:
        >>> SecRssAdapter = get_adapter("sec-rss")
        >>> if SecRssAdapter:
        ...     adapter = SecRssAdapter(form_types=["10-K"])
    """
    adapters = discover_adapters()
    return adapters.get(name)


def list_adapters() -> list[dict[str, Any]]:
    """
    List all discovered adapters with metadata.
    
    Returns:
        List of adapter info dictionaries.
    
    Example:
        >>> for info in list_adapters():
        ...     print(f"{info['name']}: {info['class']}")
    """
    adapters = discover_adapters()
    result = []
    
    for name, cls in adapters.items():
        info = {
            "name": name,
            "class": f"{cls.__module__}.{cls.__name__}",
            "docstring": cls.__doc__,
        }
        result.append(info)
    
    return result


def register_adapter(name: str, adapter_class: type) -> None:
    """
    Manually register an adapter.
    
    Useful for testing or when entry points aren't available.
    
    Args:
        name: Adapter name to register.
        adapter_class: Adapter class.
    
    Example:
        >>> from my_adapters import CustomAdapter
        >>> register_adapter("custom", CustomAdapter)
    """
    global _adapter_cache
    
    if _adapter_cache is None:
        _adapter_cache = {}
    
    _adapter_cache[name] = adapter_class
    logger.info(f"Registered adapter: {name}")


def clear_cache() -> None:
    """Clear the adapter cache."""
    global _adapter_cache
    _adapter_cache = None
