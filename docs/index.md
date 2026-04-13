---
title: "Index"
type: reference
status: active
tags: [feed-spine, pipeline, search]
created: 2026-02-22
updated: 2026-04-12
---
# FeedSpine

**Storage-agnostic feed capture framework with automatic deduplication and medallion architecture.**

## Features

- **Protocol-Based Design**: Swap storage, search, and cache backends without code changes
- **Medallion Architecture**: Bronze (raw) → Silver (clean) → Gold (enriched)
- **Async-First**: Built for high-throughput concurrent processing
- **Natural Key Deduplication**: Content hash update detection + sighting history
- **Minimal Core**: Only install what you need

## Quick Start

```bash
uv add feedspine
```

```python
import asyncio
from feedspine import create_feed_spine, MemoryStorage, RSSFeedAdapter

async def main():
    storage = MemoryStorage()
    app = create_feed_spine(storage)

    app.register_feed(RSSFeedAdapter(
        name="hacker-news",
        url="https://news.ycombinator.com/rss",
    ))

    result = await app.collect()
    print(f"New: {result.total_new}, Duplicates: {result.total_duplicates}")

asyncio.run(main())
```

## Documentation

- **[Getting Started](getting-started/installation.md)**: Installation and quick start
- **[Tutorials](tutorials/first-feed.md)**: Step-by-step guides
- **[How-To Guides](how-to/custom-storage.md)**: Solve specific problems
- **[Concepts](concepts/feeds-and-sources.md)**: Understand the design
- **[Architecture](architecture/ARCHITECTURE.md)**: Layered architecture and data flow

## Installation Options

```bash
# Core only
uv add feedspine

# With PostgreSQL storage
uv add "feedspine[postgres]"

# With entity resolution
uv add "feedspine[entity]"

# With Elasticsearch search
uv add "feedspine[elasticsearch]"

# All storage backends
uv add "feedspine[storage-all]"

# Everything
uv add "feedspine[all]"
```

## License

MIT License - see [LICENSE](https://github.com/ryansmccoy/feed-spine/blob/main/LICENSE)
