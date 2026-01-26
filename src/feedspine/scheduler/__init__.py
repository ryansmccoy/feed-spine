"""Scheduler implementations for feed polling.

This module provides scheduler implementations for automated feed collection.

Example:
    >>> from feedspine.scheduler import MemoryScheduler
    >>> from datetime import timedelta
    >>>
    >>> scheduler = MemoryScheduler()
    >>> await scheduler.initialize()
    >>> await scheduler.register("sec_rss", timedelta(minutes=5))
"""

from feedspine.scheduler.memory import MemoryScheduler

__all__ = ["MemoryScheduler"]
