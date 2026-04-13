"""Minimal get_logger compatible with spine-core's interface.

Delegates to ``structlog.get_logger`` when structlog is available,
otherwise falls back to the standard-library ``logging`` module with a
thin adapter that accepts (and discards) structlog-style ``**kwargs``.
"""

from __future__ import annotations

import logging
from typing import Any


class _StdlibAdapter:
    """Wraps :class:`logging.Logger` so callers can pass ``**kwargs``."""

    def __init__(self, logger: logging.Logger) -> None:
        self._log = logger

    # --- public logging methods ---
    def debug(self, event: str | None = None, *args: Any, **kw: Any) -> None:
        self._log.debug(event, *args)

    def info(self, event: str | None = None, *args: Any, **kw: Any) -> None:
        self._log.info(event, *args)

    def warning(self, event: str | None = None, *args: Any, **kw: Any) -> None:
        self._log.warning(event, *args)

    warn = warning

    def error(self, event: str | None = None, *args: Any, **kw: Any) -> None:
        self._log.error(event, *args)

    def exception(self, event: str | None = None, *args: Any, **kw: Any) -> None:
        self._log.exception(event, *args)

    def critical(self, event: str | None = None, *args: Any, **kw: Any) -> None:
        self._log.critical(event, *args)

    fatal = critical

    # --- structlog-style context methods (no-op) ---
    def bind(self, **kw: Any) -> _StdlibAdapter:
        return self

    def unbind(self, *keys: str) -> _StdlibAdapter:
        return self

    def new(self, **kw: Any) -> _StdlibAdapter:
        return self


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger if available, else a stdlib adapter."""
    try:
        import structlog

        return structlog.get_logger(name)
    except ImportError:
        return _StdlibAdapter(logging.getLogger(name))
