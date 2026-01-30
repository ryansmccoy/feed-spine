# Modern Earnings Intelligence

> **LLM-Powered Earnings Analysis**  
> Moving beyond the 10-year-old Excel macro to intelligent, real-time earnings insights.

---

## Vision

The Bloomberg earnings macro from 2015 showed a table with:
- TIME, TICKER, MKTCAP, Industry
- EPS ACT, EPS EST, SURP%
- Revenue, P/E ratios

**In 2026, with LLMs (local + Bedrock), we can do much more:**

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                      MODERN EARNINGS INTELLIGENCE PLATFORM                               │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌───────────────────────────────────────────────────────────────────────────────┐     │
│   │                        REAL-TIME DATA LAYER                                   │     │
│   │   SEC 8-K → py-sec-edgar → feedspine → capture-spine                         │     │
│   │   Finnhub estimates → feedspine observations                                  │     │
│   │   Company press releases → LLM extraction                                     │     │
│   └───────────────────────────────────────────────────────────────────────────────┘     │
│                                        │                                                 │
│                                        ▼                                                 │
│   ┌───────────────────────────────────────────────────────────────────────────────┐     │
│   │                        LLM ANALYSIS LAYER                                     │     │
│   │                                                                               │     │
│   │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │     │
│   │   │   8-K/PR    │   │   Surprise  │   │  Guidance   │   │  Sentiment  │      │     │
│   │   │  Parsing    │   │   Context   │   │  Extraction │   │  Analysis   │      │     │
│   │   │             │   │             │   │             │   │             │      │     │
│   │   │ "Extract    │   │ "Why did    │   │ "What is    │   │ "Is mgmt    │      │     │
│   │   │  EPS from   │   │  MSFT beat  │   │  FY26       │   │  tone       │      │     │
│   │   │  this 8-K"  │   │  by 8%?"    │   │  guidance?" │   │  bullish?"  │      │     │
│   │   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘      │     │
│   │                                                                               │     │
│   │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │     │
│   │   │   Segment   │   │   Peer      │   │   Risk      │   │   Q&A       │      │     │
│   │   │  Breakdown  │   │  Comparison │   │   Factors   │   │  Highlights │      │     │
│   │   │             │   │             │   │             │   │             │      │     │
│   │   │ "Cloud vs   │   │ "Compare    │   │ "What       │   │ "Key        │      │     │
│   │   │  Gaming"    │   │  to GOOGL"  │   │  risks?"    │   │  questions" │      │     │
│   │   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘      │     │
│   │                                                                               │     │
│   └───────────────────────────────────────────────────────────────────────────────┘     │
│                                        │                                                 │
│                                        ▼                                                 │
│   ┌───────────────────────────────────────────────────────────────────────────────┐     │
│   │                     INTELLIGENT PRESENTATION LAYER                            │     │
│   │                                                                               │     │
│   │   ┌──────────────────────────────────────────────────────────────────────┐   │     │
│   │   │  EARNINGS DASHBOARD (trading-desktop)                                │   │     │
│   │   │                                                                      │   │     │
│   │   │  ┌────────────────────────┬────────────────────────────────────────┐ │   │     │
│   │   │  │ LIVE FEED              │ ANALYSIS PANEL                         │ │   │     │
│   │   │  │                        │                                        │ │   │     │
│   │   │  │ 🔔 MSFT beat +8.2%    │ 📊 Why MSFT Beat:                      │ │   │     │
│   │   │  │    2 min ago          │                                        │ │   │     │
│   │   │  │                        │ • Cloud revenue +22% YoY              │ │   │     │
│   │   │  │ 🔔 AAPL beat +3.4%    │ • AI services drove margin expansion  │ │   │     │
│   │   │  │    5 min ago          │ • iPhone stable despite macro fears   │ │   │     │
│   │   │  │                        │                                        │ │   │     │
│   │   │  │ ⚠️ GOOGL miss -2.6%   │ 📈 Guidance: FY26 revenue +12-15%     │ │   │     │
│   │   │  │    8 min ago          │                                        │ │   │     │
│   │   │  │                        │ 🎯 Key Risks: Antitrust, competition  │ │   │     │
│   │   │  └────────────────────────┴────────────────────────────────────────┘ │   │     │
│   │   └──────────────────────────────────────────────────────────────────────┘   │     │
│   │                                                                               │     │
│   └───────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Data Capture (py-sec-edgar + feedspine)

**8-K Filing Detection:**
```python
# py-sec-edgar monitors SEC EDGAR for 8-K filings
# Item 2.02: Results of Operations (earnings release)

from py_sec_edgar import SECFeed

feed = SECFeed(form_types=["8-K"])
for filing in feed.watch():
    if "2.02" in filing.items:  # Results of Operations
        yield filing
```

