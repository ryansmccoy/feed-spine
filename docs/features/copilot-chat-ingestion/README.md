# VS Code Copilot Chat Ingestion

> **Parse and ingest VS Code Copilot chat sessions as a feedspine feed**  
> Track conversations, replay history, enrich with LLM analysis

---

## Original User Request (Jan 29, 2026)

> "I want to ingest the chat sessions from my VS Code workspace into groups by like project then sessions then chat messages so I can easily replay my chat or display it in the order it happened or in reverse order... we probably need to add like this as a model in entityspine so we can manage it but feedspine will need to be able to do the same type of logic it does RSS feeds or filings, deduplicate the blob of JSON it'll probably get and show only the new 'messages' kind of how it does it with filings."
>
> "I want the chats in capture spine to be basically like a real time feed I can follow that has my chat history but is enriched by LLMs and keep track of and features kept tracked of automatically, so like a todo management system."

### Key Requirements

1. **Hierarchy**: Project → Sessions → Messages
2. **Deduplication**: Like feedspine does with RSS/filings - only show new messages
3. **Display Options**: Chronological, reverse chronological, by project
4. **LLM Enrichment**: Auto-extract TODOs, track decisions
5. **Real-time Feed**: Follow chat history as it happens
6. **entityspine Model**: Add ChatSession/ChatMessage to domain

---

## Overview

VS Code stores Copilot chat sessions in JSON files under:
```
%APPDATA%\Code\User\workspaceStorage\<workspace-hash>\chatSessions\<session-id>.json
```

Each workspace has a unique hash. Sessions contain:
- **Session metadata**: ID, creation date, last message date, user/model info
- **Requests**: Array of user messages + AI responses with timestamps

### Goal

