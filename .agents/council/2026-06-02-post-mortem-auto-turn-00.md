# Post-mortem: Auto-turn mid-session branch churn (2026-06-02)

**Severity:** Medium — no data loss, recoverable CI failures, no deployment impact  
**Status:** Resolved

## What happened

During the 2026-06-02 session, two branches appeared with CI failures that required manual triage:

- `auto/chromatic-harness-v2-u8uj.1` (PR #228): `RoutingContext` sealed contract router work; `isinstance` tests failed due to a relative import in `context_detector.py` loaded via `spec_from_file_location`.
- `feat/u8uj-4-router-orchestrator-split` (PR #234): budget-fix commits plus an orchestrator-split refactor; mypy 2.1.0 rejected a forward-reference annotation on a dynamically-loaded type (`MissionPacket`).

Both branches were auto-created and pushed by the auto-turn/crank mechanism working on bead `u8uj` tasks.

## Root cause

The **97× budget inflation bug** in `tools/portfolio_token_telemetry.py` caused `bridge_today_to_daily()` to re-append the full `today.json` snapshot on every governance-loop run with no dedup. The budget system reported `$11,492 spent` against a `$400 monthly cap`, when actual spend was ~$112.

This triggered repeated `halt_human` / `policy_budget_decision: halt_human` decisions in the auto-turn observer, cutting sessions short mid-flight. Branches were pushed with code the auto-turn session hadn't finished validating.

## Contributing factors

1. **mypy 2.1.0 stricter valid-type check**: Auto-mode wrote `mission: "MissionPacket"` as a string forward-reference, but `MissionPacket = _orch_mod.MissionPacket` is `Any` (dynamic load). This is now a hard error in mypy 2.1.0 (`valid-type` rule).

2. **Relative import in `spec_from_file_location` context**: Auto-mode wrote `from .contracts import RoutingContext` in `context_detector.py`. When loaded via `importlib.util.spec_from_file_location`, relative imports resolve to a different module object than `from router.contracts import RoutingContext` in tests, breaking `isinstance` checks.

3. **No CI-gate before auto-mode push**: The auto-turn mechanism pushed branches regardless of local type-check state.

## Fixes shipped

| Issue | Fix | PR |
|---|---|---|
| 97× budget inflation | Dedup `bridge_today_to_daily()` via `decision_id`; add `reset_budget_daily_from_ledger.py` rebuild tool | #234 |
| `isinstance` failure | `context_detector.py`: relative → absolute import | #228 |
| mypy `valid-type` error | Remove dead `_route_for_mission()` function | #234 |

## Guardrails to add

1. **Pre-push mypy check in auto-turn sessions**: Auto-mode should run `mypy 02_RUNTIME/router/ 02_RUNTIME/api/` locally before pushing a branch. Failure → stash changes and emit `bd update <id> --status blocked --note "mypy"` instead of pushing.

2. **Budget sanity gate**: Before `halt_human`, check if `ledger.jsonl` daily total > 10× prior-day average — if so, suspect inflation and log a warning rather than halting. The `reset_budget_daily_from_ledger.py` tool can rebuild state from source of truth.

3. **Auto-mode branch naming convention**: Branches auto-created during a human session should carry a `auto/<session-id>-` prefix so they're easily identified as background work needing review.

## Prevention for future sessions

- Do not run `/crank` or `GO SWARM` when a human session is already active on the same repo.
- Check `gh pr list` for open auto-mode PRs with CI failures before starting new work.
- If budget telemetry shows spend > 5× expected, run `python scripts/reset_budget_daily_from_ledger.py` before trusting budget gates.
