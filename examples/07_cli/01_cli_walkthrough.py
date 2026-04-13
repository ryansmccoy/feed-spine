#!/usr/bin/env python3
"""
FeedSpine CLI Commands Walkthrough
==================================

A comprehensive guide to FeedSpine's command-line interface.
Demonstrates all major command groups and common workflows.

What You'll Learn:
    1. Core CLI commands and structure
    2. Feed collection workflows
    3. Data querying and export
    4. Configuration management
    5. API server management

CLI Entrypoint:
    feedspine <command> [options]
    python -m feedspine.cli <command> [options]

Usage:
    python examples/08_cli/01_cli_walkthrough.py
"""

from __future__ import annotations


def main() -> None:
    """Demonstrate CLI commands and workflows."""
    print("=" * 70)
    print("  FeedSpine CLI Commands Walkthrough")
    print("=" * 70)
    print()

    # =========================================================================
    # 1. Getting Started
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  1. GETTING STARTED" + " " * 48 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   Installation:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  pip install feedspine                                    │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Check version:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine version                                        │")
    print("   │  # Output: feedspine 0.2.0                                │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   System info:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine info                                           │")
    print("   │  # Shows Python version, storage backends, config path    │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # 2. Command Groups
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  2. COMMAND GROUPS OVERVIEW" + " " * 40 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    commands = [
        ("version", "Show version information"),
        ("info", "Show system and configuration details"),
        ("config", "Configuration management"),
        ("feeds", "List and manage feed sources"),
        ("collect", "Run feed collection workflows"),
        ("checkpoint", "Manage collection checkpoints"),
        ("query", "Query stored observations"),
        ("export", "Export data (JSON, CSV, Parquet)"),
        ("stats", "View collection and storage statistics"),
        ("health", "Health check commands"),
        ("api", "Start/stop the REST API server"),
        ("schedule", "Scheduled collection management"),
        ("migrate", "Database migrations"),
        ("enrich", "Data enrichment workflows"),
        ("capture", "Manual data capture"),
    ]

    print("   │ Command    │ Description                              │")
    print("   ├────────────┼──────────────────────────────────────────┤")
    for cmd, desc in commands:
        print(f"   │ {cmd:<10} │ {desc:<40} │")
    print()

    # =========================================================================
    # 3. Feed Collection
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  3. FEED COLLECTION" + " " * 48 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   List available feeds:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine feeds list                                     │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Initialize a collection:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine collect init --feed sec-daily                  │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Run a collection:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine collect run                                    │")
    print("   │  # Or with options:                                       │")
    print("   │  feedspine collect run --save-interval 100 --dry-run      │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Check collection status:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine collect status                                 │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Resume interrupted collection:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine collect run --resume                           │")
    print("   │  # Or from specific checkpoint:                           │")
    print("   │  feedspine collect run --resume-from run-20260215-143022  │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # 4. Querying Data
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  4. QUERYING DATA" + " " * 50 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   Simple query:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine query --days 7                                 │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Query with filters:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine query --feed sec-daily --entity AAPL --limit 50│")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Date range query:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine query \\                                        │")
    print("   │    --start 2026-01-01 \\                                   │")
    print("   │    --end 2026-02-15 \\                                     │")
    print("   │    --format json                                          │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # 5. Export Commands
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  5. EXPORT COMMANDS" + " " * 48 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   Export to JSON:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine export observations --format json > data.json  │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Export to CSV:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine export sightings --format csv -o sightings.csv │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Export to Parquet:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine export timeline --format parquet -o timeline.pq│")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # 6. Statistics and Monitoring
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  6. STATISTICS AND MONITORING" + " " * 37 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   Collection statistics:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine stats                                          │")
    print("   │  # Shows: total observations, by feed, by date            │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Health check:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine health                                         │")
    print("   │  # Shows: storage connection, API status, feed health     │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # 7. API Server
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  7. API SERVER MANAGEMENT" + " " * 42 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   Start API server:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine api start                                      │")
    print("   │  # Default: http://localhost:8000                         │")
    print("   │  feedspine api start --port 9000 --host 0.0.0.0           │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Stop API server:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine api stop                                       │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Check API status:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine api status                                     │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # 8. Scheduling
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  8. SCHEDULED COLLECTIONS" + " " * 42 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   Create a schedule:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine schedule create \\                              │")
    print("   │    --feed sec-daily \\                                     │")
    print("   │    --cron '0 6 * * 1-5' \\                                 │")
    print("   │    --name 'Daily SEC Morning'                             │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   List schedules:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine schedule list                                  │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Enable/disable schedule:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine schedule enable <id>                           │")
    print("   │  feedspine schedule disable <id>                          │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # 9. Configuration
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  9. CONFIGURATION" + " " * 50 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   Show current config:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine config show                                    │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Set a config value:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine config set storage.backend duckdb              │")
    print("   │  feedspine config set api.port 9000                       │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Config file locations:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  ~/.feedspine/config.toml        # User config            │")
    print("   │  ./feedspine.toml                # Project config         │")
    print("   │  $FEEDSPINE_CONFIG               # Environment override   │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # 10. Common Workflows
    # =========================================================================
    print("┌" + "─" * 68 + "┐")
    print("│  10. COMMON WORKFLOWS" + " " * 46 + "│")
    print("└" + "─" * 68 + "┘")
    print()

    print("   Daily SEC collection (cron job):")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  #!/bin/bash                                              │")
    print("   │  feedspine collect run --resume --save-interval 100       │")
    print("   │  feedspine stats >> /var/log/feedspine/stats.log          │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Weekly backup export:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine export timeline \\                              │")
    print("   │    --format parquet \\                                     │")
    print("   │    --days 7 \\                                             │")
    print('   │    -o "backup_$(date +%Y%m%d).parquet"                    │')
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    print("   Development API with hot reload:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  feedspine api start --reload --log-level debug           │")
    print("   └────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 70)
    print("  ✅ CLI Walkthrough Complete")
    print("=" * 70)
    print()
    print("   Quick Reference:")
    print("   • feedspine --help             Show all commands")
    print("   • feedspine <cmd> --help       Show command options")
    print("   • feedspine version            Show version")
    print("   • feedspine info               Show system info")
    print()
    print("   Documentation:")
    print("   • https://feedspine.readthedocs.io/cli/")
    print("   • feedspine docs               Open local docs")
    print()


if __name__ == "__main__":
    main()
