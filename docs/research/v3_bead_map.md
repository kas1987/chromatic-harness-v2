# v3 Bead Map

Generated from `bd list --label v3`. Companion to [CHROMATIC_HARNESS_V3_ROADMAP.md](./CHROMATIC_HARNESS_V3_ROADMAP.md).
Live program: `bd list --label v3` · one epic + children: `bd show <epic-id>`.

**9 epics · 47 beads.** Child id `<epic>.N` encodes its parent epic. Priorities P0 (highest) - P4.

## `8lri` — v3: Repo Structure Clean-Architecture Reorg  _(P0)_

- `8lri.1` · P0 · v3-6: Author REPO_LAYERS.md canonical layout
- `8lri.2` · P1 · v3-6: Retire duplicate/legacy root dirs
- `8lri.3` · P2 · v3-6: Decompose 02_RUNTIME monolith (898 files)
- `8lri.4` · P2 · v3-6: Formalize .agents/ governance tier
- `8lri.5` · P2 · v3-6: Canonicalize git_hooks (retire hooks/ duality)

## `u8uj` — v3: Typed Runtime Core & Contract Boundaries  _(P0)_

- `u8uj.1` · P0 · v3-1: Define RoutingContext sealed contract + pure-function stages
- `u8uj.2` · P0 · v3-1: Extract gate.py (609 LOC) into middleware pipeline
- `u8uj.3` · P1 · v3-1: Adapter factory + adapters.yaml registry + AdapterError
- `u8uj.4` · P1 · v3-1: Split Router vs Orchestrator concerns
- `u8uj.5` · P2 · v3-1: Decompose memory_gate.py + control_plane/controller.py
- `u8uj.6` · P1 · v3-1: mypy --strict CI gate for runtime core

## `w0wk` — v3: Schema-as-Contract Governance  _(P0)_

- `w0wk.1` · P0 · v3-3: Schema registry + CI validation gate
- `w0wk.2` · P1 · v3-3: Unify HARNESS_EVENT + magnet_event + bead schemas
- `w0wk.3` · P1 · v3-3: Canon liveness CI check
- `w0wk.4` · P2 · v3-3: CMP->MCP policy coupling (mission validator)
- `w0wk.5` · P1 · v3-3: _AUTHORITY.yaml precedence declaration
- `w0wk.6` · P2 · v3-3: Runtime schema validation at API + intake ingest

## `4kt5` — v3: Quality Gates v3 - Enforce, Measure, Stay Green  _(P1)_

- `4kt5.1` · P1 · v3-7: Wire coverage_gate to pytest-cov artifact
- `4kt5.2` · P2 · v3-7: Wire arch_compliance_gate to a real baseline
- `4kt5.3` · P1 · v3-7: Auto-rebuild pre_session manifest
- `4kt5.4` · P2 · v3-7: Promote advisory gates to blocking
- `4kt5.5` · P2 · v3-7: Flakiness budget + retry policy
- `4kt5.6` · P1 · v3-7: Land run-all-e2e.py SUITES into main CI

## `nirb` — v3: Magnets Layer Completion (active observers)  _(P1)_

- `nirb.1` · P1 · v3-2: Implement CostMagnet (replace 4-line stub)
- `nirb.2` · P2 · v3-2: Implement ExecutionMagnet + IntentMagnet
- `nirb.3` · P2 · v3-2: Implement SecurityMagnet + DisciplineMagnet
- `nirb.4` · P2 · v3-2: Wire Intake & Closure magnets (pipeline bookends)
- `nirb.5` · P1 · v3-2: Real correlate/score/recommend in magnet_orchestrator

## `sgfr` — v3: Observability v3 - OTel Export, Cost Rollup, Sampling  _(P1)_

- `sgfr.1` · P1 · v3-4: OTLP exporter bridge (traces -> collector)
- `sgfr.2` · P1 · v3-4: Mission-level cost rollup pipeline
- `sgfr.3` · P2 · v3-4: Cost-as-correctness gate
- `sgfr.4` · P1 · v3-4: Trace sampling config + log rotation
- `sgfr.5` · P2 · v3-4: Decision-log idempotency + activity join key

## `dp7b` — v3: Confidence Gate v2, Self-Heal & Autonomy Levels  _(P2)_

- `dp7b.1` · P2 · v3-8: Confidence Gate v2 (formalize scoring/bands/risk override)
- `dp7b.2` · P2 · v3-8: Self-heal loop (retry/decompose before replan)
- `dp7b.3` · P3 · v3-8: Autonomy Levels L0-L5 implementation + enforcement
- `dp7b.4` · P2 · v3-8: Complete Agent Lead synthesis/decision layer
- `dp7b.5` · P3 · v3-8: Wire playbook-evolution proposals into gate tuning

## `mrn7` — v3: Automation Consolidation & Hook Slimming  _(P2)_

- `mrn7.1` · P2 · v3-5: scripts/REGISTRY.yaml manifest + dead-code detector
- `mrn7.2` · P2 · v3-5: Consolidate validators into scripts/schema/validator.py
- `mrn7.3` · P2 · v3-5: Unify collision detection (retire 4 of 5 scripts)
- `mrn7.4` · P2 · v3-5: Split session_closeout.py (2004 LOC) into 3 modules
- `mrn7.5` · P1 · v3-5: Move PreToolUse hooks off the synchronous path
- `mrn7.6` · P3 · v3-5: Merge audit suite + deprecate orphan propose_learnings.py

## `ms4r` — v3: MCP Tool & Context Layer + Token Hygiene  _(P3)_

- `ms4r.1` · P3 · v3-9: MCP token-budget enforcement + lazy loading
- `ms4r.2` · P3 · v3-9: Context layer manifest schema + validation
- `ms4r.3` · P3 · v3-9: Curated MCP ecosystem wiring (budget-gated)


