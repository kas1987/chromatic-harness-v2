# REPO_LAYERS.md — Canonical Layout, Ownership & Deprecation Contract

> **Scope:** the *normative* per-directory contract for chromatic-harness-v2 — the
> canonical numbered scheme, who owns each layer, the write-policy for each, and the
> dated deprecation timeline for legacy root directories.
>
> **Authority:** this file is **subordinate to [`CHROMATIC_TREES.md`](CHROMATIC_TREES.md)**
> (rank 2, the repo-structure source-of-truth) and to
> [`00_SOURCE_OF_TRUTH/_AUTHORITY.yaml`](00_SOURCE_OF_TRUTH/_AUTHORITY.yaml). `CHROMATIC_TREES.md`
> is the *navigational map* ("where does X live?"); **this file is the *contract*** the
> structure-reorg epic (`v3-structure` / `8lri`) executes against. If the two disagree,
> `CHROMATIC_TREES.md` wins and this file must be reconciled.
>
> **Status:** canonical · **Owner of record:** TwistKS · **Maintained by:** harness agents
> · **Last reconciled:** 2026-06-02 · **Tracked by:** `chromatic-harness-v2-8lri.1`

---

## 0. How to use this file

- **"What is the canonical numbering and what owns each band?"** → §1 + §2.
- **"Can I write to directory X, or is it legacy?"** → §2 (write-policy) and §4 (legacy table).
- **"Why is `.agents/` not numbered?"** → §3 (meta-governance tier).
- **"When does legacy dir Y get removed, and where does its content go?"** → §4 timeline.
- **"How do I add a new top-level layer?"** → §5 conventions.

This file changes rarely. When a top-level directory is **added, retired, or moved**,
update §2/§4 here *and* §3/§4 of `CHROMATIC_TREES.md` in the same PR (see §6).

---

## 1. The canonical numbered scheme (`00_`–`13_`)

The repository's first-class content lives under a **two-digit layer band**. A band is a
*grouping*, not a unique slot: more than one cohesive directory may share a band when they
serve the same layer of the architecture (e.g. `00_SOURCE_OF_TRUTH/` and `00_META/` are both
"layer 00 — what is true"). This band convention is the accepted norm and is **not** a
collision to be renumbered.

| Band | Theme | Directories in band | Notes |
|-----:|-------|---------------------|-------|
| 00 | **Truth** — what is canonically true | `00_SOURCE_OF_TRUTH/`, `00_META/` | Manifest, authority, glossary, operating contract, event schema |
| 01 | **Contracts & state** | `01_PROTOCOLS/`, `01_STATE/` | Interface specs + live runtime state snapshots |
| 02 | **Runtime & docs** | `02_RUNTIME/`, `02_DOCS/` *(legacy)* | Core runtime; `02_DOCS/` folds into `docs/` (§4) |
| 03 | **Agents** | `03_AGENTS/` | Agent registry metadata (live flywheel is `.agents/`, §3) |
| 04 | **Playbooks** | `04_PLAYBOOKS/` | Role / workflow runbooks |
| 05 | **Surfaces & reports** | `05_FRONTEND_CONSOLE/`, `05_REPORTS/` | Visual console; KPI dashboards |
| 06 | **Data** | `06_DATA/` | SQLite / data stores |
| 07 | **Logs & audit** | `07_LOGS_AND_AUDIT/` | Execution / decision / trace logs (append-only) |
| 08 | **Design records** | `08_PDRS/` | Project design records + `_PDR_TEMPLATE.md` |
| 09 | **Deployment** | `09_DEPLOYMENT/` | Deploy configs, routing policy, CI assets |
| 10 | *(reserved)* | — | `10_RUNTIME/` was an empty duplicate of `02_RUNTIME/`; retired (§4). Band reserved. |
| 11 | **Sandbox** | `11_SANDBOX_LAB/` | Experimental harness |
| 12 | **Handoffs** | `12_HANDOFFS/` | Session handoffs, `SESSION_COMPACT.md` |
| 13 | *(reserved)* | — | Unused; reserved for a future first-class layer. Do not squat. |

Bands **10** and **13** are intentionally vacant: 10 is a retired duplicate band held in
reserve; 13 is unallocated headroom. Do not create a `10_*` or `13_*` directory without an
entry here and in `CHROMATIC_TREES.md`.

---

## 2. Ownership & write-policy matrix (numbered layers)

"Owner" is the **functional role** accountable for the layer's contents; all roles are
ultimately accountable to the owner of record (TwistKS). "Write-policy" states who/what may
add or modify files.

