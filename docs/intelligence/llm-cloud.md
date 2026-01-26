# Cloud LLM Integration

**Production-ready, highest quality, scalable inference**

---

## Why Cloud LLMs?

| Benefit | Description |
|---------|-------------|
| **Quality** | Best-in-class models (GPT-4, Claude 3.5) |
| **Scale** | Handle thousands of filings without hardware |
| **Features** | Function calling, vision, long context |
| **Reliability** | 99.9%+ uptime SLAs |
| **No Setup** | No GPU, no model management |

---

## Quick Setup

```bash
pip install openai anthropic boto3
```

```bash
# Set API keys
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
```

---

## OpenAI Examples

### Function Calling for Structured Extraction

```python
from openai import OpenAI
import json

client = OpenAI()

def extract_8k_structured(filing_text: str) -> dict:
    """Extract structured data using function calling."""
    
    tools = [{
        "type": "function",
        "function": {
            "name": "record_8k_event",
            "description": "Record extracted 8-K information",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": ["executive_change", "acquisition", 
                                 "earnings", "agreement", "other"]
                    },
                    "event_date": {"type": "string"},
                    "items_covered": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "companies_involved": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string"}
                            }
                        }
                    },
                    "summary": {"type": "string"}
                },
                "required": ["event_type", "items_covered", "summary"]
            }
        }
    }]
    
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "Extract information from SEC filings."},
            {"role": "user", "content": f"Extract from this 8-K:\n\n{filing_text[:12000]}"}
        ],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "record_8k_event"}}
    )
    
    tool_call = response.choices[0].message.tool_calls[0]
    return json.loads(tool_call.function.arguments)
```

---

## Anthropic Claude Examples

### Long Context Analysis

```python
import anthropic

client = anthropic.Anthropic()

def analyze_10k_full(filing_text: str) -> dict:
    """Analyze entire 10-K (Claude supports 200K tokens)."""
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"""Analyze this complete 10-K filing:

{filing_text}

Provide:
1. Business summary (2 paragraphs)
2. Key risks (top 5)
3. Financial highlights
4. Management changes
5. Competitive position

Format as JSON."""
        }]
    )
    
    import json
    return json.loads(response.content[0].text)
```

### Structured Output with Instructor

```python
import anthropic
import instructor
from pydantic import BaseModel

client = instructor.from_anthropic(anthropic.Anthropic())

class RiskFactor(BaseModel):
    title: str
    category: str
    severity: str
    summary: str

class RiskAnalysis(BaseModel):
    company_name: str
    risks: list[RiskFactor]

def extract_risks_structured(item_1a: str) -> RiskAnalysis:
    """Extract risks with validated structure."""
    
    return client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"Extract risk factors from:\n\n{item_1a}"
        }],
        response_model=RiskAnalysis
    )
```

---

## AWS Bedrock Examples

```python
import boto3
import json

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def extract_with_bedrock(filing_text: str) -> dict:
    """Use Claude via AWS Bedrock."""
    
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{
            "role": "user",
            "content": f"Extract key information:\n\n{filing_text[:10000]}"
        }]
    })
    
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=body
    )
    
    result = json.loads(response['body'].read())
    return json.loads(result['content'][0]['text'])
```

---

## FeedSpine Integration

### Provider Pattern

```python
from feedspine.ext.llm import OpenAIProvider, AnthropicProvider

# OpenAI
openai = OpenAIProvider(model="gpt-4o")
summary = await openai.summarize(filing_text)

# Anthropic  
claude = AnthropicProvider(model="claude-3-5-sonnet")
analysis = await claude.analyze(filing_text)

# With structured output
entities = await claude.extract(
    filing_text,
    response_model=list[Entity],
)
```

### Batch Processing with Rate Limits

```python
from feedspine.ext.llm import CloudProvider
import asyncio

async def process_filings_batch(filings: list[Filing]) -> list[dict]:
    """Process filings with rate limiting."""
    
    provider = OpenAIProvider(
        model="gpt-4o",
        rate_limit=100,  # requests per minute
        retry_on_rate_limit=True
    )
    
    tasks = [
        provider.extract(f.content, schema=EightKSchema)
        for f in filings
    ]
    
    return await asyncio.gather(*tasks)
```

---

## Cost Comparison

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Context |
|-------|---------------------|----------------------|---------|
| GPT-4o | $5 | $15 | 128K |
| GPT-4-turbo | $10 | $30 | 128K |
| Claude 3.5 Sonnet | $3 | $15 | 200K |
| Claude 3 Opus | $15 | $75 | 200K |

---

## Best Practices

1. **Use function calling** for structured extraction (OpenAI)
2. **Use Instructor** for validated Pydantic output
3. **Implement retry logic** for rate limits
4. **Cache results** to avoid reprocessing
5. **Use Claude** for long documents (200K context)
6. **Batch requests** to minimize API calls
