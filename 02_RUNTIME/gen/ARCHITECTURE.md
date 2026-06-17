# Gen Architecture

## Overview

Gen is a decision middleware layer that intercepts Claude's tool use via HTTP hooks, logs all decisions to SQLite, and enables remote coordination across machines.

## System Architecture

```
┌─────────────────┐
│  Claude Code    │
│  (any machine)  │
└────────┬────────┘
         │
         │ PreToolUse hook
         │ (HTTP POST)
         │
         ▼
┌─────────────────────────┐
│   Gen Orchestrator   │
│   (Fly.io remote)       │
├─────────────────────────┤
│ • decidePretool logic   │
│ • SQLite event log      │
│ • Routing rules         │
│ • Task queue            │
│ • Learning patterns     │
└────────────┬────────────┘
             │
             ▼
         SQLite DB
         (persistent)
```

## Request Flow

### Tool Use Hook Flow

1. Claude attempts to use a tool (e.g., `Bash`, `Write`, `Edit`)
2. Claude Code calls PreToolUse hook (HTTP POST)
3. Gen receives request:
   - Extracts `tool_name`, `tool_input`, `session_id`, `machine_id`
   - Passes to `decidePretool()` logic
   - Logs event to `pretool_events` table
4. Gen returns JSON response:
   - `continue` (boolean) — whether Claude should proceed
   - `permissionDecision` ("allow" or "deny")
   - `stopReason` (optional error message)
5. Claude honors the decision or shows error

**Current code (this repo):** See [`docs/INTENT-LLM-ROUTING.md`](docs/INTENT-LLM-ROUTING.md) for intent → provider routing, and [`../docs/agent-observability/GEN-OTEL.md`](../docs/agent-observability/GEN-OTEL.md) for span attributes (`gen.suggested_llm`, `gen.pretool_routing_source`, correlation IDs).

### Fail-Open Design

If Gen is unavailable or crashes:
- The orchestrator returns HTTP 500 with `continue: true`
- Claude proceeds unblocked (safety feature)
- No tool use is permanently blocked by infrastructure failure

## Database Schema

### pretool_events
Logs every tool use decision.

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER | Primary key |
| ts | TEXT | Timestamp (ISO 8601) |
| session_id | TEXT | Claude session ID |
| machine_id | TEXT | Machine identifier |
| tool_name | TEXT | Tool being used (Bash, Write, etc.) |
| tool_input | TEXT | Tool parameters (JSON) |
| decision | TEXT | Decision output (JSON) |
| blocked_reason | TEXT | Why it was blocked (if blocked) |
| created_at | TEXT | Record creation time |

### routing_rules
Centralized policy for routing decisions.

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER | Primary key |
| name | TEXT | Rule name (unique) |
| tool | TEXT | Tool this rule applies to |
| condition_json | TEXT | Condition to match (JSON) |
| action | TEXT | Action to take (allow/deny/route) |
| target_agent | TEXT | Where to route (if action=route) |
| priority | INTEGER | Rule precedence (lower = higher priority) |
| enabled | INTEGER | 1 if active, 0 if disabled |

### tasks
Remote task management and coordination.

| Column | Type | Purpose |
|--------|------|---------|
| id | TEXT | UUID primary key |
| user_id | TEXT | User creating task |
| title | TEXT | Task title |
| status | TEXT | pending/running/done/failed |
| created_at | TEXT | Creation timestamp |
| started_at | TEXT | When execution started |
| completed_at | TEXT | When execution finished |
| scheduled_for | TEXT | Optional scheduled start time |
| result_json | TEXT | Task output (JSON) |
| agent_type | TEXT | Type of agent to run |

### sessions
Track active Claude instances.

| Column | Type | Purpose |
|--------|------|---------|
| id | TEXT | Session UUID |
| machine_id | TEXT | Machine identifier |
| user_id | TEXT | User running Claude |
| user_agent | TEXT | HTTP user agent |
| last_activity_ts | TEXT | Last activity timestamp |
| created_at | TEXT | Session start time |
| closed_at | TEXT | Session end time (if closed) |

### webhook_events
External event ingestion (GitHub, CI, etc.).

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER | Primary key |
| source | TEXT | Event source (github, ci, etc.) |
| event_type | TEXT | Type of event (push, pr, build_pass, etc.) |
| payload | TEXT | Full event payload (JSON) |
| action | TEXT | Action taken (create_task, notify, etc.) |
| created_at | TEXT | Event timestamp |

### agent_configs
Agent settings and capabilities.

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER | Primary key |
| name | TEXT | Agent name (unique) |
| agent_type | TEXT | Type (yolo, codex-team, spawn_agent, etc.) |
| intent | TEXT | Primary intent this agent serves |
| scope | TEXT | Scope of work (files, modules, etc.) |
| enabled | INTEGER | 1 if active, 0 if disabled |
| config_json | TEXT | Agent-specific config (JSON) |

### learning_patterns
Adaptive routing foundation.

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER | Primary key |
| intent | TEXT | Intent classification |
| scope | TEXT | Work scope (files, modules, etc.) |
| routing_target | TEXT | Agent this intent was routed to |
| success_count | INTEGER | Number of successful executions |
| failure_count | INTEGER | Number of failures |
| avg_duration_ms | INTEGER | Average execution time |
| last_updated | TEXT | Last pattern update |

