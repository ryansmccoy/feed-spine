"""Observation storage subsystem.

Specialized storage for financial time-series Observation data with:
- Time-based partitioning (by captured_at)
- Supersession chain tracking
- Point-in-time queries for backtesting
- Optional TimescaleDB integration
"""

from feedspine.storage.observations.storage import ObservationStorage

__all__ = ["ObservationStorage"]