| Directory | Owner (role) | Responsibility | Write-policy | Status |
|-----------|--------------|----------------|--------------|--------|
| `00_SOURCE_OF_TRUTH/` | Governance / SoT | Manifest, glossary, decision log, `_AUTHORITY.yaml` | Humans + reconcile-PRs only; never auto-generated | CANONICAL |
| `00_META/` | Governance / SoT | Operating contract, observability meta (`HARNESS_EVENT_SCHEMA.json`) | Humans + reconcile-PRs | CANONICAL |
| `01_PROTOCOLS/` | Contracts | Interface specs + JSON schemas (BEADS, CMP, MAGNETS, MCP, INTAKE) | Schema PRs only; CI-validated | CANONICAL |
| `01_STATE/` | Runtime | Sprint/sync state snapshots | Runtime processes (machine-written) | CANONICAL |
| `02_RUNTIME/` | Runtime core | Router, magnets, audit, workflows, api, budget | Code PRs | CANONICAL ⚠ oversized (~899 files → decompose, `8lri.3`) |
| `03_AGENTS/` | Agents | Agent registry metadata | Agents + registry tooling | SPARSE |
| `04_PLAYBOOKS/` | Roles | Role / workflow runbooks | Doc PRs | CANONICAL |
| `05_FRONTEND_CONSOLE/` | Frontend | React/TS visual console (separate deliverable, ~9.3k files) | Frontend PRs | CANONICAL |
| `05_REPORTS/` | Observability | KPI dashboards, telemetry summaries | Reporting jobs + doc PRs | CANONICAL |
| `06_DATA/` | Data | SQLite / data stores | Runtime + migrations | CANONICAL |
| `07_LOGS_AND_AUDIT/` | Observability | Execution/decision/trace logs, governance intel, pre_session manifests | **Append-only**, machine-written | CANONICAL |
| `08_PDRS/` | Design | Project design records + `_PDR_TEMPLATE.md` | Design PRs | CANONICAL |
| `09_DEPLOYMENT/` | Deployment | Deploy configs, routing policy, CI assets | Ops PRs | CANONICAL |
| `11_SANDBOX_LAB/` | Any | Experiments (no stability guarantee) | Anyone; not load-bearing | CANONICAL |
| `12_HANDOFFS/` | Sessions | Session handoffs, compact docs | Agents at session boundaries | CANONICAL |

**Cross-cutting canonical directories** (outside the numbered scheme, but first-class):

| Directory | Owner (role) | Responsibility | Status |
|-----------|--------------|----------------|--------|
| `.claude/` | Harness/agents | Claude hooks, settings, lite workflows | CANONICAL |
| `git_hooks/` | Governance | Canonical git hooks (pre-commit, pre-push) | CANONICAL (resolve `hooks/` duality, `8lri.5`) |
| `scripts/` | Tooling | ~398 ops/audit scripts | CANONICAL ⚠ no registry yet (V3-5) |
| `tests/` | Quality | ~470 pytest files | CANONICAL |
| `src/` | Runtime core | `chromatic_router` library | CANONICAL |
| `docs/` | Docs | Research, governance, retros (~174 docs) | CANONICAL-PRIMARY |
| `templates/` | Authoring | Record + planning templates | CANONICAL |
| `config/`, `schemas/` | Contracts | Routing/MCP config, JSON schemas | CANONICAL |
| `registry/`, `*_registry.json` | Derived | Generated registries | DERIVED — never overrides §1–6 authority |

---

## 3. The meta-governance tier — `.agents/`

`.agents/` is **not** part of the numbered scheme and is not a runtime layer. It is the
**meta-governance tier**: the harness's flywheel of decisions, learnings, handoffs, and
governance records (~3,400 files) that *governs how the numbered layers are operated*,
rather than being one of them.

| Property | Value |
|----------|-------|
| **Tier** | Meta-governance (sits *above* the numbered layers, governs their operation) |
| **Owner** | Agent flywheel (all agents write; governance roles curate) |
| **Contents** | `decisions/`, `learnings/`, `handoffs/`, governance scopes, dispatch state |
| **Write-policy** | Agents append; background analysis writes **proposals to staging only** (never auto-implements) |
| **Read-as** | Possibly partially-written JSON — every reader must wrap `json.loads`/`JSON.parse` in try/except |
| **Status** | CANONICAL · formalization tracked by `chromatic-harness-v2-8lri.4` |

Sibling dot-dirs (`.beads/`, `.chromatic/`, `.codegraph/`, `.cursor/`, `.github/`, `.vscode/`)
are **tooling integration surfaces**, not governance tiers, and are owned by their respective
tools. They are out of scope for the numbered scheme and for retirement.

---

## 4. Legacy → canonical deprecation timeline

These loose root directories duplicate a canonical home. They are **read-only legacy**: do
not add new files to the left column; write to the canonical home instead. Retirement is
sequenced below and executed by the `v3-structure` epic.

