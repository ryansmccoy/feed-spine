# Trading Desktop Integration

> **Migrating capture-spine UI into MarketSpine Trading Desktop**  
> Unifying data capture, research, and trading in one Bloomberg-style interface

---

## Overview

**Current State:**
- **capture-spine**: React UI with newsfeed, record management, LLM enrichment
- **trading-desktop (MarketSpine)**: Full institutional platform with Trading Center, Research Hub, Portfolio Manager

**Goal:**
Migrate capture-spine's data capture and LLM enrichment capabilities into trading-desktop to create a unified platform.

---

## Architecture Comparison

### capture-spine (Current)

```
┌─────────────────────────────────────────────────────────────┐
│                    capture-spine                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Frontend (React)           Backend (Python/FastAPI)       │
│   ┌─────────────┐           ┌─────────────┐                │
│   │ • Newsfeed  │   ←───→   │ • Record API│                │
│   │ • Record UI │           │ • LLM API   │                │
│   │ • Alerts    │           │ • Alert svc │                │
│   │ • Config    │           │ • Sources   │                │
│   └─────────────┘           └─────────────┘                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### trading-desktop (MarketSpine)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              MarketSpine Trading Desktop                                 │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│   │   Trading    │  │   Research   │  │  Portfolio   │  │  Compliance  │               │
│   │   Center     │  │     Hub      │  │   Manager    │  │   Console    │               │
│   │              │  │              │  │              │  │              │               │
│   │ • Orders     │  │ • Analysis   │  │ • Holdings   │  │ • Rules      │               │
│   │ • Positions  │  │ • Screeners  │  │ • P&L        │  │ • Monitoring │               │
│   │ • Execution  │  │ • News       │  │ • Risk       │  │ • Reports    │               │
│   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                                          │
│   ┌────────────────────────────────────────────────────────────────────────────────┐    │
│   │                           EntitySpine (Knowledge Graph)                         │    │
│   │   Organizations ←→ People ←→ Filings ←→ Holdings ←→ Positions                  │    │
│   └────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Integrated Vision

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    MarketSpine Trading Desktop + capture-spine                           │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│   │   Trading    │  │   Research   │  │  Portfolio   │  │  Compliance  │               │
│   │   Center     │  │     Hub      │  │   Manager    │  │   Console    │               │
│   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                                          │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                                 │
│   │  📡 Data     │  │  🤖 LLM      │  │  🔔 Alert    │   ◄── FROM CAPTURE-SPINE       │
│   │   Capture    │  │   Analysis   │  │   Center     │                                 │
│   │              │  │              │  │              │                                 │
│   │ • Sources    │  │ • Enrichment │  │ • Rules      │                                 │
│   │ • Records    │  │ • Extraction │  │ • Channels   │                                 │
│   │ • Newsfeed   │  │ • Q&A        │  │ • History    │                                 │
│   └──────────────┘  └──────────────┘  └──────────────┘                                 │
│                                                                                          │
│   ┌────────────────────────────────────────────────────────────────────────────────┐    │
│   │                           Unified Data Layer                                    │    │
│   │                                                                                 │    │
│   │   EntitySpine ←→ feedspine ←→ py-sec-edgar ←→ spine-core                       │    │
│   └────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Migration Plan

### Phase 1: API Integration (No UI Changes)

Wire trading-desktop to capture-spine's backend APIs:

```typescript
// trading-desktop/src/api/capture-spine.ts

const CAPTURE_SPINE_BASE = process.env.CAPTURE_SPINE_URL || 'http://localhost:8080';

export const captureSpineApi = {
    // Records
    async getRecords(params: RecordQueryParams): Promise<Record[]> {
        return fetch(`${CAPTURE_SPINE_BASE}/api/records`, {
            method: 'POST',
            body: JSON.stringify(params),
        }).then(r => r.json());
    },
    
    // LLM Enrichment
    async enrichRecord(recordId: string): Promise<EnrichmentResult> {
        return fetch(`${CAPTURE_SPINE_BASE}/api/records/${recordId}/enrich`, {
            method: 'POST',
        }).then(r => r.json());
    },
    
    // Alerts
    async getAlertRules(): Promise<AlertRule[]> {
        return fetch(`${CAPTURE_SPINE_BASE}/api/alerts/rules`).then(r => r.json());
    },
    
    // Sources
    async getSources(): Promise<DataSource[]> {
        return fetch(`${CAPTURE_SPINE_BASE}/api/sources`).then(r => r.json());
    },
};
```

### Phase 2: Embed capture-spine Components

Reuse capture-spine React components via micro-frontend or shared component library:

```typescript
// Option A: Micro-frontend (iframe)
function CaptureSpineEmbed() {
    return (
        <iframe 
            src={`${CAPTURE_SPINE_URL}/embed/newsfeed`}
            className="w-full h-full border-0"
        />
    );
}

// Option B: Shared component library
// capture-spine publishes @marketspine/capture-components

import { Newsfeed, RecordViewer, AlertConfig } from '@marketspine/capture-components';

