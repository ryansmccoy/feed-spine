# FeedSpine Improvement Proposals

> Design documents for enhancing FeedSpine's core capabilities.

## Overview

These documents outline improvements and refactoring proposals specifically for FeedSpine - the domain-agnostic feed collection and deduplication library.

## Documents

| Document | Description | Priority |
|----------|-------------|----------|
| [Core Improvements](CORE_IMPROVEMENTS.md) | Progress reporting, retry logic, metrics | High |
| [Plugin Architecture](PLUGIN_ARCHITECTURE.md) | Adapter registry and entry points | High |
| [Streaming Pipeline](STREAMING_PIPELINE.md) | Memory-efficient streaming with backpressure | Medium |
| [Event System](EVENT_SYSTEM.md) | Event bus and reactive patterns | Medium |

## Relationship to py-sec-edgar

FeedSpine is designed to be **domain-agnostic**. These improvements benefit all FeedSpine consumers, not just py-sec-edgar.

```
┌─────────────────────────────────────────────────────────────┐
│                     py-sec-edgar v4                         │
│  (SEC-specific: SmartSyncStrategy, Filing model, etc.)     │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ uses
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       FeedSpine                             │
│  (Generic: Deduplication, Storage, Adapters, Events)       │
│                                                             │
│  Improvements documented here benefit ALL consumers         │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

When implementing these improvements, keep in mind:

1. **No domain knowledge** - FeedSpine should never import or reference SEC, filing, CIK, etc.
2. **Protocol-based** - Use Python Protocols for extension points
3. **Optional dependencies** - Rich, Prometheus, etc. should be optional
4. **Backward compatible** - New features shouldn't break existing code

---

*See also: [py-sec-edgar improvements](../../../../py_sec_edgar/docs/architecture/improvements/README.md)*
