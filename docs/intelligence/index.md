# Intelligence Features

This section covers the intelligence and enrichment capabilities of FeedSpine - transforming raw feed data into actionable insights.

## Documentation

- **[Feature Roadmap](roadmap.md)** - Complete intelligence features roadmap
- **[Local LLM (Ollama)](llm-local.md)** - Privacy-first, offline inference
- **[Cloud LLM APIs](llm-cloud.md)** - OpenAI, Anthropic, AWS Bedrock

## Feature Tiers

### 🟢 Basic Features
Direct extraction from single documents:
- Subsidiary extraction (Exhibit 21)
- Customer/supplier extraction (Item 101)
- Executive compensation (DEF 14A)
- 8-K item classification

### 🟡 Intermediate Features  
Cross-document analysis:
- Executive career tracking
- Institutional ownership changes (13-F)
- Competitor mapping

### 🔴 Advanced Features
Multi-source synthesis:
- Significant development detection
- Entity resolution
- Knowledge graph construction

## Quick Example

```python
from feedspine.ext.llm import OllamaProvider

# Local LLM for privacy
llm = OllamaProvider(model="llama3.1:8b")

# Extract key facts from 8-K
facts = await llm.extract(
    filing_text,
    schema={
        "event_type": "string",
        "event_date": "string",
        "entities": "list[string]"
    }
)
```
