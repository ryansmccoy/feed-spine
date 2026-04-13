"""StorageBackend adapter that delegates to FeedRepository.

Bridges the gap between the async ``StorageBackend`` protocol expected
by the API/CLI layer and the sync ``FeedRepository`` (spine-core pattern).
Manages a SQLAlchemy engine for PostgreSQL or a sqlite3 connection for
SQLite, and for each operation opens a session/connection, creates a
``FeedRepository``, and delegates.

This module uses mixins for operation implementations:
- record_mixins: RecordOperationsMixin, BatchOperationsMixin, VersionControlMixin
- feed_mixins: SightingOperationsMixin, FeedRunOperationsMixin, FeedConfigOperationsMixin,
               ObservationOperationsMixin, StatsOperationsMixin

Tags:
    storage, repository, adapter, backend
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from feedspine._vendor.logging import get_logger

from feedspine.storage.dialect import PostgreSQLDialect, SQLiteDialect
from feedspine.storage.feed_mixins import (
    FeedConfigOperationsMixin,
    FeedRunOperationsMixin,
    ObservationOperationsMixin,
    SightingOperationsMixin,
    StatsOperationsMixin,
)
from feedspine.storage.feed_repository import FeedRepository
from feedspine.storage.record_mixins import (
    BatchOperationsMixin,
    RecordOperationsMixin,
    VersionControlMixin,
)

logger = get_logger(__name__)


class RepositoryStorageBackend(
    RecordOperationsMixin,
    BatchOperationsMixin,
    VersionControlMixin,
    SightingOperationsMixin,
    FeedRunOperationsMixin,
    FeedConfigOperationsMixin,
    ObservationOperationsMixin,
    StatsOperationsMixin,
):
    """StorageBackend implemented via FeedRepository + Dialect.

    Supports both SQLite and PostgreSQL through the Dialect abstraction.
    SQLAlchemy is only imported when a PostgreSQL connection string is used.

    This class implements the same async interface as ``SQLiteStorage`` and
    ``MemoryStorage`` so it satisfies the ``StorageBackend`` protocol.

    Args:
        connection_string: Database URL (``sqlite:///...`` or ``postgresql://...``).
        pool_size: SA connection pool size (PostgreSQL only).
        max_overflow: Extra connections beyond pool_size (PostgreSQL only).
        echo: Log SQL statements (PostgreSQL only).
        use_timescale: Enable TimescaleDB features (PostgreSQL only).
        auto_migrate: Whether to run Alembic migrations on init.
    """

    def __init__(
        self,
        connection_string: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
        echo: bool = False,
        use_timescale: bool = False,
        auto_migrate: bool = False,
    ) -> None:
        self.connection_string = connection_string
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._echo = echo
        self._use_timescale = use_timescale
        self._auto_migrate = auto_migrate

        # Determined at initialize() time
        self._backend: str = "sqlite"
        self._engine: Any = None  # SA Engine (PostgreSQL)
        self._sqlite_conn: sqlite3.Connection | None = None  # SQLite connection
        self._initialized = False

    def _is_postgres(self) -> bool:
        return self.connection_string.startswith(("postgresql://", "postgres://"))

    # -- Lifecycle ---------------------------------------------------------

    async def initialize(self) -> None:
        """Create engine/connection, ensure schema, and optionally migrate."""
        if self._is_postgres():
            self._backend = "postgresql"
            self._init_postgres()
        else:
            self._backend = "sqlite"
            self._init_sqlite()

        # Run Alembic if requested (PostgreSQL only)
        if self._auto_migrate and self._is_postgres():
            try:
                from feedspine.migrations import run_migrations

                run_migrations(self.connection_string)
            except Exception as exc:
                logger.warning("Alembic migration skipped: %s", exc)

        self._initialized = True
        logger.info("RepositoryStorageBackend initialized (backend=%s)", self._backend)

    def _init_postgres(self) -> None:
        """Create a SQLAlchemy engine and ensure schema via FeedRepository."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from sqlalchemy.pool import NullPool, QueuePool

        # Choose pool strategy
        if "pgbouncer" in self.connection_string.lower() or self._pool_size == 0:
            self._engine = create_engine(
                self.connection_string,
                poolclass=NullPool,
                echo=self._echo,
            )
        else:
            self._engine = create_engine(
                self.connection_string,
                poolclass=QueuePool,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                echo=self._echo,
            )

        # Ensure schema
        with Session(self._engine) as session:
            repo = FeedRepository.from_session(session, PostgreSQLDialect())
            repo.ensure_schema()

        # TimescaleDB hypertables
        if self._use_timescale:
            try:
                from feedspine.storage.models import create_timescale_hypertable

                create_timescale_hypertable(self._engine)
                logger.info("TimescaleDB hypertable created")
            except Exception as exc:
                logger.warning("TimescaleDB not available: %s", exc)

    def _init_sqlite(self) -> None:
        """Open a sqlite3 connection and ensure schema via FeedRepository."""
        path = self.connection_string
        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///") :]
        elif path == "memory://":
            path = ":memory:"

        self._sqlite_conn = sqlite3.connect(path, timeout=30.0)
        self._sqlite_conn.row_factory = sqlite3.Row
        self._sqlite_conn.execute("PRAGMA journal_mode=WAL")
        self._sqlite_conn.execute("PRAGMA foreign_keys=ON")

        repo = FeedRepository(self._sqlite_conn, SQLiteDialect())
        repo.ensure_schema()

    async def close(self) -> None:
        """Release resources."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
        if self._sqlite_conn is not None:
            self._sqlite_conn.close()
            self._sqlite_conn = None
        self._initialized = False

    # -- Internal helpers --------------------------------------------------

    @contextmanager
    def _repo(self) -> Iterator[FeedRepository]:
        """Yield a FeedRepository scoped to a transaction.

        For PostgreSQL: opens a SA session, wraps in SAConnectionBridge.
        For SQLite: reuses the persistent sqlite3 connection.
        """
        if self._backend == "postgresql":
            from sqlalchemy.orm import Session

            with Session(self._engine) as session:
                repo = FeedRepository.from_session(session, PostgreSQLDialect())
                yield repo
                session.commit()
        else:
            if not self._sqlite_conn:
                raise RuntimeError("Storage not initialized. Call initialize() first.")
            repo = FeedRepository(self._sqlite_conn, SQLiteDialect())
            yield repo
            repo.commit()


__all__ = [
    "RepositoryStorageBackend",
]
