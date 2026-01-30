"""
Observation Storage Backend - Optimized for Financial Time-Series.

Specialized storage for Observation data type with:
- Time-based partitioning (by captured_at)
- Supersession chain tracking
- Efficient period-based queries
- Optional TimescaleDB integration for compression

Usage:
    from feedspine.storage.observation_storage import ObservationStorage
    
    storage = ObservationStorage("postgresql://localhost/feedspine")
    await storage.initialize()
    
    # Store observations (auto-dedup by observation_key)
    await storage.store_observation(obs)
    
    # Query by entity + metric + period
    obs = await storage.get_authoritative(
        entity_id="aapl",
        metric_key="eps:per_share:gaap:reported:diluted:total",
        period_key="2024:quarterly:4:0",
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator, Sequence

logger = logging.getLogger(__name__)


class ObservationStorage:
    """
    PostgreSQL storage optimized for Observation data.
    
    Schema design:
    - observations: Core table with time partitioning
    - observation_versions: History for superseded observations
    - observation_provenance: Linked provenance records
    
    Key optimizations:
    - Partitioned by captured_at (monthly)
    - BRIN index on captured_at (small, fast for time ranges)
    - B-tree on (entity_id, metric_key, period_key) for point lookups
    - GIN on content JSONB for flexible queries
    - Unique constraint on observation_key for deduplication
    """
    
    SCHEMA_VERSION = "1.0.0"
    
    def __init__(
        self,
        connection_string: str,
        schema: str = "feedspine",
        use_timescale: bool = False,
        compression_after_days: int = 30,
        pool_size: int = 5,
    ):
        """
        Initialize observation storage.
        
        Args:
            connection_string: PostgreSQL connection string
            schema: Database schema name
            use_timescale: Enable TimescaleDB features (compression, etc.)
            compression_after_days: Days before compressing old data
            pool_size: Connection pool size
        """
        self.connection_string = connection_string
        self.schema = schema
        self.use_timescale = use_timescale
        self.compression_after_days = compression_after_days
        self.pool_size = pool_size
        self._engine = None
        self._initialized = False
    
    def _get_engine(self):
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            
            self._engine = create_engine(
                self.connection_string,
                pool_size=self.pool_size,
                max_overflow=10,
            )
        return self._engine
    
    async def initialize(self) -> None:
        """Initialize schema and tables."""
        from sqlalchemy import text
        
        engine = self._get_engine()
        
        with engine.connect() as conn:
            # Create schema
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.schema}"))
            
            # Create observations table
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.observations (
                    -- Primary key
                    observation_id TEXT PRIMARY KEY,
                    
                    -- Natural key for deduplication (hash of entity+metric+period+as_of+source)
                    observation_key TEXT NOT NULL UNIQUE,
                    
                    -- Core dimensions
                    entity_id TEXT NOT NULL,
                    security_id TEXT,
                    metric_key TEXT NOT NULL,      -- MetricSpec.canonical_key
                    period_key TEXT NOT NULL,      -- FiscalPeriod.canonical_key
                    observation_type TEXT NOT NULL DEFAULT 'actual',
                    
                    -- Value (normalized)
                    value_normalized NUMERIC NOT NULL,
                    value_raw NUMERIC NOT NULL,
                    value_unit TEXT NOT NULL,
                    value_scale INTEGER NOT NULL DEFAULT 1,
                    value_currency TEXT,
                    value_string TEXT,
                    
                    -- Time semantics
                    fiscal_year INTEGER NOT NULL,
                    fiscal_quarter INTEGER,
                    period_type TEXT NOT NULL,
                    period_start DATE,
                    period_end DATE,
                    as_of TIMESTAMPTZ,
                    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    
                    -- Provenance
                    provenance_kind TEXT,
                    provenance_external_id TEXT,
                    source_vendor TEXT,
                    source_dataset TEXT,
                    source_field TEXT,
                    
                    -- Estimate metadata (for estimates/consensus/guidance)
                    estimate_scope TEXT,
                    estimator TEXT,
                    num_estimates INTEGER,
                    high_estimate NUMERIC,
                    low_estimate NUMERIC,
                    
                    -- Supersession chain
                    supersedes_id TEXT,
                    superseded_by_id TEXT,
                    is_superseded BOOLEAN NOT NULL DEFAULT FALSE,
                    
                    -- Quality
                    confidence REAL NOT NULL DEFAULT 1.0,
                    
                    -- Full content for flexibility
                    content JSONB,
                    
                    -- Timestamps
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            
            # Create indexes
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_entity_metric_period
                ON {self.schema}.observations (entity_id, metric_key, period_key)
            """))
            
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_entity_captured
                ON {self.schema}.observations (entity_id, captured_at)
            """))
            
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_metric_period
                ON {self.schema}.observations (metric_key, period_key)
            """))
            
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_fiscal
                ON {self.schema}.observations (fiscal_year, fiscal_quarter)
            """))
            
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_as_of
                ON {self.schema}.observations (as_of)
            """))
            
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_type
                ON {self.schema}.observations (observation_type)
            """))
            
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_not_superseded
                ON {self.schema}.observations (entity_id, metric_key, period_key)
                WHERE is_superseded = FALSE
            """))
            
            # BRIN index for time-ordered queries (very efficient)
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_captured_brin
                ON {self.schema}.observations USING BRIN (captured_at)
            """))
            
            # GIN index for JSONB queries
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_content_gin
                ON {self.schema}.observations USING GIN (content)
            """))
            
            conn.commit()
            
            # TimescaleDB hypertable (if enabled)
            if self.use_timescale:
                try:
                    conn.execute(text(f"""
                        SELECT create_hypertable(
                            '{self.schema}.observations',
                            'captured_at',
                            chunk_time_interval => INTERVAL '1 month',
                            if_not_exists => TRUE,
                            migrate_data => TRUE
                        )
                    """))
                    
                    # Enable compression
                    conn.execute(text(f"""
                        ALTER TABLE {self.schema}.observations SET (
                            timescaledb.compress,
                            timescaledb.compress_segmentby = 'entity_id, metric_key'
                        )
                    """))
                    
                    conn.execute(text(f"""
                        SELECT add_compression_policy(
                            '{self.schema}.observations',
                            INTERVAL '{self.compression_after_days} days',
                            if_not_exists => TRUE
                        )
                    """))
                    
                    conn.commit()
                    logger.info("TimescaleDB hypertable created with compression")
                except Exception as e:
                    logger.warning(f"TimescaleDB not available: {e}")
        
        self._initialized = True
        logger.info(f"ObservationStorage initialized (schema: {self.schema})")
    
    async def close(self) -> None:
        """Close connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
    
    # =========================================================================
    # Core Operations
    # =========================================================================
    
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
            existing = conn.execute(text(f"""
                SELECT observation_id, value_normalized
                FROM {self.schema}.observations
                WHERE observation_key = :key
            """), {"key": obs_dict["observation_key"]}).fetchone()
            
            if existing:
                # Already exists - update if value changed
                if existing.value_normalized != obs_dict["value_normalized"]:
                    # Value changed - mark old as superseded, insert new
                    if check_supersession:
                        conn.execute(text(f"""
                            UPDATE {self.schema}.observations
                            SET superseded_by_id = :new_id, is_superseded = TRUE, updated_at = NOW()
                            WHERE observation_id = :old_id
                        """), {"new_id": obs_dict["observation_id"], "old_id": existing.observation_id})
                        
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
    
    def _insert_observation(self, conn, obs: dict[str, Any]) -> None:
        """Insert observation record."""
        from sqlalchemy import text
        
        conn.execute(text(f"""
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
        """), obs)
    
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
        obs_dicts = [
            self._observation_to_dict(o) if hasattr(o, "__dataclass_fields__") else o
            for o in observations
        ]
        
        with engine.connect() as conn:
            for i in range(0, len(obs_dicts), batch_size):
                batch = obs_dicts[i:i + batch_size]
                
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
                    ) VALUES {', '.join(values)}
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
    
    # =========================================================================
    # Query Operations
    # =========================================================================
    
    async def get_observation(self, observation_id: str) -> dict[str, Any] | None:
        """Get observation by ID."""
        from sqlalchemy import text
        
        engine = self._get_engine()
        
        with engine.connect() as conn:
            row = conn.execute(text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE observation_id = :id
            """), {"id": observation_id}).mappings().fetchone()
            
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
            row = conn.execute(text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE entity_id = :entity_id
                  AND metric_key = :metric_key
                  AND period_key = :period_key
                  AND observation_type = 'actual'
                  AND is_superseded = FALSE
                  AND provenance_kind = 'sec_filing'
                ORDER BY as_of DESC NULLS LAST
                LIMIT 1
            """), {
                "entity_id": entity_id,
                "metric_key": metric_key,
                "period_key": period_key,
            }).mappings().fetchone()
            
            if row:
                return dict(row)
            
            # Fall back to any non-superseded actual
            row = conn.execute(text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE entity_id = :entity_id
                  AND metric_key = :metric_key
                  AND period_key = :period_key
                  AND observation_type = 'actual'
                  AND is_superseded = FALSE
                ORDER BY as_of DESC NULLS LAST
                LIMIT 1
            """), {
                "entity_id": entity_id,
                "metric_key": metric_key,
                "period_key": period_key,
            }).mappings().fetchone()
            
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
            row = conn.execute(text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE entity_id = :entity_id
                  AND metric_key = :metric_key
                  AND period_key = :period_key
                  AND observation_type = :observation_type
                  AND as_of <= :as_of
                ORDER BY as_of DESC
                LIMIT 1
            """), {
                "entity_id": entity_id,
                "metric_key": metric_key,
                "period_key": period_key,
                "observation_type": observation_type,
                "as_of": as_of,
            }).mappings().fetchone()
            
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
            rows = conn.execute(text(f"""
                SELECT * FROM {self.schema}.observations
                WHERE entity_id = :entity_id
                  AND metric_key = :metric_key
                  AND period_key = :period_key
                ORDER BY as_of ASC
            """), {
                "entity_id": entity_id,
                "metric_key": metric_key,
                "period_key": period_key,
            }).mappings().fetchall()
            
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
                row = conn.execute(text(f"""
                    SELECT * FROM {self.schema}.observations
                    WHERE observation_id = :id
                """), {"id": current_id}).mappings().fetchone()
                
                if not row:
                    break
                
                chain.insert(0, dict(row))
                current_id = row.get("supersedes_id")
            
            # Walk forward (superseded_by_id)
            current_id = observation_id
            seen = {observation_id}
            while current_id:
                row = conn.execute(text(f"""
                    SELECT * FROM {self.schema}.observations
                    WHERE supersedes_id = :id
                """), {"id": current_id}).mappings().fetchone()
                
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
            total = conn.execute(text(f"""
                SELECT COUNT(*) FROM {self.schema}.observations
            """)).scalar() or 0
            
            # By type
            by_type = dict(conn.execute(text(f"""
                SELECT observation_type, COUNT(*)
                FROM {self.schema}.observations
                GROUP BY observation_type
            """)).fetchall())
            
            # Superseded count
            superseded = conn.execute(text(f"""
                SELECT COUNT(*) FROM {self.schema}.observations
                WHERE is_superseded = TRUE
            """)).scalar() or 0
            
            # Entity count
            entities = conn.execute(text(f"""
                SELECT COUNT(DISTINCT entity_id) FROM {self.schema}.observations
            """)).scalar() or 0
            
            return {
                "total": total,
                "by_type": by_type,
                "superseded": superseded,
                "entities": entities,
                "schema": self.schema,
                "timescale_enabled": self.use_timescale,
            }
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _observation_to_dict(self, obs: Any) -> dict[str, Any]:
        """Convert Observation dataclass to storage dict."""
        import uuid
        
        # Generate observation_key if not present
        if hasattr(obs, "observation_key"):
            obs_key = obs.observation_key
        else:
            # Build key from components
            parts = [
                obs.entity_id,
                obs.metric.canonical_key if hasattr(obs.metric, "canonical_key") else str(obs.metric),
                obs.period.canonical_key if hasattr(obs.period, "canonical_key") else str(obs.period),
                obs.as_of.isoformat() if obs.as_of else "na",
            ]
            if hasattr(obs, "provenance_ref") and obs.provenance_ref:
                parts.append(obs.provenance_ref.external_id)
            from hashlib import sha256
            obs_key = sha256("|".join(parts).encode()).hexdigest()[:32]
        
        return {
            "observation_id": getattr(obs, "observation_id", str(uuid.uuid4())),
            "observation_key": obs_key,
            "entity_id": obs.entity_id,
            "security_id": getattr(obs, "security_id", None),
            "metric_key": obs.metric.canonical_key if hasattr(obs.metric, "canonical_key") else str(obs.metric),
            "period_key": obs.period.canonical_key if hasattr(obs.period, "canonical_key") else str(obs.period),
            "observation_type": obs.observation_type.value if hasattr(obs.observation_type, "value") else str(obs.observation_type),
            "value_normalized": float(obs.value.value_normalized),
            "value_raw": float(obs.value.value_raw),
            "value_unit": obs.value.unit,
            "value_scale": obs.value.scale,
            "value_currency": obs.value.currency,
            "value_string": getattr(obs, "value_string", None),
            "fiscal_year": obs.period.fiscal_year,
            "fiscal_quarter": getattr(obs.period, "quarter", None),
            "period_type": obs.period.period_type.value if hasattr(obs.period.period_type, "value") else str(obs.period.period_type),
            "period_start": getattr(obs.period, "period_start", None),
            "period_end": getattr(obs.period, "period_end", None),
            "as_of": obs.as_of,
            "captured_at": getattr(obs, "captured_at", datetime.now(timezone.utc)),
            "provenance_kind": obs.provenance_ref.kind.value if obs.provenance_ref and hasattr(obs.provenance_ref.kind, "value") else None,
            "provenance_external_id": obs.provenance_ref.external_id if obs.provenance_ref else None,
            "source_vendor": obs.source_key.vendor.value if obs.source_key and obs.source_key.vendor else None,
            "source_dataset": obs.source_key.dataset if obs.source_key else None,
            "source_field": obs.source_key.field_name if obs.source_key else None,
            "estimate_scope": obs.estimate_info.scope.value if obs.estimate_info and hasattr(obs.estimate_info.scope, "value") else None,
            "estimator": obs.estimate_info.estimator if obs.estimate_info else None,
            "num_estimates": obs.estimate_info.num_estimates if obs.estimate_info else None,
            "high_estimate": float(obs.estimate_info.high_estimate) if obs.estimate_info and obs.estimate_info.high_estimate else None,
            "low_estimate": float(obs.estimate_info.low_estimate) if obs.estimate_info and obs.estimate_info.low_estimate else None,
            "supersedes_id": getattr(obs, "supersedes_id", None),
            "is_superseded": getattr(obs, "superseded_by_id", None) is not None,
            "confidence": getattr(obs, "confidence", 1.0),
            "content": json.dumps({
                "raw_value": getattr(obs, "raw_value", None),
                "notes": getattr(obs, "notes", None),
            }),
        }
