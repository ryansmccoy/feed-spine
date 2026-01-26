# FeedSpine

**Storage-agnostic, executor-agnostic feed capture framework.**

FeedSpine provides a flexible, protocol-based architecture for capturing data from
feeds and processing it through a medallion (Bronze → Silver → Gold) pipeline.

## Features

- 🔌 **Protocol-Based Design**: Swap storage, cache, queue, and executor backends
- 🥉🥈🥇 **Medallion Architecture**: Bronze (raw) → Silver (clean) → Gold (enriched)
- ⚡ **Async-First**: Built for high-throughput concurrent processing
- 🔍 **Deduplication**: Natural key-based sighting tracking
- 📦 **Minimal Core**: Only install what you need

## Quick Start

```bash
pip install feedspine
```

```python
import asyncio
from feedspine.storage.memory import MemoryStorage
from feedspine.models.record import Record, RecordCandidate
from feedspine.models.base import Layer, Metadata
from datetime import datetime, timezone

async def main():
    # Initialize storage
    storage = MemoryStorage()
    await storage.initialize()
    
    # Create a record candidate from feed data
    candidate = RecordCandidate(
        natural_key="SEC-AAPL-10K-2024",
        published_at=datetime.now(timezone.utc),
        content={"form_type": "10-K", "company": "Apple Inc."},
        metadata=Metadata(source="sec-edgar"),
    )
    
    # Promote to Bronze record
    record = Record.from_candidate(candidate, record_id="rec-001")
    
    # Store it
    await storage.store(record)
    
    # Later, promote to Silver with enrichments
    silver = record.promote(Layer.SILVER, enrichments={"verified": True})
    await storage.store(silver)
    
    print(f"Stored record at layer: {silver.layer}")
    
    await storage.close()

asyncio.run(main())
```

## Documentation

- **[Getting Started](getting-started/installation.md)**: Installation and quick start
- **[Tutorials](tutorials/first-feed.md)**: Step-by-step guides
- **[How-To Guides](how-to/custom-storage.md)**: Solve specific problems
- **[Concepts](concepts/architecture.md)**: Understand the design
- **[API Reference](reference/)**: Complete API documentation

## Installation Options

```bash
# Core only
pip install feedspine

# With PostgreSQL storage
pip install feedspine[postgres]

# With Redis cache
pip install feedspine[redis]

# With all storage backends
pip install feedspine[storage-all]

# Everything
pip install feedspine[all]
```

## License

MIT License - see [LICENSE](https://github.com/ryansmccoy/feedspine/blob/main/LICENSE)
