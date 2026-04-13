"""Observation models for various data sources.

Observations are specialized records for capturing specific types of events
or data from different providers.

Example:
    >>> from feedspine.models.observation import BaseObservation
    >>> class EarningsObservation(BaseObservation):
    ...     observation_type: str = "earnings_event"
    ...     @computed_field
    ...     @property
    ...     def fingerprint(self) -> str:
    ...         return f"earnings:{self.id}"
"""

from __future__ import annotations

from pydantic import Field

from feedspine.models.base import FeedSpineModel


class BaseObservation(FeedSpineModel):
    """Base class for all observations.

    Observations are structured data captured from external sources.
    Each observation type provides a fingerprint for deduplication.

    Example:
        >>> class MyObservation(BaseObservation):
        ...     observation_type: Literal["my_type"] = "my_type"
        ...     @computed_field
        ...     @property
        ...     def fingerprint(self) -> str:
        ...         return f"my:{self.id}"
    """

    observation_type: str = Field(
        ...,
        description="Type discriminator for the observation",
    )
