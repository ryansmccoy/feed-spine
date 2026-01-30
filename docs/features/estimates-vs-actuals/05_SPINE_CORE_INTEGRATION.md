# spine-core Integration

> Integrating with spine-core pipeline infrastructure for production-quality earnings data.

## Overview

The earnings feature follows the spine-core architecture:
- **spine-core**: Framework (Pipeline, Workflow, Registry, Steps, Execution Tracking)
- **spine-domains/earnings**: Domain-specific implementation

### Key Components

| Component | Purpose |
|-----------|---------|
| Pipeline | Base class for data processing |
| Workflow | Multi-step orchestration |
| Step | Individual workflow unit |
| Registry | Pipeline/workflow discovery |
| ExecutionContext | Lineage tracking |
| ExecutionRepository | Persistence layer |
| WorkflowRunner | Execution engine |

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          EARNINGS DOMAIN ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  spine-core (framework)              spine-domains/earnings (this domain)       │
│  ─────────────────────               ────────────────────────────────────       │
│                                                                                  │
│  ┌─────────────────┐                 ┌─────────────────────────────────────┐   │
│  │ Pipeline        │ ◀──implements── │ earnings/pipelines.py               │   │
│  │   - run()       │                 │   - IngestCalendarPipeline          │   │
│  │   - spec        │                 │   - EnrichEstimatesPipeline         │   │
│  │   - validate    │                 │   - CompareActualsPipeline          │   │
│  └─────────────────┘                 └─────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────┐                 ┌─────────────────────────────────────┐   │
│  │ Workflow        │ ◀──uses──────── │ earnings/workflows.py               │   │
│  │   - steps       │                 │   - earnings.daily_calendar         │   │
│  │   - context     │                 │   - earnings.watch_releases         │   │
│  └─────────────────┘                 │   - earnings.compare_batch          │   │
│                                      └─────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────┐                 ┌─────────────────────────────────────┐   │
│  │ Step            │ ◀──uses──────── │ earnings/steps.py                   │   │
│  │   - pipeline()  │                 │   - validate_release()              │   │
│  │   - lambda_()   │                 │   - compute_surprise()              │   │
│  │   - choice()    │                 │   - route_by_status()               │   │
│  └─────────────────┘                 └─────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────┐                 ┌─────────────────────────────────────┐   │
│  │ Registry        │ ◀──registers─── │ @register_pipeline(...)             │   │
│  │ PIPELINES       │                 │ @register_workflow(...)             │   │
│  └─────────────────┘                 └─────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Registration Pattern

Following spine-core conventions:

```python
from spine.framework.pipelines import Pipeline, PipelineResult, PipelineStatus
from spine.framework.registry import register_pipeline
from spine.framework.params import ParamDef, PipelineSpec, date_format

@register_pipeline("earnings.ingest_calendar")
class IngestCalendarPipeline(Pipeline):
    """
    Ingest earnings calendar from multiple sources.
    
    Params:
        target_date: Calendar date to ingest (ISO format)
        sources: Comma-separated source names (default: "sec,finnhub")
        entity_filter: Optional entity IDs to filter
        force: Re-ingest even if already done
    """
    
    name = "earnings.ingest_calendar"
    description = "Fetch and normalize earnings calendar from SEC, Finnhub, etc."
    
    spec = PipelineSpec(
        required_params={
            "target_date": ParamDef(
                name="target_date",
                type=str,
                description="Target date in ISO format (YYYY-MM-DD)",
                validator=date_format,
            ),
        },
        optional_params={
            "sources": ParamDef(
                name="sources",
                type=str,
                description="Comma-separated source names",
                default="sec,finnhub",
            ),
            "entity_filter": ParamDef(
                name="entity_filter",
                type=str,
                description="Filter to specific entity IDs (comma-separated)",
            ),
            "force": ParamDef(
                name="force",
                type=bool,
                default=False,
            ),
        },
        examples=[
            "spine run earnings.ingest_calendar -p target_date=2026-01-30",
            "spine run earnings.ingest_calendar -p target_date=2026-01-30 -p sources=sec",
        ],
    )
    
    def run(self) -> PipelineResult:
        # Implementation follows...
```

---

## Workflow Definition Pattern

