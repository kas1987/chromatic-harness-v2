# Autonomous Loop Flags & Budget Guards (OMH-3)

> How autonomous a long-running loop (`/loop`, `/crank`, GO modes) is allowed to be, and the
> two guards that stop it running away. Defines the **flag taxonomy** (scope / risk / budget)
> and pairs it with the existing iteration guard and the new spend guard.

## 1. Autonomy flag taxonomy

Every long-running loop declares these before it starts. Defaults are conservative.

| Flag | Values | Meaning |
|------|--------|---------|
| `scope` | `single-bead` · `epic` · `area` | What the loop may touch. `area` requires explicit opt-in. |
| `max_t_level` | `T1`–`T4` | Highest risk tier the loop may execute autonomously. T4 (force push / hard reset / secrets) is **never** autonomous (see global auto-mode scope). |
| `max_usd` | number | USD spend ceiling for the loop. `0` = inherit session/weekly budget. |
| `max_tokens` | number | Token spend ceiling for the loop. `0` = no token ceiling. |
| `max_iterations` | int | Hard cap on loop turns (backstop even if work remains). |
| `on_breach` | `pause` · `handoff` · `halt` | What to do when a guard trips. Default `pause`. |

These map onto existing governance: T-levels from auto-mode scope, budget from the weekly
`WORKFLOW_BUDGET_CONTRACT.md`, and the continuous-execution rule in `CONTINUOUS_EXECUTION_SOP.md`.

## 2. The two complementary guards

A loop runs away in two independent ways — both are now guarded:

| Vector | Guard | Verdict |
|--------|-------|---------|
| **Iteration** — same task fired N times (cache-read amplification) | `02_RUNTIME/router/loop_guard.py` (`ROUTER_LOOP_WARN`/`_BLOCK`, default 10/25) | ok → warn → block |
| **Spend** — slow cumulative token/USD drip | `scripts/loop_budget_guard.py` (`--max-usd`/`--max-tokens` or `LOOP_BUDGET_MAX_*`) | ok → warn (≥80%) → pause |

Both are **fail-open**: a guard malfunction never strands a loop.

## 3. Using the spend guard

Reads the existing budget ledger (`07_LOGS_AND_AUDIT/budget/ledger.jsonl`).

```bash
# Pause check — exit 3 if over ceiling, else 0. Call between loop iterations.
python scripts/loop_budget_guard.py --check --max-usd 5

# Windowed (only the last 24h of spend), machine-readable:
python scripts/loop_budget_guard.py --window-hours 24 --max-tokens 2000000 --json
```

Wire it into a loop's per-iteration step: if `--check` exits 3, apply `on_breach`
(pause / handoff / halt). With no ceiling set (`0`), `--check` always passes — opt in by
setting `--max-usd`/`--max-tokens` or the `LOOP_BUDGET_MAX_*` env vars.

## 4. Recommended defaults by scope

| scope | max_t_level | suggested ceiling | on_breach |
|-------|-------------|-------------------|-----------|
| single-bead | T3 | tight (e.g. $2) | pause |
| epic | T3 | medium (e.g. $10) | handoff |
| area | T3 (T4 never auto) | explicit, logged | halt |

## 5. Quick rule
**Declare scope + ceilings before a long loop. Check the spend guard each iteration; honor the
iteration guard's block. T4 is never autonomous.** Breach → pause/handoff, never silently continue.
