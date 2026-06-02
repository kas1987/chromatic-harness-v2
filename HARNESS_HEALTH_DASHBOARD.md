# Harness Health Dashboard Cockpit

> Issue #79 / NW-RG-079 — the runtime cockpit for the Chromatic Harness governance work.
> One command reports the live health of every runtime dependency, each as **pass / warn / fail**.

## Quick start

```bash
# JSON to stdout (read-only, nothing written)
python scripts/harness_health_check.py

# Markdown dashboard
python scripts/harness_health_check.py --markdown

# Persist the report artifact (the ONLY thing --write touches)
python scripts/harness_health_check.py --write
# -> 05_REPORTS/harness_health/latest.json
# -> 05_REPORTS/harness_health/latest.md
```

Exit code is `0` unless an **integrity** check fails (`overall_status: red`).
Optional services being down never fail the cockpit — they WARN.

## What it checks

### Runtime services (bare TCP probe — no credentials, no mutation)

| Service | Env override | Default endpoint |
|---|---|---|
| Rudalo | `RUDALO_URL` | `127.0.0.1:8800` |
| Ollama | `OLLAMA_URL` | `127.0.0.1:11434` |
| Neo4j | `NEO4J_URL` | `127.0.0.1:7687` |
| ChromaDB | `CHROMADB_URL` | `127.0.0.1:8000` |
| ComfyUI | `COMFYUI_URL` | `127.0.0.1:8188` |

Each probe opens a TCP connection (default 0.6s timeout) and immediately closes it.
No bytes are sent, no auth is attempted — so a probe can never trigger the
"requires credentials" or "would mutate state" stop conditions.

- **PASS** — port accepts a connection (service is up).
- **WARN** — port refused / timed out (service down or not configured), or the
  endpoint string is unparseable.

### Local integrity (read-only file inspection)

| Check | Source | Fails when |
|---|---|---|
| `hooks` | `.claude/settings.json`, `.claude/settings.local.json` | invalid JSON, or zero hooks configured |
| `routing_log` | latest `07_LOGS_AND_AUDIT/routing/routes_*.jsonl` | missing, unreadable, or any corrupt JSON line |
| `skill_inventory` | `SKILL.md` under `.agents/skills`, `.claude/skills`, `skills` | fewer than 1 discoverable skill |
| `last_go_artifact` | `07_LOGS_AND_AUDIT/decisions/decision_log.jsonl` | (warn only) missing / empty / stale > 7d |
| `active_queue` | `bd ready --json` | (warn only) bd unavailable or probe error |

`hooks`, `routing_log`, and `skill_inventory` are **authoritative** — a failure
sets `overall_status: red` and a non-zero exit, because the harness cannot be
trusted to dispatch safely without them. `last_go_artifact` and `active_queue`
only ever warn.

## Interpreting the output

- `overall_status`: `green` (all pass) · `yellow` (warnings only) · `red` (a hard
  integrity check failed).
- `readiness_score`: `100 - 20·fails - 6·warns`, floored at 0.
- `counts`: pass / warn / fail totals.

## Read-only guarantee

The cockpit mutates **nothing** by default. `--write` is the only flag that
touches disk, and it writes solely to `05_REPORTS/harness_health/` — a report
artifact, never harness state. This satisfies the NW-RG-079 stop condition
"health check would mutate state."

## Programmatic use

`summarize()` returns a fail-open compact dict (reads the last written artifact)
so the closeout report and the `release_readiness` meta-gate can aggregate the
cockpit's verdict via the standard governance gate contract
(`07_LOGS_AND_AUDIT/<area>/latest.json` + `summarize()`).

## Relationship to `harness_health_snapshot.py`

`harness_health_snapshot.py` covers **internal governance/budget** health (guard
freshness, token governance, budget forecast, telemetry coverage). This cockpit
covers **external runtime dependencies and integrity** (services, hooks, routing
log, skills, queue). They are complementary — run both for a full picture.
