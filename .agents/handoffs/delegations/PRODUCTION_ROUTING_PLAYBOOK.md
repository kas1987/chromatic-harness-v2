# Production Readiness Routing Playbook

## Objective
Move highest-value analysis/integration work to Claude while keeping mechanical implementation and validation local. This maximizes budget leverage without slowing execution.

## Routing Policy
- Route to Claude:
  - Cross-file design and decomposition
  - Integration planning
  - Blocker analysis and risk reduction
- Keep local:
  - Mechanical UI/view completion
  - Deterministic implementation
  - Test execution, CI checks, and audit runs

## Current Priority Assignment

### Claude lane (delegated)
- chromatic-harness-v2-bpq (P1 epic): `.agents/handoffs/delegations/chromatic-harness-v2-bpq.prompt.md`
- chromatic-harness-v2-bpq.4 (P2 integration): `.agents/handoffs/delegations/chromatic-harness-v2-bpq.4.prompt.md`
- chromatic-harness-v2-sq2 (P2 blocked decomposition): `.agents/handoffs/delegations/chromatic-harness-v2-sq2.prompt.md`

### Local lane (execute immediately)
- chromatic-harness-v2-bpq.1 (P1 frontend required views)
- chromatic-harness-v2-bpq.5 (P2 sandbox promotion ladder E2E)

## Operating Cadence
1. Run `bd ready` and pull top 5 open priorities.
2. Classify each item as analysis-heavy or mechanical.
3. For analysis-heavy items, run:
   - `python scripts/claude_delegate_gate.py --task "<objective>" --bead-id <id> --t-level T2 --privacy-class P1 --invoked-by automation`
4. Copy artifacts into `.agents/handoffs/delegations/<bead>.*`.
5. Execute local-lane items directly and validate with:
   - `python scripts/token_governance_closed_loop.py`
   - `python scripts/daily_harness_audit.py --root . --report --strict`

## Production Readiness Exit Signals
- P1 items complete or in active execution with no blocker drift.
- Governance closed loop status green (pass 4, warn 0, fail 0).
- Strict daily audit pass.
- Delegation artifacts exist for every analysis-heavy top-priority bead.
