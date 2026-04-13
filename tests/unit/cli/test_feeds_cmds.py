"""Tests for feedspine.cli_modules.feeds_cmds."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from feedspine.cli_modules.feeds_cmds import feeds_app


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


def test_list_types_shows_adapter_count(cli_runner: CliRunner) -> None:
    """`feeds list-types` should render available adapter types."""
    adapters = {
        "rss": "feedspine.adapters.rss.RssAdapter",
        "sec": "feedspine.adapters.sec.SecAdapter",
    }

    with patch("feedspine.core.feed_config.list_adapter_types", return_value=adapters):
        result = cli_runner.invoke(feeds_app, ["list-types"])

    assert result.exit_code == 0
    assert "Available Feed Adapter Types" in result.stdout
    assert "rss" in result.stdout
    assert "sec" in result.stdout
    assert "2 adapter types available" in result.stdout


def test_list_configured_feeds_no_config(cli_runner: CliRunner) -> None:
    """`feeds list` should exit non-zero when no config is found."""
    with patch("feedspine.core.feed_config.find_config_file", return_value=None):
        result = cli_runner.invoke(feeds_app, ["list"])

    assert result.exit_code == 1
    assert "No feed config found" in result.stdout


def test_list_configured_feeds_success(cli_runner: CliRunner) -> None:
    """`feeds list` should render configured feed rows."""
    config = SimpleNamespace(
        feeds=[
            {"name": "SEC 8-K", "type": "sec", "url": "https://sec.example/rss", "enabled": True},
            {"name": "HN", "type": "rss", "url": "https://news.ycombinator.com/rss", "enabled": False},
        ]
    )

    with (
        patch("feedspine.core.feed_config.find_config_file", return_value="feeds.yaml"),
        patch("feedspine.core.feed_config.load_config", return_value=config),
    ):
        result = cli_runner.invoke(feeds_app, ["list"])

    assert result.exit_code == 0
    assert "Configured Feeds" in result.stdout
    assert "SEC 8-K" in result.stdout
    assert "HN" in result.stdout
    assert "2 feeds configured" in result.stdout


def test_validate_config_success(cli_runner: CliRunner) -> None:
    """`feeds validate` should pass for valid config and adapters."""
    config = SimpleNamespace(feeds=[{"name": "SEC", "type": "sec", "url": "https://sec.example/rss"}])

    with (
        patch("feedspine.core.feed_config.find_config_file", return_value="feeds.yaml"),
        patch("feedspine.core.feed_config.load_config", return_value=config),
        patch("feedspine.core.feed_config.create_adapters_from_config", return_value=[object()]),
    ):
        result = cli_runner.invoke(feeds_app, ["validate"])

    assert result.exit_code == 0
    assert "Config file parsed successfully" in result.stdout
    assert "1 feeds defined" in result.stdout
    assert "1 adapters created successfully" in result.stdout


def test_validate_config_adapter_failure(cli_runner: CliRunner) -> None:
    """`feeds validate` should fail when adapter creation fails."""
    config = SimpleNamespace(feeds=[{"name": "SEC", "type": "sec", "url": "https://sec.example/rss"}])

    with (
        patch("feedspine.core.feed_config.find_config_file", return_value="feeds.yaml"),
        patch("feedspine.core.feed_config.load_config", return_value=config),
        patch("feedspine.core.feed_config.create_adapters_from_config", side_effect=RuntimeError("invalid type")),
    ):
        result = cli_runner.invoke(feeds_app, ["validate"])

    assert result.exit_code == 1
    assert "Adapter creation failed" in result.stdout