```python
from spine.orchestration import Workflow, Step

# Register workflow
earnings_daily_workflow = Workflow(
    name="earnings.daily_calendar",
    domain="earnings",
    description="Daily earnings calendar ingestion and comparison",
    steps=[
        # Step 1: Ingest calendar from all sources
        Step.pipeline(
            name="ingest",
            pipeline_name="earnings.ingest_calendar",
            params={"sources": "sec,finnhub,company_ir"},
        ),
        
        # Step 2: Validate we got data
        Step.lambda_(
            name="validate_ingest",
            handler=validate_calendar_ingest,
            error_policy=ErrorPolicy.FAIL,
        ),
        
        # Step 3: Resolve entities
        Step.pipeline(
            name="resolve_entities",
            pipeline_name="earnings.resolve_entities",
        ),
        
        # Step 4: Enrich with estimates
        Step.pipeline(
            name="enrich_estimates",
            pipeline_name="earnings.enrich_estimates",
        ),
        
        # Step 5: Route based on release status
        Step.choice(
            name="check_releases",
            condition=has_new_releases,
            then_step="compare_actuals",
            else_step="store_calendar",
        ),
        
        # Step 6a: Compare actuals (if released)
        Step.pipeline(
            name="compare_actuals",
            pipeline_name="earnings.compare_actuals",
        ),
        
        # Step 6b: Just store (if not released)
        Step.pipeline(
            name="store_calendar",
            pipeline_name="earnings.store_calendar",
        ),
    ],
)
```

---

## Domain File Structure

```
feedspine/src/feedspine/earnings/
├── __init__.py              # Public API exports
├── pipelines.py             # Pipeline classes (IngestCalendar, EnrichEstimates, etc.)
├── workflows.py             # Workflow definitions
├── steps.py                 # Lambda step handlers
├── calculations.py          # Business logic (surprise calculation, etc.)
├── connectors/              # Data source connectors
│   ├── __init__.py
│   ├── base.py              # BaseConnector ABC
│   ├── sec_edgar.py         # SEC EDGAR 8-K connector
│   ├── finnhub.py           # Finnhub calendar API
│   └── company_ir.py        # Company IR page scraper
├── normalizers.py           # Raw → normalized records
├── validators.py            # Quality checks
├── models.py                # Pydantic models
├── schema/                  # Database schema
│   ├── 00_tables.sql
│   └── 02_views.sql
└── docs/                    # Domain documentation
    └── PIPELINES.md
```

---

## API Design: Well-Named Methods with Customization

### Calendar Service

