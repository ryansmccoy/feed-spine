"""Tests for feedspine.cli_modules.util_cmds."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from feedspine.cli_modules.util_cmds import config_app


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


def test_config_show_masks_urls(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """`config show` should print config and mask URL-like values."""
    monkeypatch.setenv("FEEDSPINE_DATABASE_URL", "postgresql://user:password@localhost:5432/feedspine")
    monkeypatch.setenv("FEEDSPINE_STORAGE", "postgresql")

    result = cli_runner.invoke(config_app, ["show"])

    assert result.exit_code == 0
    assert "FEEDSPINE_DATABASE_URL" in result.stdout
    assert "postgresql://" in result.stdout
    assert "password" not in result.stdout


def test_config_validate_success(cli_runner: CliRunner) -> None:
    """`config validate` should succeed when storage initialize/count works."""
    storage = AsyncMock()
    storage.count.return_value = 123

    with patch("feedspine.cli_modules.shared.get_storage", return_value=storage):
        result = cli_runner.invoke(config_app, ["validate"])

    assert result.exit_code == 0
    assert "Storage connection valid" in result.stdout
    storage.initialize.assert_awaited_once()
    storage.count.assert_awaited_once()
    storage.close.assert_awaited_once()


def test_config_validate_failure(cli_runner: CliRunner) -> None:
    """`config validate` should exit non-zero when connection fails."""
    storage = AsyncMock()
    storage.initialize.side_effect = RuntimeError("boom")

    with patch("feedspine.cli_modules.shared.get_storage", return_value=storage):
        result = cli_runner.invoke(config_app, ["validate"])

    assert result.exit_code == 1
    assert "Storage connection failed" in result.stdout