**Press Release Capture:**
```python
# capture-spine captures company press releases
# Triggers on keywords: "reports", "earnings", "quarterly results"

from capture_spine import AlertRule

rule = AlertRule(
    name="Earnings Press Release",
    conditions={
        "title_contains": ["reports", "quarterly results", "earnings"],
        "source_type": "press_release",
    },
    actions=["enrich_with_llm", "store_as_earnings"],
)
```

---

### 2. LLM Analysis Layer

#### Deployment Options

| Option | Model | Use Case | Latency | Cost |
|--------|-------|----------|---------|------|
| **Local** | Llama 3.1 8B | Bulk processing | ~2s | Free |
| **Local** | Mistral 7B | Extraction | ~1s | Free |
| **Bedrock** | Claude 3.5 Sonnet | Complex analysis | ~3s | $$ |
| **Bedrock** | Claude 3 Haiku | Quick summaries | ~1s | $ |

#### Analysis Functions

```python
# feedspine/src/feedspine/intelligence/earnings.py

from feedspine.llm import LLMProvider, LocalLlama, BedrockClaude

class EarningsIntelligence:
    """LLM-powered earnings analysis."""
    
    def __init__(self, provider: LLMProvider = None):
        self.provider = provider or LocalLlama()  # Default to local
        self.bedrock = BedrockClaude()  # For complex analysis
    
    async def extract_earnings(self, filing_text: str) -> EarningsData:
        """Extract structured earnings from 8-K or press release."""
        prompt = """
        Extract the following from this earnings release:
        - EPS (actual)
        - Revenue (actual)
        - EPS guidance (if provided)
        - Revenue guidance (if provided)
        - Key segment breakdowns
        
        Return as JSON.
        
        Text: {text}
        """
        response = await self.provider.complete(prompt.format(text=filing_text))
        return EarningsData.model_validate_json(response)
    
    async def analyze_surprise(
        self, 
        actual: EarningsData, 
        estimate: EstimateData,
        filing_text: str,
    ) -> SurpriseAnalysis:
        """Use LLM to explain why earnings beat/missed."""
        # Use Bedrock for complex reasoning
        prompt = """
        Company beat/missed earnings estimates.
        
        Actual: EPS ${actual_eps}, Revenue ${actual_rev}B
        Estimate: EPS ${est_eps}, Revenue ${est_rev}B
        Surprise: {surprise_pct}%
        
        Based on the earnings release text, explain:
        1. What drove the beat/miss? (3-5 bullet points)
        2. Which segments outperformed/underperformed?
        3. Any one-time items affecting results?
        
        Text: {text}
        """
        response = await self.bedrock.complete(prompt.format(
            actual_eps=actual.eps,
            actual_rev=actual.revenue,
            est_eps=estimate.eps,
            est_rev=estimate.revenue,
            surprise_pct=actual.surprise_pct(estimate),
            text=filing_text[:8000],  # Token limit
        ))
        return SurpriseAnalysis.parse(response)
    
    async def extract_guidance(self, filing_text: str) -> GuidanceData:
        """Extract forward guidance from earnings release."""
        prompt = """
        Extract forward guidance from this earnings release:
        
        - Next quarter guidance (EPS, revenue ranges)
        - Full year guidance (EPS, revenue ranges)
        - Any qualitative guidance (e.g., "expect strong holiday season")
        - Guidance changes vs prior (raised, lowered, maintained)
        
        Return as JSON. Use null if not provided.
        
        Text: {text}
        """
        response = await self.provider.complete(prompt.format(text=filing_text))
        return GuidanceData.model_validate_json(response)
    
    async def sentiment_analysis(self, filing_text: str) -> SentimentScore:
        """Analyze management tone and sentiment."""
        prompt = """
        Analyze the tone and sentiment of this earnings release:
        
        1. Overall sentiment: bullish, neutral, or bearish (with confidence 0-1)
        2. Key positive phrases (list up to 5)
        3. Key negative phrases (list up to 5)
        4. Management confidence level: high, medium, low
        
        Text: {text}
        """
        response = await self.provider.complete(prompt.format(text=filing_text[:4000]))
        return SentimentScore.parse(response)
```

---

### 3. Intelligent Alerts

Beyond simple "beat by X%" alerts:

```python
# feedspine/src/feedspine/intelligence/alerts.py

class IntelligentAlerts:
    """LLM-enhanced alerting."""
    
    async def generate_alert(self, earnings: EarningsData, analysis: SurpriseAnalysis) -> Alert:
        """Generate human-readable alert with context."""
        
        if abs(earnings.surprise_pct) > 10:
            # Big move - use full analysis
            title = f"🔔 {earnings.ticker} {'BEAT' if earnings.surprise_pct > 0 else 'MISS'} by {abs(earnings.surprise_pct):.1f}%"
            body = f"""
{earnings.ticker} reported Q{earnings.quarter} results:

📊 **Results:**
- EPS: ${earnings.eps_actual} vs ${earnings.eps_estimate} est ({earnings.surprise_pct:+.1f}%)
- Revenue: ${earnings.revenue_actual}B vs ${earnings.revenue_estimate}B est

🎯 **Why the {'beat' if earnings.surprise_pct > 0 else 'miss'}:**
{analysis.bullet_points}

📈 **Guidance:** {analysis.guidance_summary}
"""
        else:
            # Inline - use concise format
            title = f"{earnings.ticker} {'beat' if earnings.surprise_pct > 0 else 'missed'} by {abs(earnings.surprise_pct):.1f}%"
            body = f"EPS ${earnings.eps_actual} vs ${earnings.eps_estimate} est"
        
        return Alert(
            title=title,
            body=body,
            severity="high" if abs(earnings.surprise_pct) > 10 else "medium",
            metadata=earnings.to_dict(),
        )
```

