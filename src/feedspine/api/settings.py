"""API configuration settings.

Re-exports from the unified feedspine.core.config module.
Kept for backwards compatibility.
"""

from __future__ import annotations

from feedspine.core.config import FeedSpineSettings as APISettings
from feedspine.core.config import get_settings

__all__ = ["APISettings", "get_settings"]
