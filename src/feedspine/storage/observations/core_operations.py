"""
Core storage operations: store, insert, batch store.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from spine.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

logger = get_logger(__name__)


class CoreOperationsMixin:
    """Mixin for core storage operations."""

    schema: str
    _get_engine: callable
    _observation_to_dict: callable

    async def store_observation(
        self,
        observation: Any,
        check_supersession: bool = True,
    ) -> str:
        """
        Store an observation with automatic deduplication.

        Args:
            observation: Observation dataclass or dict
            check_supersession: Check if this supersedes existing observation

        Returns:
            observation_id
        """
        from sqlalchemy import text

        # Convert to dict if needed
        if hasattr(observation, "__dataclass_fields__"):
            obs_dict = self._observation_to_dict(observation)
        else:
            obs_dict = observation

        engine = self._get_engine()

        with engine.connect() as conn:
            # Check for existing by observation_key
            existing = conn.execute(
                text(f"""
                SELECT observation_id, value_normalized
                FROM {self.schema}.observations
                WHERE observation_key = :key
            """),
                {"key": obs_dict["observation_key"]},
            ).fetchone()

            if existing:
                # Already exists - update if value changed
                if existing.value_normalized != obs_dict["value_normalized"] and check_supersession:
                    # Value changed - mark old as superseded, insert new
                    conn.execute(
                        text(f"""
                            UPDATE {self.schema}.observations
                            SET superseded_by_id = :new_id, is_superseded = TRUE, updated_at = NOW()
                            WHERE observation_id = :old_id
                        """),
                        {
                            "new_id": obs_dict["observation_id"],
                            "old_id": existing.observation_id,
                        },
                    )

                    obs_dict["supersedes_id"] = existing.observation_id

                # Insert new version
                self._insert_observation(conn, obs_dict)
                conn.commit()
                return obs_dict["observation_id"]
            else:
                # New observation
                self._insert_observation(conn, obs_dict)
                conn.commit()
                return obs_dict["observation_id"]

    def _insert_observation(self, conn: Connection, obs: dict[str, Any]) -> None:
        """Insert observation record."""
        from sqlalchemy import text

        conn.execute(
            text(f"""
            INSERT INTO {self.schema}.observations (
                observation_id, observation_key, entity_id, security_id,
                metric_key, period_key, observation_type,
                value_normalized, value_raw, value_unit, value_scale, value_currency, value_string,
                fiscal_year, fiscal_quarter, period_type, period_start, period_end,
                as_of, captured_at,
                provenance_kind, provenance_external_id,
                source_vendor, source_dataset, source_field,
                estimate_scope, estimator, num_estimates, high_estimate, low_estimate,
                supersedes_id, is_superseded, confidence, content
            ) VALUES (
                :observation_id, :observation_key, :entity_id, :security_id,
                :metric_key, :period_key, :observation_type,
                :value_normalized, :value_raw, :value_unit, :value_scale, :value_currency, :value_string,
                :fiscal_year, :fiscal_quarter, :period_type, :period_start, :period_end,
                :as_of, :captured_at,
                :provenance_kind, :provenance_external_id,
                :source_vendor, :source_dataset, :source_field,
                :estimate_scope, :estimator, :num_estimates, :high_estimate, :low_estimate,
                :supersedes_id, :is_superseded, :confidence, :content::jsonb
            )
        """),
            obs,
        )

    async def batch_store_observations(
        self,
        observations: Sequence[Any],
        batch_size: int = 5000,
    ) -> int:
        """
        Bulk store observations efficiently.

        Uses PostgreSQL COPY for maximum throughput.

        Returns:
            Number of observations stored
        """
        from sqlalchemy import text

        engine = self._get_engine()
        total = 0

        # Convert all to dicts
        obs_dicts = [self._observation_to_dict(o) if hasattr(o, "__dataclass_fields__") else o for o in observations]

        with engine.connect() as conn:
            for i in range(0, len(obs_dicts), batch_size):
                batch = obs_dicts[i : i + batch_size]

                # Build VALUES clause
                values = []
                params = {}

                for j, obs in enumerate(batch):
                    prefix = f"o{j}_"
                    values.append(f"""(
                        :{prefix}observation_id, :{prefix}observation_key, :{prefix}entity_id, :{prefix}security_id,
                        :{prefix}metric_key, :{prefix}period_key, :{prefix}observation_type,
                        :{prefix}value_normalized, :{prefix}value_raw, :{prefix}value_unit, :{prefix}value_scale, :{prefix}value_currency, :{prefix}value_string,
                        :{prefix}fiscal_year, :{prefix}fiscal_quarter, :{prefix}period_type, :{prefix}period_start, :{prefix}period_end,
                        :{prefix}as_of, :{prefix}captured_at,
                        :{prefix}provenance_kind, :{prefix}provenance_external_id,
                        :{prefix}source_vendor, :{prefix}source_dataset, :{prefix}source_field,
                        :{prefix}estimate_scope, :{prefix}estimator, :{prefix}num_estimates, :{prefix}high_estimate, :{prefix}low_estimate,
                        :{prefix}supersedes_id, :{prefix}is_superseded, :{prefix}confidence, :{prefix}content::jsonb
                    )""")

                    for key, value in obs.items():
                        params[f"{prefix}{key}"] = value

                # Insert with ON CONFLICT
                sql = f"""
                    INSERT INTO {self.schema}.observations (
                        observation_id, observation_key, entity_id, security_id,
                        metric_key, period_key, observation_type,
                        value_normalized, value_raw, value_unit, value_scale, value_currency, value_string,
                        fiscal_year, fiscal_quarter, period_type, period_start, period_end,
                        as_of, captured_at,
                        provenance_kind, provenance_external_id,
                        source_vendor, source_dataset, source_field,
                        estimate_scope, estimator, num_estimates, high_estimate, low_estimate,
                        supersedes_id, is_superseded, confidence, content
                    ) VALUES {", ".join(values)}
                    ON CONFLICT (observation_key) DO UPDATE SET
                        value_normalized = EXCLUDED.value_normalized,
                        value_raw = EXCLUDED.value_raw,
                        updated_at = NOW()
                    WHERE observations.value_normalized != EXCLUDED.value_normalized
                """

                conn.execute(text(sql), params)
                total += len(batch)

                logger.debug(f"Batch stored {total} observations")

            conn.commit()

        return total
