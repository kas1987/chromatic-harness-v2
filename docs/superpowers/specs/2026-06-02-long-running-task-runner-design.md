# Long-Running Next-Task Runner — Design Spec

> **Status:** approved-architecture (2026-06-02). Single-supervisor, full end-to-end
> (auto-merge) execution, confidence-gated, guard-bounded, resumable.
> **Owner:** harness runtime. **Base branch:** `session/chromatic-harness-v2-initial`.

## 1. Goal

A long-running agent that **autonomously takes on the next ready task**, end to end, with an
explicit **confidence score** gating every action. One supervisor, one task at a time. It runs
until the ready queue is empty, a budget/iteration guard trips, or a kill-switch is set.

"Take on" means the full lifecycle: select → score → claim → implement (worker) → test →
PR → watch CI → squash-merge → close bead → record outcome → next.

## 2. This is integration, not a new engine

Every hard part already exists and is tested. The runner is **thin orchestration glue** over:

| Concern | Reused component | Notes |
|---|---|---|
| Next-task selection | `scripts/go_mode.py` selection (ready > planned, P0>…>P4, dep-aware, non-epic) | factored into a shared selector |
| **Confidence score + decide + dispatch** | `scripts/claude_delegate_gate.py` | scores 7-factor confidence, gates T-level/destructive/pre-swarm, spawns worker with `--spawn-claude-cli` |
| Confidence math | `02_RUNTIME/workflows/confidence.py` (`score_task`, `mutation_allowed`) → `orchestrator/confidence_engine.py` | one model, not re-implemented |
| Claim safety / liveness | `scripts/lease_manager.py` + `scripts/lease_heartbeat.py` | acquire on claim, heartbeat each poll, release on done |
| Implement → test → PR → merge | `scripts/workflow_git.py ship` → `run_git_pipeline(...)` | confidence+verifier+tests+collision-gated commit/push/open_pr/merge |
| Spend guard | `scripts/loop_budget_guard.py --check` (exit 3 over ceiling) | per-iteration |
| Iteration guard | `02_RUNTIME/router/loop_guard.py` (warn/block) | per-iteration |
| Autonomy flag taxonomy | `docs/governance/AUTONOMOUS_LOOP_FLAGS.md` | scope / max_t_level / max_usd / max_tokens / max_iterations / on_breach |
| **Post-hoc agent scorecards** | `scripts/agent_scoring.py` | runner emits one event per task; closes the confidence feedback loop |

**Net new code:** the supervisor loop, the per-iteration state machine, resumable state, the
kill-switch, and the wiring that records each task's outcome+confidence back into `agent_scoring`.

## 3. Non-goals (YAGNI)

