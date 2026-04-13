"""Example auto-discovery registry.

Adapts the filesystem convention (numbered dirs + numbered scripts with
docstrings) into a typed, queryable catalog.  No example files need
modification - the registry reads metadata from the filesystem and
module docstrings.

Usage::

    from ._registry import registry

    # All examples, auto-discovered
    for ex in registry.examples:
        print(ex.category, ex.name, ex.title)

"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_NUM_PREFIX = re.compile(r"^(\d+)_")


@dataclass(frozen=True, slots=True)
class ExampleInfo:
    """Metadata for a single example script."""

    category: str
    name: str
    path: Path
    title: str = ""
    description: str = ""
    order: int = 0
    requires_target: bool = False


def _extract_docstring(path: Path) -> tuple[str, str]:
    """Extract the module docstring from a Python file via AST.

    Returns ``(first_line, full_docstring)``; both empty on failure.
    """
    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
        docstring = ast.get_docstring(tree)
        if docstring:
            first_line = docstring.strip().split("\n")[0].strip()
            return first_line, docstring.strip()
    except Exception:
        pass
    return "", ""


class ExampleRegistry:
    """Auto-discovers examples from a root directory.

    This is a local copy of the spine-core ExampleRegistry pattern.
    Keep in sync with ``spine-core/src/spine/operations/examples/registry.py``.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            root = Path(__file__).parent
        self._root = Path(root).resolve()
        self._examples: list[ExampleInfo] | None = None

    @property
    def root(self) -> Path:
        return self._root

    @property
    def examples(self) -> list[ExampleInfo]:
        """All discovered examples, sorted by category then order."""
        if self._examples is None:
            self._examples = list(self._discover())
        return self._examples

    @property
    def categories(self) -> list[str]:
        """Sorted unique category names."""
        seen: dict[str, None] = {}
        for ex in self.examples:
            seen.setdefault(ex.category, None)
        return list(seen)

    def by_category(self, category: str) -> list[ExampleInfo]:
        """Return examples in a single category."""
        return [e for e in self.examples if e.category == category]

    def as_pytest_params(self) -> list[tuple[str, Path]]:
        """Return ``(name, path)`` tuples for ``@pytest.mark.parametrize``."""
        return [(e.name, e.path) for e in self.examples]

    def refresh(self) -> None:
        """Force re-discovery."""
        self._examples = None

    def _discover(self) -> Iterator[ExampleInfo]:
        """Walk numbered subdirectories and yield ExampleInfo."""
        if not self._root.exists() or not self._root.is_dir():
            return

        category_dirs = sorted(d for d in self._root.iterdir() if d.is_dir() and _NUM_PREFIX.match(d.name))

        for cat_dir in category_dirs:
            py_files = sorted(f for f in cat_dir.glob("*.py") if f.name != "__init__.py" and not f.name.startswith("_"))
            for py_file in py_files:
                yield self._build_info(cat_dir.name, py_file)

    def _build_info(self, category: str, path: Path) -> ExampleInfo:
        """Build ExampleInfo for a single file."""
        stem = path.stem
        m = _NUM_PREFIX.match(stem)
        order = int(m.group(1)) if m else 0

        title, description = _extract_docstring(path)
        if not title:
            title = stem.replace("_", " ").strip()

        try:
            content = path.read_text(encoding="utf-8")
            requires_target = "TARGET_DIR" in content or "get_target" in content
        except Exception:
            requires_target = False

        return ExampleInfo(
            category=category,
            name=f"{category}/{stem}",
            path=path,
            title=title,
            description=description,
            order=order,
            requires_target=requires_target,
        )

    def run_example(
        self,
        example: ExampleInfo,
        target_dir: Path | None = None,
        timeout: int = 120,
    ) -> tuple[bool, str]:
        """Run a single example and return (success, output)."""
        env = os.environ.copy()
        if target_dir:
            env["TARGET_DIR"] = str(target_dir)

        src_dir = self._root.parent / "src"
        existing_pythonpath = env.get("PYTHONPATH", "")
        if existing_pythonpath:
            env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pythonpath}"
        else:
            env["PYTHONPATH"] = str(src_dir)

        try:
            result = subprocess.run(
                [sys.executable, str(example.path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=self._root,
                env=env,
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"[TIMEOUT after {timeout}s]"
        except Exception as e:
            return False, f"[ERROR: {e}]"

    def run_all(
        self,
        target_dir: Path | None = None,
        categories: list[str] | None = None,
    ) -> list[tuple[ExampleInfo, bool, str]]:
        """Run all examples and return results."""
        results = []
        for ex in self.examples:
            if categories and ex.category not in categories:
                continue
            if ex.requires_target and not target_dir:
                results.append((ex, True, "[SKIPPED - requires target dir]"))
                continue
            success, output = self.run_example(ex, target_dir)
            results.append((ex, success, output))
        return results

    def __len__(self) -> int:
        return len(self.examples)

    def __iter__(self) -> Iterator[ExampleInfo]:
        return iter(self.examples)

    def __repr__(self) -> str:
        return f"ExampleRegistry(root={self._root!r}, categories={len(self.categories)}, examples={len(self)})"


# Module-level registry instance pointing to this directory
registry = ExampleRegistry()
