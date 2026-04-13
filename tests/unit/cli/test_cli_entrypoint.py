"""Tests for feedspine.cli top-level commands."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from feedspine.cli import app


def test_version_command() -> None:
    """`feedspine version` should print the package version."""
    runner = CliRunner()

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert re.search(r"feedspine\s+\d+\.\d+\.\d+", result.stdout)


def test_info_command() -> None:
    """`feedspine info` should print app and Python info."""
    runner = CliRunner()

    result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    assert "FeedSpine" in result.stdout
    assert "Python" in result.stdout
