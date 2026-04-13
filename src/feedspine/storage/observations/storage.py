"""
Observation Storage Backend - Optimized for Financial Time-Series.

Specialized storage for Observation data type with:
- Time-based partitioning (by captured_at)
- Supersession chain tracking
- Efficient period-based queries
- Optional TimescaleDB integration for compression

Usage:
    from feedspine.storage.observations import ObservationStorage

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

import re

from spine.core.logging import get_logger

from feedspine.storage.observations.converter import ObservationConverterMixin
from feedspine.storage.observations.core_operations import CoreOperationsMixin
from feedspine.storage.observations.query_operations import QueryOperationsMixin

logger = get_logger(__name__)

# Valid SQL identifier pattern — letters, digits, underscores only
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class ObservationStorage(
    CoreOperationsMixin,
    QueryOperationsMixin,
    ObservationConverterMixin,
):
    """
    Observation storage with PostgreSQL optimization.

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
        if not _SAFE_IDENTIFIER_RE.match(schema):
            raise ValueError(f"Invalid schema name: {schema!r}")
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
            conn.execute(
                text(f"""
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
            """)
            )

            # Create indexes
            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_entity_metric_period
                ON {self.schema}.observations (entity_id, metric_key, period_key)
            """)
            )

            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_entity_captured
                ON {self.schema}.observations (entity_id, captured_at)
            """)
            )

            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_metric_period
                ON {self.schema}.observations (metric_key, period_key)
            """)
            )

            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_fiscal
                ON {self.schema}.observations (fiscal_year, fiscal_quarter)
            """)
            )

            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_as_of
                ON {self.schema}.observations (as_of)
            """)
            )

            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_type
                ON {self.schema}.observations (observation_type)
            """)
            )

            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_not_superseded
                ON {self.schema}.observations (entity_id, metric_key, period_key)
                WHERE is_superseded = FALSE
            """)
            )

            # BRIN index for time-ordered queries (very efficient)
            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_captured_brin
                ON {self.schema}.observations USING BRIN (captured_at)
            """)
            )

            # GIN index for JSONB queries
            conn.execute(
                text(f"""
                CREATE INDEX IF NOT EXISTS ix_obs_content_gin
                ON {self.schema}.observations USING GIN (content)
            """)
            )

            conn.commit()

            # TimescaleDB hypertable (if enabled)
            if self.use_timescale:
                try:
                    conn.execute(
                        text(f"""
                        SELECT create_hypertable(
                            '{self.schema}.observations',
                            'captured_at',
                            chunk_time_interval => INTERVAL '1 month',
                            if_not_exists => TRUE,
                            migrate_data => TRUE
                        )
                    """)
                    )

                    # Enable compression
                    conn.execute(
                        text(f"""
                        ALTER TABLE {self.schema}.observations SET (
                            timescaledb.compress,
                            timescaledb.compress_segmentby = 'entity_id, metric_key'
                        )
                    """)
                    )

                    conn.execute(
                        text(f"""
                        SELECT add_compression_policy(
                            '{self.schema}.observations',
                            INTERVAL '{self.compression_after_days} days',
                            if_not_exists => TRUE
                        )
                    """)
                    )

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
