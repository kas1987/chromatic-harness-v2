# CHROMATIC_TREES.md — Repo Structure & Agent Operating Map

> **This is the #1 source-of-truth for repository structure.** Every agent (Claude,
> Cursor, Codex, Pi, VS Code) reads `.claude/CLAUDE.md` first, then defers to **this
> file** for *where things live* and *which file to use for any operation*.
>
> **Status:** canonical · **Maintained by:** harness agents · **Last reconciled:** 2026-06-02
>
> If this file conflicts with a generated artifact, **this file wins**. If a task would
> change repo structure and this file is missing or stale, **stop and reconcile it first.**

---

## 0. How to use this file (TL;DR for agents)

1. **"Where does X live?"** → §2 Layered Architecture + §3 Directory Tree.
2. **"How do I create an epic / bead / roadmap / PDR / retro?"** → §5 Agent Quick Reference, then §6 recipes.
3. **"Which file is authoritative?"** → §1 Source-of-Truth Hierarchy (or `00_SOURCE_OF_TRUTH/_AUTHORITY.yaml`).
4. **"What is the harness becoming?"** → §7 v3 Direction → `docs/research/CHROMATIC_HARNESS_V3_ROADMAP.md`.

Operational *behavior* (session start/end, gates, git autonomy) lives in
[`AGENT_OPERATIONS.md`](AGENT_OPERATIONS.md). This file is the *map*; that file is the *checklist*.

---

## 1. Source-of-Truth Hierarchy

When two documents disagree, the higher entry wins. Machine-readable form:
[`00_SOURCE_OF_TRUTH/_AUTHORITY.yaml`](00_SOURCE_OF_TRUTH/_AUTHORITY.yaml).

| Rank | Source | Governs |
|-----:|--------|---------|
| 1 | `.claude/CLAUDE.md` + `~/.claude/CLAUDE.md` | Agent operating mandate, autonomy, security tiers |
| 2 | **`CHROMATIC_TREES.md`** (this file) | Repo structure, file locations, operation→file map |
| 3 | `00_SOURCE_OF_TRUTH/CHROMATIC_HARNESS_MANIFEST.md` | Harness identity, canonical components |
| 4 | `01_PROTOCOLS/**` (BEADS, CMP, MAGNETS, MCP, INTAKE) | Interface contracts + JSON schemas |
| 5 | `08_PDRS/**` (project design records) | Per-feature design decisions |
| 6 | `04_PLAYBOOKS/**` | Role/workflow runbooks |
| 7 | Generated registries (`registry/`, `*_registry.json`) | Derived state — never overrides 1–6 |

---

## 2. The Layered Architecture (`00_–12_`)

The numbered scheme is the intended layout. Each directory owns one layer.

| Layer | Directory | Role | Status |
|-------|-----------|------|--------|
| 00 | `00_SOURCE_OF_TRUTH/` | Manifest, glossary, decision log, governance policy, **`_AUTHORITY.yaml`** | CANONICAL |
| 00 | `00_META/` | Repo operating contract, observability meta (`HARNESS_EVENT_SCHEMA.json`) | CANONICAL |
| 01 | `01_PROTOCOLS/` | Interface specs + JSON schemas (BEADS, CMP, MAGNETS, MCP, INTAKE) | CANONICAL |
| 01 | `01_STATE/` | Runtime state snapshots (sprint state, sync registry) | CANONICAL |
| 02 | `02_RUNTIME/` | **Core runtime** — router, magnets, audit, workflows, api, budget (899 files) | CANONICAL ⚠ oversized |
| 03 | `03_AGENTS/` | Agent registry metadata (`.agents/` holds the live flywheel) | SPARSE |
| 04 | `04_PLAYBOOKS/` | Role/workflow runbooks (13 playbooks) | CANONICAL |
| 05 | `05_FRONTEND_CONSOLE/` | React/TS visual console (9,274 files) | CANONICAL (separate deliverable) |
| 05 | `05_REPORTS/` | KPI dashboards, telemetry summaries | CANONICAL |
| 06 | `06_DATA/` | SQLite / data stores (placeholder + DBs) | CANONICAL |
| 07 | `07_LOGS_AND_AUDIT/` | Execution/decision/trace logs, governance intelligence, pre_session manifests | CANONICAL (append-only) |
| 08 | `08_PDRS/` | Project design records + **`_PDR_TEMPLATE.md`** | CANONICAL |
| 09 | `09_DEPLOYMENT/` | Deploy configs, routing policy, CI assets | CANONICAL |
| 10 | `10_RUNTIME/` | *(empty placeholder — real content under `02_RUNTIME/`)* | LEGACY → see §4 |
| 11 | `11_SANDBOX_LAB/` | Experimental harness | CANONICAL |
| 12 | `12_HANDOFFS/` | Session handoffs, compact docs, `SESSION_COMPACT.md` | CANONICAL |

