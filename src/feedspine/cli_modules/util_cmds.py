"""Configuration management CLI commands.

Provides commands for viewing and validating configuration.
"""

from __future__ import annotations

import os

import typer

from feedspine.cli_modules.shared import console

config_app = typer.Typer(name="config", help="Configuration management", no_args_is_help=True)


@config_app.command("show")
def config_show() -> None:
    """Show current configuration from environment variables.

    Displays all FEEDSPINE_* environment variables and their values,
    with sensitive values masked.
    """
    from rich.table import Table

    env_vars = {
        "FEEDSPINE_DATABASE_URL": "Storage connection string",
        "FEEDSPINE_STORAGE": "Storage backend type",
        "FEEDSPINE_STORAGE_CONNECTION": "Storage connection (API default)",
        "FEEDSPINE_DATA_DIR": "Data directory for file storage",
        "FEEDSPINE_CORS_ORIGINS": "Allowed CORS origins (comma-separated)",
        "FEEDSPINE_POOL_SIZE": "Database connection pool size",
        "FEEDSPINE_BATCH_SIZE": "Batch size for bulk operations",
        "FEEDSPINE_USE_TIMESCALE": "Enable TimescaleDB extensions",
        "FEEDSPINE_ENV": "Environment (development/production/test)",
        "DATABASE_URL": "Fallback database URL",
    }

    table = Table(title="FeedSpine Configuration")
    table.add_column("Variable", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Description", style="dim")

    for var, desc in env_vars.items():
        value = os.environ.get(var, "")
        if not value:
            display = "[dim]not set[/dim]"
        elif "password" in var.lower() or "url" in var.lower():
            # Mask sensitive values
            if "://" in value:
                parts = value.split("@")
                display = f"{parts[0][:15]}...@{parts[-1]}" if len(parts) > 1 else value[:20] + "..."
            else:
                display = value[:5] + "..." if len(value) > 5 else value
        else:
            display = value
        table.add_row(var, display, desc)

    console.print(table)


@config_app.command("validate")
def config_validate() -> None:
    """Validate storage configuration by testing connection."""
    from feedspine.cli_modules.shared import async_command, get_storage

    @async_command
    async def _validate() -> None:
        try:
            storage = get_storage()
            await storage.initialize()
            count = await storage.count()
            await storage.close()
            console.print(f"[green]✓ Storage connection valid[/green] ({count:,} records)")
        except Exception as e:
            console.print(f"[red]✗ Storage connection failed: {e}[/red]")
            raise typer.Exit(code=1) from e

    _validate()


__all__ = ["config_app"]