```python
class EarningsCalendarService:
    """
    Service for earnings calendar operations.
    
    All methods follow naming convention:
    - get_*: Synchronous retrieval
    - fetch_*: Async retrieval from external sources
    - compute_*: Calculations that may be cached
    - store_*: Persistence operations
    """
    
    def __init__(
        self,
        connectors: list[BaseConnector] | None = None,
        entity_resolver: EntityResolver | None = None,
        storage: StorageBackend | None = None,
    ):
        """
        Initialize with optional dependency injection.
        
        Args:
            connectors: List of data source connectors (default: all registered)
            entity_resolver: Entity resolution service (default: EntitySpine)
            storage: Storage backend (default: configured default)
        """
        self.connectors = connectors or get_default_connectors()
        self.entity_resolver = entity_resolver or get_entity_resolver()
        self.storage = storage or get_default_storage()
    
    # =========================================================================
    # Calendar Retrieval
    # =========================================================================
    
    async def fetch_calendar(
        self,
        target_date: date,
        *,
        sources: list[str] | None = None,
        include_estimates: bool = True,
        include_links: bool = True,
        entity_ids: list[str] | None = None,
        tickers: list[str] | None = None,
        sectors: list[str] | None = None,
        min_market_cap: float | None = None,
        max_results: int | None = None,
        timeout_seconds: float = 30.0,
    ) -> CalendarResult:
        """
        Fetch earnings calendar from configured sources.
        
        Args:
            target_date: The date to fetch calendar for.
            sources: Source names to query (default: all configured).
            include_estimates: Include consensus estimates.
            include_links: Include IR/PR/SEC links.
            entity_ids: Filter to specific EntitySpine IDs.
            tickers: Filter to specific tickers.
            sectors: Filter to specific sectors.
            min_market_cap: Minimum market cap filter.
            max_results: Maximum events to return.
            timeout_seconds: Request timeout.
            
        Returns:
            CalendarResult with events and metadata.
            
        Example:
            result = await service.fetch_calendar(
                date(2026, 1, 30),
                sources=["sec", "finnhub"],
                sectors=["Technology"],
                include_estimates=True,
            )
        """
        ...
    
    async def fetch_calendar_range(
        self,
        start_date: date,
        end_date: date,
        *,
        sources: list[str] | None = None,
        batch_size: int = 7,
        **kwargs,
    ) -> AsyncIterator[CalendarResult]:
        """
        Fetch calendar for a date range, yielding results as batches complete.
        
        Args:
            start_date: Start of range (inclusive).
            end_date: End of range (inclusive).
            batch_size: Days per batch.
            **kwargs: Passed to fetch_calendar.
            
        Yields:
            CalendarResult for each batch.
        """
        ...
    
    def get_calendar_cached(
        self,
        target_date: date,
        *,
        max_age_minutes: int = 60,
        **kwargs,
    ) -> CalendarResult | None:
        """
        Get calendar from cache if fresh enough.
        
        Args:
            target_date: Target date.
            max_age_minutes: Maximum cache age to accept.
            **kwargs: Filter criteria.
            
        Returns:
            Cached result or None if stale/missing.
        """
        ...
    
    # =========================================================================
    # Release Monitoring
    # =========================================================================
    
    async def watch_releases(
        self,
        target_date: date | None = None,
        *,
        poll_interval_seconds: float = 60.0,
        on_release: Callable[[EarningsRelease], Awaitable[None]] | None = None,
        on_change: Callable[[CalendarChange], Awaitable[None]] | None = None,
        entity_ids: list[str] | None = None,
        tickers: list[str] | None = None,
        stop_after: timedelta | None = None,
    ) -> AsyncIterator[CalendarEvent]:
        """
        Watch for earnings releases in real-time.
        
        Args:
            target_date: Date to watch (default: today).
            poll_interval_seconds: How often to poll sources.
            on_release: Callback for new releases.
            on_change: Callback for any calendar change.
            entity_ids: Filter to specific entities.
            tickers: Filter to specific tickers.
            stop_after: Stop watching after duration.
            
        Yields:
            CalendarEvent for each detected release.
            
        Example:
            async for event in service.watch_releases(
                target_date=date.today(),
                tickers=["AAPL", "MSFT"],
                poll_interval_seconds=30,
            ):
                print(f"🔔 {event.ticker} just released!")
        """
        ...
    
    # =========================================================================
    # Comparison Operations
    # =========================================================================
    
    async def compute_surprise(
        self,
        entity_id: str,
        period: str,
        *,
        estimate_source: str | None = None,
        actual_source: str | None = None,
        metrics: list[str] | None = None,
    ) -> SurpriseResult:
        """
        Compute earnings surprise for an entity.
        
        Args:
            entity_id: EntitySpine entity ID.
            period: Fiscal period (e.g., "2026:Q1").
            estimate_source: Preferred estimate source.
            actual_source: Preferred actual source.
            metrics: Metrics to compare (default: ["eps", "revenue"]).
            
        Returns:
            SurpriseResult with beat/miss analysis.
        """
        ...
    
    async def compute_surprise_batch(
        self,
        entity_ids: list[str],
        period: str,
        *,
        concurrency: int = 10,
        **kwargs,
    ) -> AsyncIterator[SurpriseResult]:
        """
        Compute surprises for multiple entities concurrently.
        
        Args:
            entity_ids: List of entity IDs.
            period: Fiscal period.
            concurrency: Max concurrent computations.
            **kwargs: Passed to compute_surprise.
            
        Yields:
            SurpriseResult for each entity.
        """
        ...
    
    # =========================================================================
    # Storage Operations
    # =========================================================================
    
    async def store_calendar(
        self,
        result: CalendarResult,
        *,
        upsert: bool = True,
        capture_id: str | None = None,
    ) -> StoreResult:
        """
        Persist calendar to storage.
        
        Args:
            result: Calendar result to store.
            upsert: Update existing records (vs insert-only).
            capture_id: Tracking ID for provenance.
            
        Returns:
            StoreResult with counts.
        """
        ...
    
    async def store_observation(
        self,
        entity_id: str,
        metric: str,
        value: Decimal,
        period: str,
        *,
        source: str,
        as_of: date | None = None,
        capture_id: str | None = None,
    ) -> str:
        """
        Store a single observation (estimate or actual).
        
        Args:
            entity_id: EntitySpine entity ID.
            metric: Metric name (e.g., "eps_estimate", "eps_actual").
            value: Metric value.
            period: Fiscal period.
            source: Data source name.
            as_of: As-of date for point-in-time.
            capture_id: Tracking ID.
            
        Returns:
            Observation ID.
        """
        ...
```

