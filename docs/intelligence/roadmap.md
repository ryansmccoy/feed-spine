# Intelligence Features Roadmap

**Financial Intelligence & Knowledge Graph Capabilities**

*Beyond basic feed capture - towards actionable insights*

---

## Overview

Building on the core FeedSpine framework, this roadmap outlines tiered features for transforming raw filings into **financial intelligence**.

Each tier builds on the previous:
- **Basic**: Core extraction, direct from filings
- **Intermediate**: Cross-filing analysis, entity linking
- **Advanced**: Multi-source synthesis, temporal analysis

---

## 🟢 BASIC Features

*Direct extraction from single documents - the foundation*

### 1. Subsidiary Extraction (Exhibit 21)

Extract the complete corporate tree from 10-K Exhibit 21.

```python
def extract_subsidiaries(filing_10k) -> list[Subsidiary]:
    """Extract subsidiary list from Exhibit 21."""
    return [
        Subsidiary(
            parent_id="apple_inc",
            name="Apple Operations International Limited",
            jurisdiction="IE",  # Ireland
            ownership_pct=100.0,
        ),
        # ... 200+ subsidiaries
    ]
```

**Use cases:**
- Corporate structure visualization
- Tax jurisdiction analysis
- M&A due diligence

---

### 2. Major Customer Extraction (Item 101)

Extract customer concentration disclosures (SEC requires >10% revenue).

```python
def extract_major_customers(filing_10k) -> list[CustomerRelationship]:
    return [
        CustomerRelationship(
            company_id="apple_inc",
            customer_name="Undisclosed cellular carrier",
            revenue_pct=0.15,
            year=2024,
        ),
    ]
```

**Use cases:**
- Revenue concentration risk
- Customer dependency analysis

---

### 3. Executive Compensation (DEF 14A)

Extract NEO compensation from proxy statements.

```python
def extract_executive_comp(proxy_filing) -> list[ExecutiveCompensation]:
    return [
        ExecutiveCompensation(
            person_name="Tim Cook",
            title="CEO",
            salary=3_000_000,
            stock_awards=58_000_000,
            total=74_500_000,
        ),
    ]
```

**Use cases:**
- Compensation benchmarking
- Pay-for-performance analysis

---

### 4. 8-K Item Classification

Classify 8-K filings by item number for event routing.

```python
ITEM_DEFINITIONS = {
    "1.01": "Material Definitive Agreement",
    "2.02": "Results of Operations (Earnings)",
    "4.02": "Non-Reliance on Prior Financials",  # High priority!
    "5.02": "Executive/Director Changes",
}
```

**Use cases:**
- Event routing
- Alert prioritization

---

## 🟡 INTERMEDIATE Features

*Cross-filing analysis, entity resolution*

### 5. Executive Career Tracking

Track executives across companies over time using DEF 14A, 8-K, Form 4.

```python
def build_executive_career(person_name: str) -> CareerTimeline:
    return CareerTimeline(
        person_name="Lisa Jackson",
        roles=[
            Role(company="EPA", title="Administrator", start=2009, end=2013),
            Role(company="Apple", title="VP Environment", start=2013, end=None),
        ],
    )
```

**Use cases:**
- Executive network analysis
- Talent flow tracking

---

### 6. Institutional Ownership Changes (13-F)

Track institutional position changes quarter-over-quarter.

```python
def track_institutional_changes(company_id: str) -> InstitutionalAnalysis:
    return InstitutionalAnalysis(
        company_id="apple_inc",
        top_holders=[
            Holder(name="Vanguard", shares=1_300_000_000, change_pct=+0.2),
            Holder(name="Berkshire", shares=400_000_000, change_pct=-50.0),  # Big reduction!
        ],
    )
```

**Use cases:**
- "Smart money" tracking
- Concentration risk

---

### 7. Competitor Mapping

Build competitive landscape from SIC codes and 10-K mentions.

```python
def build_competitive_landscape(company_id: str) -> CompetitiveLandscape:
    return CompetitiveLandscape(
        company_id="apple_inc",
        sic_code="3571",
        mentioned_competitors=["Samsung", "Google", "Microsoft"],
    )
```

---

## 🔴 ADVANCED Features

*Multi-source synthesis, predictive signals*

### 8. Significant Development Detection

Identify material changes across filing versions.

```python
def detect_significant_changes(current: Filing, previous: Filing) -> list[Change]:
    return [
        Change(
            section="Risk Factors",
            change_type="new_risk",
            description="Added cybersecurity incident disclosure",
            severity="high",
        ),
    ]
```

---

### 9. Entity Resolution

Link mentions across documents to canonical entities.

```python
# "Tim Cook", "Timothy D. Cook", "Mr. Cook" → person:tim_cook
# "Apple Inc.", "Apple", "AAPL" → company:apple_inc
```

---

### 10. Knowledge Graph Construction

Build relationships from filings:

```
Apple Inc. --[employs]--> Tim Cook
Tim Cook --[sold_shares]--> Apple Inc. (Form 4)
Vanguard --[owns_8.5%]--> Apple Inc. (13-F)
Apple Inc. --[competitor_of]--> Samsung (10-K mention)
```

---

## LLM Integration

### Local (Ollama)

```python
from feedspine.ext.llm import OllamaProvider

llm = OllamaProvider(model="llama3.1:8b")
summary = await llm.summarize(filing_text, max_tokens=500)
```

### Cloud APIs

```python
from feedspine.ext.llm import OpenAIProvider, AnthropicProvider

# OpenAI
openai = OpenAIProvider(model="gpt-4o")

# Anthropic
claude = AnthropicProvider(model="claude-3-5-sonnet")

# With structured output (Instructor)
entities = await claude.extract(
    filing_text,
    response_model=list[Entity],
)
```

---

## Implementation Priority

| Feature | Complexity | Value | Priority |
|---------|------------|-------|----------|
| 8-K Classification | Low | High | 🔴 P0 |
| Subsidiary Extraction | Medium | High | 🔴 P0 |
| Executive Comp | Medium | Medium | 🟡 P1 |
| Customer Extraction | Medium | Medium | 🟡 P1 |
| 13-F Changes | Medium | High | 🟡 P1 |
| Executive Tracking | High | Medium | 🟢 P2 |
| Entity Resolution | High | High | 🟢 P2 |
| Knowledge Graph | High | High | 🟢 P2 |
