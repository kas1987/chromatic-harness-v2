# Gen orchestrator (hook pipeline)

Decision middleware for Claude Code: **`/hooks/user-prompt`**, **`/hooks/pretool`**, **`/hooks/posttool`**, budget guardrails, LLM routing, memory, and related routes. Default listen: **`http://localhost:43123`** (`GEN_PORT` overrides).

## Observability

- **OpenTelemetry:** Set **`OTEL_EXPORTER_OTLP_ENDPOINT`** to your OTLP collector base URL (no path). The process sends traces to `{endpoint}/v1/traces` and metrics to `{endpoint}/v1/metrics` (see [`src/otel/otel-init.ts`](src/otel/otel-init.ts)). If unset, traces and metrics are disabled (console log only).
- **LLM routing on traces:** Successful **`hook.pretool`** and **`hook.user-prompt`** spans set **`gen.suggested_llm`**; pretool also sets **`gen.pretool_routing_source`**, reconciliation, session-hint age, and optional **`gen.actual_llm`** when clients send **`activeLlm`**. Full table: **[`../docs/agent-observability/GEN-OTEL.md`](../docs/agent-observability/GEN-OTEL.md)**. Behavior and diagrams: **[`docs/INTENT-LLM-ROUTING.md`](docs/INTENT-LLM-ROUTING.md)**. PromQL / SQL examples: **[`docs/META-ROUTING-DASHBOARD.md`](docs/META-ROUTING-DASHBOARD.md)**.
- **E2E metadata (optional):** Set **`GEN_E2E_METADATA=1`** and send headers `X-Gen-E2E-Run` / `X-Gen-E2E-Tags` (or body `metadata.e2eRunId` / `e2eTags`) so hook spans and observability logs include test run identity — see **[`../docs/agent-observability/GEN-OTEL.md`](../docs/agent-observability/GEN-OTEL.md)** (E2E section).
- **Reference docs:** Target event taxonomy, data models, and rollout phases: **[`../docs/agent-observability/README.md`](../docs/agent-observability/README.md)**. Local OTLP setup notes: **[`../docs/agent-observability/GEN-OTEL.md`](../docs/agent-observability/GEN-OTEL.md)**.

## Quick Start

### Development

1. Install dependencies:
```bash
npm install --ignore-scripts
```

2. Set environment variables (optional auth and features — see `.env.example` if present):
```bash
# cp .env.example .env  # when available
# Set GEN_TOKEN (and other GEN_* flags) as needed
```

3. Run the server:
```bash
npm run dev
```

Server listens on **`http://localhost:43123`** (or `GEN_PORT`).

### Build

```bash
npm run build
npm start
```

## API Endpoints

### Health Check
- `GET /health` — Returns `{status: "ok"}` (no auth required)

### Hooks
- `POST /hooks/pretool` — Pre-tool hook
- `POST /hooks/posttool` — Post-tool hook
- `POST /hooks/user-prompt` — User prompt hook  
  When **`GEN_TOKEN`** is set, send an `Authorization: Bearer` header with your token.
- `POST /hooks/dispatch-outcome` — Queue async dispatch completion lines for a **`sessionId`** (same auth as hooks). Body: `{ "sessionId": "...", "hop_id": "...", "status": "completed", "summary": "optional" }`. The **next** `/hooks/user-prompt` for that session prepends a **`[DISPATCH UPDATES]`** block to the raw prompt so Claude sees worker results on the following turn.

### Model dispatch gateway (`/api/delegate`)

Server-side **multi-provider** completions (Claude / GPT / Gemini / Ollama / LM Studio / MiniMax) with queue, capacity limits, and a SQLite **`delegation_log`** audit trail. Same `Authorization: Bearer` header (with your token) as other protected routes.

- `POST /api/delegate` — Body: `{ "prompt": "..." }` plus optional `role`, `preferredProvider`, `task`, `workflowType` (`interactive` default, `background` for fail-open when all providers fail), and envelope fields (`repo`, `userId`, `sessionId`, `taskIntent`, `riskLevel`, `toolContext`). See **[`../docs/architecture/MODEL-DISPATCH-GATEWAY.md`](../docs/architecture/MODEL-DISPATCH-GATEWAY.md)**.
- `GET /api/delegate/status` | `queue` | `roles` | `services` | `sysinfo` — Operations and UI helpers ([`public/dispatch.html`](public/dispatch.html)).

