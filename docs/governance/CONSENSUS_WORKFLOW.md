# Multi-Agent Review Consensus Workflow (GH #65)

`scripts/consensus_workflow.py` implements a lightweight multi-role review
consensus protocol for proposed changes. Each reviewer role independently
rates the change; the result is a deterministic `approve / reject / escalate`
verdict written to `.agents/council/latest_consensus.json`.

---

## Reviewer roles and responsibilities

| Role | Responsibility |
|------|---------------|
| `security` | Detects dangerous patterns: secrets, force-push, credential exposure, destructive ops |
| `correctness` | Checks for regressions, broken logic, invalid state |
| `completeness` | Ensures the change is complete — no stubs, missing tests, or TODO markers |

Default roles (when `--roles` is not specified): `security,correctness,completeness`.

Custom roles may be specified with `--roles`. Any string is accepted; unknown
roles fall back to the `completeness` heuristic bucket.

---

## Scoring model

Each role produces one of three votes:

| Vote | Meaning |
|------|---------|
| `approve` | Reviewer is satisfied; no concerns detected |
| `reject` | Reviewer detected a disqualifying signal |
| `abstain` | Reviewer has insufficient signal to vote |

Votes are produced via keyword heuristics over `--subject` and `--diff-summary`.
In a live multi-agent environment, each role would be backed by a dedicated LLM
call with a role-specific prompt; the heuristic here provides deterministic
behaviour for CI and offline use.

---

## Consensus rules (verdict computation)

```
quorum  = approve_count + reject_count   (non-abstaining votes)

if quorum == 0:           verdict = escalate  ("all abstained")
elif approve > reject:    verdict = approve
elif reject  > approve:   verdict = reject
else (tie):               verdict = escalate  ("tie vote")
```

Summary table:

| Condition | Verdict |
|-----------|---------|
| Majority approve | `approve` |
| Majority reject | `reject` |
| Tie (equal approve/reject) | `escalate` |
| All reviewers abstained | `escalate` |

---

## Tie-break and escalation path

When the verdict is `escalate`:

1. The orchestrator receives exit code `2`.
2. The full consensus record is available at `.agents/council/latest_consensus.json`.
3. A human reviewer reads the `scores` and `reason` fields and makes the
   final call.
4. The human decision should be recorded in the PR description or commit
   message with a reference to the escalation timestamp.

For automated pipelines, the escalation may be forwarded to the verifier agent:

```bash
python 02_RUNTIME/orchestrator/verifier_agent.py \
    --mutation-file mutation.json
```

A T4 mutation always triggers escalation regardless of consensus outcome.

---

## Integration with PR workflow

Typical PR gate sequence:

```
1. Policy check (policy_engine.py)
      ↓ allow / ask
2. Consensus review (consensus_workflow.py)
      ↓ approve / reject / escalate
3. If approve → merge
   If reject  → open remediation task
   If escalate → human review required
```

For CI integration, run consensus as a pre-merge check:

```yaml
# Example GitHub Actions step
- name: Consensus review
  run: |
    python scripts/consensus_workflow.py \
      --subject "${{ github.event.pull_request.title }}" \
      --diff-summary "${{ env.DIFF_SUMMARY }}"
  # exit 0 = approve, 1 = reject, 2 = escalate
```

---

## CLI usage

```bash
# Default three-role consensus
python scripts/consensus_workflow.py \
    --subject "Add policy engine" \
    --diff-summary "Adds scripts/policy_engine.py with YAML rule loader and audit log"

# Custom roles
python scripts/consensus_workflow.py \
    --subject "Remove deprecated endpoint" \
    --diff-summary "Deletes src/api/v1/deprecated.py" \
    --roles security,correctness

# Dry-run (no artifact written)
python scripts/consensus_workflow.py \
    --subject "Refactor memory gate" \
    --diff-summary "Refactors 02_RUNTIME/memory/memory_gate.py for clarity" \
    --dry-run
```

### Output format

```json
{
  "verdict": "approve",
  "scores": {
    "security": "approve",
    "correctness": "approve",
    "completeness": "approve"
  },
  "quorum": 3,
  "approve_count": 3,
  "reject_count": 0,
  "abstain_count": 0,
  "subject": "Add policy engine",
  "diff_summary": "Adds scripts/policy_engine.py with YAML rule loader",
  "roles": ["security", "correctness", "completeness"],
  "reason": "Majority approve (3/3 non-abstaining votes).",
  "timestamp": "2026-06-01T00:00:00Z",
  "_artifact_path": ".agents/council/latest_consensus.json"
}
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | `approve` — consensus reached: merge allowed |
| `1` | `reject` — consensus reached: changes required |
| `2` | `escalate` — tie or no quorum: human review required |

---

## Artifact

After each run (unless `--dry-run`) the consensus record is written to:

```
.agents/council/latest_consensus.json
```

This file is overwritten on each run; historical records may be archived
by the orchestrator or CI pipeline if long-term audit trails are required.

---

## Related files

| File | Purpose |
|------|---------|
| `scripts/consensus_workflow.py` | Consensus engine implementation |
| `.agents/council/latest_consensus.json` | Latest consensus artifact |
| `scripts/policy_engine.py` | Policy-as-code engine (upstream gate) |
| `docs/governance/POLICY_ENGINE.md` | Policy engine reference |
| `02_RUNTIME/orchestrator/verifier_agent.py` | T3+ mutation verifier (escalation target) |
