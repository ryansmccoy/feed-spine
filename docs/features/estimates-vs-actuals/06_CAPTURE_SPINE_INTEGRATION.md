# Capture-Spine Integration

> **Display earnings data in capture-spine and track pipeline execution.**

---

## Overview

This document covers two integration patterns:
1. **Earnings data → capture-spine UI** - Display earnings as records in newsfeed
2. **spine-core execution → capture-spine** - Track pipeline runs as records

Both use the same mechanism: capture-spine's `records` table with `record_type` discrimination.

---

## 1. Earnings Data as Records

### Record Schema

```python
# Earnings release stored in capture-spine
RecordCreate(
    region="us",
    record_type="earnings",          # Key discriminator
    unique_id="MSFT-2024-Q3",        # Ticker + period
    entity_type="company",
    entity_id="MSFT",
    title="Microsoft Q3 2024 Earnings - Beat by 8.2%",
    url="https://sec.gov/cgi-bin/...",
    event_time=datetime(2024, 4, 23, 8, 0),
    metadata={
        # Core earnings data
        "eps_actual": 2.45,
        "eps_estimate": 2.26,
        "eps_surprise_pct": 8.2,
        "revenue_actual_b": 65.2,
        "revenue_estimate_b": 63.8,
        "revenue_surprise_pct": 2.2,
        
        # YoY comparisons
        "eps_yoy_pct": 12.5,
        "revenue_yoy_pct": 8.7,
        
        # Valuation metrics
        "pe_trailing": 35.2,
        "pe_forward_f1": 31.4,
        "pe_forward_f2": 28.1,
        "peg_ratio": 2.1,
        
        # Classification
        "market_cap_b": 3100,
        "industry_group": "Software",
        "report_time": "AMC",
        "fiscal_period": "Q3",
        "fiscal_year": 2024,
    }
)
```

### API Query

```typescript
// GET /api/reader/timeline?record_types=earnings
// Returns standard ReaderResponse with earnings-enriched metadata

interface EarningsRecord extends Record {
    metadata: {
        eps_actual: number;
        eps_estimate: number;
        eps_surprise_pct: number;
        revenue_actual_b: number;
        revenue_estimate_b: number;
        revenue_surprise_pct: number;
        // ... other fields
    }
}
```

---

## 2. Pipeline Execution Tracking

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     spine-core → capture-spine Integration                   │
└─────────────────────────────────────────────────────────────────────────────┘

    spine-core WorkflowRunner
           │
           │ on complete/fail
           ▼
    ┌──────────────────────┐
    │  CaptureSpineAdapter │  ← POST /api/records
    └──────────────────────┘
           │
           ▼
    capture-spine PostgreSQL
    ┌──────────────────────┐
    │ records table        │
    │ record_type=         │
    │   'pipeline_run'     │
    │ metadata = {         │
    │   workflow_name,     │
    │   run_id,            │
    │   status,            │
    │   duration_seconds,  │
    │   step_executions,   │
    │   error,             │
    │ }                    │
    └──────────────────────┘
           │
           ▼
    capture-spine Alert Rules
    ┌──────────────────────┐
    │ Rule: Pipeline Fail  │
    │ condition:           │
    │   record_type=       │
    │     'pipeline_run'   │
    │   metadata.status=   │
    │     'failed'         │
    │ → Slack notification │
    └──────────────────────┘
           │
           ▼
    capture-spine Newsfeed
    ┌──────────────────────┐
    │ 🔴 FINRA ingest fail │
    │ ✅ SEC sync complete │
    └──────────────────────┘
```

### Adapter Implementation

```python
# spine-core/packages/spine-core/src/spine/adapters/capture_spine.py
import httpx
from spine.orchestration import WorkflowResult, WorkflowStatus

class CaptureSpineAdapter:
    """Store workflow results in capture-spine."""
    
    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip('/')
        self.headers = {"X-API-Key": api_key} if api_key else {}
    
    def store_execution(self, result: WorkflowResult) -> str | None:
        """POST workflow result as a record."""
        record = {
            "region": "system",
            "record_type": "pipeline_run",
            "unique_id": result.run_id,
            "entity_type": "workflow",
            "entity_id": result.workflow_name,
            "title": f"{result.workflow_name} - {result.status.value}",
            "event_time": result.started_at.isoformat(),
            "metadata": result.to_dict(),
        }
        
        try:
            resp = httpx.post(
                f"{self.base_url}/api/records",
                json=record,
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("record_id")
        except Exception as e:
            logger.warning("capture_spine_store_failed", error=str(e))
            return None
```

### Usage

```python
from spine.adapters.capture_spine import CaptureSpineAdapter
from spine.orchestration import WorkflowRunner

# Configure adapter
adapter = CaptureSpineAdapter(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)

# Run workflow and store result
runner = WorkflowRunner()
result = runner.execute(earnings_daily_workflow)

# Post to capture-spine (shows in newsfeed, triggers alerts)
adapter.store_execution(result)
```

### Alert Rules

```yaml
# capture-spine alert configuration
alert_rules:
  - name: "Pipeline Failure"
    conditions:
      record_type: "pipeline_run"
      metadata.status: "failed"
    notification:
      priority: "high"
      channel: "slack"
      title: "🔴 Pipeline Failed: {entity_id}"
      body: |
        Workflow: {entity_id}
        Run ID: {unique_id}
        Error: {metadata.error}

  - name: "Pipeline Success (verbose)"
    enabled: false  # Optional - enable for debugging
    conditions:
      record_type: "pipeline_run"
      metadata.status: "completed"
    notification:
      priority: "info"
      title: "✅ {entity_id} completed in {metadata.duration_seconds}s"
```

---

## 3. Benefits of This Approach

| Benefit | Description |
|---------|-------------|
| **No new tables** | Uses existing `records` table |
| **Unified UI** | Pipeline runs show alongside earnings, filings |
| **Alert reuse** | Same alert rules engine for all record types |
| **Searchable** | capture-spine's search works for executions |
| **No duplication** | Don't need `ExecutionRepository` in spine-core |
| **Audit trail** | All executions persisted with full metadata |

---

## 4. Record Types Summary

| record_type | Purpose | entity_type |
|-------------|---------|-------------|
| `earnings` | Earnings releases | `company` |
| `pipeline_run` | Workflow executions | `workflow` |
| `sec-8k` | SEC 8-K filings | `company` |
| `news` | News articles | varies |

---

## Related Documents

- [05_SPINE_CORE_INTEGRATION.md](05_SPINE_CORE_INTEGRATION.md) - Pipeline/Workflow definitions
- [mockups/EarningsTable.tsx](mockups/EarningsTable.tsx) - Bloomberg-style table component
- [mockups/EarningsPage.tsx](mockups/EarningsPage.tsx) - Dual-panel page layout
