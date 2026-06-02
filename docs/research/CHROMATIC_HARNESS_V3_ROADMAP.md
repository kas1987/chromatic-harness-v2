# Chromatic Harness v3 Roadmap — "Typed · Enforced · Observable · Consolidated"

**Status:** Proposed
**Date:** 2026-06-02
**Author:** harness agent (autonomous audit)
**Predecessor:** [CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md](./CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md)
**Tracking:** bd label `v3` (9 epics, 47 beads) — see [§7 Epic Index](#7-epic-index). Full list: [`v3_bead_map.md`](./v3_bead_map.md).

---

## 1. Executive Summary

A six-stream parallel audit of the whole harness (~46k LOC Python across 117 runtime + 203 script files, 188 test files, 168 docs, plus a 9,274-file TypeScript console) finds a system that is **feature-complete in breadth but architecturally unfocused**. Every major capability exists — routing, budgets, two-log audit, intake→beads, workflows, magnets, a FastAPI backend — but the implementation carries the debt of fast growth:

- **Untyped boundaries.** Core dataflow crosses `dict[str, Any]` seams (RoutingContext, MagnetEvent, context manifest), so stages can't be type-checked or tested in isolation.
- **God-files.** `session_closeout.py` (2,004 LOC), `api/main.py` (670), `router/gate.py` (609), `control_plane/controller.py` (460), `memory/memory_gate.py` (418).
- **Stub-heavy magnets.** 15 of 17 magnet classes are <50 LOC skeletons; the six-stage orchestrator pipeline's `correlate/score/recommend` return empty dicts.
- **Specs defined but unenforced.** Rich JSON schemas (BEADS, CMP, MAGNETS, INTAKE) exist but are disconnected from CI and runtime; three competing event schemas coexist.
- **Observability real but incomplete.** The two-log model (36k execution + 24k decision entries) works and now feeds the just-shipped playbook-evolution loop — but traces are OTel-*shaped* and never exported, cost is daily/monthly only (no per-mission rollup), and `traces.jsonl` is 19.9 MB and unbounded.
- **Quality gates perpetually RED (36/100).** `coverage_gate` and `arch_compliance_gate` have no artifacts, so quality caps at 40; advisory gates are non-blocking; the pre-session manifest ages out at 360 min.
- **Repo sprawl.** The numbered `00_–12_` scheme is undermined by legacy duplicates (`10_RUNTIME`, `agent_handoffs`, `hooks` vs `git_hooks`, `state`, `reports`, `02_DOCS` vs `docs`) and a 898-file `02_RUNTIME` monolith.
- **Automation sprawl.** 203 scripts with no registry; 9 synchronous hooks, two of which (`git_collision_pretooluse`, `router/gate`) run hundreds of times per session on the critical path; duplicated validators/collision/audit scripts; orphaned `propose_learnings.py`.

**v3 is not new features — it is hardening.** The thesis: invert the stack so **types and contracts come first**, then make the magnets/adapters real plugins over those contracts, **enforce every spec in CI**, **export and bound observability**, **consolidate** the automation and directory sprawl, and **keep the quality gate green**. The outcome is a production-grade, self-governing agent OS rather than a feature-complete prototype.

---

## 2. Audit Method

Six read-only `Explore` subagents ran in parallel, each owning one slice and returning a structured report (inventory · maturity map · debt · v3 opportunities):

| # | Slice | Scope |
|---|-------|-------|
| 1 | Runtime core | `02_RUNTIME/` — router, magnets, audit, workflows, api, budget |
| 2 | Automation & scripts | `scripts/` (203), `.claude/` hooks & workflows, `git_hooks/` |
| 3 | Protocols & canon | `01_PROTOCOLS/`, `00_SOURCE_OF_TRUTH/`, `00_META/`, schemas |
| 4 | Observability & cost | `07_LOGS_AND_AUDIT/`, `audit/two_log.py`, `router/observability.py` |
| 5 | Repo structure & hygiene | top-level layout, duplicate/legacy dirs |
| 6 | Quality, tests & governance | `tests/` (188), CI, gates, readiness scoring |

Findings below are the synthesis. Each is tied to concrete evidence (file:line or artifact).

---

## 3. Consolidated Findings

### 3.1 Runtime core — broad but unfocused
- Router/gate are feature-complete (15 provider adapters, confidence/privacy/budget/context gates) but **hardcoded**: `_register_default_adapters()` wires all 15 in code; each adapter has its own 7–10 exception types — no normalized error boundary.
- `gate.py` (609 LOC) is a hook-dispatch monolith doing stdin I/O + context load + classify + select + dispatch + log + recover.
- Magnets are **passive signal carriers**; all pipeline logic lives in `magnet_orchestrator.process()`, and `correlate/score/recommend` are stubs.
- Multi-language fragmentation: Python runtime + 252 TypeScript files (CMP bridge, sandbox-lab) joined by `sys.path` manipulation, no interface contract.

### 3.2 Observability — real foundation, missing the production edge
- **REAL:** execution log (`execution.jsonl`, 36k lines, SHA-256 hashes + idempotency keys), decision log (`decision_log.jsonl`, 24k lines), playbook-evolution loop (just shipped).
- **PARTIAL/STUB:** traces are GenAI-semconv-*shaped* but there is **no OTLP exporter**; cost is tracked per agent/tool/day but **not rolled up per mission**; `CostMagnet` is a 4-line stub; no sampling/rotation (traces 19.9 MB, growing); decision log has **weak idempotency** (no `decision_id`).
- Live signal worth acting on: **1,797 medium-band `replan` decisions** — the harness replans instead of self-healing.

### 3.3 Protocols — spec-rich, enforcement-poor
- Schemas exist for BEADS, CMP (mission_packet, confidence_gate), MAGNETS (magnet_event, inflection_points), INTAKE — but **CI validates only `HARNESS_EVENT_SCHEMA`**. Beads, missions, magnet events, and intake entries are not validated at ingest.
- **Three event schemas** (`HARNESS_EVENT`, `magnet_event`, `bead`) operate independently with no convergence rule.
- **Authority conflict:** `00_META/REPO_OPERATING_CONTRACT.md` and `00_SOURCE_OF_TRUTH/CHROMATIC_HARNESS_MANIFEST.md` both claim to be authoritative; `canon_registry.yaml` has no liveness check.

### 3.4 Repo structure — numbered scheme undermined
- Intended `00_–12_` layering is real, but legacy duplicates violate it: `10_RUNTIME` (empty; real content under `02_RUNTIME/10_RUNTIME/`), `agent_handoffs/` (vs `12_HANDOFFS/`), `hooks/` (vs `git_hooks/`), `state/` & `reports/` (stale), `02_DOCS/` (1 file vs `docs/` 173).
- `02_RUNTIME` is a 898-file monolith; `.agents/` (3,397 files — the flywheel) sits outside the numbered scheme entirely.

### 3.5 Quality — perpetually red
- `coverage_gate.py` and `arch_compliance_gate.py` exist but their artifacts don't, so `quality_score` caps at 40/100 and readiness is RED (36/100).
- Advisory gates (`ai_review_gate`, `drift_gate`, `pr_size`) are `continue-on-error: true` — non-blocking.
- Pre-session manifest ages out at 360 min → readiness fails on staleness; `run-all-e2e.py` SUITES live only in worktrees, not main CI; 23 test files carry skip/xfail with no flakiness budget.

### 3.6 Automation — sprawl on the hot path
- 203 scripts, no registry to distinguish production-critical from observational.
- 9 synchronous hooks; `git_collision_pretooluse.py` (PreToolUse Bash) and `router/gate.py` (PreToolUse Agent) run **hundreds of times per session**; `session_closeout.py` (2,004 LOC) blocks exit up to 180 s.
- Duplication: 3 event-validators, **5 collision scripts**, overlapping audit scripts; `propose_learnings.py` is an orphan (no callers).

---

## 4. v3 Vision

> **Chromatic Harness v3 makes the implicit explicit and the advisory enforced.**

Four pillars, each mapping to a cluster of epics:

1. **Typed** — sealed contracts at every runtime boundary; god-files decomposed into tested units; `mypy --strict` on the core. *(V3-1)*
2. **Enforced** — every schema validated in CI and at runtime; one unified event envelope; canon liveness; quality gates that actually block and stay green. *(V3-3, V3-7)*
3. **Observable** — OTLP export, per-mission cost rollup, cost-as-correctness alerting, bounded retention; real magnets feeding a real pipeline. *(V3-2, V3-4)*
4. **Consolidated** — script registry, hot-path hooks moved async, collision/validator/audit dedup, clean numbered directory architecture. *(V3-5, V3-6)*

Plus the intelligence work the v2 gaps doc deferred — confidence gate v2, self-heal, autonomy levels, MCP/context layer. *(V3-8, V3-9)*

---

## 5. Priority Sequencing

| Tier | Epics | Rationale |
|------|-------|-----------|
| **P0 — Foundation** | V3-1 Typed Runtime · V3-3 Schema-as-Contract · V3-6 Structure Reorg | Contracts + enforced schemas + clean layout unblock everything else. |
| **P1 — Core** | V3-2 Magnets · V3-4 Observability · V3-7 Quality Gates | Build real subsystems on the typed foundation; get to green. |
| **P2 — Intelligence** | V3-5 Automation Consolidation · V3-8 Confidence/Self-Heal/Autonomy | Tame sprawl; act on the replan signal; add autonomy levels. |
| **P3 — Maturity** | V3-9 MCP & Context Layer | Token-budgeted ecosystem wiring once the core is solid. |

Dependency notes: V3-2 depends on V3-1 contracts; V3-4 cost-gate depends on V3-2 CostMagnet; V3-8 builds on V3-3 (CMP enforcement) and the V3-4 cost signal; V3-9 builds on V3-3's CMP→MCP coupling.

---

## 6. Success Metrics (v2 → v3 targets)

| Metric | v2 (now) | v3 target |
|--------|----------|-----------|
| Readiness score | 36/100 (RED) | ≥ 80 (GREEN), sustained |
| `dict[str,Any]` at runtime public boundaries | pervasive | 0 (mypy --strict on core) |
| Magnets fully implemented | 2/17 | 17/17 |
| JSON schemas enforced in CI | 1/6 | 6/6 |
| Observability export | none | OTLP to collector |
| Per-mission cost visibility | none | `mission_costs.jsonl` rollup |
| Unbounded JSONL growth | yes (19.9 MB traces) | sampled + 30-day rotation |
| Synchronous hot-path hooks | 2 (100s×/session) | 0 (async/batched) |
| Largest single file | 2,004 LOC | < 400 LOC |
| Legacy duplicate root dirs | 6 | 0 |
| Medium-band replans (self-heal) | 1,797 | self-heal first; replan as fallback |

---

## 7. Epic Index

Each epic is tracked in bd under label `v3` (+ a per-epic label). Bead IDs are listed in the companion map `docs/research/v3_bead_map.md` (generated at creation). Summary:

### V3-1 — Typed Runtime Core & Contract Boundaries `[P0 · v3-runtime]`
RoutingContext sealed contract · gate.py → middleware pipeline · adapter factory + `adapters.yaml` · split Router/Orchestrator · decompose memory_gate/controller · `mypy --strict` CI gate.

### V3-3 — Schema-as-Contract Governance `[P0 · v3-governance]`
Schema registry + CI validator · unify the 3 event schemas · canon liveness check · CMP→MCP policy coupling · `_AUTHORITY.yaml` precedence · runtime ingest validation.

### V3-6 — Repo Structure Clean-Architecture Reorg `[P0 · v3-structure]`
`REPO_LAYERS.md` canonical layout · retire 6 duplicate root dirs · decompose `02_RUNTIME` · formalize `.agents/` · canonicalize `git_hooks`.

### V3-2 — Magnets Layer Completion `[P1 · v3-magnets]`
CostMagnet · Execution+Intent magnets · Security+Discipline magnets · Intake/Closure bookends · real correlate/score/recommend.

### V3-4 — Observability v3 `[P1 · v3-observability]`
OTLP exporter · mission cost rollup · cost-as-correctness gate · trace sampling + rotation · decision-log idempotency + trace_id join.

### V3-7 — Quality Gates v3 `[P1 · v3-quality]`
Wire coverage_gate to pytest-cov · wire arch_compliance baseline · auto-rebuild manifest · promote advisory gates to blocking · flakiness budget · run-all-e2e into main CI.

### V3-5 — Automation Consolidation & Hook Slimming `[P2 · v3-automation]`
`scripts/REGISTRY.yaml` · consolidate validators · unify collision detection · split session_closeout · move PreToolUse hooks async · merge audit suite / deprecate orphans.

### V3-8 — Confidence Gate v2, Self-Heal & Autonomy Levels `[P2 · v3-intelligence]`
Confidence Gate v2 · self-heal loop (targets the 1,797 replans) · Autonomy L0–L5 · complete Agent Lead synthesis · playbook-evolution → gate tuning.

### V3-9 — MCP Tool & Context Layer + Token Hygiene `[P3 · v3-mcp]`
MCP token-budget enforcement + lazy load · typed context-layer manifest · budget-gated MCP ecosystem wiring.

---

## 8. Migration & Risk

- **Incremental, behind the full gate.** Each bead ships as its own worktree → PR → CI-green → squash-merge, exactly as the v2 j2r0/7d2.5 work did. No big-bang rewrite.
- **Structure reorg (V3-6) is the highest-risk epic** — moving/retiring directories can break path references across 203 scripts and 9 hooks. Do it via `git mv` + a path-reference sweep + the full E2E gate, one directory cluster per PR.
- **Hot-path hook changes (V3-5)** must preserve collision-safety; land the async supervisor before retiring the synchronous detector.
- **Schema enforcement (V3-3)** may surface existing non-conforming data; add validators in *warn* mode first, then promote to *blocking* once the corpus is clean.
- **TypeScript/Python boundary** is out of scope for v3 unless a specific bead calls for it; the console (`05_FRONTEND_CONSOLE`) is treated as a separate deliverable.

---

## 9. Out of Scope for v3

- Rewriting the React/TypeScript console (`05_FRONTEND_CONSOLE`, 9,274 files).
- Replacing beads/Dolt or the CI provider.
- New provider adapters beyond normalizing the existing 15.
- `bb7x` (GH_TOKEN PAT rotation) — user-gated, tracked separately.
