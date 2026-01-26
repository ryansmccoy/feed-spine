"""FeedSpine progress reporter implementations.

Provides concrete implementations of the ProgressReporter protocol
for different output targets.

Example:
    >>> from feedspine.reporter import RichProgressReporter, SimpleProgressReporter
    >>> 
    >>> # Rich terminal output with progress bars
    >>> reporter = RichProgressReporter()
    >>> 
    >>> # Simple logging output
    >>> reporter = SimpleProgressReporter()
"""

from feedspine.reporter.rich import RichProgressReporter
from feedspine.reporter.simple import SimpleProgressReporter

__all__ = [
    "RichProgressReporter",
    "SimpleProgressReporter",
]
