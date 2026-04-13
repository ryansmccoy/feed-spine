"""API server management CLI commands.

Provides commands for starting the API server and managing API keys.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer

from feedspine.cli_modules.shared import console

api_app = typer.Typer(name="api", help="API server management", no_args_is_help=True)


@api_app.command("start")
def api_start(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Bind host"),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Bind port"),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Enable auto-reload for development"),
    ] = False,
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Number of worker processes"),
    ] = 1,
) -> None:
    """Start the FeedSpine API server.

    Runs the FastAPI application using uvicorn.

    Examples:
        feedspine api start
        feedspine api start --port 9000 --reload
        feedspine api start --workers 4 --host 0.0.0.0
    """
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is required. Install with: pip install feedspine[api][/red]")
        raise typer.Exit(code=1) from None

    console.print(f"[bold]Starting FeedSpine API[/bold] on {host}:{port}")
    if reload:
        console.print("[dim]Auto-reload enabled (development mode)[/dim]")

    uvicorn.run(
        "feedspine.api.fastapi:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )


# =============================================================================
# API Key Management
# =============================================================================

_DEFAULT_API_KEYS_PATH: Path | None = None


def _get_api_keys_file(path: Path | None = None) -> Path:
    """Get the API keys file path.

    Args:
        path: Explicit path to use. Falls back to ``~/.feedspine/api_keys.json``.
    """
    if path is not None:
        return path
    global _DEFAULT_API_KEYS_PATH
    if _DEFAULT_API_KEYS_PATH is None:
        _DEFAULT_API_KEYS_PATH = Path.home() / ".feedspine" / "api_keys.json"
    return _DEFAULT_API_KEYS_PATH


def _load_api_keys() -> dict:
    """Load API keys from storage file."""
    import json

    keys_file = _get_api_keys_file()
    if keys_file.exists():
        try:
            return json.loads(keys_file.read_text())
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load API keys: {e}[/yellow]")
            return {"keys": []}
    return {"keys": []}


def _save_api_keys(data: dict) -> None:
    """Save API keys to storage file."""
    import json

    keys_file = _get_api_keys_file()
    keys_file.parent.mkdir(parents=True, exist_ok=True)
    keys_file.write_text(json.dumps(data, indent=2))


@api_app.command("keys")
def api_keys_list(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List all configured API keys.

    Shows API keys that can be used to authenticate with the FeedSpine API.

    Examples:
        feedspine api keys
        feedspine api keys --json
    """
    from rich.table import Table

    data = _load_api_keys()
    keys = data.get("keys", [])

    if json_output:
        import json

        # Mask key values for security
        masked = [{**k, "key": k["key"][:8] + "..." if len(k.get("key", "")) > 8 else k.get("key", "")} for k in keys]
        console.print_json(json.dumps({"keys": masked, "total": len(keys)}))
        return

    if not keys:
        console.print("[dim]No API keys configured.[/dim]")
        console.print("\nTo generate a new key:")
        console.print("  feedspine api generate-key --name my-app")
        return

    table = Table(title="API Keys")
    table.add_column("Name", style="cyan")
    table.add_column("Key (masked)", style="dim")
    table.add_column("Created", style="green")
    table.add_column("Expires")

    for k in keys:
        key_masked = k.get("key", "")[:8] + "..." if len(k.get("key", "")) > 8 else k.get("key", "")
        expires = k.get("expires_at") or "[dim]Never[/dim]"
        table.add_row(
            k.get("name", "unnamed"),
            key_masked,
            k.get("created_at", ""),
            expires,
        )

    console.print(table)


@api_app.command("generate-key")
def api_keys_generate(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Name/label for the key"),
    ] = "default",
    expires_days: Annotated[
        int | None,
        typer.Option("--expires", "-e", help="Days until expiry (omit for never)"),
    ] = None,
) -> None:
    """Generate a new API key.

    Creates a new API key that can be used to authenticate with the
    FeedSpine API. The key will be shown once — save it securely.

    Examples:
        feedspine api generate-key --name my-app
        feedspine api generate-key --name temp-key --expires 7
    """
    import secrets
    from datetime import UTC, datetime, timedelta

    # Generate a secure key
    key = "fsk_" + secrets.token_urlsafe(32)

    now = datetime.now(UTC)
    expires_at = None
    if expires_days:
        expires_at = (now + timedelta(days=expires_days)).isoformat()

    key_entry = {
        "name": name,
        "key": key,
        "created_at": now.isoformat(),
        "expires_at": expires_at,
    }

    data = _load_api_keys()
    data["keys"].append(key_entry)
    _save_api_keys(data)

    console.print("[green]✓ API key generated successfully[/green]\n")
    console.print(f"Name:    [cyan]{name}[/cyan]")
    console.print(f"Key:     [bold yellow]{key}[/bold yellow]")
    if expires_at:
        console.print(f"Expires: {expires_at}")
    else:
        console.print("Expires: [dim]Never[/dim]")

    console.print("\n[yellow]⚠ Save this key now — it won't be shown again.[/yellow]")
    console.print("\nTo use this key with the API:")
    console.print(f'  export FEEDSPINE_API_KEY="{key}"')
    console.print("  export FEEDSPINE_REQUIRE_AUTH=true")


@api_app.command("revoke-key")
def api_keys_revoke(
    name: Annotated[
        str,
        typer.Argument(help="Name of the key to revoke"),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation"),
    ] = False,
) -> None:
    """Revoke an API key.

    Permanently removes an API key. This cannot be undone.

    Examples:
        feedspine api revoke-key my-app
        feedspine api revoke-key temp-key --force
    """
    data = _load_api_keys()
    keys = data.get("keys", [])

    # Find the key
    key_to_remove = None
    for k in keys:
        if k.get("name") == name:
            key_to_remove = k
            break

    if not key_to_remove:
        console.print(f"[red]API key not found: {name}[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Revoke API key '{name}'?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            return

    keys.remove(key_to_remove)
    data["keys"] = keys
    _save_api_keys(data)

    console.print(f"[green]✓ Revoked API key: {name}[/green]")


@api_app.command("auth-status")
def api_auth_status() -> None:
    """Show current API authentication status.

    Displays whether authentication is enabled and the configured API key.

    Examples:
        feedspine api auth-status
    """
    api_key = os.environ.get("FEEDSPINE_API_KEY", "")
    require_auth = os.environ.get("FEEDSPINE_REQUIRE_AUTH", "").lower() in ("true", "1", "yes")

    console.print("[bold]API Authentication Status[/bold]\n")

    if require_auth:
        console.print("  Auth Required: [green]Yes[/green]")
    else:
        console.print("  Auth Required: [yellow]No[/yellow] (all requests allowed)")

    if api_key:
        masked = api_key[:8] + "..." if len(api_key) > 8 else api_key
        console.print(f"  API Key:       [cyan]{masked}[/cyan]")
    else:
        console.print("  API Key:       [dim]Not set[/dim]")

    # Check stored keys
    data = _load_api_keys()
    key_count = len(data.get("keys", []))
    console.print(f"  Stored Keys:   {key_count}")

    if not require_auth:
        console.print("\n[dim]To enable authentication:[/dim]")
        console.print("  export FEEDSPINE_REQUIRE_AUTH=true")
        console.print("  export FEEDSPINE_API_KEY=your-key")


__all__ = ["api_app"]
