#!/usr/bin/env python3
"""
FeedSpine CLI Workflow Execution
================================

Demonstrates running actual FeedSpine CLI commands programmatically
using subprocess. This verifies that CLI entry points are functional.

What You'll Learn:
    1. How to invoke feedspine CLI commands from Python
    2. Key CLI workflows: version, feeds, stats, health, query
    3. Parsing CLI output for automation

Prerequisites:
    pip install feedspine   (or: uv pip install -e .[dev])

Usage:
    python examples/07_cli/02_cli_workflows.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def run_cli(*args: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run a feedspine CLI command and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "-m", "feedspine.cli", *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as exc:
        return -1, "", str(exc)


def show_result(label: str, exit_code: int, stdout: str, stderr: str) -> None:
    """Display a CLI command result."""
    status = "OK" if exit_code == 0 else f"FAIL({exit_code})"
    print(f"\n[{status}] {label}")
    if stdout:
        for line in stdout.split("\n")[:10]:
            print(f"  {line}")
        lines = stdout.split("\n")
        if len(lines) > 10:
            print(f"  ... ({len(lines) - 10} more lines)")
    if stderr and exit_code != 0:
        print(f"  stderr: {stderr[:200]}")


def main() -> None:
    """Execute key FeedSpine CLI commands."""
    print("=" * 60)
    print("  FeedSpine CLI Workflows")
    print("=" * 60)

    # Check feedspine is installed
    if not shutil.which("feedspine") and not _module_available():
        print("\nFeedSpine CLI not found. Install with: pip install feedspine")
        return

    results: list[tuple[str, bool]] = []

    # ---- 1. Version ----
    code, out, err = run_cli("version")
    show_result("feedspine version", code, out, err)
    results.append(("version", code == 0))

    # ---- 2. Help ----
    code, out, err = run_cli("--help")
    show_result("feedspine --help", code, out, err)
    results.append(("--help", code == 0))

    # ---- 3. Feed types ----
    code, out, err = run_cli("feeds", "list-types")
    show_result("feedspine feeds list-types", code, out, err)
    results.append(("feeds list-types", code == 0))

    # ---- 4. Stats summary ----
    code, out, err = run_cli("stats", "summary")
    show_result("feedspine stats summary", code, out, err)
    results.append(("stats summary", code == 0))

    # ---- 5. Health summary ----
    code, out, err = run_cli("health", "summary")
    show_result("feedspine health summary", code, out, err)
    results.append(("health summary", code == 0))

    # ---- 6. Config show ----
    code, out, err = run_cli("config", "show")
    show_result("feedspine config show", code, out, err)
    results.append(("config show", code == 0))

    # ---- Summary ----
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\n  {passed_count}/{len(results)} commands succeeded")
    print("\n  (Some commands may fail without a configured storage backend)")


def _module_available() -> bool:
    """Check if feedspine.cli module is importable."""
    try:
        import feedspine.cli  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