**Cross-cutting (outside the numbered scheme):**

| Directory | Role | Status |
|-----------|------|--------|
| `.agents/` | The flywheel — decisions, learnings, handoffs, governance (3,406 files) | CANONICAL (meta-governance) |
| `.claude/` | Claude hooks, settings, lite workflows | CANONICAL |
| `scripts/` | 398 operational + audit scripts | CANONICAL ⚠ no registry yet |
| `tests/` | 470 pytest files | CANONICAL |
| `src/` | `chromatic_router` library | CANONICAL |
| `docs/` | 174 working docs (research, governance, playbooks, retros) | CANONICAL-PRIMARY |
| `templates/` | Reusable record + planning templates | CANONICAL |
| `config/`, `schemas/` | Routing/MCP config, JSON schemas | CANONICAL |

---

## 3. Annotated Directory Tree (reconciled 2026-06-02)

```
chromatic-harness-v2/
├── CHROMATIC_TREES.md          ← you are here (repo structure SoT)
├── AGENT_OPERATIONS.md         ← operational checklist (session start/during/end)
├── AGENTS.md / CLAUDE.md       ← agent entry instructions
├── README.md
├── 00_SOURCE_OF_TRUTH/         CANONICAL  manifest · glossary · _AUTHORITY.yaml
├── 00_META/                    CANONICAL  operating contract · HARNESS_EVENT_SCHEMA.json
├── 01_PROTOCOLS/               CANONICAL  BEADS · CMP · MAGNETS · MCP · INTAKE (+ schemas)
├── 01_STATE/                   CANONICAL  sprint/sync state snapshots
├── 02_RUNTIME/                 CANONICAL  router · magnets · audit · workflows · api · budget  (899 ⚠)
├── 03_AGENTS/                  SPARSE     agent registry (live data in .agents/)
├── 04_PLAYBOOKS/               CANONICAL  13 role/workflow runbooks
├── 05_FRONTEND_CONSOLE/        CANONICAL  React/TS console (9,274 — separate deliverable)
├── 05_REPORTS/                 CANONICAL  KPI dashboards
├── 06_DATA/                    CANONICAL  data stores
├── 07_LOGS_AND_AUDIT/          CANONICAL  execution · decisions · traces · pre_session  (append-only)
├── 08_PDRS/                    CANONICAL  design records + _PDR_TEMPLATE.md
├── 09_DEPLOYMENT/              CANONICAL  deploy · routing policy · CI assets
├── 10_RUNTIME/                 LEGACY     empty placeholder (retire → §4)
├── 11_SANDBOX_LAB/             CANONICAL  experiments
├── 12_HANDOFFS/                CANONICAL  handoffs · SESSION_COMPACT.md
├── .agents/                    CANONICAL  flywheel: decisions · learnings · handoffs (3,406)
├── .claude/                    CANONICAL  hooks · settings · lite workflows
├── scripts/                    CANONICAL  398 ops/audit scripts (⚠ registry pending — V3-5)
├── tests/                      CANONICAL  470 pytest files
├── src/                        CANONICAL  chromatic_router library
├── docs/                       CANONICAL  174 docs (research · governance · retros)
├── templates/                  CANONICAL  record + planning templates (see §5)
├── config/ · schemas/          CANONICAL  routing/MCP config · JSON schemas
└── ── legacy root dirs (retire in V3-6) ──
    ├── 02_DOCS/                LEGACY → docs/
    ├── agent_handoffs/         LEGACY → 12_HANDOFFS/
    ├── hooks/                  LEGACY → git_hooks/
    ├── state/ · reports/       LEGACY → 01_STATE/ · 05_REPORTS/
    └── queue/ · issues/ · dashboards/  LEGACY (stale)
```

