# Guardrails MVP - Frontend

Beautiful and functional UI for the Guardrails MVP system.

## Features

✅ **Chat Interface**
- Clean chat UI with markdown support
- Message status indicators (ok/refused/blocked/regenerated)
- Real-time typing indicator
- Request cancellation

✅ **Session Management**
- Multiple chat sessions
- Auto-save to localStorage
- Session rename/delete
- Message history persistence

✅ **Guardrails Control Panel**
- Master ON/OFF toggle
- Monitor-only mode
- Individual rail toggles (13 rails across 4 categories)
- Settings persistence
- Tooltips for each rail

✅ **Inspector Panel**
- **Actions Tab**: Tool calls with TOOL_CALL_ID, args, results
- **Guardrails Tab**: Active/inactive rails status
- **Blocks Tab**: Rail events (info/warn/block) with before/after diffs
- **Generated Tab**: Dynamically generated rails config

## Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- Mantine UI (v7)
- Zustand (state management)
- React Markdown (message rendering)

## Getting Started

### Install Dependencies

```bash
npm install
```

### Development Server

```bash
npm run dev
```

Frontend will start on `http://localhost:3000` with API proxy to `http://localhost:8000`

### Build for Production

```bash
npm run build
npm run preview
```

## Project Structure

```
src/
├── components/
│   ├── chat/              # Chat components
│   │   ├── ChatView.tsx
│   │   ├── MessageList.tsx
│   │   ├── MessageBubble.tsx
│   │   └── Composer.tsx
│   ├── sessions/          # Session management
│   │   └── SessionsList.tsx
│   ├── guardrails/        # Guardrails controls
│   │   ├── GuardrailsToggleAll.tsx
│   │   └── GuardrailsTogglesList.tsx
│   ├── inspector/         # Inspector tabs
│   │   ├── InspectorTabs.tsx
│   │   ├── ActionsTab.tsx
│   │   ├── GuardrailsTab.tsx
│   │   ├── BlocksEditsTab.tsx
│   │   └── GeneratedRailsTab.tsx
│   └── layout/            # Layout components
│       ├── AppShellLayout.tsx
│       ├── LeftPanel.tsx
│       └── RightPanel.tsx
├── store/                 # Zustand stores
│   ├── sessionsStore.ts
│   ├── guardrailsStore.ts
│   └── inspectorStore.ts
├── api/                   # API client
│   └── client.ts
├── types/                 # TypeScript types
│   └── index.ts
├── utils/                 # Utilities
│   └── storage.ts
├── App.tsx
└── main.tsx
```

## API Integration

Frontend expects the following backend endpoints:

### POST /api/chat

Request:
```json
{
  "session_id": "string",
  "user_message": "string",
  "agent_profile": "default",
  "guardrails": {
    "enabled": true,
    "monitor_only": false,
    "toggles": {
      "input.pii": true,
      ...
    }
  }
}
```

Response:
```json
{
  "session_id": "string",
  "message_id": "string",
  "assistant_message": "string",
  "status": "ok" | "refused" | "escalated",
  "trace_id": "string",
  "tool_calls": [...],
  "rail_events": [...],
  "generated_rails": {...}
}
```

### GET /api/health

Health check endpoint.

## Storage

- **Sessions**: localStorage (`guardrails_sessions`)
- **Messages**: localStorage (`guardrails_messages_{sessionId}`)
- **Guardrails Config**: localStorage (`guardrails_config`)

All data persists across page refreshes.

## Configuration

### Vite Proxy

API requests to `/api/*` are proxied to `http://localhost:8000` (configured in `vite.config.ts`).

Change backend URL:
```ts
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://your-backend:port',
      ...
    }
  }
}
```

## Development Notes

### Guardrails Toggles

13 guardrails across 4 categories:

1. **Input Rails** (4)
   - PII Detection
   - Injection Protection
   - Policy Check
   - Length Validation

2. **Execution Rails** (4)
   - Tool Allowlist
   - Argument Validation
   - Rate Limiting
   - Loop Detection

3. **Output Rails** (4)
   - Format Validation
   - PII Leakage
   - Tool Truthfulness
   - Safety Check

4. **Advanced** (1)
   - Hallucination Judge

### Inspector Context

Inspector shows data for the **selected message** (click message to select).

### Message Status

- `sending` - Request in progress
- `ok` - Success
- `refused` - Blocked by guardrails
- `blocked` - Modified by rails
- `regenerated` - Required regeneration
- `error` - Request failed
- `cancelled` - User cancelled

## License

MIT