### Response Types

```python
@dataclass(frozen=True)
class CalendarResult:
    """Result from calendar fetch operations."""
    
    target_date: date
    events: tuple[CalendarEvent, ...]
    sources_queried: tuple[str, ...]
    sources_succeeded: tuple[str, ...]
    sources_failed: tuple[str, ...]
    fetch_duration_ms: float
    cached: bool = False
    
    @property
    def event_count(self) -> int:
        return len(self.events)
    
    @property
    def released_count(self) -> int:
        return sum(1 for e in self.events if e.status == EventStatus.RELEASED)
    
    @property
    def scheduled_count(self) -> int:
        return sum(1 for e in self.events if e.status == EventStatus.SCHEDULED)
    
    def filter(
        self,
        *,
        status: EventStatus | None = None,
        tickers: list[str] | None = None,
        sectors: list[str] | None = None,
    ) -> "CalendarResult":
        """Return filtered copy."""
        ...
    
    def to_dataframe(self) -> "pd.DataFrame":
        """Convert to pandas DataFrame."""
        ...
    
    def to_dict(self) -> dict:
        """Serialize to dict."""
        ...


@dataclass(frozen=True) 
class SurpriseResult:
    """Result from surprise calculation."""
    
    entity_id: str
    ticker: str
    period: str
    
    # EPS
    eps_estimate: Decimal | None
    eps_actual: Decimal | None
    eps_surprise: Decimal | None  # (actual - estimate) / |estimate|
    eps_direction: SurpriseDirection | None
    
    # Revenue
    revenue_estimate: Decimal | None
    revenue_actual: Decimal | None
    revenue_surprise: Decimal | None
    revenue_direction: SurpriseDirection | None
    
    # Metadata
    estimate_source: str | None
    actual_source: str | None
    computed_at: datetime
    
    @property
    def beat_eps(self) -> bool:
        return self.eps_direction == SurpriseDirection.BEAT
    
    @property
    def miss_eps(self) -> bool:
        return self.eps_direction == SurpriseDirection.MISS
    
    @property
    def beat_revenue(self) -> bool:
        return self.revenue_direction == SurpriseDirection.BEAT
```

---

## Execution Tracking

spine-core tracks all pipeline and workflow executions in PostgreSQL tables.

### Database Schema

```sql
-- Core execution tracking table
CREATE TABLE executions (
    id              TEXT PRIMARY KEY,     -- ULID
    pipeline_name   TEXT NOT NULL,
    params          JSONB DEFAULT '{}',
    logical_key     TEXT,                 -- For idempotency/deduplication
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- pending, queued, running, completed, failed, cancelled
    backend         TEXT,                 -- "local", "celery", "temporal"
    backend_run_id  TEXT,                 -- External run ID
    parent_execution_id TEXT REFERENCES executions(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    
    UNIQUE (logical_key) WHERE status IN ('pending', 'queued', 'running')
);

-- Execution events for detailed tracking
CREATE TABLE execution_events (
    id              TEXT PRIMARY KEY,     -- ULID
    execution_id    TEXT NOT NULL REFERENCES executions(id),
    event_type      TEXT NOT NULL,        -- step_started, step_completed, step_failed
    payload         JSONB DEFAULT '{}',
    idempotency_key TEXT,                 -- Prevent duplicate events
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE (idempotency_key)
);

-- Indexes for common queries
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_pipeline ON executions(pipeline_name);
CREATE INDEX idx_executions_created ON executions(created_at DESC);
CREATE INDEX idx_execution_events_execution ON execution_events(execution_id);
```

### ExecutionContext

Every pipeline run gets an `ExecutionContext` for lineage tracking:

