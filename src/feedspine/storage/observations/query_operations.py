"""
Query operations for ObservationStorage.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from spine.core.logging import get_logger

logger = get_logger(__name__)


class QueryOperationsMixin:
    """Mixin for observation query operations."""

    schema: str
    _get_engine: callable

    async def get_observation(self, observation_id: str) -> dict[str, Any] | None:
        """Get observation by ID."""
        from sqlalchemy import text

        engine = self._get_engine()

        with engine.connect() as conn:
            row = (
                conn.execute(
                    text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE observation_id = :id
            """),
                    {"id": observation_id},
                )
                .mappings()
                .fetchone()
            )

            return dict(row) if row else None

    async def get_authoritative(
        self,
        entity_id: str,
        metric_key: str,
        period_key: str,
    ) -> dict[str, Any] | None:
        """
        Get the authoritative observation for entity+metric+period.

        Priority:
        1. Most recent non-superseded SEC filing
        2. Most recent non-superseded vendor actual
        3. Any non-superseded actual
        """
        from sqlalchemy import text

        engine = self._get_engine()

        with engine.connect() as conn:
            # Try SEC first
            row = (
                conn.execute(
                    text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE entity_id = :entity_id
                  AND metric_key = :metric_key
                  AND period_key = :period_key
                  AND observation_type = 'actual'
                  AND is_superseded = FALSE
                  AND provenance_kind = 'sec_filing'
                ORDER BY as_of DESC NULLS LAST
                LIMIT 1
            """),
                    {
                        "entity_id": entity_id,
                        "metric_key": metric_key,
                        "period_key": period_key,
                    },
                )
                .mappings()
                .fetchone()
            )

            if row:
                return dict(row)

            # Fall back to any non-superseded actual
            row = (
                conn.execute(
                    text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE entity_id = :entity_id
                  AND metric_key = :metric_key
                  AND period_key = :period_key
                  AND observation_type = 'actual'
                  AND is_superseded = FALSE
                ORDER BY as_of DESC NULLS LAST
                LIMIT 1
            """),
                    {
                        "entity_id": entity_id,
                        "metric_key": metric_key,
                        "period_key": period_key,
                    },
                )
                .mappings()
                .fetchone()
            )

            return dict(row) if row else None

    async def query_pit(
        self,
        entity_id: str,
        metric_key: str,
        period_key: str,
        as_of: datetime,
        observation_type: str = "actual",
    ) -> dict[str, Any] | None:
        """
        Point-in-time query: Get the observation known at a specific moment.

        CRITICAL FOR BACKTESTING - prevents lookahead bias.

        Returns the LATEST observation with as_of <= requested as_of.
        This is the value that was known to the market at that time.

        Args:
            entity_id: Entity identifier
            metric_key: MetricSpec canonical key
            period_key: FiscalPeriod canonical key
            as_of: Point in time to query (what was known THEN)
            observation_type: Filter by type (default: actual)

        Returns:
            Observation dict or None

        Example:
            # What did we know about AAPL Q4 revenue on Dec 1, 2024?
            obs = await storage.query_pit(
                entity_id="aapl",
                metric_key="revenue:income_statement:gaap:reported:na:total",
                period_key="2024:quarterly:4:0",
                as_of=datetime(2024, 12, 1),
            )
            # Returns the preliminary $95.2B, NOT the later restated $94.9B
        """
        from sqlalchemy import text

        engine = self._get_engine()

        with engine.connect() as conn:
            row = (
                conn.execute(
                    text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE entity_id = :entity_id
                  AND metric_key = :metric_key
                  AND period_key = :period_key
                  AND observation_type = :observation_type
                  AND as_of <= :as_of
                ORDER BY as_of DESC
                LIMIT 1
            """),
                    {
                        "entity_id": entity_id,
                        "metric_key": metric_key,
                        "period_key": period_key,
                        "observation_type": observation_type,
                        "as_of": as_of,
                    },
                )
                .mappings()
                .fetchone()
            )

            return dict(row) if row else None

    async def query_pit_batch(
        self,
        queries: list[dict[str, Any]],
    ) -> list[dict[str, Any] | None]:
        """
        Batch point-in-time queries for efficient backtesting.

        Each query dict should have: entity_id, metric_key, period_key, as_of

        Returns list of observations in same order as queries.

        Example:
            # Backtest: Get EPS for 500 companies as of each quarter end
            queries = [
                {"entity_id": "aapl", "metric_key": "eps:...", "period_key": "2024:quarterly:1:0", "as_of": datetime(2024, 4, 1)},
                {"entity_id": "msft", "metric_key": "eps:...", "period_key": "2024:quarterly:1:0", "as_of": datetime(2024, 4, 1)},
                ...
            ]
            results = await storage.query_pit_batch(queries)
        """
        # For now, simple sequential implementation
        # TODO: Optimize with lateral joins or CTEs for large batches
        results = []
        for q in queries:
            obs = await self.query_pit(
                entity_id=q["entity_id"],
                metric_key=q["metric_key"],
                period_key=q["period_key"],
                as_of=q["as_of"],
                observation_type=q.get("observation_type", "actual"),
            )
            results.append(obs)
        return results

    async def get_revision_history(
        self,
        entity_id: str,
        metric_key: str,
        period_key: str,
    ) -> list[dict[str, Any]]:
        """
        Get all historical values for an observation, ordered by as_of.

        Shows how the reported value changed over time (preliminary → audited → restated).

        Returns:
            List of observations ordered by as_of (oldest first)
        """
        from sqlalchemy import text

        engine = self._get_engine()

        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE entity_id = :entity_id
                  AND metric_key = :metric_key
                  AND period_key = :period_key
                ORDER BY as_of ASC
            """),
                    {
                        "entity_id": entity_id,
                        "metric_key": metric_key,
                        "period_key": period_key,
                    },
                )
                .mappings()
                .fetchall()
            )

            return [dict(row) for row in rows]

    async def query_observations(
        self,
        entity_id: str | None = None,
        metric_key: str | None = None,
        period_key: str | None = None,
        observation_type: str | None = None,
        fiscal_year: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        include_superseded: bool = False,
        limit: int = 1000,
        offset: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Query observations with filters.

        Yields observation dicts.
        """
        from sqlalchemy import text

        engine = self._get_engine()

        # Build query
        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if entity_id:
            conditions.append("entity_id = :entity_id")
            params["entity_id"] = entity_id
        if metric_key:
            conditions.append("metric_key = :metric_key")
            params["metric_key"] = metric_key
        if period_key:
            conditions.append("period_key = :period_key")
            params["period_key"] = period_key
        if observation_type:
            conditions.append("observation_type = :observation_type")
            params["observation_type"] = observation_type
        if fiscal_year:
            conditions.append("fiscal_year = :fiscal_year")
            params["fiscal_year"] = fiscal_year
        if since:
            conditions.append("captured_at >= :since")
            params["since"] = since
        if until:
            conditions.append("captured_at < :until")
            params["until"] = until
        if not include_superseded:
            conditions.append("is_superseded = FALSE")

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        sql = f"""
            SELECT * FROM {self.schema}.observations
            WHERE {where_clause}
            ORDER BY captured_at DESC
            LIMIT :limit OFFSET :offset
        """

        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            for row in result.mappings():
                yield dict(row)

    async def get_supersession_chain(self, observation_id: str) -> list[dict[str, Any]]:
        """
        Get the full supersession chain for an observation.

        Returns list from oldest to newest.
        """
        from sqlalchemy import text

        engine = self._get_engine()
        chain = []

        with engine.connect() as conn:
            # Walk backward (supersedes_id)
            current_id = observation_id
            while current_id:
                row = (
                    conn.execute(
                        text(f"""
                    SELECT * FROM {self.schema}.observations
                    WHERE observation_id = :id
                """),
                        {"id": current_id},
                    )
                    .mappings()
                    .fetchone()
                )

                if not row:
                    break

                chain.insert(0, dict(row))
                current_id = row.get("supersedes_id")

            # Walk forward (superseded_by_id)
            current_id = observation_id
            seen = {observation_id}
            while current_id:
                row = (
                    conn.execute(
                        text(f"""
                    SELECT * FROM {self.schema}.observations
                    WHERE supersedes_id = :id
                """),
                        {"id": current_id},
                    )
                    .mappings()
                    .fetchone()
                )

                if not row or row["observation_id"] in seen:
                    break

                chain.append(dict(row))
                seen.add(row["observation_id"])
                current_id = row["observation_id"]

        return chain

    async def compare_estimates_actuals(
        self,
        entity_id: str | None = None,
        metric_key: str | None = None,
        period_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Compare estimates to actuals for surprise analysis.

        Returns list of {period, actual, consensus, surprise, surprise_pct}
        """
        from sqlalchemy import text

        engine = self._get_engine()

        conditions = ["TRUE"]
        params: dict[str, Any] = {}

        if entity_id:
            conditions.append("entity_id = :entity_id")
            params["entity_id"] = entity_id
        if metric_key:
            conditions.append("metric_key = :metric_key")
            params["metric_key"] = metric_key
        if period_key:
            conditions.append("period_key = :period_key")
            params["period_key"] = period_key

        where_clause = " AND ".join(conditions)

        sql = f"""
            WITH actuals AS (
                SELECT entity_id, metric_key, period_key, value_normalized as actual_value
                FROM {self.schema}.observations
                WHERE observation_type = 'actual' AND is_superseded = FALSE
                  AND {where_clause}
            ),
            estimates AS (
                SELECT entity_id, metric_key, period_key,
                       AVG(value_normalized) as consensus_value,
                       COUNT(*) as estimate_count
                FROM {self.schema}.observations
                WHERE observation_type IN ('estimate', 'consensus')
                  AND is_superseded = FALSE
                  AND {where_clause}
                GROUP BY entity_id, metric_key, period_key
            )
            SELECT
                a.entity_id,
                a.metric_key,
                a.period_key,
                a.actual_value,
                e.consensus_value,
                e.estimate_count,
                (a.actual_value - e.consensus_value) as surprise,
                CASE WHEN e.consensus_value != 0
                     THEN ((a.actual_value - e.consensus_value) / ABS(e.consensus_value) * 100)
                     ELSE NULL
                END as surprise_pct
            FROM actuals a
            LEFT JOIN estimates e ON a.entity_id = e.entity_id
                                  AND a.metric_key = e.metric_key
                                  AND a.period_key = e.period_key
            ORDER BY a.period_key DESC
        """

        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            return [dict(row) for row in result.mappings()]

    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        from sqlalchemy import text

        engine = self._get_engine()

        with engine.connect() as conn:
            # Total count
            total = (
                conn.execute(
                    text(f"""
                SELECT COUNT(*) FROM {self.schema}.observations
            """)
                ).scalar()
                or 0
            )

            # By type
            by_type = dict(
                conn.execute(
                    text(f"""
                SELECT observation_type, COUNT(*)
                FROM {self.schema}.observations
                GROUP BY observation_type
            """)
                ).fetchall()
            )

            # Superseded count
            superseded = (
                conn.execute(
                    text(f"""
                SELECT COUNT(*) FROM {self.schema}.observations
                WHERE is_superseded = TRUE
            """)
                ).scalar()
                or 0
            )

            # Entity count
            entities = (
                conn.execute(
                    text(f"""
                SELECT COUNT(DISTINCT entity_id) FROM {self.schema}.observations
            """)
                ).scalar()
                or 0
            )

            return {
                "total": total,
                "by_type": by_type,
                "superseded": superseded,
                "entities": entities,
                "schema": self.schema,
                "timescale_enabled": self.use_timescale,
            }
