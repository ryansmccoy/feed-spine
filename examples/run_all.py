#!/usr/bin/env python3
"""Run all feedspine examples and verify they work.

Uses the :class:`ExampleRegistry` to auto-discover examples from numbered
subdirectories — no hardcoded list required.

Run: python examples/run_all.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from _registry import ExampleRegistry

REPO_ROOT = Path(__file__).resolve().parent.parent


def _normalize_stream(text: str | bytes | None) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        return text.decode("utf-8", errors="replace")
    return text


def _safe_log_name(name: str) -> str:
    return name.replace("/", "__").replace("\\", "__").replace(" ", "_")


def _create_log_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = REPO_ROOT / "logs" / "examples" / timestamp
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _print_output_block(label: str, text: str) -> None:
    if not text.strip():
        return
    print(f"\n{label}:")
    print(text.rstrip())


def _write_example_log(
    log_dir: Path,
    *,
    name: str,
    path: Path,
    status: str,
    returncode: int | None,
    stdout: str,
    stderr: str,
) -> Path:
    log_path = log_dir / f"{_safe_log_name(name)}.log"
    lines = [
        f"name: {name}",
        f"path: {path}",
        f"status: {status}",
        f"returncode: {returncode if returncode is not None else 'n/a'}",
        "",
        "STDOUT",
        "------",
        stdout.rstrip(),
        "",
        "STDERR",
        "------",
        stderr.rstrip(),
        "",
    ]
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path


def run_example(name: str, path: Path, log_dir: Path) -> tuple[bool, Path]:
    """Run a single example and return its success status and log path."""
    print(f"\n{'=' * 60}")
    print(f"Running: {name}")
    print("=" * 60)

    env = os.environ.copy()
    env["FEEDSPINE_DEMO_MODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            cwd=path.parent.parent,
            env=env,
        )
        stdout = _normalize_stream(result.stdout)
        stderr = _normalize_stream(result.stderr)
        status = "PASS" if result.returncode == 0 else "FAIL"
        log_path = _write_example_log(
            log_dir,
            name=name,
            path=path,
            status=status,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
        )
        _print_output_block("STDOUT", stdout)
        _print_output_block("STDERR", stderr)
        print(f"\nLog: {log_path}")
        if result.returncode == 0:
            print("\n[PASS]")
            return True, log_path
        print(f"\n[FAIL] (exit code {result.returncode})")
        return False, log_path

    except subprocess.TimeoutExpired as exc:
        stdout = _normalize_stream(exc.stdout)
        stderr = _normalize_stream(exc.stderr)
        log_path = _write_example_log(
            log_dir,
            name=name,
            path=path,
            status="TIMEOUT",
            returncode=None,
            stdout=stdout,
            stderr=stderr,
        )
        _print_output_block("STDOUT", stdout)
        _print_output_block("STDERR", stderr)
        print(f"\nLog: {log_path}")
        print("\n[FAIL] TIMEOUT (60s)")
        return False, log_path
    except Exception as exc:  # noqa: BLE001
        log_path = _write_example_log(
            log_dir,
            name=name,
            path=path,
            status="ERROR",
            returncode=None,
            stdout="",
            stderr=str(exc),
        )
        print(f"\nLog: {log_path}")
        print(f"\n[FAIL] ERROR: {exc}")
        return False, log_path


def _write_summary(log_dir: Path, results: list[tuple[str, bool, Path]]) -> Path:
    summary_path = log_dir / "summary.txt"
    lines = []
    for name, success, log_path in results:
        status = "PASS" if success else "FAIL"
        lines.append(f"{status}\t{name}\t{log_path.name}")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def main() -> None:
    """Run all examples and report results."""
    print("=" * 60)
    print("FeedSpine Examples Runner")
    print("=" * 60)

    log_dir = _create_log_dir()
    print(f"\nLogs will be written to: {log_dir}")

    registry = ExampleRegistry()
    examples = registry.as_pytest_params()
    print(f"\nDiscovered {len(examples)} examples across {len(registry.categories)} categories:")
    for cat in registry.categories:
        cat_examples = registry.by_category(cat)
        print(f"  [{cat}] ({len(cat_examples)} examples)")
        for ex in cat_examples:
            print(f"    - {ex.title}")

    results: list[tuple[str, bool, Path]] = []
    for name, path in examples:
        success, log_path = run_example(name, path, log_dir)
        results.append((name, success, log_path))

    summary_path = _write_summary(log_dir, results)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed

    for name, success, log_path in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status}: {name} ({log_path.name})")

    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed}")
    print(f"Summary log: {summary_path}")

    if failed > 0:
        sys.exit(1)

    print("\n[OK] All examples passed!")


if __name__ == "__main__":
    main()