---

### 4. Trading Desktop Widget

```typescript
// trading-desktop/src/widgets/EarningsIntelligence.tsx

interface EarningsIntelligenceProps {
    ticker?: string;  // Optional filter to single company
}

export function EarningsIntelligence({ ticker }: EarningsIntelligenceProps) {
    const { data: earnings, isLoading } = useQuery({
        queryKey: ['earnings', 'live', ticker],
        queryFn: () => earningsApi.getLiveReleases({ ticker }),
        refetchInterval: 10000,  // 10 second refresh during earnings season
    });

    const [selectedRelease, setSelectedRelease] = useState<EarningsRelease | null>(null);
    
    const { data: analysis } = useQuery({
        queryKey: ['earnings', 'analysis', selectedRelease?.id],
        queryFn: () => earningsApi.getAnalysis(selectedRelease!.id),
        enabled: !!selectedRelease,
    });

    return (
        <div className="flex h-full">
            {/* Left: Live Feed */}
            <div className="w-1/3 border-r overflow-auto">
                <EarningsLiveFeed 
                    releases={earnings?.items ?? []}
                    onSelect={setSelectedRelease}
                    selected={selectedRelease}
                />
            </div>
            
            {/* Right: Analysis Panel */}
            <div className="w-2/3 p-4 overflow-auto">
                {selectedRelease && analysis ? (
                    <EarningsAnalysisPanel 
                        release={selectedRelease}
                        analysis={analysis}
                    />
                ) : (
                    <EmptyState message="Select a release to view analysis" />
                )}
            </div>
        </div>
    );
}

function EarningsAnalysisPanel({ release, analysis }: { 
    release: EarningsRelease; 
    analysis: EarningsAnalysis;
}) {
    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">{release.ticker}</h2>
                    <p className="text-gray-500">Q{release.quarter} {release.fiscal_year}</p>
                </div>
                <SurpriseBadge percent={release.eps_surprise_pct} />
            </div>
            
            {/* Results Grid */}
            <ResultsGrid 
                eps={{ actual: release.eps_actual, estimate: release.eps_estimate }}
                revenue={{ actual: release.revenue_actual, estimate: release.revenue_estimate }}
            />
            
            {/* LLM Analysis */}
            <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-semibold mb-2">
                    📊 Why {release.eps_surprise_pct > 0 ? 'Beat' : 'Missed'}
                </h3>
                <ul className="list-disc list-inside space-y-1">
                    {analysis.drivers.map((driver, i) => (
                        <li key={i}>{driver}</li>
                    ))}
                </ul>
            </div>
            
            {/* Guidance */}
            {analysis.guidance && (
                <GuidanceCard guidance={analysis.guidance} />
            )}
            
            {/* Sentiment */}
            <SentimentMeter sentiment={analysis.sentiment} />
            
            {/* Source Document */}
            <SourceDocumentLink url={release.filing_url} />
        </div>
    );
}
```

---

## Implementation Plan

### Phase 1: Data Foundation
| Task | Owner | Status |
|------|-------|--------|
| 8-K filing detection in py-sec-edgar | | ⏳ |
| Press release capture in capture-spine | | ⏳ |
| Estimates storage in feedspine | | ✅ |

### Phase 2: LLM Layer
| Task | Owner | Status |
|------|-------|--------|
| Local Llama integration | | ⏳ |
| Bedrock Claude integration | | ⏳ |
| Extraction prompts | | ⏳ |
| Analysis prompts | | ⏳ |

### Phase 3: Intelligence Features
| Task | Owner | Status |
|------|-------|--------|
| Surprise analysis | | ⏳ |
| Guidance extraction | | ⏳ |
| Sentiment analysis | | ⏳ |
| Intelligent alerts | | ⏳ |

### Phase 4: UI Integration
| Task | Owner | Status |
|------|-------|--------|
| Trading-desktop widget | | ⏳ |
| Live feed component | | ⏳ |
| Analysis panel | | ⏳ |

---

## Related Docs

- [estimates-vs-actuals](../estimates-vs-actuals/) - Core comparison engine
- [8k-release-capture](../8k-release-capture/) - 8-K detection and parsing
- [ECOSYSTEM.md](../../../../ECOSYSTEM.md) - Project integration overview
