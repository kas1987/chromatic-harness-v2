# Validation Matrix — Chromatic Harness v2

> **Purpose:** Tracks proof-of-operation status for every existing layer.  
> **Gate rule:** [GOVERNANCE_EXPANSION_GATE.md](GOVERNANCE_EXPANSION_GATE.md)  
> **Legend:** ✓ proven | ⚠️ partial | ✗ missing  
> **Last updated:** 2026-05-30

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| ✓ | Evidence present and verified |
| ⚠️ | Evidence exists but incomplete or untested end-to-end |
| ✗ | Evidence absent — layer cannot be treated as proven |

---

## Layer Evidence Matrix

| Layer | Runtime Test | Frontend/Operator Evidence | Telemetry/Event Evidence | Overall Status |
|-------|-------------|---------------------------|--------------------------|----------------|
| **00_SOURCE_OF_TRUTH** — Canonical harness flow docs | ⚠️ `test_runtime_spine.py` (file-existence checks only) | ✗ No console surface | ✗ No events emitted | ⚠️ partial |
| **01_PROTOCOLS / BEADS** — Bead schema + intake protocol | ✓ `test_bead_lifecycle_e2e.py`, `test_intake_queue.py` | ⚠️ `bd ready` CLI visible; no UI panel | ✓ `.beads/issues.jsonl` + audit log | ⚠️ partial |
| **01_PROTOCOLS / CMP** — Mission packet schema | ✓ `test_schema_validation.py` validates MISSION_PACKET_SCHEMA.json | ✗ No frontend panel | ✓ Schema events in `07_LOGS_AND_AUDIT` | ⚠️ partial |
| **01_PROTOCOLS / INTAKE** — Intake queue pipeline | ✓ `test_auto_intake.py`, `test_run_intake_cycle_scripts.py` | ✗ No frontend panel | ✓ `.tmp_ingest/` + intake logs | ⚠️ partial |
| **01_PROTOCOLS / MAGNETS** — Magnet plugin system | ✓ `test_magnet_orchestrator.py`, `test_magnet_plugins.py` | ✗ No console widget | ✓ Events logged to audit | ⚠️ partial |
| **01_PROTOCOLS / MCP** — MCP server wiring | ✓ `test_chromatic_mcp_handlers.py` | ✗ No frontend indicator | ⚠️ MCP tool calls logged but not queryable | ⚠️ partial |
| **02_RUNTIME / router** — Model routing engine | ✓ `test_router_gates.py`, `test_complexity_and_routing.py` | ✗ No console routing panel | ✓ Router decisions logged | ⚠️ partial |
| **02_RUNTIME / orchestrator** — Task orchestrator | ✓ `test_workflows.py`, `test_workflow_guardrails.py` | ✗ No frontend panel | ✓ Workflow events in audit logs | ⚠️ partial |
| **02_RUNTIME / intake** — Runtime intake adapter | ✓ `test_auto_intake.py` | ✗ No console surface | ✓ Intake events logged | ⚠️ partial |
| **02_RUNTIME / concurrency** — Lock/concurrency primitives | ✓ `test_concurrency_primitives.py`, `test_lock_contention.py` | ✗ No frontend indicator | ✓ `test_lock_metrics_rollup.py` traces | ⚠️ partial |
| **02_RUNTIME / budget** — Budget ledger | ✓ `test_budget_ledger.py` | ✗ No console widget | ⚠️ Ledger file exists; no event stream | ⚠️ partial |
| **02_RUNTIME / activity** — Activity log | ✓ `test_activity_log.py` | ✗ No frontend panel | ✓ `07_LOGS_AND_AUDIT` activity log | ⚠️ partial |
| **02_RUNTIME / magnets** — Runtime magnet execution | ✓ `test_discipline_magnet.py`, `test_magnet_orchestrator.py` | ✗ No UI | ✓ Magnet events audited | ⚠️ partial |
| **02_RUNTIME / chromatic_mcp** — MCP handler runtime | ✓ `test_chromatic_mcp_handlers.py` | ✗ No console surface | ⚠️ Tool-call logs only | ⚠️ partial |
| **02_RUNTIME / api + console_api** — API layer | ✓ `test_api.py`, `test_agent_lead_api.py` | ✗ No frontend health widget | ✓ API request logs | ⚠️ partial |
| **02_RUNTIME / knowledge** — Knowledge store | ✗ No dedicated test | ✗ No console surface | ✗ No event evidence | ✗ missing |
| **02_RUNTIME / memory** — Memory subsystem | ✗ No dedicated test | ✗ No console surface | ✗ No event evidence | ✗ missing |
| **02_RUNTIME / pi** — Pi (Raspberry Pi) runtime | ✓ `test_roach_pi_guard.py` | ✗ No console panel | ⚠️ Status script only; no event stream | ⚠️ partial |
| **02_RUNTIME / runtime-engines** — Runtime engine registry | ✓ `test_runtime_spine.py` (partial) | ✗ No frontend | ✗ No event evidence | ⚠️ partial |
| **03_AGENTS** — Agent registry and lead | ✓ `test_agent_lead.py`, `test_agent_lead_api.py` | ✗ No frontend agent panel | ⚠️ Agent activity logged via `log_agent_activity.py` | ⚠️ partial |
| **04_PLAYBOOKS** — Operational playbooks | ⚠️ Playbook scripts referenced in tests indirectly | ✗ No frontend panel | ✗ No event evidence | ⚠️ partial |
| **05_FRONTEND_CONSOLE** — Next.js operator console | ✓ Build artifacts present; `test_src_chromatic_router_coverage.py` | ✓ Console UI exists at :3030 | ⚠️ Frontend events not yet wired to audit | ⚠️ partial |
| **06_DATA** — Data layer | ✗ `.gitkeep` only; no content | ✗ No frontend panel | ✗ No event evidence | ✗ missing |
| **07_LOGS_AND_AUDIT** — Log and audit sink | ✓ `test_two_log_audit.py`, `test_audit_hooks.py` | ✗ No frontend log viewer | ✓ Files written; queryable by scripts | ⚠️ partial |
| **08_PDRS** — Post-decision records | ⚠️ No direct test; referenced by audit scripts | ✗ No frontend | ✓ PDR files in directory | ⚠️ partial |
| **09_DEPLOYMENT** — Docker/deployment configs | ⚠️ Smoke stack script (`smoke_stack.ps1`) exists | ✗ No console health panel | ✗ No event evidence | ⚠️ partial |
| **10_RUNTIME (root)** — Legacy runtime logs | ✗ No test | ✗ No frontend | ⚠️ Log files only | ✗ missing |
| **11_SANDBOX_LAB** — Sandbox experimentation | ✗ No test | ✗ No frontend | ✗ No event evidence | ✗ missing |
| **12_HANDOFFS** — Session handoff artifacts | ⚠️ `test_session_compact.py` (partial) | ✗ No console panel | ⚠️ Handoff JSON files only | ⚠️ partial |
| **src/** — Core Python source modules | ✓ Extensive test coverage across `tests/` | ✗ No dedicated frontend panel | ✓ Module events logged | ⚠️ partial |
| **scripts/** — Operational scripts | ✓ Many scripts have companion tests | ✗ No frontend panel | ✓ Script outputs logged | ⚠️ partial |

---

## Summary

| Status | Count |
|--------|-------|
| ✓ fully proven | 0 |
| ⚠️ partial | 22 |
| ✗ missing | 5 (`02_RUNTIME/knowledge`, `02_RUNTIME/memory`, `06_DATA`, `10_RUNTIME`, `11_SANDBOX_LAB`) |

**No layer is currently fully proven (all three evidence columns ✓).** Expansion is blocked until at least the prerequisite layers for any proposed new layer reach ✓ status.

---

## How to Advance a Layer to Proven

To move a layer from ⚠️ or ✗ to ✓:

1. Add or fix a runtime test that exercises the layer end-to-end and passes in pytest.
2. Wire a visible indicator into `05_FRONTEND_CONSOLE` (status widget, log panel, or health endpoint shown in the UI).
3. Ensure the layer emits at least one structured event to `07_LOGS_AND_AUDIT` that can be replayed or queried.

Update this table when all three are satisfied and record the bead that closed the gap.