### Hop dispatch, SSE, and Claude loop-back

- **Hop** ([`src/middleware/hop-middleware.ts`](src/middleware/hop-middleware.ts)) runs only when `metadata.intent_tag` is set on `/hooks/user-prompt`. It uses [`hop-routes.json`](hop-routes.json) and shares the app **`ChannelBroadcaster`** with **`GET /channels/subscribe/:channelId`** (e.g. subscribe to `hop.inbox` to receive `hop.dispatch` SSE events).
- **Same turn:** The user-prompt response may include a **`hop`** object (`hop_id`, `destination`, `rule_id`, `dispatch_mode`) and an appended **`[Hop]`** footer in `hookSpecificOutput.updatedUserMessage` with instructions to call **`/hooks/dispatch-outcome`**.
- **Next turn:** Pending outcomes are merged into the user message as **`[DISPATCH UPDATES]`** (see above). There is no supported way to push text into an in-flight Claude Code turn from Gen; use hook output or the next message.
- **Remote MCP forward:** Rules with **`destination_type`: `remote_mcp`** POST JSON to **`GEN_HOP_REMOTE_MCP_URL`**/`destination` (or optional rule field **`mcp_forward_path`**). If the env var is unset, the forward is skipped and a warning is logged.
- **Claude Code hook commands on Windows:** Use **forward slashes** in script paths inside JSON hook configs (e.g. `D:/.04_Prism/...`) so paths are not mangled by a second escape pass.

### Deployment

#### Local Testing

```bash
# Start server
npm run dev

# In another terminal, test pretool (omit Bearer if GEN_TOKEN unset)
curl -X POST http://localhost:43123/hooks/pretool \
  -H "Content-Type: application/json" \
  -d "{\"tool\":\"Read\",\"input\":{\"file_path\":\"README.md\"}}"
```

#### Remote deployment

Treat Gen like any Node/Express service: set `GEN_PORT`, **`GEN_TOKEN`** (if you want auth), embedding/Ollama flags from `.env.example`, and optional **`OTEL_EXPORTER_OTLP_ENDPOINT`**. Fly.io or other hosts are supported, but **no canonical Fly app name or legacy Rudalo URL is maintained in this README** — use your own app URL and secrets.

## Architecture

- **Dispatch and orchestration (cross-repo reference):** [../docs/architecture/DISPATCH-AND-ORCHESTRATION-REFERENCE.md](../docs/architecture/DISPATCH-AND-ORCHESTRATION-REFERENCE.md) — two-plane model (Gen vs front door), flows, SWOT, next steps.
- **Express.js** — HTTP server and middleware
- **SQLite** — Memory, budget, learning, events, and related stores (single DB path from config)
- **TypeScript** — Type-safe implementation
- **Intent-based LLM routing** — How `user-prompt` + `pretool` choose `suggestedLlm` using `IntentClass`, session TTL cache, and read-only tool overrides — see **[`docs/INTENT-LLM-ROUTING.md`](docs/INTENT-LLM-ROUTING.md)** (includes Mermaid sequence and flow diagrams).

### Schema

Tables evolve with features (memories, budgets, learning, ingest, queue, etc.). Inspect initialization in [`src/index.ts`](src/index.ts) and store modules under `src/` rather than relying on a static list here.

## Security

- When **`GEN_TOKEN`** is set, clients must send an `Authorization: Bearer` header with their token for protected routes; if **`GEN_TOKEN`** is unset, auth middleware logs a warning and **allows** requests (dev convenience — see [`src/middleware/auth.ts`](src/middleware/auth.ts)).
- `BudgetGuard` and hook logic still enforce dangerous-operation blocks where configured.
- Fail-open: if Gen is unreachable, the client hook implementation typically continues (product-specific).

## Development

### Testing

```bash
npm test          # watch mode (excludes Playwright dispatch UI)
npm run test:run  # CI-style single pass (same exclusions)
```

Dispatch UI smoke tests ([`tests/integration/dispatch-ui.test.ts`](tests/integration/dispatch-ui.test.ts)) use **Playwright** and are **not** part of the default Vitest run (see `vitest.config.ts`). Run them explicitly after installing browsers:

```bash
npm run test:dispatch-ui
# First time (or CI): download Chromium for Playwright
npx playwright install chromium
```

### Linting

```bash
npm run lint
```

## License

MIT