| Legacy dir | Tracked files | Canonical home | Disposition | Bead | Status |
|------------|--------------:|----------------|-------------|------|--------|
| `10_RUNTIME/` | 0 (empty) | `02_RUNTIME/` | Absent on disk; band 10 reserved | `8lri.2` | ✅ done |
| `02_DOCS/` | 1 (`GO_MODE_STARTUP_SOP.md`) | `docs/` | Moved → `docs/`; roadmap reference is historical (left as-is) | `8lri.2` | ✅ done |
| `agent_handoffs/` | 3 (review/impl handoffs) | `12_HANDOFFS/` | Moved → `12_HANDOFFS/` | `8lri.2` | ✅ done |
| `hooks/` | 2 (`pre-commit`, `pre-push`) | `git_hooks/` | Reconcile vs `git_hooks/` (they **diverge**); keep one canonical set | `8lri.5` | ⏳ pending |
| `state/` | 2 (leases placeholder) | `01_STATE/` | **Carved out → `8lri.6`**: `state/leases/active_leases.jsonl` is the live lease ledger hardcoded as `DEFAULT_LEDGER` in ~8 collision-subsystem scripts; an atomic coordinated move, not a placeholder shuffle | `8lri.6` | ⏳ deferred |
| `reports/` | 2 (harness_health placeholder) | `05_REPORTS/` | Moved → `05_REPORTS/harness_health/`; updated `harness_health_check.OUT_DIR` + registry | `8lri.2` | ✅ done |
| `queue/` | 1 (`claude_adapter_next_work.queue.json`) | `07_LOGS_AND_AUDIT/queue/` | Moved → audit (stale #99 bootstrap, kept for provenance) | `8lri.2` | ✅ done |
| `issues/` | 1 (`claude_adapter_issue_map.md`) | `07_LOGS_AND_AUDIT/` | Stale (bd is the tracker) — moved to audit for provenance, not deleted | `8lri.2` | ✅ done |
| `dashboards/` | 3 (exporter + grafana/n8n READMEs) | `09_DEPLOYMENT/dashboards/` | Moved as a unit (exporter `_REPO` depth preserved); updated test + PDR + docstrings | `8lri.2` | ✅ done |

### Phased timeline

Dates are **targets**, gated on the named bead landing — not hard calendar commitments. Each
phase is reversible until Phase 3.

| Phase | Gate | What happens | Target |
|------:|------|--------------|--------|
| **0 — Announce** | this doc (`8lri.1`) | Legacy set declared; left column frozen to read-only | **2026-06-02** ✅ |
| **1 — Freeze & redirect** | `8lri.2` opens | CI warns on new writes to legacy dirs; inbound links updated to canonical homes | 2026-06 |
| **2 — Migrate** | `8lri.2` (+ `8lri.5` for hooks) | Files moved to canonical homes via `git mv`; `dashboards/` triaged; `CHROMATIC_TREES.md` §4 updated in the same PR | 2026-06 |
| **3 — Remove** | `8lri.2` closes | Empty legacy dirs deleted; bands 10/13 left reserved; final reconcile of `CHROMATIC_TREES.md` §3/§4 | 2026-07 |

`02_RUNTIME/` decomposition (`8lri.3`) and `.agents/` formalization (`8lri.4`) run on their own
tracks and are **not** part of this retirement timeline — they restructure *canonical* layers,
not legacy ones.

**Carve-outs from `8lri.2`:** `hooks/` (→ `8lri.5`, the hook sets genuinely diverge) and
`state/leases/` (→ `8lri.6`, the live lease ledger is wired into ~8 collision-subsystem scripts
via `DEFAULT_LEDGER`; moving it is an atomic coordinated refactor that must not be done as a
drive-by, or collision detection silently splits across two ledger paths).

---

## 5. Conventions for changing the layout

1. **Adding a top-level layer** — only from a reserved band (10, 13) or a new band ≥14. Add a
   row to §1 and §2 *here*, a row to §2/§3 of `CHROMATIC_TREES.md`, and state the owner and
   write-policy. No silent top-level directories.
2. **A band may hold multiple directories** when they serve the same architectural layer
   (see §1). Prefer reusing an existing band over inventing a number.
3. **Never write to a legacy dir** (§4 left column) once Phase 1 lands. Use the canonical home.
4. **Derived/generated output** (`registry/`, `*_registry.json`, `07_LOGS_AND_AUDIT/`) never
   asserts authority over a higher-ranked source (`_AUTHORITY.yaml` rank 8).
5. **Removal is a `git mv` then delete**, never a `git rm` of content that has no canonical
   home — find or create the home first.

---

## 6. Maintenance

- This file and `CHROMATIC_TREES.md` §3/§4 must be updated **in the same PR** whenever a
  top-level directory is added, retired, or moved.
- The `v3-structure` epic (`chromatic-harness-v2-8lri`) drives §4 to completion; mark each
  legacy row done as its bead closes.
- Keep §2 owners in sync with `00_SOURCE_OF_TRUTH/_AUTHORITY.yaml` precedence — they describe
  *who owns content*, while `_AUTHORITY.yaml` describes *which document wins*; they must not
  contradict.
- When bands 10 or 13 are allocated, remove their "reserved" note in §1 in the same PR.
