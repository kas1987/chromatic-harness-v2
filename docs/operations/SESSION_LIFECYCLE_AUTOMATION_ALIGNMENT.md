# Session Lifecycle ↔ Automation ↔ /ship-idea Alignment

> **Purpose:** Walk every step of the pre-session, active-session, and closeout phases;
> classify each step by *who runs it* (agent vs. non-agent automation); and bind the whole
> lifecycle to the **/ship-idea 11-stage completion contract** so nothing ships half-wired.
>
> **Companion docs:** [AGENT_OPERATIONS.md](../../AGENT_OPERATIONS.md) (canonical checklist),
> [.claude/skills/ship-idea/SKILL.md](../../.claude/skills/ship-idea/SKILL.md) (the 11-stage pipeline),
> [04_PLAYBOOKS/MAGNETS_PLAYBOOK.md](../../04_PLAYBOOKS/MAGNETS_PLAYBOOK.md) (event-driven observers).

---

## 1. Automation primitives (what can run *without* an agent)

These are the four non-agent execution surfaces already in the harness. Anything we mark
"automatable" below must land on one of them — never on "the agent remembers to."

| Primitive | Trigger | Examples already wired |
|-----------|---------|------------------------|
| **Lifecycle hooks** | Claude/Cursor session events | `SessionStart → session_start.py`, `SessionEnd → session_closeout.py`, `PreCompact → bd prime`, `PreToolUse/Agent → 02_RUNTIME/router/gate.py` |
| **Task Scheduler** | Wall-clock (daily 07:55) | `ChromaticSessionBoot → run_session_boot.ps1` |
| **Magnets** | Mission inflection points (event-driven, not polled) | `intent`, `scope`, `execution`, `confidence`, `cost`, `validation`, `security`, `quota`, `closure`, `discipline`, `intake`, `memory` — registered in [`magnets/plugin.py:default_registry`](../../02_RUNTIME/magnets/plugin.py) |
| **Deterministic scripts / MCP** | Called by a hook, scheduler, or magnet | `session_boot_automation.py`, `session_unified_guard.py`, `workflow_git.py`, `harvest_rigs.py`, `harness_health_snapshot.py`, `review-daemon` MCP |

**Rule of thumb (from /ship-idea Stage 8 lean gate):** prefer an **event-driven Magnet at an
inflection point** over a poller, and prefer an **on-demand script behind a hook** over an
always-on agent step.

---

## 2. Pre-session phase

| # | Step | Runs today | Classification | ship-idea tie-in |
|---|------|------------|----------------|------------------|
| 1 | Doc guard | `session_boot_automation.py` | ✅ automated (hook/scheduler) | guards Stage 2 PDR template integrity |
| 2 | MCP context audit | `audit_mcp_context.py` | ✅ automated | Stage 8 lean (boot-tax) |
| 3 | Pre-session manifest | `pre_session_manifest.py --write` | ✅ automated | feeds Stage 1 capture context |
| 4 | Intake validation / drain | `auto_intake.py` | ✅ automated | Stage 1 (no idea lost) |
| 5 | Context-trim audit + rebuild | `context_trim_audit.py` | ✅ automated (red-zone) | Stage 8 lean (inject on-demand) |
| 6 | Unified cross-surface guard | `session_unified_guard.py` | ✅ automated | overall readiness gate |
| 7 | `bd prime` / `bd ready` | **agent runs CLI** | ⚙️ **automatable** — pure CLI, can be a SessionStart sub-step that injects the ready queue | Stage 1/4 work selection |
| 8 | Read handoff (`latest.json`) | injected at SessionStart | ✅ automated (context injection) | continuity into Stage 5 |
| 9 | Learning injection | SessionStart hook | ✅ automated | Stage 11 observe (closes flywheel) |

**Gap A — `bd ready` surfacing.** Step 7 is the only pre-session step still leaning on the
agent. It is a deterministic CLI read; move the *surfacing* into the SessionStart hook
(inject the ready list into context) and leave only the *judgment* (which bead to claim) to
the agent. No new primitive needed — extend `session_start.py`.

---

## 3. Active-session phase

| # | Step | Runs today | Classification | ship-idea tie-in |
|---|------|------------|----------------|------------------|
| 1 | Pick next work at task boundary | agent | 🧠 **agent-required** (judgment) | Stage 5 dispatch routing |
| 2 | Track all tasks in `bd` | agent + CLI | 🧠 agent-driven, CLI-backed | Stage 1/4 |
| 3 | Router/T-level gating | `02_RUNTIME/router/gate.py` (PreToolUse) | ✅ automated (hook) | Stage 5 efficiency doctrine |
| 4 | Continuous-execution discipline | `continuous_execution_check.py` | ✅ automatable (checker exists) | keeps pipeline moving |
| 5 | Magnet observation at inflection points | Magnets | ✅ automated (event-driven) | Stage 11 observe — **already the model** |
| 6 | Compact at 50–65% context | **agent-judged** | ⚙️ **automatable** — context-pressure signal → `PreCompact` hook / a `context_pressure_magnet` | Stage 8 lean (inject on-demand) |

