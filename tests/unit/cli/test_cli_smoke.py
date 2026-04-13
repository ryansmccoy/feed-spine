"""Smoke tests for all CLI commands referenced in README.

These tests verify that every CLI command advertised in the README
actually exists, accepts the expected arguments, and runs to
completion (or fails gracefully) with in-memory storage.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from feedspine.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── Top-level commands ───────────────────────────────────────────


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "feedspine" in result.stdout


def test_info(runner: CliRunner) -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "FeedSpine" in result.stdout


# ── feeds ────────────────────────────────────────────────────────


def test_feeds_list_types(runner: CliRunner) -> None:
    """README: `feedspine feeds list-types`"""
    result = runner.invoke(app, ["feeds", "list-types"])
    assert result.exit_code == 0
    assert "adapter" in result.stdout.lower() or "Adapter" in result.stdout


def test_feeds_list_no_config(runner: CliRunner) -> None:
    """README: `feedspine feeds list` — graceful when no config."""
    with patch("feedspine.core.feed_config.find_config_file", return_value=None):
        result = runner.invoke(app, ["feeds", "list"])
    assert result.exit_code == 1
    assert "No feed config" in result.stdout


# ── health ───────────────────────────────────────────────────────


def test_health_summary_empty(runner: CliRunner) -> None:
    """README: `feedspine health summary` — empty storage."""
    mock_result = type("R", (), {"success": True, "data": {"feeds": [], "summary": {}}})()

    with (
        patch("feedspine.cli_modules.health_cmds.get_storage") as mock_storage,
        patch("feedspine.ops.health.fetch_all_feed_health", new_callable=AsyncMock, return_value=mock_result),
    ):
        storage_inst = AsyncMock()
        mock_storage.return_value = storage_inst
        result = runner.invoke(app, ["health", "summary"])

    assert result.exit_code == 0


def test_health_no_args_shows_help(runner: CliRunner) -> None:
    """`feedspine health` without subcommand shows help."""
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 2
    assert "summary" in result.stdout.lower() or "Usage" in result.stdout


# ── stats ────────────────────────────────────────────────────────


def test_stats_summary_empty(runner: CliRunner) -> None:
    """README: `feedspine stats summary` — empty storage."""
    mock_result = type(
        "R",
        (),
        {"success": True, "data": {"total": 0, "by_layer": {}, "storage_type": "MemoryStorage"}},
    )()

    with (
        patch("feedspine.cli_modules.stats_cmds.get_storage") as mock_storage,
        patch("feedspine.ops.stats.fetch_layer_distribution", new_callable=AsyncMock, return_value=mock_result),
    ):
        storage_inst = AsyncMock()
        mock_storage.return_value = storage_inst
        result = runner.invoke(app, ["stats", "summary"])

    assert result.exit_code == 0


def test_stats_no_args_shows_help(runner: CliRunner) -> None:
    """`feedspine stats` without subcommand shows help."""
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 2
    assert "summary" in result.stdout.lower() or "Usage" in result.stdout


# ── query ────────────────────────────────────────────────────────


def test_query_records_empty(runner: CliRunner) -> None:
    """README: `feedspine query records --limit 10` — empty storage."""
    mock_result = type("R", (), {"success": True, "data": []})()

    with (
        patch("feedspine.cli_modules.shared.get_storage") as mock_storage,
        patch("feedspine.ops.query.fetch_records", new_callable=AsyncMock, return_value=mock_result),
    ):
        storage_inst = AsyncMock()
        mock_storage.return_value = storage_inst
        result = runner.invoke(app, ["query", "records", "--limit", "10"])

    assert result.exit_code == 0


def test_query_no_args_shows_help(runner: CliRunner) -> None:
    """`feedspine query` without subcommand shows help."""
    result = runner.invoke(app, ["query"])
    assert result.exit_code == 2


# ── export ───────────────────────────────────────────────────────


def test_export_json_empty(runner: CliRunner, tmp_path: object) -> None:
    """README: `feedspine export json output.json` — empty storage."""
    import pathlib

    out = pathlib.Path(str(tmp_path)) / "output.json"
    mock_result = type("R", (), {"success": True, "data": {"count": 0, "path": str(out)}})()

    with (
        patch("feedspine.cli_modules.shared.get_storage") as mock_storage,
        patch("feedspine.ops.export.export_to_json", new_callable=AsyncMock, return_value=mock_result),
    ):
        storage_inst = AsyncMock()
        mock_storage.return_value = storage_inst
        result = runner.invoke(app, ["export", "json", str(out)])

    assert result.exit_code == 0
    assert "Exported" in result.stdout


def test_export_no_args_shows_help(runner: CliRunner) -> None:
    """`feedspine export` without subcommand shows help."""
    result = runner.invoke(app, ["export"])
    assert result.exit_code == 2


# ── collect ──────────────────────────────────────────────────────


def test_collect_run_no_config(runner: CliRunner) -> None:
    """README: `feedspine collect run --feed news` — no config file."""
    with patch("feedspine.core.feed_config.find_config_file", return_value=None):
        result = runner.invoke(app, ["collect", "run"])
    assert result.exit_code == 1
    assert "No feeds.yaml" in result.stdout


def test_collect_no_args_shows_help(runner: CliRunner) -> None:
    """`feedspine collect` without subcommand shows help."""
    result = runner.invoke(app, ["collect"])
    assert result.exit_code == 2
    assert "run" in result.stdout.lower()


# ── Subcommand existence checks ──────────────────────────────────


@pytest.mark.parametrize(
    "subcommand,expected_subcommands",
    [
        (["health", "--help"], ["summary"]),
        (["stats", "--help"], ["summary", "feeds"]),
        (["query", "--help"], ["records", "search"]),
        (["export", "--help"], ["json", "csv"]),
        (["collect", "--help"], ["run"]),
        (["feeds", "--help"], ["list-types", "list"]),
    ],
)
def test_subcommand_help_lists_commands(
    runner: CliRunner,
    subcommand: list[str],
    expected_subcommands: list[str],
) -> None:
    """Verify every sub-app advertises its subcommands in --help."""
    result = runner.invoke(app, subcommand)
    assert result.exit_code == 0
    for cmd in expected_subcommands:
        assert cmd in result.stdout, f"Expected '{cmd}' in {subcommand} help output"
