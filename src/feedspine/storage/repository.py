"""Base repository with dialect-aware database access.

Provides :class:`BaseRepository` — a base class that pairs a
:class:`Connection` protocol with a :class:`Dialect` so that domain
repositories can write **portable** SQL without referencing any specific
database driver.

Also provides :class:`SAConnectionBridge` that adapts a SQLAlchemy
``Session`` to the ``Connection`` protocol, enabling ORM sessions to
be used with the same repository helpers.

Architecture::

    ┌────────────────────────────────────────────────────────────────────┐
    │                       BaseRepository                               │
    │                                                                    │
    │   conn: Connection        ← protocol (sqlite3, SA bridge, etc.)    │
    │   dialect: Dialect         ← from feedspine.storage.dialect         │
    │                                                                    │
    │   execute(sql, params)     → cursor                                │
    │   query(sql, params)       → list[dict]                            │
    │   query_one(sql, params)   → dict | None                           │
    │   insert(table, data)      → cursor                                │
    │   insert_many(table, rows) → int                                   │
    └────────────────────────────────────────────────────────────────────┘

Pattern:
    Follows spine-core's BaseRepository + SAConnectionBridge pattern
    (spine.data.repository, spine.core.orm.session) adapted for
    feedspine's domain.

Usage:
    >>> class FeedRepo(BaseRepository):
    ...     def get_by_id(self, record_id: str):
    ...         return self.query_one(
    ...             f"SELECT * FROM records WHERE id = {self.ph(1)}",
    ...             (record_id,),
    ...         )

Tags:
    repository, database, abstraction, portability
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from feedspine.storage.dialect import Dialect, SQLiteDialect

# Valid SQL identifier — letters, digits, underscores only
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# =========================================================================
# Connection Protocol
# =========================================================================


@runtime_checkable
class Connection(Protocol):
    """Minimal synchronous connection interface for database operations.

    This is the canonical definition for feedspine storage.  Any object
    that satisfies this protocol (``sqlite3.Connection``, SAConnectionBridge,
    etc.) can be used with :class:`BaseRepository`.
    """

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> Any:
        """Execute a single SQL statement."""
        ...

    def executemany(self, sql: str, seq_of_parameters: Sequence[Sequence[Any]]) -> Any:
        """Execute a statement with multiple parameter sets."""
        ...

    def commit(self) -> None:
        """Commit the current transaction."""
        ...


# =========================================================================
# SQLAlchemy Connection Bridge
# =========================================================================


class SAConnectionBridge:
    """Adapter that makes a SQLAlchemy ``Session`` look like :class:`Connection`.

    This lets callers that depend on the ``Connection`` protocol re-use
    the same ORM session when mixing raw-SQL writes with ORM operations.

    The bridge rewrites ``?`` placeholders (used by SQLite dialect) to
    ``:p0, :p1`` named parameters required by SQLAlchemy's ``text()``.

    Example::

        from sqlalchemy.orm import Session
        from feedspine.storage.repository import SAConnectionBridge, BaseRepository

        with Session(engine) as session:
            bridge = SAConnectionBridge(session)
            repo = BaseRepository(conn=bridge)
            repo.insert("records", {"id": "1", "natural_key": "test"})
            repo.commit()
    """

    def __init__(self, session: Any) -> None:
        self._session = session
        self._last_result: Any = None

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> SAConnectionBridge:
        """Execute SQL through the SA session, rewriting ``?`` or ``%s`` → ``:pN``."""
        import re

        from sqlalchemy import text

        if parameters:
            # Rewrite ? or %s placeholders to :p0, :p1, ... for SA text()
            # SQLite uses ?, PostgreSQL uses %s
            idx = 0

            def replacer(match: re.Match[str]) -> str:
                nonlocal idx
                result = f":p{idx}"
                idx += 1
                return result

            rewritten_sql = re.sub(r"\?|%s", replacer, sql)
            stmt = text(rewritten_sql)
            mapping = {f"p{i}": v for i, v in enumerate(parameters)}
            self._last_result = self._session.execute(stmt, mapping)
        else:
            self._last_result = self._session.execute(text(sql))
        return self

    def executemany(self, sql: str, seq_of_parameters: Sequence[Sequence[Any]]) -> None:
        """Execute a statement with multiple parameter sets."""
        for params in seq_of_parameters:
            self.execute(sql, params)

    def fetchone(self) -> tuple[Any, ...] | None:
        """Fetch one row from the last result."""
        if self._last_result is None:
            return None
        row = self._last_result.fetchone()
        return tuple(row) if row is not None else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Fetch all rows from the last result."""
        if self._last_result is None:
            return []
        return [tuple(r) for r in self._last_result.fetchall()]

    def commit(self) -> None:
        """Commit the current transaction."""
        self._session.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self._session.rollback()

    @property
    def description(self) -> list[tuple[str, ...]] | None:
        """DB-API 2.0 compatible description from the last result.

        Returns a list of (column_name, ...) tuples that
        :class:`BaseRepository` uses to build dicts from rows.
        """
        if self._last_result is None:
            return None
        keys = list(self._last_result.keys())
        return [(k, None, None, None, None, None, None) for k in keys]

    @property
    def session(self) -> Any:
        """Access the underlying SA session (e.g., for ORM queries)."""
        return self._session