function ResearchHub() {
    return (
        <div className="flex h-full">
            <div className="w-1/3">
                <Newsfeed 
                    sources={['sec-8k', 'finnhub-news']}
                    onRecordSelect={setSelectedRecord}
                />
            </div>
            <div className="w-2/3">
                <RecordViewer record={selectedRecord} />
            </div>
        </div>
    );
}
```

### Phase 3: Native Integration

Port capture-spine UI components directly into trading-desktop:

```
trading-desktop/
├── src/
│   ├── modules/
│   │   ├── trading/          # Existing
│   │   ├── research/         # Existing
│   │   ├── portfolio/        # Existing
│   │   ├── compliance/       # Existing
│   │   │
│   │   ├── capture/          # NEW - from capture-spine
│   │   │   ├── Newsfeed.tsx
│   │   │   ├── RecordList.tsx
│   │   │   ├── RecordViewer.tsx
│   │   │   ├── SourceConfig.tsx
│   │   │   └── index.ts
│   │   │
│   │   ├── intelligence/     # NEW - LLM features
│   │   │   ├── EnrichmentPanel.tsx
│   │   │   ├── EarningsAnalysis.tsx
│   │   │   ├── DocumentQA.tsx
│   │   │   └── index.ts
│   │   │
│   │   └── alerts/           # NEW - from capture-spine
│   │       ├── AlertCenter.tsx
│   │       ├── RuleBuilder.tsx
│   │       ├── AlertHistory.tsx
│   │       └── index.ts
```

---

## Component Migration Matrix

| capture-spine Component | trading-desktop Location | Migration Effort |
|------------------------|-------------------------|------------------|
| Newsfeed | Research Hub > News | Medium |
| RecordList | Research Hub > Documents | Low |
| RecordViewer | Research Hub > Document Panel | Low |
| SourceConfig | Settings > Data Sources | Low |
| AlertRuleBuilder | Alert Center > Rules | Medium |
| AlertHistory | Alert Center > History | Low |
| LLMEnrichmentPanel | Intelligence > Enrichment | Medium |
| SearchInterface | Global Search | High |

---

## Backend Considerations

### Option A: Keep capture-spine Backend Separate

```
trading-desktop (React)
         │
         ├──────→ capture-spine API (FastAPI)
         │              │
         │              └──→ LLM (local/Bedrock)
         │
         └──────→ MarketSpine API (existing)
```

**Pros:**
- No backend changes
- Independent deployment
- Separation of concerns

**Cons:**
- Two API endpoints to manage
- Potential latency from extra hops

### Option B: Unified Backend

```
trading-desktop (React)
         │
         └──────→ MarketSpine API (unified)
                       │
                       ├──→ Trading services
                       ├──→ Research services
                       └──→ Capture services (migrated)
                              │
                              └──→ LLM (local/Bedrock)
```

**Pros:**
- Single API surface
- Unified auth/session
- Better integration

**Cons:**
- Significant backend work
- Risk of monolith

### Recommendation: Option A (Phase 1-2), Option B (Phase 3+)

---

## Data Integration

### EntitySpine as Unified Identity

Both platforms use EntitySpine. Ensure consistency:

```python
# Shared entity resolution

from entityspine import EntityService

entity_service = EntityService()

# capture-spine: resolve from CIK
entity = entity_service.get_by_cik("0001318605")  # Tesla

# trading-desktop: resolve from ticker
entity = entity_service.get_by_ticker("TSLA")

# Same entity ID flows through both systems
assert entity.id == "ent_abc123"
```

### feedspine as Unified Feed Layer

```python
# Both systems write to/read from feedspine

from feedspine import FeedService

feed_service = FeedService()

# capture-spine: write captured records
await feed_service.create_item(
    feed_id="capture-news",
    entity_id=entity.id,
    content=record_content,
)

# trading-desktop: read for Research Hub
items = await feed_service.get_items(
    entity_id=entity.id,
    feed_types=["capture-news", "sec-8k"],
)
```

---

## UI/UX Considerations

### Bloomberg Terminal Inspiration

trading-desktop already uses Bloomberg-style design. capture-spine components should match:

```typescript
// Shared design tokens
const designTokens = {
    colors: {
        background: '#000000',
        surface: '#1a1a1a',
        primary: '#ff6b00',  // Bloomberg orange
        success: '#00ff00',
        danger: '#ff0000',
        text: '#ffffff',
        textMuted: '#888888',
    },
    fonts: {
        mono: 'Bloomberg Terminal, Consolas, monospace',
    },
};

// capture-spine components must use these tokens
<Newsfeed 
    theme={designTokens}
    className="font-mono text-sm"
/>
```

### Keyboard Navigation

Bloomberg is keyboard-first. capture-spine components need:

```typescript
// Keyboard shortcuts for capture components
const captureShortcuts = {
    'Alt+N': 'Open newsfeed',
    'Alt+R': 'Refresh records',
    'Alt+E': 'Enrich selected',
    'Alt+A': 'Open alert config',
    '/': 'Focus search',
    'j/k': 'Navigate records',
    'Enter': 'Open record',
    'Escape': 'Close panel',
};
```

---

## Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1: API Integration | 2 weeks | API client, basic data flow |
| Phase 2: Embed Components | 3 weeks | Micro-frontend, shared components |
| Phase 3: Native Integration | 6 weeks | Full component migration |
| Phase 4: Backend Unification | 8 weeks | Unified API (optional) |

---

## Related Docs

- [ECOSYSTEM.md](../../../../ECOSYSTEM.md) - Project integration overview
- [modern-earnings-intelligence](../modern-earnings-intelligence/) - LLM earnings feature
- [8k-release-capture](../8k-release-capture/) - 8-K capture pipeline
- [capture-spine VISION](../../../spine-core/trading-desktop-temp/docs/CAPTURE_SPINE_VISION.md) - Original capture-spine vision
- [MarketSpine OVERVIEW](../../../spine-core/trading-desktop-temp/docs/MARKETSPINE_OVERVIEW.md) - Trading desktop overview