---

## 4. Legacy → Canonical Map (do not write to the left column)

| Legacy / duplicate | Canonical home | Retire in |
|--------------------|----------------|-----------|
| `10_RUNTIME/` (empty) | `02_RUNTIME/` | V3-6 |
| `02_DOCS/` (1 file) | `docs/` | V3-6 |
| `agent_handoffs/` | `12_HANDOFFS/` | V3-6 |
| `hooks/` | `git_hooks/` | V3-6 |
| `state/` | `01_STATE/` | V3-6 |
| `reports/` | `05_REPORTS/` | V3-6 |
| `queue/`, `issues/`, `dashboards/` | `07_LOGS_AND_AUDIT/` or retire | V3-6 |

Until V3-6 lands, treat the left column as read-only legacy and write to the canonical home.

---

## 5. Agent Quick Reference — operation → file

**This is the table the user asked for: any agent, any operation, the exact file.**

| I want to… | Use this | Command / next step |
|------------|----------|---------------------|
| **Create an epic** | [`templates/EPIC_TEMPLATE.md`](templates/EPIC_TEMPLATE.md) | `bd create "<title>" --type epic -p P1 -l <area>` → fill template into `--design` |
| **Create a bead (task)** | [`templates/BEAD_TEMPLATE.md`](templates/BEAD_TEMPLATE.md) | `bd create "<title>" --type task -p P2 --parent <epic-id>` |
| **Write a roadmap** | [`templates/ROADMAP_TEMPLATE.md`](templates/ROADMAP_TEMPLATE.md) | save to `docs/research/<TOPIC>_ROADMAP.md` |
| **Write a PDR (design record)** | [`08_PDRS/_PDR_TEMPLATE.md`](08_PDRS/_PDR_TEMPLATE.md) | save to `08_PDRS/<feature>.md` |
| **Write a retro** | [`templates/RETRO_TEMPLATE.md`](templates/RETRO_TEMPLATE.md) | save to `docs/retros/YYYY-MM-DD-<slug>.md` |
| **Record a learning** | [`templates/LEARNING_RECORD_TEMPLATE.md`](templates/LEARNING_RECORD_TEMPLATE.md) | or `bd remember "<insight>"` |
| **Record a fix pattern** | [`templates/FIX_PATTERN_TEMPLATE.md`](templates/FIX_PATTERN_TEMPLATE.md) | — |
| **Record an incident** | [`templates/INCIDENT_RECORD_TEMPLATE.md`](templates/INCIDENT_RECORD_TEMPLATE.md) | — |
| **Record a collision** | [`templates/COLLISION_RECORD_TEMPLATE.md`](templates/COLLISION_RECORD_TEMPLATE.md) | — |
| **Emit a harness event** | [`templates/EVENT_RECORD_TEMPLATE.json`](templates/EVENT_RECORD_TEMPLATE.json) | schema: `00_META/observability/HARNESS_EVENT_SCHEMA.json` |
| **Build a mission packet** | [`templates/AGENT_MISSION_PACKET_OBSERVABILITY.md`](templates/AGENT_MISSION_PACKET_OBSERVABILITY.md) | — |
| **Start / end a session** | [`AGENT_OPERATIONS.md`](AGENT_OPERATIONS.md) | `bd prime` → `bd ready` |
| **Pick next work** | `bd ready` | never from chat |
| **Understand the directory layout** | this file (§2, §3) | — |
| **Understand execution flow** | [`00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md`](00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md) | — |
| **Find which file is authoritative** | §1 + [`00_SOURCE_OF_TRUTH/_AUTHORITY.yaml`](00_SOURCE_OF_TRUTH/_AUTHORITY.yaml) | — |
| **See all templates** | [`templates/README.md`](templates/README.md) | — |
| **Operate via workflows (lifecycle)** | [`04_PLAYBOOKS/WORKFLOWS_PLAYBOOK.md`](04_PLAYBOOKS/WORKFLOWS_PLAYBOOK.md) | `/audit → /plan → /go → /close-issue` |
| **Audit the harness** | [`.claude/workflows/audit.js`](.claude/workflows/audit.js) | `/audit [slices]` |
| **Plan an epic from a goal** | [`.claude/workflows/plan.js`](.claude/workflows/plan.js) | `/plan <goal\|roadmap>` |
| **Execute / ship one bead** | [`.claude/workflows/go.js`](.claude/workflows/go.js) | `/go` · `/close-issue <id>` |