Ingest these sessions into feedspine/capture-spine to:
1. **Track conversation history** across workspaces and sessions
2. **Deduplicate** messages (feedspine's core capability)
3. **Enrich with LLM** - extract TODOs, decisions, code patterns
4. **Display in newsfeed** - real-time feed of your AI pair programming
5. **Replay conversations** - understand what you built and when

---

## VS Code Chat Session Structure

### File Location

```
C:\Users\<user>\AppData\Roaming\Code\User\workspaceStorage\
└── <workspace-hash>/
    ├── workspace.json          # Maps hash → folder path
    ├── chatSessions/
    │   ├── <session-id>.json   # Full conversation
    │   └── ...
    └── chatEditingSessions/    # Agent mode edit sessions
        └── <session-id>/
            ├── state.json
            └── contents/       # File snapshots
```

### Session JSON Schema

```json
{
  "sessionId": "uuid",
  "creationDate": 1753564508125,       // Unix timestamp ms
  "lastMessageDate": 1753565465326,
  "requesterUsername": "ryansmccoy",   // Your GitHub user
  "responderUsername": "GitHub Copilot",
  "requesterAvatarIconUri": "...",
  "responderAvatarIconUri": "...",
  "version": 1,
  "isImported": false,
  "initialLocation": "...",
  "requests": [
    {
      "requestId": "uuid",
      "timestamp": 1753564649970,
      "modelId": "github.copilot-chat/claude-sonnet-4",
      "message": {
        "text": "User's prompt text",
        "parts": [...]
      },
      "response": {
        "kind": "...",
        "isComplete": true,
        "resultDetails": {...}
      },
      "contentReferences": [...],      // Files referenced
      "codeCitations": [...],          // Code snippets
      "followups": [...],
      "agent": "...",                  // @workspace, etc.
      "variableData": {...}
    }
  ]
}
```

### Key Fields for Ingestion

| Field | Purpose |
|-------|---------|
| `sessionId` | Unique ID, use as feed item external_id |
| `creationDate` | Session start time |
| `lastMessageDate` | Latest activity |
| `requests[].timestamp` | Individual message time |
| `requests[].message.text` | User's prompt |
| `requests[].modelId` | Which AI model |
| `requests[].contentReferences` | Files mentioned |
| `requests[].agent` | @workspace, @terminal, etc. |

---

## Data Model

### entityspine: ChatSession and ChatMessage

```python
# entityspine/domain/chat.py

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass
class ChatSession:
    """Represents a VS Code Copilot chat session."""
    
    session_id: UUID
    workspace_id: str              # Hash from workspaceStorage
    workspace_path: str            # Decoded folder path
    project_name: str              # Extracted from path (e.g., "py-sec-edgar")
    
    created_at: datetime
    last_message_at: datetime
    
    user_name: str
    model_name: str                # e.g., "GitHub Copilot"
    
    message_count: int
    
    # Optional metadata
    initial_location: str | None = None
    is_imported: bool = False

@dataclass
class ChatMessage:
    """A single request/response pair in a chat session."""
    
    message_id: UUID               # request_id from JSON
    session_id: UUID               # Parent session
    
    timestamp: datetime
    model_id: str                  # e.g., "github.copilot-chat/claude-sonnet-4"
    
    user_text: str                 # The prompt
    response_kind: str             # Tool call, text, etc.
    response_complete: bool
    
    # References
    files_referenced: list[str]    # From contentReferences
    code_citations: list[dict]     # Code snippets
    agent: str | None              # @workspace, @terminal, etc.
    
    # Extracted by LLM (optional)
    extracted_todos: list[str] | None = None
    extracted_decisions: list[str] | None = None
    extracted_code_patterns: list[str] | None = None
```

### feedspine: Chat Feed Provider

```python
# feedspine/src/feedspine/providers/copilot_chat.py

from feedspine.core import Feed, FeedItem, FeedProvider

class CopilotChatProvider(FeedProvider):
    """Feed provider for VS Code Copilot chat sessions."""
    
    feed_id = "vscode-copilot-chat"
    feed_name = "VS Code Copilot Chat"
    
    def __init__(self, workspace_storage_path: str = None):
        self.storage_path = workspace_storage_path or self._default_storage_path()
    
    def _default_storage_path(self) -> str:
        import os
        return os.path.join(
            os.environ.get('APPDATA', ''),
            'Code', 'User', 'workspaceStorage'
        )
    
    async def sync(self, since: datetime = None) -> list[FeedItem]:
        """Scan for new/updated chat sessions."""
        items = []
        
        for workspace_dir in self._get_workspace_dirs():
            workspace_info = self._read_workspace_json(workspace_dir)
            sessions_dir = workspace_dir / 'chatSessions'
            
            if not sessions_dir.exists():
                continue
            
            for session_file in sessions_dir.glob('*.json'):
                session = self._parse_session(session_file)
                
                if since and session.last_message_at < since:
                    continue
                
                items.append(FeedItem(
                    feed_id=self.feed_id,
                    external_id=str(session.session_id),
                    timestamp=session.last_message_at,
                    title=f"Chat: {session.project_name} - {session.message_count} messages",
                    content=self._serialize_session(session),
                    metadata={
                        'workspace_path': session.workspace_path,
                        'project_name': session.project_name,
                        'message_count': session.message_count,
                        'model': session.model_name,
                    }
                ))
        
        return items
    
    def get_messages(self, session_id: UUID) -> list[ChatMessage]:
        """Get individual messages for a session."""
        # ...
```

---

## capture-spine Integration

### Record Type: `copilot_chat`

```python
# New record type for capture-spine

COPILOT_CHAT_RECORD_TYPE = "copilot_chat"

# Records created:
# - One record per session (high-level)
# - Or one record per message (granular)

record = RecordCreate(
    region="local",
    record_type="copilot_chat",
    unique_id=f"copilot-chat:{session_id}",
    entity_id=project_name,      # Link to project entity
    entity_type="project",
    title=f"Chat Session - {project_name}",
    url=None,                    # Local file, no URL
    event_time=session.last_message_at,
    metadata={
        "session_id": str(session_id),
        "workspace_path": workspace_path,
        "message_count": message_count,
        "models_used": ["claude-sonnet-4", "gpt-4o"],
        "files_discussed": [...],
    }
)
```

### Newsfeed Display

In capture-spine's React newsfeed:

```typescript
// frontend/src/components/CopilotChatCard.tsx

interface CopilotChatRecord {
    record_type: 'copilot_chat';
    title: string;
    metadata: {
        session_id: string;
        project_name: string;
        message_count: number;
        models_used: string[];
    };
}

function CopilotChatCard({ record }: { record: CopilotChatRecord }) {
    return (
        <div className="chat-card">
            <div className="chat-header">
                <span className="icon">💬</span>
                <span className="project">{record.metadata.project_name}</span>
                <span className="count">{record.metadata.message_count} messages</span>
            </div>
            <div className="chat-models">
                {record.metadata.models_used.map(m => (
                    <span key={m} className="model-tag">{m}</span>
                ))}
            </div>
            <button onClick={() => openSessionReplay(record.metadata.session_id)}>
                Replay Session
            </button>
        </div>
    );
}
```

---

## Python Parser Script

```python
#!/usr/bin/env python3
"""Parse VS Code Copilot chat sessions.

Usage:
    python parse_copilot_chats.py --workspace b:/github/py-sec-edgar --output chats.json
    python parse_copilot_chats.py --all --output all_chats.json
"""

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote

@dataclass
class ChatSession:
    session_id: str
    workspace_path: str
    project_name: str
    created_at: datetime
    last_message_at: datetime
    user_name: str
    model_name: str
    message_count: int
    messages: list[dict]

def get_workspace_storage_path() -> Path:
    """Get VS Code workspace storage path."""
    appdata = os.environ.get('APPDATA', '')
    return Path(appdata) / 'Code' / 'User' / 'workspaceStorage'

def parse_workspace_json(workspace_dir: Path) -> dict | None:
    """Parse workspace.json to get folder path."""
    ws_file = workspace_dir / 'workspace.json'
    if not ws_file.exists():
        return None
    
    with open(ws_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    folder = data.get('folder', '')
    if folder.startswith('file:///'):
        # Decode URI: file:///b%3A/github/py-sec-edgar -> b:/github/py-sec-edgar
        folder = unquote(folder[8:])
    
    return {
        'hash': workspace_dir.name,
        'folder': folder,
        'project_name': Path(folder).name if folder else 'unknown'
    }

def parse_session_file(session_file: Path, workspace_info: dict) -> ChatSession | None:
    """Parse a chat session JSON file."""
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    
    requests = data.get('requests', [])
    
    messages = []
    for req in requests:
        msg_text = ''
        if isinstance(req.get('message'), dict):
            msg_text = req['message'].get('text', '')
        elif isinstance(req.get('message'), str):
            msg_text = req['message']
        
        messages.append({
            'request_id': req.get('requestId'),
            'timestamp': req.get('timestamp'),
            'model_id': req.get('modelId'),
            'user_text': msg_text,
            'agent': req.get('agent'),
            'files_referenced': [
                ref.get('uri', '') for ref in req.get('contentReferences', [])
                if isinstance(ref, dict)
            ],
        })
    
    return ChatSession(
        session_id=data.get('sessionId', session_file.stem),
        workspace_path=workspace_info['folder'],
        project_name=workspace_info['project_name'],
        created_at=datetime.fromtimestamp(data.get('creationDate', 0) / 1000),
        last_message_at=datetime.fromtimestamp(data.get('lastMessageDate', 0) / 1000),
        user_name=data.get('requesterUsername', 'unknown'),
        model_name=data.get('responderUsername', 'GitHub Copilot'),
        message_count=len(requests),
        messages=messages,
    )

def find_sessions(
    workspace_filter: str = None,
    storage_path: Path = None,
) -> Iterator[ChatSession]:
    """Find all chat sessions, optionally filtered by workspace."""
    storage = storage_path or get_workspace_storage_path()
    
    for workspace_dir in storage.iterdir():
        if not workspace_dir.is_dir():
            continue
        
        workspace_info = parse_workspace_json(workspace_dir)
        if not workspace_info:
            continue
        
        # Filter by workspace path if specified
        if workspace_filter:
            if workspace_filter.lower() not in workspace_info['folder'].lower():
                continue
        
        sessions_dir = workspace_dir / 'chatSessions'
        if not sessions_dir.exists():
            continue
        
        for session_file in sessions_dir.glob('*.json'):
            session = parse_session_file(session_file, workspace_info)
            if session:
                yield session

def main():
    parser = argparse.ArgumentParser(description='Parse VS Code Copilot chat sessions')
    parser.add_argument('--workspace', '-w', help='Filter by workspace path')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--all', action='store_true', help='Include all workspaces')
    parser.add_argument('--since', help='Only sessions since date (YYYY-MM-DD)')
    args = parser.parse_args()
    
    since = None
    if args.since:
        since = datetime.fromisoformat(args.since)
    
    sessions = []
    for session in find_sessions(workspace_filter=args.workspace):
        if since and session.last_message_at < since:
            continue
        sessions.append(asdict(session))
    
    # Sort by last message date
    sessions.sort(key=lambda s: s['last_message_at'], reverse=True)
    
    output = {
        'extracted_at': datetime.now().isoformat(),
        'session_count': len(sessions),
        'sessions': sessions,
    }
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, default=str)
        print(f"Wrote {len(sessions)} sessions to {args.output}")
    else:
        print(json.dumps(output, indent=2, default=str))

if __name__ == '__main__':
    main()
```

---

## Implementation Plan

### Phase 1: Parser Script
| Task | Status |
|------|--------|
| Python script to parse chat sessions | ⏳ |
| Filter by workspace | ⏳ |
| Output as JSON | ⏳ |
| CLI tool | ⏳ |

### Phase 2: entityspine Models
| Task | Status |
|------|--------|
| ChatSession model | ⏳ |
| ChatMessage model | ⏳ |
| Storage adapter | ⏳ |

### Phase 3: feedspine Provider
| Task | Status |
|------|--------|
| CopilotChatProvider | ⏳ |
| Deduplication logic | ⏳ |
| Incremental sync | ⏳ |

### Phase 4: capture-spine Integration
| Task | Status |
|------|--------|
| Record type: copilot_chat | ⏳ |
| Newsfeed card component | ⏳ |
| Session replay viewer | ⏳ |
| LLM enrichment (TODOs, decisions) | ⏳ |

---

## Related Features

### feedspine Features
- [ECOSYSTEM.md](../../../../ECOSYSTEM.md) - Project integration overview

### capture-spine Productivity Suite
The other LLM is working on these complementary features:
- [VS Code Chat Ingestion](../../../../capture-spine/docs/features/productivity/vscode-chat-ingestion.md) - capture-spine side parser
- [File Upload Enhancement](../../../../capture-spine/docs/features/productivity/file-upload-enhancement.md) - Drag-drop upload
- [Todo Management](../../../../capture-spine/docs/features/productivity/todo-management.md) - Task tracking
- [Content Ingestion API](../../../../capture-spine/docs/features/productivity/content-ingestion-api.md) - Unified ingestion API