- **No parallel fleet** in v1 (single supervisor; leasing is still recorded so a fleet is a later, additive change).
- **No new confidence formula** — reuse the 7-factor gate verbatim.
- **No T4 autonomy** — force-push, hard-reset, secrets, firewall stay blocked (delegate gate's destructive guard + `max_t_level ≤ T3` assertion).
- **No bespoke git** — all mutation goes through `workflow_git.py` / `gh`.
- **No daemon/service install** — it's a foreground CLI loop you start; OS-level scheduling is out of scope (the existing `scheduled-tasks` MCP can wrap it later if wanted).

## 4. Architecture

A single Python supervisor: `02_RUNTIME/orchestrator/task_runner.py` (pure-ish, testable core) +
thin CLI `scripts/task_runner.py`. Per-iteration state machine:

```
Observe → Select → Score/Decide (gate) → Claim+Lease → Dispatch(worker) → Await+CI → Integrate(merge/close) → Record → Guard
```

Per `run_once()`:

1. **Guard** — `loop_budget_guard --check` and the iteration guard. On breach → apply `on_breach` (pause/handoff/halt) and return `BREACH`. Guards are **fail-open** (a guard *error* never strands; a guard *breach* stops).
2. **Kill-switch** — if `07_LOGS_AND_AUDIT/task_runner/STOP` exists or `TASK_RUNNER_STOP=1` → return `HALT` cleanly.
3. **Select** — `bd ready --json`; exclude epics/blocked/excluded states; apply the `scope` filter (`epic` → only children of `--epic <id>`; `area`/no epic → whole ready queue, logged as broad-scope opt-in); top by (ready>planned, P0>…>P4, id). None → `IDLE` (queue drained → stop loop).
4. **Score + Decide + Dispatch** — call `claude_delegate_gate.py --task <title+body> --bead-id <id> --t-level <T> --spawn-claude-cli`. The gate scores confidence and only spawns the worker when `decision == execute` (≥75, or ≥60 reversible+low-risk). If `plan_only`/`halt`: record the skip with its confidence, **do not claim**, return `SKIPPED`.
5. **Claim + Lease** — `bd update <id> --claim`; `lease_manager.acquire(bead_id, file_scope)`. (Claim happens only once the gate says execute.)
6. **Await + CI** — poll `gh pr checks` for the worker's PR until green/fail/timeout; `lease_heartbeat beat` each poll so the lease never reaps a live task.
7. **Integrate** — if CI green **and** band == execute **and** no conflicts: `workflow_git.py ship --execute --confidence <score> --verifier approve --tests-passed --bead-id <id>` (commit/push already done by worker; this drives squash-merge), then `bd close <id>` + `gh issue close`. On CI failure or low confidence → apply `on_breach` and record `failed`.
8. **Record** — append an `agent_scoring` event `{agent, outcome: completed|failed|abandoned, confidence: score/100, false_positive}`; release lease; append run log; write `07_LOGS_AND_AUDIT/task_runner/latest.json`.

`run_loop(max_iterations)` repeats `run_once()` until `HALT`, `IDLE`, a halting `BREACH`, or the cap.
State is persisted after every step so the loop is **resumable** across restarts.

## 5. Confidence model (two layers, one loop)

- **Pre-execution gate** (per task, before claiming): the 7-factor `score_task` confidence, surfaced via the delegate gate. Decides *whether to take the task* and which band (execute / reversible-only / plan-only / halt). Factors are derived from bead metadata (acceptance criteria, description, linked spec, risk/T-level) using the delegate gate's existing `_score_for_delegate` mapping — so there is exactly one confidence model.
- **Post-execution scorecard** (per task, after outcome): the runner emits one `agent_scoring` event. Over time this builds per-agent `completion_rate`, `avg_confidence`, `false_positive_rate`, and a 0–100 performance score with trend — feeding back into routing/throttling decisions.

`agent_scoring` expects `confidence ∈ [0,1]`; the gate's score is 0–100 → the runner normalizes (`score/100`) when emitting events.

## 6. Safety invariants

- **T4 never autonomous.** Runner asserts `max_t_level ≤ T3`; the delegate gate's destructive-pattern guard blocks force-push/hard-reset/`rm -rf`/secrets regardless.
- **Never push to a protected branch.** Worker commits to its own feature branch; integration only squash-merges the runner's *own* PR for the *claimed* bead. Never merges others' PRs.
- **Guarded every iteration.** Budget + iteration guards run before any work; breach → `on_breach`.
- **Bounded.** `max_iterations` hard cap is a backstop even if work remains.
- **Kill-switch.** STOP file / env halts cleanly between iterations.
- **Fail-open.** Any helper exception is caught; the loop records and degrades to `pause`/`handoff` rather than crashing or looping hot.
- **JSON safety.** All reads of `bd`/gate/handoff JSON wrapped in try/except (files may be partially written — per repo rule).

Default flags (overridable): `scope=epic`, `max_t_level=T3`, `max_iterations=25`,
`max_usd=10`, `on_breach=pause`, dispatch threshold = existing band (≥75 / ≥60 reversible).

## 7. Error handling

- Worker spawn fails / `claude` CLI missing → record `abandoned`, release lease, `on_breach`.
- CI red → record `failed` (not merged), leave PR open for human, `on_breach`.
- Lease acquire fails (already leased / collision) → skip task, try next.
- `bd`/`gh` non-zero → captured via `run_safe`, surfaced in `latest.json`, never crashes loop.

## 8. Observability / artifacts

- `07_LOGS_AND_AUDIT/task_runner/latest.json` — last iteration result (selected bead, confidence, band, decision, outcome, guard verdicts).
- `07_LOGS_AND_AUDIT/task_runner/history.jsonl` — one line per iteration.
- `07_LOGS_AND_AUDIT/task_runner/state.json` — resume state (in-flight bead, phase, iteration count).
- `STOP` sentinel file in the same dir = kill-switch.
- Feeds `append_run_log` (workflow run log) and `agent_scoring` history.

## 9. Testing

Unit tests (`tests/test_task_runner.py`) with **injected fakes** (fake `bd`, fake delegate gate,
fake git/CI, fake clock) — no network, no real `claude`/`gh`:

- selection ordering (ready>planned, P0>…, dep-aware, epics excluded, empty → IDLE);
- gate `plan_only`/`halt` → SKIPPED, no claim;
- gate `execute` → claim+lease+dispatch path;
- CI green → merge+close+`completed` event with normalized confidence;
- CI red → `failed`, no merge, `on_breach` applied;
- budget breach / iteration breach → BREACH + `on_breach`;
- kill-switch (STOP file + env) → HALT;
- resume: restart mid-flight reattaches the in-flight bead;
- fail-open: helper raising never crashes `run_once`.

**Suite registration (required):** add the runner's e2e suite to `tests/run-all-e2e.py` `SUITES`
— the pre-push gate only runs listed suites, so an unregistered test won't block regressions.

`ruff check` clean; targeted `pytest tests/test_task_runner.py` green before commit.

## 10. Rollout

1. Land core + CLI + tests behind conservative defaults (`on_breach=pause`, `max_iterations` small).
2. Dry-run mode (`--once --no-execute`) prints the decision packet without claiming/merging — validate selection + confidence on the live queue first.
3. Flip to `--loop` once a few single-task dry-runs look right.
4. Fleet/parallel workers = a later additive PR (leasing is already recorded).

## 11. Open risks

- Worker quality: a low-quality worker can open a green-CI PR that's still wrong. Mitigation: confidence gate + `agent_scoring` false-positive tracking + (future) review-daemon in the integrate step.
- Auto-merge blast radius: bounded by single-supervisor, own-PR-only merge, `max_iterations`, and `on_breach`. The kill-switch is the human override.
- Budget forecast noise (boot showed an over-budget forecast): the spend guard reads the real ledger; if the ledger is miscalibrated the guard may over-pause. Acceptable (fail-safe direction).
