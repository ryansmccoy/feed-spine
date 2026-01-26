# Local LLM Integration (Ollama)

**Privacy-first, offline-capable, cost-free inference**

---

## Why Local LLMs?

| Benefit | Description |
|---------|-------------|
| **Privacy** | Sensitive financial data never leaves your machine |
| **Cost** | $0 per token - unlimited usage |
| **Offline** | Works without internet after model download |
| **Speed** | No API latency, parallel processing |
| **Control** | Choose models, fine-tune, no rate limits |

---

## Quick Setup

### 1. Install Ollama

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows - download from https://ollama.com
```

### 2. Pull Models

```bash
# Recommended models for SEC filing analysis
ollama pull llama3.2:3b      # Fast, good for extraction
ollama pull llama3.1:8b      # Balanced quality/speed  
ollama pull llama3.1:70b     # Best quality (48GB+ VRAM)
ollama pull nomic-embed-text # Embeddings for semantic search

# Verify installation
ollama list
```

### 3. Python Client

```bash
pip install ollama
```

```python
import ollama

response = ollama.chat(model='llama3.1:8b', messages=[
    {'role': 'user', 'content': 'Hello!'}
])
print(response['message']['content'])
```

---

## SEC Filing Examples

### Extract Key Facts from 8-K

```python
import ollama
import json

def extract_8k_facts(filing_text: str) -> dict:
    """Extract key facts from an 8-K filing."""
    
    prompt = f"""Extract from this SEC 8-K filing. Return JSON only.

{filing_text[:8000]}

Extract:
- event_type: Main event (executive_departure, acquisition, earnings)
- event_date: Date (YYYY-MM-DD)
- entities_mentioned: Company/person names
- dollar_amounts: Dollar amounts mentioned
- key_facts: 3-5 bullet points

Return valid JSON only."""

    response = ollama.chat(
        model='llama3.1:8b',
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.1}  # Low temp for extraction
    )
    
    return json.loads(response['message']['content'])
```

### Classify 8-K Items

```python
def classify_8k_items(filing_text: str) -> list[str]:
    """Classify which 8-K items are present."""
    
    ITEMS = """
    1.01: Material Definitive Agreement
    2.02: Results of Operations (Earnings)
    4.02: Non-Reliance on Prior Financials
    5.02: Executive/Director Changes
    7.01: Regulation FD Disclosure
    """
    
    prompt = f"""Identify which items apply to this 8-K:

{ITEMS}

Filing: {filing_text[:6000]}

Return JSON list: ["5.02", "9.01"]"""

    response = ollama.chat(
        model='llama3.2:3b',  # Fast model for classification
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0}
    )
    
    return json.loads(response['message']['content'])
```

### Extract Risk Factors

```python
def extract_risk_factors(item_1a_text: str) -> list[dict]:
    """Extract risk factors from 10-K Item 1A."""
    
    prompt = f"""Extract each risk factor from this 10-K Item 1A.

{item_1a_text[:10000]}

For each risk, extract:
- title: Short title
- category: cybersecurity/regulatory/financial/operational/market
- severity: high/medium/low
- summary: 1-2 sentences

Return JSON list."""

    response = ollama.chat(
        model='llama3.1:8b',
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.1}
    )
    
    return json.loads(response['message']['content'])
```

---

## FeedSpine Integration

### Provider Pattern

```python
from feedspine.ext.llm import OllamaProvider

# Initialize
llm = OllamaProvider(model="llama3.1:8b")

# Summarize a filing
summary = await llm.summarize(filing_text, max_tokens=500)

# Extract structured data
data = await llm.extract(
    filing_text,
    schema={
        "event_type": "string",
        "event_date": "string",
        "entities": "list[string]"
    }
)

# Generate embeddings for search
embeddings = await llm.embed(filing_text)
```

### Batch Processing

```python
async def process_filings_batch(filings: list[Filing]) -> list[dict]:
    """Process multiple filings with local LLM."""
    
    llm = OllamaProvider(model="llama3.2:3b")  # Fast model
    
    results = []
    for filing in filings:
        result = await llm.extract(
            filing.content,
            schema=EightKSchema
        )
        results.append(result)
    
    return results
```

---

## Model Recommendations

| Use Case | Model | VRAM | Notes |
|----------|-------|------|-------|
| Classification | `llama3.2:3b` | 4GB | Fast, good accuracy |
| Extraction | `llama3.1:8b` | 8GB | Best balance |
| Complex Analysis | `llama3.1:70b` | 48GB | Highest quality |
| Embeddings | `nomic-embed-text` | 2GB | Semantic search |

---

## Performance Tips

1. **Use streaming** for long outputs
2. **Batch similar requests** to keep model hot
3. **Use lower temperatures** (0.0-0.2) for extraction
4. **Chunk large documents** (8K tokens typical limit)
5. **Run multiple Ollama instances** for parallelism