> **The harness operates as Claude workflows.** The lifecycle (audit → plan → execute →
> ship) is the chain of bounded workflows in `.claude/workflows/`. See the
> [Workflows Playbook](04_PLAYBOOKS/WORKFLOWS_PLAYBOOK.md).

---

## 6. Creating Work — recipes

### Epic
1. Copy [`templates/EPIC_TEMPLATE.md`](templates/EPIC_TEMPLATE.md); fill goal, acceptance, child beads.
2. `bd create "<area>: <title>" --type epic -p P0..P4 -l <area-label> -d "<summary>" --acceptance "<criteria>"`
3. Capture the returned epic id (`--silent` prints only the id).

### Bead (task under an epic)
1. Copy [`templates/BEAD_TEMPLATE.md`](templates/BEAD_TEMPLATE.md).
2. `bd create "<title>" --type task -p P2 --parent <epic-id> -l <area-label> -d "<one-paragraph scope>"`
3. One bead = one artifact + its tests (per the PDR decomposition rule).

### Roadmap
1. Copy [`templates/ROADMAP_TEMPLATE.md`](templates/ROADMAP_TEMPLATE.md) → `docs/research/<TOPIC>_ROADMAP.md`.
2. Decompose into epics; create each epic per above; link bead ids back into the roadmap's Epic Index.

> After creating beads, run `bd dolt commit` then `bd dolt push` (the `.beads/issues.jsonl` export is passive).

---

## 7. v3 Direction

The harness is mid-transition from **v2 (feature-complete prototype)** to
**v3 ("Typed · Enforced · Observable · Consolidated")**. Full plan, audit findings,
success metrics, and the 9-epic / 47-bead program:

- **Roadmap:** [`docs/research/CHROMATIC_HARNESS_V3_ROADMAP.md`](docs/research/CHROMATIC_HARNESS_V3_ROADMAP.md)
- **v2 gaps basis:** [`docs/research/CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md`](docs/research/CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md)
- **Structure reorg epic:** `bd show` the `v3-structure` epic (retires the §4 legacy dirs).

Find the v3 program: `bd list --label v3`.

---

## 8. Maintaining this file

- Update §3/§4 whenever a top-level directory is added, retired, or moved.
- The `v3-structure` epic (V3-6) will retire the §4 legacy dirs — update this file in the same PR.
- Keep §5 in sync with `templates/README.md`; they must agree on every template.
- This file is referenced by the visual-control-plane PDR/playbook/handoff as the repo
  structure SoT — do not rename it without updating those references.