## Middleware Stack

```
Express App
├─ JSON Parser
├─ Logging Middleware
│  └─ Logs all requests to console
├─ Health Endpoint (no auth required)
│  └─ GET /health
├─ Auth Middleware
│  └─ Verifies Bearer token
├─ Hooks Router
│  └─ POST /hooks/pretool
├─ Stats Router (Wave 2)
│  ├─ GET /events/recent
│  └─ GET /stats
├─ Tasks Router (Wave 2)
│  ├─ POST /tasks
│  ├─ GET /tasks/{id}
│  └─ PATCH /tasks/{id}
├─ Config Router (Wave 2)
│  ├─ GET /config/rules
│  └─ POST /config/rules
├─ Webhooks Router (Wave 3)
│  ├─ POST /webhooks/github
│  └─ POST /webhooks/ci
├─ Channels Router (Wave 4)
│  └─ POST /channels/event
└─ Error Handler
   └─ Catches unhandled errors
```

## Decision Logic

### decidePretool(input)

Core blocking and routing logic.

```typescript
input = {
  tool_name: string,      // "Bash", "Write", "Edit", etc.
  tool_input: {           // Tool parameters
    command?: string,     // For shell commands
    file_path?: string,   // For file operations
    ...
  },
  session_id?: string,    // Claude session ID
  machine_id?: string     // Machine identifier
}

output = {
  blocked: boolean,       // true if tool use should be blocked
  reason?: string,        // Why it was blocked
  routing?: string        // Optional routing target
}
```

### Blocking Rules

1. **Dangerous Shell Commands**
   - Patterns: `rm -rf /`, `format `, `mkfs`, `shutdown `
   - Applies to: `Bash` tool
   - Action: BLOCK

2. **Protected File Paths**
   - Paths: `.git`, `.env`, `\Windows\`, `\System32\`, `node_modules`
   - Applies to: `Write`, `Edit` tools
   - Action: BLOCK

3. **System Reads**
   - Paths: `\Windows\`, `\System32\`
   - Applies to: `Read`, `Glob` tools
   - Action: BLOCK

### Extensibility (Wave 2+)

The `routing_rules` table allows adding custom routing policies without code changes:

```json
{
  "name": "route-large-files-to-codex",
  "tool": "*",
  "condition_json": "{\"input_size_bytes\": {\"$gt\": 1000000}}",
  "action": "route",
  "target_agent": "codex-team",
  "priority": 50,
  "enabled": 1
}
```

## Deployment

### Development
- Node.js with TypeScript compilation
- SQLite in-memory or file-based
- Health endpoint: http://localhost:3000/health

### Production (Fly.io)
- Docker container (node:20-alpine)
- SQLite with WAL mode for concurrency
- Persistent volume for database
- Health check: GET /health every 30 seconds
- Regional deployment (default: London, can be changed)

## Security

### Authentication
- Bearer token required for all endpoints except `/health`
- Token verified against `GEN_TOKEN` env var
- Returns 401 Unauthorized if missing or invalid
- Returns 500 if `GEN_TOKEN` not configured

### Authorization
- All authenticated requests allowed to all endpoints
- Per-endpoint/resource authorization added in Wave 5

### Data Protection
- SQLite database on persistent volume
- No credentials logged in events
- Tool input stored as JSON (sensitive params should be masked at call site)

### Fail-Open Safety
- If Gen crashes or is unavailable, Claude continues unblocked
- HTTP 500 errors return `continue: true`
- Prevents infrastructure from blocking legitimate work

## Observability

### Logging
- Console logs all HTTP requests with method, path, status, duration
- Tool events logged to SQLite for audit trail

### Metrics (Wave 5)
- Optional Prometheus endpoint: GET /metrics
- Tracks: total requests, decision distribution, event counts, etc.

### Monitoring
- Fly.io health check: GET /health every 30 seconds
- Database size monitoring
- Event log growth rate

## Scaling

### Horizontal Scaling
- Stateless HTTP server (no session affinity needed)
- Multiple instances can share SQLite database (WAL mode)
- Fly.io scales automatically based on CPU/memory

### Vertical Scaling
- Increase memory: `fly scale memory 512`
- Increase vCPU: `fly scale vm <type>`

### Database Scaling
- Current: SQLite with persistent volume
- Future: Migrate to PostgreSQL for multi-instance sync

## Extensibility

Wave 2–5 add:
- **Wave 2:** Query APIs (events, stats, tasks, config)
- **Wave 3:** Webhook ingestion (GitHub, CI)
- **Wave 4:** MCP channel integration
- **Wave 5:** Learning patterns + adaptive routing

Each layer preserves the core decision logic and plugs into the logging pipeline.

## Testing

- **L0 (Contract):** Module loads, schema syntax valid
- **L1 (Unit):** decidePretool logic, auth token validation
- **L2 (Integration):** HTTP endpoints, database interactions
- **L3 (Component):** Full deployment simulation, end-to-end flows

Test pyramid emphasis: lots of fast unit tests, fewer slower integration tests.
