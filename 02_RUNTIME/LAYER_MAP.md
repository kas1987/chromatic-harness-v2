# 02_RUNTIME — Layer Map

> **Purpose:** `02_RUNTIME/` is the harness runtime layer. This map groups its
> sub-directories into three coherent architectural sub-areas **without
> relocating them**, because the directory is wired as a `sys.path` root and
> its packages are imported by bare top-level name (see [Import Model](#import-model)).
> Moving directories would break ~110 import sites for no architectural gain.
>
> Bead: `chromatic-harness-v2-8lri.3` (v3-6) · Epic: `8lri` v3 Repo Structure Reorg.

## TL;DR — what's actually here

| Claim | Reality |
|-------|---------|
| "898 files" | On-disk count **inflated by the vendored `roach-pi` submodule** (566 files). |
| Harness-owned | **158 git-tracked files** across 22 subdirs. |
| Decompose by moving | **Not recommended** — `02_RUNTIME` is a `sys.path` entry with bare imports (`import router`, `import magnets`). A physical move requires either mass import rewrites or multiplying `sys.path` roots, which recreates the flat layout one level down. |
| "keep 02_RUNTIME as a layer map" | ✅ This document. Grouping is **documentary**, the physical layout stays flat. |

## Import Model

`02_RUNTIME` is added to `sys.path` as a **path entry** by 20+ scripts
(`sys.path.insert(0, str(REPO / "02_RUNTIME"))`; see `scripts/pre_session_common.py:180`,
`scripts/ci_preflight.py:44`). Its subdirs are therefore imported as **bare,
top-level package names**:

```python
import router          # NOT  import runtime.router
from magnets import …  # NOT  from runtime.magnets import …
```

`ci_preflight.py:36` documents this explicitly: *"sys.path is set to REPO/02_RUNTIME
so these are bare dotted names."* A numeric-prefixed dir (`02_RUNTIME`) is **not
importable as a dotted prefix** — it can only ever be a path entry.

**Consequence:** relocating `magnets/` to `pipelines/magnets/` breaks every
`import magnets` (12 files) unless you (a) rewrite all imports to
`pipelines.magnets`, or (b) add `pipelines/` to `sys.path` too — option (b) just
recreates a flat bare-import root one level down, defeating the purpose. Keep the
layout flat; use this map for the architecture.

## Sub-Area A — Orchestration & Routing

*Decides what runs, where, and in what order.*

| Dir | Files | Role |
|-----|-------|------|
| `router/` | 32 | Model / task routing (largest import surface: 24 importers) |
| `workflows/` | 13 | Workflow definitions & execution |
| `orchestrator/` | 5 | Top-level run orchestration |
| `concurrency/` | 2 | `session_lock`, `github_collision` — concurrency control |
| `scope/` | 2 | `enforcer`, `guard` — scope gating |
| `control_plane/` | 2 | `controller` — control-plane surface |

## Sub-Area B — Interfaces (API + Adapters + Bridges)

*External surfaces: HTTP, WebSocket, MCP, provider adapters, CMP gates.*

| Dir | Files | Role |
|-----|-------|------|
| `api/` | 6 | HTTP API (`main.py`) |
| `console-api/` | 4 (TS) | Console server, websocket-server, mission-store |
| `console_api/` | 3 (Py) | `event_store`, `harness_events` |
| `adapters/` | 4 | Provider adapters |
| `cmp-bridge/` | 4 (TS) | `cmp-executor`, confidence/intent/scope gates |
| `chromatic_mcp/` | 3 | MCP server + handlers |
| `pi/` | 1 (TS) | Pi engine overlay (`overlays/discipline.ts`) |

> ⚠️ `console-api` (TypeScript) and `console_api` (Python) are two impls of one
> concept under confusingly near-identical names. Unify naming — tracked as a
> hygiene bead (see below).

## Sub-Area C — Pipelines & Magnets

*The work/knowledge flow: intake → magnets → budget/audit/activity → knowledge/memory.*

| Dir | Files | Role |
|-----|-------|------|
| `magnets/` | 32 | The 7 canonical magnets (intake/plan/dispatch/execution/validation/decision/closure) |
| `intake/` | 7 | Issue / work intake (22 importers) |
| `budget/` | 5 | Token / cost budget |
| `sandbox-lab/` | 5 (TS) | Promotion scorer, sandbox |
| `activity/` | 4 | Activity logging |
| `audit/` | 3 | Audit trail |
| `knowledge/` | 3 | Knowledge store |
| `memory/` | 3 | Memory store |

## Vendored Engine (NOT a sub-area)

| Dir | Files | Notes |
|-----|-------|-------|
| `runtime-engines/` | 566 | **`roach-pi` git submodule** pinned `v1.35.0` (`e47a1427`). External, vendored — do **not** decompose. Only `manifest.json` + `README.md` are harness-owned here. |

## Hygiene Smells (→ separate small beads, not 8lri.3)

These are cleanup items surfaced during discovery; each is a low-risk standalone
fix, intentionally **out of scope** for the layer-map bead:

1. **7× `PHASE_*_COMPLETION_SUMMARY.md`** loose in the runtime root → move to `05_REPORTS/` or archive (stale phase docs, not runtime code).
2. **`console_api` (Py) vs `console-api` (TS)** confusing dual naming → unify under one convention.
3. **Nested `02_RUNTIME/10_RUNTIME/logs/agentops-events.jsonl`** → gitignore (runtime telemetry, same class of junk gitignored in the wiki).
4. **Loose root TS** — `test-*.ts` (6), `runtime-registry.ts`, `beads-bridge.ts` → a `tests/` / entrypoint subdir.
5. **`.ruff_cache/`** present on disk → confirm gitignored (currently untracked, OK).

## How to extend this map

When adding a new `02_RUNTIME` subdir, append it to the matching sub-area table
above and confirm it's reachable via the `sys.path`-root bare-import model. Do
**not** introduce intermediate directories for the named sub-areas — they are an
architectural grouping, not a filesystem hierarchy.
