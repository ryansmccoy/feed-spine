# 8-K Release Capture

> **Automated SEC 8-K Filing Detection and Earnings Extraction**  
> Leveraging py-sec-edgar + capture-spine's LLM capabilities

---

## Overview

8-K filings are the "instant notification" filings that companies must submit for material events. **Item 2.02** specifically covers "Results of Operations and Financial Condition" - i.e., earnings releases.

### Where Does This Logic Live?

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            8-K CAPTURE ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐                   │
│   │ py-sec-edgar│   →→→   │  feedspine  │   →→→   │capture-spine│                   │
│   │             │         │             │         │             │                   │
│   │ • SEC API   │         │ • Feed mgmt │         │ • LLM enrich│                   │
│   │ • 8-K fetch │         │ • Storage   │         │ • UI display│                   │
│   │ • XBRL parse│         │ • Compare   │         │ • Alerts    │                   │
│   └─────────────┘         └─────────────┘         └─────────────┘                   │
│                                                                                      │
│   ────────────────────────────────────────────────────────────────────────────────  │
│                                                                                      │
│   py-sec-edgar:                                                                      │
│     - Polls SEC EDGAR for new 8-K filings                                           │
│     - Downloads filing documents (8-K HTML, exhibits)                               │
│     - Parses basic metadata (CIK, filing date, items)                               │
│     - DOES NOT interpret content (no LLM)                                           │
│                                                                                      │
│   feedspine:                                                                         │
│     - Stores 8-K filing records as Feed items                                       │
│     - Associates with entities via EntitySpine                                      │
│     - Stores extracted earnings as Observations                                     │
│     - Comparison engine for estimates vs actuals                                    │
│                                                                                      │
│   capture-spine:                                                                     │
│     - LLM extraction layer (local + Bedrock)                                        │
│     - Parses 8-K content to extract earnings data                                   │
│     - Enriches records with analysis                                                │
│     - Real-time alerts and UI                                                       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### 1. py-sec-edgar: 8-K Detection

```python
# py_sec_edgar/feeds/sec_8k_feed.py

from py_sec_edgar.core import SECClient
from py_sec_edgar.models import Filing

class SEC8KFeed:
    """Monitor SEC EDGAR for 8-K filings."""
    
    # Item 2.02 = Results of Operations and Financial Condition
    EARNINGS_ITEMS = ["2.02"]
    
    def __init__(self, client: SECClient = None):
        self.client = client or SECClient()
    
    async def poll(self) -> list[Filing]:
        """Get recent 8-K filings from SEC."""
        filings = await self.client.get_filings(
            form_types=["8-K", "8-K/A"],  # Include amendments
            since=datetime.now() - timedelta(hours=24),
        )
        return filings
    
    async def get_earnings_releases(self) -> list[Filing]:
        """Filter to only Item 2.02 filings."""
        filings = await self.poll()
        return [f for f in filings if self._is_earnings_release(f)]
    
    def _is_earnings_release(self, filing: Filing) -> bool:
        """Check if filing contains Item 2.02."""
        return any(item in self.EARNINGS_ITEMS for item in filing.items)
    
    async def download_filing(self, filing: Filing) -> FilingContent:
        """Download full filing content."""
        # Get 8-K HTML document
        doc = await self.client.download_document(filing.primary_document_url)
        
        # Get press release exhibit (usually EX-99.1)
        exhibits = await self.client.download_exhibits(filing, types=["EX-99"])
        
        return FilingContent(
            filing=filing,
            document=doc,
            exhibits=exhibits,
        )
```

### 2. feedspine: Storage and Association

