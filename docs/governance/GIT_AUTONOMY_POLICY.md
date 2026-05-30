# Git Autonomy Policy (tiered confidence + risk)

> **Applies to:** All harness agents in `chromatic-harness-v2`.  
> **Supersedes:** Generic “only commit/push when the user asks” for work **in this repo** when gates below pass.  
> **Enforcement:** `python scripts/workflow_git.py plan` (dry-run) before any `ship --execute`.

## Principle

Agents have **graded git autonomy**. Higher confidence and lower risk unlock more git steps without a separate human “please commit” message. Below threshold → stop or leave changes staged for human review.

Always prefer the pipeline over ad-hoc `git commit` / `git push`:

```bash
python scripts/workflow_git.py plan --confidence <score> --verifier approve --tests-passed --risk low
python scripts/workflow_git.py ship --execute ...   # only when plan shows allowed steps
```

Use `--from-log` after `workflow_go.py GO VERIFY` to pull score/risk from the workflow run log.

## Tier matrix

| Tier | Confidence | Risk | Autonomous actions |
|------|------------|------|-------------------|
| **0 — Blocked** | &lt; 75 | any critical | No commit. Escalate. |
| **1 — Local commit** | ≥ 75 | not critical | `git commit` via pipeline if verifier approves + staged changes |
| **2 — Push** | ≥ 88 | not high/critical | Tier 1 + `git push` if tests passed |
| **3 — PR** | ≥ 85 | not high/critical | Tier 2 + open/update PR (not on protected branch) |
| **4 — Merge** | ≥ 95 | **low only** | Tier 3 + merge if CI green |

### Risk modifiers

| Risk | Commit | Push | Merge |
|------|--------|------|-------|
| low | ✓ (if conf ≥ 75) | ✓ (if conf ≥ 88) | ✓ (if conf ≥ 95 + CI) |
| medium | ✓ | ✓ | ✗ (human) |
| high | ✓ | ✗ | ✗ |
| critical | ✗ | ✗ | ✗ |

Secrets in changed paths (`.env`, keys, credentials) → **all tiers blocked**.

## Agent workflow (required)

1. **Score** work (`workflow_go`, mission packet, or explicit confidence block in handoff).
2. **Plan** — `workflow_git.py plan` (never skip for autonomous git).
3. **Execute** — `ship --execute` only for steps marked `true` in pipeline JSON.
4. **Log** — append outcome to workflow run log / beads close note.

## When user did not say “commit” or “push”

| Situation | Allowed without extra user prompt |
|-----------|-----------------------------------|
| Bead implementation complete, tests green, conf ≥ 88, risk low | Commit + push via pipeline |
| Session end, harness rules, conf ≥ 88, tests green | Push (commit first if needed) |
| conf 75–87 or risk medium | Commit only; ask or hand off for push |
| conf &lt; 75 or high/critical risk | No git write; update beads + handoff |

## Hard stops (never autonomous)

- `git push --force` to `main` / `master`
- `git reset --hard`, `git clean`, amend after push to remote
- Skipping hooks (`--no-verify`) unless user explicitly requests
- Committing `.env`, credentials, or files flagged by secret scan
- Merge on medium+ risk or confidence &lt; 95

## Related docs

- [docs/workflows/PERMISSION_GATE.md](../workflows/PERMISSION_GATE.md)
- [docs/workflows/GIT_CONFIDENCE_PIPELINE.md](../workflows/GIT_CONFIDENCE_PIPELINE.md)
- [docs/governance/CONFIDENCE_GATE.md](CONFIDENCE_GATE.md)
- Code: `02_RUNTIME/workflows/git_policy.py`, `scripts/workflow_git.py`
