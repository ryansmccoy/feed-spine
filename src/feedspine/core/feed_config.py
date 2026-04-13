"""Feed configuration loading from YAML/TOML files.

Loads feed definitions from a configuration file and instantiates
the corresponding adapter classes. This bridges the gap between
feedspine's SDK-level adapter registration and CLI-driven collection.

Supported config formats: YAML (.yml/.yaml) and TOML (.toml)

Example feeds.yaml::

    storage:
      type: sqlite
      connection: feeds.db

    search:
      type: memory

    feeds:
      - name: sec-rss
        type: rss
        url: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=10-K&dateb=&owner=include&count=40&search_text=&action=getcompany&output=atom
        requests_per_second: 0.5

      - name: polygon-earnings
        type: json
        url: https://api.polygon.io/v2/reference/financials
        headers:
          Authorization: "Bearer ${POLYGON_API_KEY}"
        items_path: results
        timeout: 60

      - name: local-filings
        type: file
        source_url: /data/filings/
        track_changes: true
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from feedspine._vendor.logging import get_logger

logger = get_logger(__name__)

# Adapter type string → class mapping
_ADAPTER_REGISTRY: dict[str, str] = {
    "rss": "feedspine.adapter.rss:RSSFeedAdapter",
    "json": "feedspine.adapter.json:JSONFeedAdapter",
    "file": "feedspine.adapter.file:FileFeedAdapter",
    "diffable_file": "feedspine.adapter.file:DiffableFileFeedAdapter",
    "csv": "feedspine.adapter.csv_adapter:CSVFeedAdapter",
    "sec_edgar": "feedspine.adapter.sec_edgar:SECEdgarFilingAdapter",
    "polygon_earnings": "feedspine.adapter.polygon_earnings:PolygonEarningsAdapter",
}

# Env var interpolation pattern: ${VAR_NAME} or ${VAR_NAME:-default}
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def _interpolate_env(value: str) -> str:
    """Replace ${VAR} and ${VAR:-default} with environment variable values."""

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        if default is not None:
            return default
        return match.group(0)  # leave as-is if no env var and no default

    return _ENV_PATTERN.sub(_replace, value)


def _interpolate_recursive(obj: Any) -> Any:
    """Recursively interpolate env vars in strings within dicts/lists."""
    if isinstance(obj, str):
        return _interpolate_env(obj)
    if isinstance(obj, dict):
        return {k: _interpolate_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_recursive(item) for item in obj]
    return obj


def _import_class(dotted_path: str) -> type:
    """Import a class from a 'module.path:ClassName' string."""
    module_path, class_name = dotted_path.rsplit(":", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@dataclass
class FeedConfig:
    """Parsed feed configuration."""

    feeds: list[dict[str, Any]] = field(default_factory=list)
    storage: dict[str, Any] = field(default_factory=dict)
    search: dict[str, Any] = field(default_factory=dict)


def load_config(path: str | Path) -> FeedConfig:
    """Load feed configuration from a YAML or TOML file.

    Args:
        path: Path to the configuration file.

    Returns:
        Parsed FeedConfig with feeds, storage, and search sections.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If file format is unsupported.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in (".yml", ".yaml"):
        data = _load_yaml(path)
    elif suffix == ".toml":
        data = _load_toml(path)
    else:
        raise ValueError(f"Unsupported config format: {suffix}. Use .yml, .yaml, or .toml")

    # Interpolate env vars
    data = _interpolate_recursive(data)

    return FeedConfig(
        feeds=data.get("feeds", []),
        storage=data.get("storage", {}),
        search=data.get("search", {}),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file."""
    try:
        import yaml
    except ImportError as e:
        raise ImportError("PyYAML is required for YAML config files. Install with: pip install pyyaml") from e
    with open(path, encoding="utf-8", errors="replace") as f:
        return yaml.safe_load(f) or {}


def _load_toml(path: Path) -> dict[str, Any]:
    """Load TOML file."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError as e:
            raise ImportError("Python 3.11+ or tomli is required for TOML config files.") from e
    with open(path, "rb") as f:
        return tomllib.load(f)


def create_adapters_from_config(config: FeedConfig) -> list[Any]:
    """Instantiate adapter instances from config feed definitions.

    Args:
        config: Parsed feed configuration.

    Returns:
        List of adapter instances ready for FeedSpine.register_feed().

    Raises:
        ValueError: If a feed definition has an unknown type.
    """
    adapters = []

    for feed_def in config.feeds:
        feed_def = dict(feed_def)  # copy to avoid mutation
        feed_type = feed_def.pop("type", None)

        if feed_type is None:
            raise ValueError(f"Feed definition missing 'type': {feed_def}")

        if feed_type not in _ADAPTER_REGISTRY:
            available = ", ".join(sorted(_ADAPTER_REGISTRY.keys()))
            raise ValueError(f"Unknown feed type '{feed_type}'. Available: {available}")

        adapter_class = _import_class(_ADAPTER_REGISTRY[feed_type])

        # Remove non-constructor keys that are config-level metadata
        feed_def.pop("enabled", None)
        enabled = feed_def.pop("enabled", True)
        if not enabled:
            logger.info("Skipping disabled feed", name=feed_def.get("name", "?"))
            continue

        try:
            adapter = adapter_class(**feed_def)
            adapters.append(adapter)
            logger.info("Loaded feed adapter", name=adapter.name, type=feed_type)
        except TypeError as e:
            raise ValueError(f"Invalid config for feed type '{feed_type}': {e}") from e

    return adapters


def find_config_file(start_dir: str | Path | None = None) -> Path | None:
    """Search for a feeds config file in standard locations.

    Searches in order:
    1. ./feeds.yaml, ./feeds.yml, ./feeds.toml
    2. ./.feedspine/feeds.yaml, etc.
    3. ./config/feeds.yaml, etc.

    Args:
        start_dir: Directory to start searching from. Defaults to cwd.

    Returns:
        Path to config file if found, None otherwise.
    """
    start = Path(start_dir) if start_dir else Path.cwd()

    candidates = [
        start / "feeds.yaml",
        start / "feeds.yml",
        start / "feeds.toml",
        start / ".feedspine" / "feeds.yaml",
        start / ".feedspine" / "feeds.yml",
        start / ".feedspine" / "feeds.toml",
        start / "config" / "feeds.yaml",
        start / "config" / "feeds.yml",
        start / "config" / "feeds.toml",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def list_adapter_types() -> dict[str, str]:
    """Return a mapping of adapter type names to their class paths.

    Returns:
        Dict of {type_name: module_path:ClassName}.
    """
    return dict(_ADAPTER_REGISTRY)