```python
# feedspine/src/feedspine/providers/sec_8k.py

from feedspine.core import Feed, FeedItem, Observation
from feedspine.models import EarningsRelease

class SEC8KProvider:
    """Feed provider for SEC 8-K filings."""
    
    def __init__(self, sec_feed: SEC8KFeed, entity_service: EntityService):
        self.sec_feed = sec_feed
        self.entities = entity_service
    
    async def sync(self) -> list[FeedItem]:
        """Sync recent 8-K filings into feedspine."""
        filings = await self.sec_feed.get_earnings_releases()
        items = []
        
        for filing in filings:
            # Resolve entity from CIK
            entity = await self.entities.get_by_cik(filing.cik)
            
            item = FeedItem(
                feed_id="sec-8k",
                external_id=filing.accession_number,
                entity_id=entity.id if entity else None,
                timestamp=filing.filing_date,
                title=f"{filing.company_name} - 8-K Item 2.02",
                content_url=filing.primary_document_url,
                metadata={
                    "cik": filing.cik,
                    "items": filing.items,
                    "accession_number": filing.accession_number,
                },
            )
            items.append(item)
        
        return await self.feed_store.upsert_many(items)
    
    async def store_extracted_earnings(
        self, 
        item: FeedItem, 
        earnings: EarningsRelease,
    ) -> Observation:
        """Store LLM-extracted earnings as an Observation."""
        return await self.observation_store.create(
            feed_item_id=item.id,
            entity_id=item.entity_id,
            observation_type="earnings_actual",
            period=f"Q{earnings.quarter}-{earnings.fiscal_year}",
            metrics={
                "eps_actual": earnings.eps,
                "revenue_actual": earnings.revenue,
                "eps_diluted": earnings.eps_diluted,
                "guidance_eps_low": earnings.guidance_eps_low,
                "guidance_eps_high": earnings.guidance_eps_high,
            },
        )
```

### 3. capture-spine: LLM Extraction

This is where the **actual intelligence** lives. capture-spine has existing LLM infrastructure.

```python
# capture_spine/enrichers/earnings_extractor.py

from capture_spine.llm import LLMProvider
from capture_spine.models import Record, EnrichmentResult

class EarningsExtractor:
    """LLM-powered earnings extraction from 8-K filings."""
    
    # Extraction prompt
    EXTRACTION_PROMPT = """
    Extract earnings information from this SEC 8-K filing (Item 2.02).
    
    Extract the following if present:
    - EPS (earnings per share) - both GAAP and non-GAAP if available
    - Revenue / Net sales
    - Net income
    - Gross margin
    - Operating income
    - Forward guidance (if provided)
    
    For each metric, extract:
    - Value (number)
    - Unit (dollars, millions, etc.)
    - Period (Q1, Q2, Q3, Q4, FY)
    - Fiscal year
    - Comparison to prior period (if mentioned)
    
    Return as JSON with this structure:
    {
        "eps_gaap": {"value": float, "period": str, "fiscal_year": int},
        "eps_non_gaap": {"value": float, "period": str, "fiscal_year": int},
        "revenue": {"value": float, "unit": str, "period": str, "fiscal_year": int},
        "net_income": {"value": float, "unit": str, "period": str, "fiscal_year": int},
        "guidance": {
            "eps_low": float,
            "eps_high": float,
            "revenue_low": float,
            "revenue_high": float,
            "period": str
        }
    }
    
    Use null for any fields not found in the document.
    
    Document:
    {document}
    """
    
    def __init__(self, provider: LLMProvider):
        self.provider = provider
    
    async def extract(self, record: Record) -> EnrichmentResult:
        """Extract earnings data from 8-K filing."""
        # Get the filing content
        content = record.content
        
        # Use local model for extraction (fast, cheap)
        response = await self.provider.complete(
            self.EXTRACTION_PROMPT.format(document=content[:12000]),
            model="llama-3.1-8b",  # Local model
        )
        
        try:
            earnings_data = json.loads(response)
            return EnrichmentResult(
                record_id=record.id,
                enrichment_type="earnings_extraction",
                data=earnings_data,
                confidence=0.9,
            )
        except json.JSONDecodeError:
            # Retry with more capable model
            response = await self.provider.complete(
                self.EXTRACTION_PROMPT.format(document=content[:12000]),
                model="claude-3-5-sonnet",  # Bedrock
            )
            earnings_data = json.loads(response)
            return EnrichmentResult(
                record_id=record.id,
                enrichment_type="earnings_extraction",
                data=earnings_data,
                confidence=0.95,
            )
```

### 4. Integration Pipeline

