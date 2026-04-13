"""SQL dialect abstraction for database-agnostic storage code.

Provides a ``Dialect`` protocol and concrete implementations for SQLite
and PostgreSQL — the two backends FeedSpine supports.

Domain repositories use ``Dialect`` methods to generate SQL fragments
(placeholders, timestamps, upsert logic, JSON functions) without
referencing any specific database driver.

Architecture::

    ┌──────────────────────────────────────────────────────────────────┐
    │                     Dialect Abstraction Layer                     │
    └──────────────────────────────────────────────────────────────────┘

    Domain Code:
    ┌────────────────────────────────────────────────────────────────┐
    │  sql = f"INSERT INTO t (a,b) VALUES ({d.placeholders(2)})"    │
    │  sql += f" WHERE ts > {d.now()}"                               │
    │  conn.execute(sql, params)                                     │
    └────────────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────┐ ┌──────────────┐
    │ SQLite   │ │ PostgreSQL   │
    │ ?, ?, ?  │ │ %s, %s, %s   │
    │ datetime │ │ NOW()        │
    └──────────┘ └──────────────┘

Pattern:
    Follows spine-core's Dialect protocol (spine.infra.dialect) adapted
    for feedspine's two-backend scope (SQLite + PostgreSQL).

Usage:
    >>> from feedspine.storage.dialect import get_dialect, SQLiteDialect
    >>> d = SQLiteDialect()
    >>> d.placeholders(3)
    '?, ?, ?'
    >>> d.now()
    "datetime('now')"

Tags:
    dialect, sql, abstraction, portability, database
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

# Valid SQL identifier — letters, digits, underscores only
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
# Allowed time units for interval()
_ALLOWED_INTERVAL_UNITS = frozenset({"seconds", "minutes", "hours", "days", "weeks", "months", "years"})


@runtime_checkable
class Dialect(Protocol):
    """SQL dialect contract.

    Every method returns a **SQL fragment** (string) valid for the target
    database.  Domain code interpolates these fragments into SQL templates,
    keeping all dialect-specific syntax out of business logic.
    """

    @property
    def name(self) -> str:
        """Human-readable dialect name (e.g. ``'sqlite'``)."""
        ...

    # -- Placeholder generation --------------------------------------------

    def placeholder(self, index: int) -> str:
        """Single positional placeholder (0-based index)."""
        ...

    def placeholders(self, count: int) -> str:
        """Comma-separated placeholder list.

        >>> dialect.placeholders(3)
        '?, ?, ?'          # SQLite
        '%s, %s, %s'       # PostgreSQL
        """
        ...

    # -- Timestamp expressions ---------------------------------------------

    def now(self) -> str:
        """SQL expression for current UTC timestamp."""
        ...

    def interval(self, value: int, unit: str) -> str:
        """SQL expression for date/time arithmetic."""
        ...

    # -- DML helpers -------------------------------------------------------

    def insert_or_ignore(self, table: str, columns: list[str]) -> str:
        """INSERT … ON CONFLICT DO NOTHING (or equivalent)."""
        ...

    def upsert(
        self,
        table: str,
        columns: list[str],
        key_columns: list[str],
    ) -> str:
        """INSERT … ON CONFLICT (keys) DO UPDATE SET …"""
        ...

    # -- JSON helpers ------------------------------------------------------

    def json_set(self, column: str, path: str, param_placeholder: str) -> str:
        """SQL fragment to set a value inside a JSON column."""
        ...

    # -- DDL helpers -------------------------------------------------------

    def auto_increment(self) -> str:
        """DDL fragment for auto-incrementing primary key type."""
        ...

    def timestamp_default_now(self) -> str:
        """DDL DEFAULT clause for a timestamp column."""
        ...

    def boolean_true(self) -> str:
        """Literal SQL value for boolean True."""
        ...

    def boolean_false(self) -> str:
        """Literal SQL value for boolean False."""
        ...

    def table_exists_query(self) -> str:
        """SQL query that returns rows if a given table exists."""
        ...


# =========================================================================
# Concrete Implementations
# =========================================================================


class SQLiteDialect:
    """SQLite dialect — ``?`` placeholders, ``datetime('now')``."""

    @property
    def name(self) -> str:
        return "sqlite"

    def placeholder(self, index: int) -> str:  # noqa: ARG002
        return "?"

    def placeholders(self, count: int) -> str:
        return ", ".join("?" for _ in range(count))

    def now(self) -> str:
        return "datetime('now')"

    def interval(self, value: int, unit: str) -> str:
        if unit not in _ALLOWED_INTERVAL_UNITS:
            raise ValueError(f"Invalid interval unit: {unit!r}")
        return f"datetime('now', '{int(value)} {unit}')"

    def insert_or_ignore(self, table: str, columns: list[str]) -> str:
        if not _SAFE_IDENTIFIER_RE.match(table):
            raise ValueError(f"Invalid table name: {table!r}")
        for col in columns:
            if not _SAFE_IDENTIFIER_RE.match(col):
                raise ValueError(f"Invalid column name: {col!r}")
        cols = ", ".join(columns)
        ph = self.placeholders(len(columns))
        return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({ph})"

    def upsert(self, table: str, columns: list[str], key_columns: list[str]) -> str:
        if not _SAFE_IDENTIFIER_RE.match(table):
            raise ValueError(f"Invalid table name: {table!r}")
        for col in columns + key_columns:
            if not _SAFE_IDENTIFIER_RE.match(col):
                raise ValueError(f"Invalid column name: {col!r}")
        cols = ", ".join(columns)
        ph = self.placeholders(len(columns))
        keys = ", ".join(key_columns)
        update_cols = [c for c in columns if c not in key_columns]
        updates = ", ".join(f"{c} = excluded.{c}" for c in update_cols)
        return f"INSERT INTO {table} ({cols}) VALUES ({ph}) ON CONFLICT ({keys}) DO UPDATE SET {updates}"

    def json_set(self, column: str, path: str, param_placeholder: str) -> str:
        if not _SAFE_IDENTIFIER_RE.match(column):
            raise ValueError(f"Invalid column name: {column!r}")
        if not re.match(r"^\$?(\.[a-zA-Z_][a-zA-Z0-9_]*)+$", path) and not re.match(
            r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$", path
        ):
            raise ValueError(f"Invalid JSON path: {path!r}")
        return f"json_set(COALESCE({column}, '{{}}'), '{path}', {param_placeholder})"

    def auto_increment(self) -> str:
        return "INTEGER PRIMARY KEY AUTOINCREMENT"

    def timestamp_default_now(self) -> str:
        return "DEFAULT (datetime('now'))"

    def boolean_true(self) -> str:
        return "1"

    def boolean_false(self) -> str:
        return "0"

    def table_exists_query(self) -> str:
        return "SELECT name FROM sqlite_master WHERE type='table' AND name = ?"


class PostgreSQLDialect:
    """PostgreSQL dialect — ``%s`` placeholders, ``NOW()``."""

    @property
    def name(self) -> str:
        return "postgresql"

    def placeholder(self, index: int) -> str:  # noqa: ARG002
        return "%s"

    def placeholders(self, count: int) -> str:
        return ", ".join("%s" for _ in range(count))

    def now(self) -> str:
        return "NOW()"

    def interval(self, value: int, unit: str) -> str:
        if unit not in _ALLOWED_INTERVAL_UNITS:
            raise ValueError(f"Invalid interval unit: {unit!r}")
        if value < 0:
            return f"NOW() - INTERVAL '{abs(int(value))} {unit}'"
        return f"NOW() + INTERVAL '{int(value)} {unit}'"

    def insert_or_ignore(self, table: str, columns: list[str]) -> str:
        if not _SAFE_IDENTIFIER_RE.match(table):
            raise ValueError(f"Invalid table name: {table!r}")
        for col in columns:
            if not _SAFE_IDENTIFIER_RE.match(col):
                raise ValueError(f"Invalid column name: {col!r}")
        cols = ", ".join(columns)
        ph = self.placeholders(len(columns))
        return f"INSERT INTO {table} ({cols}) VALUES ({ph}) ON CONFLICT DO NOTHING"

    def upsert(self, table: str, columns: list[str], key_columns: list[str]) -> str:
        if not _SAFE_IDENTIFIER_RE.match(table):
            raise ValueError(f"Invalid table name: {table!r}")
        for col in columns + key_columns:
            if not _SAFE_IDENTIFIER_RE.match(col):
                raise ValueError(f"Invalid column name: {col!r}")
        cols = ", ".join(columns)
        ph = self.placeholders(len(columns))
        keys = ", ".join(key_columns)
        update_cols = [c for c in columns if c not in key_columns]
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        return f"INSERT INTO {table} ({cols}) VALUES ({ph}) ON CONFLICT ({keys}) DO UPDATE SET {updates}"

    def json_set(self, column: str, path: str, param_placeholder: str) -> str:
        if not _SAFE_IDENTIFIER_RE.match(column):
            raise ValueError(f"Invalid column name: {column!r}")
        pg_path = path.lstrip("$.")
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$", pg_path):
            raise ValueError(f"Invalid JSON path: {path!r}")
        return (
            f"jsonb_set(COALESCE({column}::jsonb, '{{}}'::jsonb), '{{{pg_path}}}', to_jsonb({param_placeholder}::text))"
        )

    def auto_increment(self) -> str:
        return "SERIAL PRIMARY KEY"

    def timestamp_default_now(self) -> str:
        return "DEFAULT NOW()"

    def boolean_true(self) -> str:
        return "TRUE"

    def boolean_false(self) -> str:
        return "FALSE"

    def table_exists_query(self) -> str:
        return "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s"


def get_dialect(backend: str) -> Dialect:
    """Get a Dialect instance for the given backend name.

    Args:
        backend: One of 'sqlite', 'postgresql'

    Returns:
        Dialect instance

    Raises:
        ValueError: If the backend is not supported

    Example:
        >>> d = get_dialect("sqlite")
        >>> d.placeholders(2)
        '?, ?'
    """
    dialects: dict[str, type[SQLiteDialect] | type[PostgreSQLDialect]] = {
        "sqlite": SQLiteDialect,
        "postgresql": PostgreSQLDialect,
        "postgres": PostgreSQLDialect,
    }
    cls = dialects.get(backend)
    if cls is None:
        raise ValueError(f"Unsupported dialect: {backend!r}. Choose from: {sorted(dialects)}")
    return cls()


__all__ = [
    "Dialect",
    "SQLiteDialect",
    "PostgreSQLDialect",
    "get_dialect",
]
