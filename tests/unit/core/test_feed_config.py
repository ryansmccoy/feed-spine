"""Tests for feedspine.core.feed_config module.

Tests config loading, env-var interpolation, find_config_file,
list_adapter_types, and FeedConfig dataclass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from feedspine.core.feed_config import (
    FeedConfig,
    _interpolate_env,
    _interpolate_recursive,
    find_config_file,
    list_adapter_types,
    load_config,
)

# ---------------------------------------------------------------------------
# _interpolate_env
# ---------------------------------------------------------------------------


class TestInterpolateEnv:
    """Tests for environment variable interpolation."""

    def test_no_vars(self):
        assert _interpolate_env("hello world") == "hello world"

    def test_existing_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TEST_FEED_VAR", "my_value")
        assert _interpolate_env("key=${TEST_FEED_VAR}") == "key=my_value"

    def test_missing_var_with_default(self):
        result = _interpolate_env("${UNLIKELY_VAR_XYZ:-fallback}")
        assert result == "fallback"

    def test_missing_var_no_default_keeps_literal(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("UNLIKELY_VAR_ABC", raising=False)
        result = _interpolate_env("${UNLIKELY_VAR_ABC}")
        assert result == "${UNLIKELY_VAR_ABC}"

    def test_multiple_vars(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("A_VAR", "x")
        monkeypatch.setenv("B_VAR", "y")
        result = _interpolate_env("${A_VAR}-${B_VAR}")
        assert result == "x-y"


# ---------------------------------------------------------------------------
# _interpolate_recursive
# ---------------------------------------------------------------------------


class TestInterpolateRecursive:
    """Tests for recursive env-var interpolation in nested structures."""

    def test_dict(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("R_VAR", "resolved")
        data = {"key": "${R_VAR}", "num": 42}
        result = _interpolate_recursive(data)
        assert result["key"] == "resolved"
        assert result["num"] == 42

    def test_list(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("L_VAR", "item")
        data = ["${L_VAR}", "plain"]
        result = _interpolate_recursive(data)
        assert result == ["item", "plain"]

    def test_nested(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("N_VAR", "deep")
        data = {"outer": [{"inner": "${N_VAR}"}]}
        result = _interpolate_recursive(data)
        assert result["outer"][0]["inner"] == "deep"


# ---------------------------------------------------------------------------
# FeedConfig
# ---------------------------------------------------------------------------


class TestFeedConfig:
    """Tests for the FeedConfig dataclass."""

    def test_defaults(self):
        cfg = FeedConfig()
        assert cfg.feeds == []
        assert cfg.storage == {}
        assert cfg.search == {}

    def test_init_with_values(self):
        cfg = FeedConfig(
            feeds=[{"name": "a", "type": "rss"}],
            storage={"type": "sqlite"},
            search={"type": "memory"},
        )
        assert len(cfg.feeds) == 1
        assert cfg.storage["type"] == "sqlite"


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for YAML and TOML config loading."""

    def test_load_yaml(self, tmp_path: Path):
        cfg_file = tmp_path / "feeds.yaml"
        cfg_file.write_text(
            "storage:\n  type: sqlite\n  connection: test.db\n"
            "feeds:\n  - name: test\n    type: rss\n    url: http://example.com\n"
        )
        cfg = load_config(cfg_file)
        assert isinstance(cfg, FeedConfig)
        assert cfg.storage["type"] == "sqlite"
        assert len(cfg.feeds) == 1
        assert cfg.feeds[0]["name"] == "test"

    def test_load_yaml_with_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("MY_API_KEY", "secret123")
        cfg_file = tmp_path / "feeds.yml"
        cfg_file.write_text(
            "feeds:\n  - name: api\n    type: json\n    url: http://api.example.com\n"
            "    headers:\n      Authorization: 'Bearer ${MY_API_KEY}'\n"
        )
        cfg = load_config(cfg_file)
        assert cfg.feeds[0]["headers"]["Authorization"] == "Bearer secret123"

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_unsupported_format(self, tmp_path: Path):
        cfg_file = tmp_path / "feeds.json"
        cfg_file.write_text("{}")
        with pytest.raises(ValueError, match="Unsupported config format"):
            load_config(cfg_file)


# ---------------------------------------------------------------------------
# find_config_file
# ---------------------------------------------------------------------------


class TestFindConfigFile:
    """Tests for config file discovery."""

    def test_finds_yaml(self, tmp_path: Path):
        (tmp_path / "feeds.yaml").write_text("feeds: []")
        result = find_config_file(tmp_path)
        assert result is not None
        assert result.name == "feeds.yaml"

    def test_finds_yml(self, tmp_path: Path):
        (tmp_path / "feeds.yml").write_text("feeds: []")
        result = find_config_file(tmp_path)
        assert result is not None
        assert result.name == "feeds.yml"

    def test_finds_toml(self, tmp_path: Path):
        (tmp_path / "feeds.toml").write_text("[storage]\ntype = 'sqlite'\n")
        result = find_config_file(tmp_path)
        assert result is not None
        assert result.name == "feeds.toml"

    def test_finds_in_subdirectory(self, tmp_path: Path):
        config_dir = tmp_path / ".feedspine"
        config_dir.mkdir()
        (config_dir / "feeds.yaml").write_text("feeds: []")
        result = find_config_file(tmp_path)
        assert result is not None
        assert ".feedspine" in str(result)

    def test_returns_none_if_no_config(self, tmp_path: Path):
        result = find_config_file(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# list_adapter_types
# ---------------------------------------------------------------------------


class TestListAdapterTypes:
    """Tests for list_adapter_types."""

    def test_returns_dict(self):
        result = list_adapter_types()
        assert isinstance(result, dict)

    def test_contains_rss(self):
        result = list_adapter_types()
        assert "rss" in result

    def test_contains_json(self):
        result = list_adapter_types()
        assert "json" in result

    def test_values_are_import_paths(self):
        for path in list_adapter_types().values():
            assert ":" in path  # module:ClassName format
