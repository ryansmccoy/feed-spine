"""Database migration CLI commands.

Provides commands for managing database migrations using Alembic.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Annotated

import typer

from feedspine.cli_modules.shared import console

if TYPE_CHECKING:
    from alembic.config import Config as AlembicConfig

migrate_app = typer.Typer(name="migrate", help="Database migration commands", no_args_is_help=True)


def _get_alembic_config(connection: str | None = None) -> AlembicConfig:
    """Create Alembic config pointing to feedspine migrations."""
    from pathlib import Path

    from alembic.config import Config as AlembicConfig

    # Find alembic.ini relative to feedspine package
    feedspine_root = Path(__file__).parent.parent.parent.parent
    alembic_ini = feedspine_root / "alembic.ini"

    if not alembic_ini.exists():
        console.print(f"[red]Error: alembic.ini not found at {alembic_ini}[/red]")
        raise typer.Exit(1)

    cfg = AlembicConfig(str(alembic_ini))

    # Override connection if provided
    if connection:
        cfg.set_main_option("sqlalchemy.url", connection)
    elif db_url := os.environ.get("FEEDSPINE_DB_URL") or os.environ.get("FEEDSPINE_DATABASE_URL"):
        cfg.set_main_option("sqlalchemy.url", db_url)

    return cfg


@migrate_app.command("status")
def migrate_status(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
) -> None:
    """Show current database migration status.

    Displays the current revision and any pending migrations.
    """
    from alembic.script import ScriptDirectory

    cfg = _get_alembic_config(connection)
    script = ScriptDirectory.from_config(cfg)

    # Get current revision
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    url = cfg.get_main_option("sqlalchemy.url")
    console.print(f"[dim]Database: {url}[/dim]\n")

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

        # Get head revision
        head_rev = script.get_current_head()

        if current_rev is None:
            console.print("[yellow]No migrations applied yet.[/yellow]")
            console.print(f"Head revision: {head_rev}")
            console.print("\nRun [green]feedspine migrate up[/green] to apply migrations.")
        elif current_rev == head_rev:
            console.print("[green]✓ Database is up to date[/green]")
            console.print(f"Current revision: {current_rev}")
        else:
            console.print("[yellow]Database needs migration[/yellow]")
            console.print(f"Current revision: {current_rev}")
            console.print(f"Head revision: {head_rev}")
            console.print("\nRun [green]feedspine migrate up[/green] to apply pending migrations.")

    except Exception as e:
        console.print(f"[red]Error connecting to database: {e}[/red]")
        raise typer.Exit(1) from None


@migrate_app.command("up")
def migrate_up(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    revision: Annotated[
        str,
        typer.Option("--revision", "-r", help="Target revision (default: head)"),
    ] = "head",
) -> None:
    """Apply database migrations.

    Upgrades the database to the specified revision (default: latest).
    """
    from alembic import command

    cfg = _get_alembic_config(connection)
    console.print(f"[blue]Upgrading to revision: {revision}[/blue]")

    try:
        command.upgrade(cfg, revision)
        console.print("[green]✓ Migration completed successfully[/green]")
    except Exception as e:
        console.print(f"[red]Migration failed: {e}[/red]")
        raise typer.Exit(1) from None


@migrate_app.command("down")
def migrate_down(
    connection: Annotated[
        str | None,
        typer.Option("--connection", "-c", help="Storage connection string"),
    ] = None,
    revision: Annotated[
        str,
        typer.Option("--revision", "-r", help="Target revision (default: -1)"),
    ] = "-1",
) -> None:
    """Rollback database migrations.

    Downgrades the database by one revision (or to specified revision).
    """
    from alembic import command

    cfg = _get_alembic_config(connection)
    console.print(f"[yellow]Downgrading to revision: {revision}[/yellow]")

    try:
        command.downgrade(cfg, revision)
        console.print("[green]✓ Downgrade completed successfully[/green]")
    except Exception as e:
        console.print(f"[red]Downgrade failed: {e}[/red]")
        raise typer.Exit(1) from None


@migrate_app.command("history")
def migrate_history(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed revision info"),
    ] = False,
) -> None:
    """Show migration history.

    Lists all available migrations in order.
    """
    from alembic import command

    cfg = _get_alembic_config()

    try:
        command.history(cfg, verbose=verbose)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


@migrate_app.command("init")
def migrate_init() -> None:
    """Initialize the migration system.

    Shows the location of the existing Alembic configuration.
    """
    from pathlib import Path

    migrations_dir = Path(__file__).parent.parent / "migrations"
    versions_dir = migrations_dir / "versions"

    if versions_dir.exists():
        version_files = list(versions_dir.glob("*.py"))
        console.print("[green]✓ Migration system already initialized[/green]")
        console.print(f"\nMigrations directory: {migrations_dir}")
        console.print(f"Existing migrations: {len(version_files)}")
        for vf in sorted(version_files):
            console.print(f"  • {vf.name}")
    else:
        console.print("[yellow]Migrations directory not found.[/yellow]")
        console.print("Run 'alembic init' from the feedspine root directory.")


__all__ = ["migrate_app"]