```python
# spine_core/pipelines/earnings_capture.py

from spine_core import Pipeline, Step
from py_sec_edgar.feeds import SEC8KFeed
from feedspine.providers import SEC8KProvider
from capture_spine.enrichers import EarningsExtractor

class EarningsCapturePipeline(Pipeline):
    """End-to-end pipeline for 8-K earnings capture."""
    
    name = "earnings_capture"
    
    steps = [
        Step("poll_sec", poll_sec_8k),
        Step("filter_earnings", filter_item_2_02),
        Step("store_feed_items", store_in_feedspine),
        Step("extract_earnings", extract_with_llm),
        Step("store_observations", store_observations),
        Step("send_alerts", send_earnings_alerts),
    ]
    
async def poll_sec_8k(ctx):
    """Step 1: Poll SEC for new 8-K filings."""
    sec_feed = SEC8KFeed()
    filings = await sec_feed.poll()
    ctx.data["filings"] = filings
    return len(filings)

async def filter_item_2_02(ctx):
    """Step 2: Filter to earnings releases (Item 2.02)."""
    filings = ctx.data["filings"]
    earnings_filings = [f for f in filings if "2.02" in f.items]
    ctx.data["earnings_filings"] = earnings_filings
    return len(earnings_filings)

async def store_in_feedspine(ctx):
    """Step 3: Store as feed items in feedspine."""
    provider = SEC8KProvider()
    items = await provider.sync(ctx.data["earnings_filings"])
    ctx.data["feed_items"] = items
    return len(items)

async def extract_with_llm(ctx):
    """Step 4: Extract earnings data with LLM."""
    extractor = EarningsExtractor()
    results = []
    for item in ctx.data["feed_items"]:
        result = await extractor.extract(item)
        results.append(result)
    ctx.data["extractions"] = results
    return len(results)

async def store_observations(ctx):
    """Step 5: Store extracted data as observations."""
    provider = SEC8KProvider()
    observations = []
    for item, extraction in zip(ctx.data["feed_items"], ctx.data["extractions"]):
        obs = await provider.store_extracted_earnings(item, extraction.data)
        observations.append(obs)
    ctx.data["observations"] = observations
    return len(observations)

async def send_earnings_alerts(ctx):
    """Step 6: Send alerts for significant earnings."""
    from capture_spine.alerts import AlertService
    
    alert_service = AlertService()
    for obs in ctx.data["observations"]:
        await alert_service.check_and_fire(
            event_type="earnings_release",
            data=obs.to_dict(),
        )
```

---

## Data Flow

```
SEC EDGAR                                                     Trading Desktop
    │                                                               ▲
    │ (RSS/API)                                                     │
    ▼                                                               │
┌─────────────┐                                                     │
│ py-sec-edgar│                                                     │
│             │                                                     │
│ • Poll 8-Ks │                                                     │
│ • Download  │                                                     │
└──────┬──────┘                                                     │
       │                                                            │
       │ (FilingContent)                                            │
       ▼                                                            │
┌─────────────┐         ┌─────────────┐         ┌─────────────┐    │
│  feedspine  │  ←───   │ spine-core  │  ←───   │capture-spine│────┘
│             │         │             │         │             │
│ • FeedItem  │         │ • Pipeline  │         │ • LLM       │
│ • Obs store │         │ • Execution │         │ • Alerts    │
└─────────────┘         └─────────────┘         └─────────────┘
       │                                               │
       │                                               │
       └───────────────────────────────────────────────┘
                           │
                           ▼
                   Observations DB
                   (estimates vs actuals)
```

---

## Configuration

```yaml
# config/earnings_capture.yaml

sec_8k:
  poll_interval: 300  # 5 minutes
  backfill_days: 7
  items_of_interest:
    - "2.02"  # Results of Operations
    - "7.01"  # Regulation FD Disclosure (sometimes used)

llm:
  extraction:
    model: "llama-3.1-8b"  # Fast, local
    fallback_model: "claude-3-5-sonnet"  # Bedrock, more capable
    max_tokens: 2000
  
  analysis:
    model: "claude-3-5-sonnet"  # Always use best model
    max_tokens: 4000

alerts:
  earnings_release:
    enabled: true
    channels: ["slack", "email"]
    
  earnings_surprise:
    enabled: true
    threshold_pct: 5.0  # Alert if surprise > 5%
    channels: ["slack", "pagerduty"]
```

---

## Related Docs

- [modern-earnings-intelligence](../modern-earnings-intelligence/) - Full LLM-powered analysis
- [estimates-vs-actuals](../estimates-vs-actuals/) - Comparison engine
- [ECOSYSTEM.md](../../../../ECOSYSTEM.md) - Project integration overview
