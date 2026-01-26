"""Rich-based progress reporter for terminal output.

Provides beautiful progress bars and statistics using the Rich library.
Works with any FeedSpine feed collection.

Example:
    >>> from feedspine.reporter import RichProgressReporter
    >>> from feedspine.composition import Feed
    >>> 
    >>> reporter = RichProgressReporter()
    >>> reporter.start()
    >>> # ... feed.collect() reports progress events ...
    >>> reporter.finish(success=True)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None
    Live = None
    Panel = None
    Progress = None
    TaskID = None
    Table = None

from feedspine.protocols.progress import (
    ProgressEvent,
    ProgressReporter,
    ProgressStage,
)

logger = logging.getLogger("feedspine.reporter.rich")


class RichProgressReporter:
    """Rich-based progress reporter with live-updating progress bars.
    
    Shows:
    - Overall progress bar
    - Per-adapter progress
    - Statistics (new records, duplicates, rate)
    - Estimated time remaining
    
    Requires the 'rich' package: pip install rich
    
    Example:
        >>> reporter = RichProgressReporter()
        >>> reporter.start()
        >>> # ... during collection ...
        >>> reporter.report(event)
        >>> reporter.finish(success=True)
        
        # Output:
        # ┌─────────────────────────────────────────────────────────────┐
        # │                   Feed Collection Progress                  │
        # ├─────────────────────────────────────────────────────────────┤
        # │ ⠋ quarterly.2025Q1  ━━━━━━━━━━━━━━━━━━━  45%  45K/100K     │
        # │ ✓ quarterly.2025Q2  ━━━━━━━━━━━━━━━━━━━ 100%  102K/102K    │
        # │ ⠋ daily.2026-01     ━━━━━━━━━━━━━━━━━━━  20%  800/4K       │
        # ├─────────────────────────────────────────────────────────────┤
        # │ New: 147,234 | Duplicates: 2,341 | Rate: 1,234/s | ETA: 2m │
        # └─────────────────────────────────────────────────────────────┘
    
    Attributes:
        title: Panel title to display
        show_stats: Whether to show statistics row
        refresh_per_second: Display refresh rate
    """
    
    def __init__(
        self,
        console: "Console | None" = None,
        title: str = "Feed Collection Progress",
        show_stats: bool = True,
        refresh_per_second: int = 4,
    ):
        """Initialize the reporter.
        
        Args:
            console: Rich Console to use (default: new console)
            title: Panel title
            show_stats: Show statistics row (default: True)
            refresh_per_second: How often to refresh display (default: 4)
            
        Raises:
            ImportError: If rich package is not installed
        """
        if not RICH_AVAILABLE:
            raise ImportError(
                "Rich progress reporter requires the 'rich' package. "
                "Install with: pip install rich"
            )
        
        self._console = console or Console()
        self._title = title
        self._show_stats = show_stats
        self._refresh_per_second = refresh_per_second
        
        # State
        self._live: Live | None = None
        self._progress: Progress | None = None
        self._tasks: dict[str, TaskID] = {}
        self._stats: dict[str, Any] = {
            "records_new": 0,
            "records_duplicate": 0,
            "bytes_downloaded": 0,
            "started_at": None,
        }
    
    def start(self) -> None:
        """Initialize the progress display."""
        self._stats["started_at"] = datetime.now()
        
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._console,
            refresh_per_second=self._refresh_per_second,
        )
        
        self._live = Live(
            self._make_layout(),
            console=self._console,
            refresh_per_second=self._refresh_per_second,
        )
        self._live.start()
    
    def report(self, event: ProgressEvent) -> None:
        """Update the progress display with new event.
        
        Args:
            event: Progress event from feed collection
        """
        if not self._progress:
            return
        
        # Update stats
        self._stats["records_new"] = event.records_new
        self._stats["records_duplicate"] = event.records_duplicate
        self._stats["bytes_downloaded"] = event.bytes_downloaded
        
        # Get or create task for this adapter
        adapter_name = event.adapter_name or "feed"
        if adapter_name not in self._tasks:
            task_id = self._progress.add_task(
                adapter_name,
                total=event.total or 100,
            )
            self._tasks[adapter_name] = task_id
        
        task_id = self._tasks[adapter_name]
        
        # Update task progress
        if event.total > 0:
            self._progress.update(
                task_id,
                completed=event.current,
                total=event.total,
                description=self._format_description(event),
            )
        
        # Handle stage-specific updates
        if event.stage == ProgressStage.COMPLETE:
            self._progress.update(task_id, completed=event.total)
        elif event.stage == ProgressStage.FAILED:
            self._progress.update(
                task_id, 
                description=f"[red]✗ {adapter_name}[/red]",
            )
        
        # Update the live display
        if self._live:
            self._live.update(self._make_layout())
    
    def finish(self, success: bool) -> None:
        """Finalize the progress display.
        
        Args:
            success: Whether the collection completed successfully
        """
        if self._live:
            # Show final stats
            self._live.update(self._make_final_panel(success))
            self._live.stop()
            self._live = None
        
        # Print summary
        elapsed = datetime.now() - self._stats["started_at"]
        status = "[green]✓ Complete[/green]" if success else "[red]✗ Failed[/red]"
        
        self._console.print()
        self._console.print(Panel.fit(
            f"{status}\n"
            f"[dim]New records:[/dim] {self._stats['records_new']:,}\n"
            f"[dim]Duplicates:[/dim] {self._stats['records_duplicate']:,}\n"
            f"[dim]Duration:[/dim] {elapsed.total_seconds():.1f}s",
            title="Collection Summary",
            border_style="green" if success else "red",
        ))
    
    def _format_description(self, event: ProgressEvent) -> str:
        """Format task description based on stage."""
        name = event.adapter_name or "feed"
        
        if event.stage == ProgressStage.FETCHING:
            return f"[cyan]↓ {name}[/cyan]"
        elif event.stage == ProgressStage.PARSING:
            return f"[yellow]⚙ {name}[/yellow]"
        elif event.stage == ProgressStage.STORING:
            return f"[blue]💾 {name}[/blue]"
        elif event.stage == ProgressStage.COMPLETE:
            return f"[green]✓ {name}[/green]"
        elif event.stage == ProgressStage.FAILED:
            return f"[red]✗ {name}[/red]"
        else:
            return f"[dim]{name}[/dim]"
    
    def _make_layout(self) -> "Panel":
        """Create the progress panel layout."""
        # Main progress
        content = self._progress if self._progress else ""
        
        # Add stats row if enabled
        if self._show_stats and self._stats["started_at"]:
            elapsed = (datetime.now() - self._stats["started_at"]).total_seconds()
            rate = 0
            if elapsed > 0:
                total = self._stats["records_new"] + self._stats["records_duplicate"]
                rate = total / elapsed
            
            stats_text = (
                f"[bold]New:[/bold] {self._stats['records_new']:,} | "
                f"[bold]Dups:[/bold] {self._stats['records_duplicate']:,} | "
                f"[bold]Rate:[/bold] {rate:,.0f}/s"
            )
            
            table = Table.grid(padding=(0, 1))
            table.add_row(content)
            table.add_row(stats_text)
            content = table
        
        return Panel(
            content,
            title=f"[bold]{self._title}[/bold]",
            border_style="blue",
        )
    
    def _make_final_panel(self, success: bool) -> "Panel":
        """Create the final summary panel."""
        elapsed = (datetime.now() - self._stats["started_at"]).total_seconds()
        total = self._stats["records_new"] + self._stats["records_duplicate"]
        rate = total / elapsed if elapsed > 0 else 0
        dedup_rate = 0
        if total > 0:
            dedup_rate = (self._stats["records_duplicate"] / total) * 100
        
        status = "[green]✓ Collection Complete[/green]" if success else "[red]✗ Collection Failed[/red]"
        
        return Panel(
            f"{status}\n\n"
            f"[bold]Records:[/bold]\n"
            f"  New: {self._stats['records_new']:,}\n"
            f"  Duplicates: {self._stats['records_duplicate']:,}\n"
            f"  Total Processed: {total:,}\n\n"
            f"[bold]Performance:[/bold]\n"
            f"  Duration: {elapsed:.1f}s\n"
            f"  Rate: {rate:,.0f} records/s\n"
            f"  Dedup Rate: {dedup_rate:.1f}%",
            title="[bold]Collection Summary[/bold]",
            border_style="green" if success else "red",
        )


__all__ = ["RichProgressReporter"]
