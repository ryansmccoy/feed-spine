#!/usr/bin/env python3
"""
Observations — Financial Time-Series Data
============================================

This example demonstrates FeedSpine's **observation subsystem** —
specialized storage for versioned financial data points like earnings,
prices, and analyst estimates.

What You'll Learn:
    1. Defining custom observation types with BaseObservation
    2. Observation deduplication via observation_key
    3. Supersession chains (how corrections replace old values)
    4. Authoritative value resolution (which source wins?)
    5. Storage configuration for PostgreSQL + optional TimescaleDB

Key Concepts:
    - BaseObservation: Base class for all observation types
    - observation_key: Dedup key (hash of entity+metric+period+source)
    - Supersession: When a value changes, old observation is superseded
    - Authoritative: Priority-based resolution (SEC filing > vendor > any)
    - ObservationStorage: PostgreSQL-optimized backend

Usage:
    python examples/16_observations/01_financial_observations.py

Note:
    ObservationStorage requires PostgreSQL. This example demonstrates
    the data model and patterns using in-memory structures. See the
    docstring in each section for the production equivalent.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from pydantic import computed_field

from feedspine.models.observation import BaseObservation


# ============================================================================
# STEP 1: Define Custom Observation Types
# ============================================================================
class EarningsObservation(BaseObservation):
    """Earnings per share observation."""

    observation_type: Literal["earnings"] = "earnings"
    entity_id: str  # e.g., "AAPL"
    metric_key: str  # e.g., "eps:per_share:gaap:reported:diluted:total"
    period_key: str  # e.g., "2024:quarterly:2"
    value: float
    source: str  # e.g., "sec-10q", "bloomberg", "refinitiv"

    @computed_field
    @property
    def fingerprint(self) -> str:
        """Deduplication fingerprint."""
        key = f"{self.entity_id}:{self.metric_key}:{self.period_key}:{self.source}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class PriceObservation(BaseObservation):
    """End-of-day price observation."""

    observation_type: Literal["price"] = "price"
    entity_id: str  # ticker
    metric_key: str = "price:close:eod"
    period_key: str  # e.g., "2024-06-15"
    value: float
    volume: int | None = None
    source: str = "market-data"

    @computed_field
    @property
    def fingerprint(self) -> str:
        key = f"{self.entity_id}:{self.metric_key}:{self.period_key}:{self.source}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class EstimateObservation(BaseObservation):
    """Analyst estimate (consensus or individual)."""

    observation_type: Literal["estimate"] = "estimate"
    entity_id: str
    metric_key: str  # e.g., "eps:estimate:consensus"
    period_key: str
    value: float
    num_estimates: int | None = None
    high: float | None = None
    low: float | None = None
    source: str = "consensus"

    @computed_field
    @property
    def fingerprint(self) -> str:
        key = f"{self.entity_id}:{self.metric_key}:{self.period_key}:{self.source}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


def main() -> None:
    # =========================================================================
    # STEP 2: Create Observations
    # =========================================================================
    print("=" * 60)
    print("STEP 2: Create Observation Instances")
    print("=" * 60)

    # Earnings from SEC filing (highest priority)
    sec_eps = EarningsObservation(
        entity_id="AAPL",
        metric_key="eps:per_share:gaap:reported:diluted:total",
        period_key="2024:quarterly:2",
        value=1.40,
        source="sec-10q",
    )

    # Same metric from Bloomberg (lower priority)
    bbg_eps = EarningsObservation(
        entity_id="AAPL",
        metric_key="eps:per_share:gaap:reported:diluted:total",
        period_key="2024:quarterly:2",
        value=1.40,
        source="bloomberg",
    )

    # Price observation
    price = PriceObservation(
        entity_id="AAPL",
        period_key="2024-06-15",
        value=214.29,
        volume=45_123_456,
    )

    # Analyst consensus estimate
    estimate = EstimateObservation(
        entity_id="AAPL",
        metric_key="eps:estimate:consensus",
        period_key="2024:quarterly:3",
        value=1.35,
        num_estimates=38,
        high=1.45,
        low=1.25,
    )

    for obs in [sec_eps, bbg_eps, price, estimate]:
        print(f"\n  Type:        {obs.observation_type}")
        print(f"  Entity:      {obs.entity_id}")
        print(f"  Metric:      {obs.metric_key}")
        print(f"  Period:      {obs.period_key}")
        print(f"  Value:       {obs.value}")
        print(f"  Fingerprint: {obs.fingerprint}")

    # =========================================================================
    # STEP 3: Deduplication via Fingerprint
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 3: Deduplication Logic")
    print("=" * 60)

    # Same source + entity + metric + period = same fingerprint
    sec_eps_dup = EarningsObservation(
        entity_id="AAPL",
        metric_key="eps:per_share:gaap:reported:diluted:total",
        period_key="2024:quarterly:2",
        value=1.40,  # Same value
        source="sec-10q",
    )
    print(f"\n  Original fingerprint: {sec_eps.fingerprint}")
    print(f"  Duplicate fingerprint: {sec_eps_dup.fingerprint}")
    print(f"  Match: {sec_eps.fingerprint == sec_eps_dup.fingerprint}")

    # Different source = different fingerprint (both stored)
    print(f"\n  SEC fingerprint: {sec_eps.fingerprint}")
    print(f"  BBG fingerprint: {bbg_eps.fingerprint}")
    print(f"  Match: {sec_eps.fingerprint == bbg_eps.fingerprint}")

    # =========================================================================
    # STEP 4: Supersession Chains
    # =========================================================================
    print("\n" + "=" * 60)
    print("STEP 4: Supersession (Corrections & Amendments)")
    print("=" * 60)

    # Simulating an EPS revision (10-K/A amendment)
    original = EarningsObservation(
        entity_id="AAPL",
        metric_key="eps:per_share:gaap:reported:diluted:total",
        period_key="2024:quarterly:2",
        value=1.40,
        source="sec-10q",
    )

    revised = EarningsObservation(
        entity_id="AAPL",
        metric_key="eps:per_share:gaap:reported:diluted:total",
        period_key="2024:quarterly:2",
        value=1.42,  # Revised!
        source="sec-10q",
    )

    print(f"\n  Original EPS: ${original.value}")
    print(f"  Revised EPS:  ${revised.value}")
    print(f"  Same fingerprint: {original.fingerprint == revised.fingerprint}")
    print("""
  When stored via ObservationStorage.store_observation():
    → Original is marked: is_superseded=True, superseded_by_id=<revised_id>
    → Revised is stored:  supersedes_id=<original_id>
    → Full audit trail is preserved
    """)

    # =========================================================================
    # STEP 5: Production Storage Pattern
    # =========================================================================
    print("=" * 60)
    print("STEP 5: Production Storage (PostgreSQL)")
    print("=" * 60)
    print("""
  from feedspine.storage.observations import ObservationStorage

  # Initialize with PostgreSQL
  storage = ObservationStorage(
      connection_string="postgresql://user:pass@localhost/feedspine",
      schema="feedspine",
      use_timescale=False,      # Set True for TimescaleDB compression
      compression_after_days=30,
      pool_size=5,
  )
  await storage.initialize()

  # Store (auto-dedup by observation_key, auto-supersession)
  await storage.store_observation(obs_dict)

  # Batch store (async, uses ON CONFLICT for efficiency)
  await storage.batch_store_observations(observations, batch_size=5000)

  # Query authoritative value (priority: SEC > vendor > any)
  auth = await storage.get_authoritative(
      entity_id="AAPL",
      metric_key="eps:per_share:gaap:reported:diluted:total",
      period_key="2024:quarterly:2",
  )

  # Point-in-time query (for backtesting)
  obs = await storage.get_observation(observation_id)
    """)


if __name__ == "__main__":
    main()