**Gap B — compaction trigger.** Step 6 depends on the agent noticing pressure. The harness
already emits context-trim signals; bind them to an event so compaction fires deterministically
(new Magnet at the "context-pressure" inflection point, mirroring how `quota_magnet` watches
budget). This is the highest-value non-agent win in the active phase.

---

## 4. Closeout phase

`session_closeout.py` (wired to the `SessionEnd` hook) already automates most of this:

| # | Step | Runs today | Classification | ship-idea tie-in |
|---|------|------------|----------------|------------------|
| 1 | Write handoff + transfer packet | `session_closeout.py` | ✅ automated | continuity |
| 2 | EPIC-SWOT continuity chain | `ensure_epic_swot_chain()` (policy-gated) | ✅ automated | seeds next-cycle Stage 1 |
| 3 | Knowledge harvest | `harvest_rigs.py` (auto on threshold) | ✅ automated | Stage 11 observe |
| 4 | Harness health snapshot | `harness_health_snapshot.py` | ✅ automated | readiness |
| 5 | Learning-outcome emission | `_emit_injected_learning_outcomes()` | ✅ automated | flywheel apply-step |
| 6 | Auto-turn post-mortem / checkpoint | threshold-gated | ✅ automated | retro |
| 7 | Quality gates (pytest/ruff) | `--pytest` flag (opt-in) | ⚙️ **automatable** — make default-on when code changed | Stage 6 verify |
| 8 | Git plan → ship (confidence-gated) | `workflow_git.py` | ⚙️ **automatable** — invoke from closeout when conf ≥ 88 | Stage 9 ship |
| 9 | Close session beads | agent | 🧠 agent-required (judgment) | Stage 9 `bd close` |
| 10 | **Ship-completion verification** | **MISSING** | ❌ **gap** — see below | **Stages 8 + 10 (non-skippable)** |

**Gap C — the alignment gap (most important).** `/ship-idea` declares **Stage 8 (lean gate)**
and **Stage 10 (live-wiring + PROVE)** *non-skippable*, but **closeout never checks them.** A
session can hand off "done" beads whose work was merged (Stage 9) yet never wired into the
runtime path or proven live. That is exactly the "implemented-but-not-wired" failure the
PDR template's actuation edge exists to prevent.

### Closing Gap C without an agent

Extend the **`ClosureMagnet`** (it already fires at mission/session completion and emits
`close_mission | replan | handoff`). Today it only reads `validation_passed/failed`. Add a
deterministic **ship-completion check** that, for each bead the session marks done, verifies:

1. **Lean evidence (Stage 8):** a `[S8-LEAN]` log line exists for the bead (boot-tax / poll /
   inject / swappable all `ok` or a justified WARN).
2. **Live evidence (Stage 10):** a `[S10-LIVE] wired=… proof=…` record exists — a registry
   entry (e.g. an addition to `default_registry`), a trace line, or a Magnet event showing the
   code executed — **not** a unit-test assertion.
3. **DoD gate:** the bead satisfies [`08_PDRS/DEFINITION_OF_DONE.md`](../../08_PDRS/DEFINITION_OF_DONE.md).

If any is missing, `ClosureMagnet` returns `recommended_action = "replan"` (not `close_mission`)
and emits the gap as a structured event to `07_LOGS_AND_AUDIT/magnet_events/`. `session_closeout.py`
reads that event and **refuses to mark the bead closed**, instead writing it into the handoff's
`next_session_goals` with the specific missing stage. This makes the ship-idea completion contract
the *exit condition of every session* — enforced by a Magnet + the closeout script, with **zero
extra agent turns**.

---

## 5. Summary scorecard

| Phase | Automated | Automatable (non-agent, identified) | Agent-required |
|-------|-----------|-------------------------------------|----------------|
| Pre-session | 8 / 9 | 1 (Gap A: `bd ready` surfacing) | 0 |
| Active | 4 / 6 | 1 (Gap B: compaction magnet) | 1 (work selection) |
| Closeout | 6 / 10 | 3 (Gaps: pytest-default, git-ship, **Stage 8/10 ship-completion magnet — Gap C**) | 1 (bead-close judgment) |

**Headline:** the lifecycle is ~70% non-agent already. The one structural gap is **Gap C** —
the closeout does not enforce `/ship-idea`'s two non-skippable gates. Closing it via a
`ClosureMagnet` ship-completion check binds every session's exit to the ship-idea completion
contract without adding an agent step.

---

## 6. Recommended backlog (beads)

| Priority | Bead | Primitive | Effort |
|----------|------|-----------|--------|
| **P1** | Gap C — `ClosureMagnet` ship-completion check (Stage 8 + 10 + DoD) wired into `session_closeout` bead-close path | Magnet + script | M |
| P2 | Gap B — `context_pressure_magnet` → deterministic compaction at 50–65% | Magnet | S–M |
| P2 | Gap A — inject `bd ready` queue at SessionStart | hook script | S |
| P3 | Closeout default-on pytest/ruff when code changed; auto `workflow_git.py ship` at conf ≥ 88 | script flags | S |