```python
from spine.core import ExecutionContext, new_context, new_batch_id

# Create root context (new execution)
ctx = new_context(batch_id=new_batch_id("earnings_daily"))
# ctx.execution_id = "01HXYZ..."
# ctx.batch_id = "earnings_daily_20260129T083022_a1b2c3d4"

# All DB writes include context
conn.execute(
    "INSERT INTO earnings_calendar (execution_id, batch_id, ...) VALUES (%s, %s, ...)",
    (ctx.execution_id, ctx.batch_id, ...)
)

# Sub-pipeline gets child context
child_ctx = ctx.child()
# child_ctx.parent_execution_id = ctx.execution_id
# child_ctx.batch_id = ctx.batch_id (inherited)
```

### ExecutionRepository

CRUD operations for execution records:

```python
from spine.repositories import ExecutionRepository

# Create execution
execution_id = ExecutionRepository.create(
    pipeline_name="earnings.ingest_calendar",
    params={"target_date": "2026-01-30"},
    logical_key="earnings_calendar_2026-01-30",  # Prevents concurrent runs
)

# Update status
ExecutionRepository.update_status(execution_id, "running")
ExecutionRepository.update_status(execution_id, "completed")
ExecutionRepository.update_status(execution_id, "failed", error_message="API timeout")

# Query executions
executions = ExecutionRepository.list_executions(
    status="failed",
    pipeline_name="earnings.%",
    limit=10,
)

# Check for conflicts (idempotency)
conflict = ExecutionRepository.check_logical_key_conflict("earnings_calendar_2026-01-30")
if conflict:
    raise ValueError(f"Execution already running: {conflict}")
```

### Event Emission

Track step-level progress:

```python
from spine.repositories import ExecutionEventRepository

# Emit events during workflow
ExecutionEventRepository.emit(
    execution_id=ctx.execution_id,
    event_type="step_started",
    payload={"step_name": "ingest", "pipeline": "earnings.ingest_calendar"},
)

ExecutionEventRepository.emit(
    execution_id=ctx.execution_id,
    event_type="step_completed",
    payload={"step_name": "ingest", "records_created": 150, "duration_ms": 2340},
    idempotency_key=f"{ctx.execution_id}:ingest:completed",  # Prevent duplicates
)

# Query events
events = ExecutionEventRepository.get_events(execution_id)
```

### WorkflowResult

The `WorkflowRunner` returns a detailed result:

```python
from spine.orchestration import WorkflowRunner, WorkflowStatus

runner = WorkflowRunner()
result = runner.execute(earnings_daily_workflow, params={"target_date": "2026-01-30"})

# Result includes everything for tracking
result.workflow_name    # "earnings.daily_calendar"
result.run_id           # "01HXYZ..." (ULID)
result.status           # WorkflowStatus.COMPLETED
result.started_at       # datetime
result.completed_at     # datetime
result.duration_seconds # 45.2
result.completed_steps  # ["ingest", "validate", "enrich"]
result.failed_steps     # []
result.error_step       # None
result.error            # None

# Serialize for storage/alerting
result.to_dict()  # Full dict with step_executions
```

### capture-spine Integration

To persist executions in capture-spine (unified UI/alerts), see [06_CAPTURE_SPINE_INTEGRATION.md](06_CAPTURE_SPINE_INTEGRATION.md):

```python
from spine.adapters.capture_spine import CaptureSpineAdapter

adapter = CaptureSpineAdapter("http://capture-spine:8000")
adapter.store_execution(result)  # POSTs as record_type='pipeline_run'
```

---

## CLI Integration

```bash
# Run pipelines
spine run earnings.ingest_calendar -p target_date=2026-01-30
spine run earnings.ingest_calendar -p target_date=2026-01-30 -p sources=sec,finnhub

# Run workflows
spine workflow run earnings.daily_calendar -p target_date=2026-01-30

# Check status
spine workflow status earnings.daily_calendar

# List executions
spine executions list --status failed --pipeline "earnings.%"
spine executions get 01HXYZ...
spine executions events 01HXYZ...

# List pipelines
spine list-pipelines --domain earnings
```

---

## Next Steps

1. **Create earnings domain in spine-domains** following FINRA pattern
2. **Implement connectors** for SEC, Finnhub, company IR
3. **Wire up to spine-core** registry and runner
4. **Real data** via actual API calls
