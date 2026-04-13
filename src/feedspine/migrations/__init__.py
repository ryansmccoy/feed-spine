"""Programmatic Alembic migration runner.

Allows feedspine to run migrations at startup when auto_migrate=True
on the StorageOptions. For raw SQL backends (SQLite, DuckDB), schema
is always auto-created via _create_schema(). This module is for
SQLAlchemy-based backends (PostgreSQL, TimescaleDB).

Usage:
    from feedspine.migrations import run_migrations

    # Run all pending migrations
    run_migrations("postgresql://localhost/feedspine")

    # Check current revision
    from feedspine.migrations import get_current_revision
    rev = get_current_revision("postgresql://localhost/feedspine")
"""

from __future__ import annotations

from pathlib import Path

from spine.core.logging import get_logger

logger = get_logger(__name__)

# Path to this migrations package (contains env.py and versions/)
MIGRATIONS_DIR = Path(__file__).parent


def run_migrations(database_url: str) -> None:
    """Run all pending Alembic migrations.

    Args:
        database_url: SQLAlchemy connection string.

    Raises:
        ImportError: If alembic is not installed (install feedspine[sqlalchemy]).
    """
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        logger.warning("alembic not installed — skipping auto-migrate. Install with: pip install feedspine[sqlalchemy]")
        return

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    logger.info("Running database migrations...")
    command.upgrade(alembic_cfg, "head")
    logger.info("Migrations complete.")


def get_current_revision(database_url: str) -> str | None:
    """Get the current Alembic revision for this database.

    Args:
        database_url: SQLAlchemy connection string.

    Returns:
        Current revision string, or None if no migrations applied.
    """
    try:
        from alembic.config import Config
    except ImportError:
        return None

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    with engine.connect() as conn:
        from alembic.migration import MigrationContext

        context = MigrationContext.configure(conn)
        return context.get_current_revision()