# =========================================================================
# Base Repository
# =========================================================================


class BaseRepository:
    """Dialect-aware base class for data-access repositories.

    Subclasses gain portable helper methods for building and executing
    SQL.  The :attr:`dialect` determines placeholder style, timestamp
    functions, and DML syntax.

    Parameters:
        conn: Any object satisfying the :class:`Connection` protocol.
        dialect: SQL dialect to use.  Defaults to :class:`SQLiteDialect`.
    """

    def __init__(self, conn: Connection, dialect: Dialect | None = None) -> None:
        self.conn = conn
        self.dialect: Dialect = dialect or SQLiteDialect()

    @classmethod
    def from_session(
        cls,
        session: Any,
        dialect: Dialect | None = None,
        **kwargs: Any,
    ) -> BaseRepository:
        """Create a repository backed by a SQLAlchemy ORM session.

        Wraps *session* in :class:`SAConnectionBridge` so that the same
        ``Connection``-based helpers work transparently over an ORM session.

        Parameters:
            session: A ``sqlalchemy.orm.Session`` instance.
            dialect: SQL dialect.  Defaults to :class:`SQLiteDialect`.
            **kwargs: Forwarded to the subclass constructor.

        Returns:
            A repository instance whose :attr:`conn` is the bridge adapter.

        Example::

            from sqlalchemy.orm import Session
            from feedspine.storage.repository import BaseRepository

            with Session(engine) as session:
                repo = BaseRepository.from_session(session)
                repo.insert("records", {"id": "1", "natural_key": "x"})
                repo.commit()
        """
        bridge = SAConnectionBridge(session)
        return cls(conn=bridge, dialect=dialect, **kwargs)  # type: ignore[arg-type]

    # -- Convenience shortcuts ---------------------------------------------

    def ph(self, count: int) -> str:
        """Shortcut for ``self.dialect.placeholders(count)``.

        Embed directly in f-strings::

            f"SELECT * FROM t WHERE id = {self.ph(1)}"
        """
        return self.dialect.placeholders(count)

    # -- Query helpers -----------------------------------------------------

    def execute(self, sql: str, params: tuple = ()) -> Any:
        """Execute a statement and return the raw cursor/result."""
        return self.conn.execute(sql, params)

    def execute_many(self, sql: str, params: list[tuple]) -> Any:
        """Execute a statement with multiple parameter sets."""
        return self.conn.executemany(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute a SELECT and return rows as dicts.

        Uses ``cursor.description`` (DB-API 2.0) to extract column names.
        Falls back to ``dict(row)`` for row-factory cursors.
        """
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        if not rows:
            return []

        # Try dict(row) first — works with sqlite3.Row and DictCursor
        try:
            return [dict(row) for row in rows]
        except (TypeError, ValueError):
            pass

        # Fallback: use cursor.description
        if hasattr(cursor, "description") and cursor.description:
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in rows]

        # Last resort: integer-keyed dicts
        return [{i: v for i, v in enumerate(row)} for row in rows]

    def query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """Execute a SELECT and return the first row as a dict (or None)."""
        results = self.query(sql, params)
        return results[0] if results else None

    # -- Insert helpers ----------------------------------------------------

    def insert(self, table: str, data: dict[str, Any]) -> Any:
        """Insert a single row from a dict.

        Column names come from ``data.keys()``; values are bound via
        dialect placeholders.
        """
        if not _SAFE_IDENTIFIER_RE.match(table):
            raise ValueError(f"Invalid table name: {table!r}")
        columns = list(data.keys())
        for col in columns:
            if not _SAFE_IDENTIFIER_RE.match(col):
                raise ValueError(f"Invalid column name: {col!r}")
        values = list(data.values())
        ph = self.dialect.placeholders(len(values))
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({ph})"
        return self.conn.execute(sql, tuple(values))

    def insert_many(self, table: str, rows: list[dict[str, Any]]) -> int:
        """Insert multiple rows from a list of dicts.

        Returns the number of rows inserted.
        """
        if not rows:
            return 0

        if not _SAFE_IDENTIFIER_RE.match(table):
            raise ValueError(f"Invalid table name: {table!r}")
        columns = list(rows[0].keys())
        for col in columns:
            if not _SAFE_IDENTIFIER_RE.match(col):
                raise ValueError(f"Invalid column name: {col!r}")
        ph = self.dialect.placeholders(len(columns))
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({ph})"
        params = [tuple(row[col] for col in columns) for row in rows]
        self.conn.executemany(sql, params)
        return len(rows)

    def commit(self) -> None:
        """Commit the current transaction."""
        self.conn.commit()


__all__ = [
    "BaseRepository",
    "Connection",
    "SAConnectionBridge",
]
