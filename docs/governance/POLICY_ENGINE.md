# Policy Engine — Reference (GH #64)

`scripts/policy_engine.py` is the policy-as-code governance engine for Chromatic
Harness v2. It loads declarative allow/deny/ask rules from
`00_SOURCE_OF_TRUTH/governance_policy.yaml` and evaluates an
**action + resource + tier** triple against those rules.

---

## Policy YAML schema

File: `00_SOURCE_OF_TRUTH/governance_policy.yaml`

```yaml
policy_version: "1.0"
description: "Human-readable description"

rules:
  - id: unique-rule-id           # required; must be unique across all rules
    action: "write"              # glob or comma-list: write, read, delete, execute, push, *
    resource: "scripts/**"       # glob or comma-list matching file/path
    tier: "T2"                   # T1 | T2 | T3 | T4 | * | comma-list e.g. "T1,T2"
    effect: allow                # allow | deny | ask
    conditions:                  # optional extra conditions (all must match)
      risk_level: ["low", "medium"]
    rationale: "Human-readable reason shown in output"
```

### Rule fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique rule identifier (snake_case recommended) |
| `action` | Yes | Action glob: `*`, `write`, `read`, `delete`, `execute`, `push`, `push_force`, `deploy`, `merge`, etc. Comma-list for multiple. |
| `resource` | Yes | File/path glob. Supports `**` wildcards and comma-lists. |
| `tier` | Yes | Tier spec: `T1`, `T2`, `T3`, `T4`, `*`, or comma-list. |
| `effect` | Yes | `allow`, `deny`, or `ask`. |
| `conditions` | No | Dict of extra conditions. `risk_level` may be a string or list of strings. |
| `rationale` | No | Human explanation shown in engine output. |

### Evaluation order

Rules are evaluated **top-to-bottom; first match wins**. This means:

1. Hard denials (secrets, force-push) are placed at the top.
2. T4 ask/deny rules follow.
3. T3 ask/allow rules.
4. T2 and T1 allow rules.
5. Catch-all fallbacks at the bottom.

When no rule matches, the engine returns `effect: ask` (conservative default).

---

## CLI usage

```bash
# Evaluate a write action on scripts/ at tier T3
python scripts/policy_engine.py --action write --resource scripts/ --tier T3

# Evaluate a delete on a secret file
python scripts/policy_engine.py --action delete --resource secrets/vault.key --tier T2

# With optional conditions
python scripts/policy_engine.py --action write --resource "**" --tier T3 --risk-level high

# Force-push (should deny)
python scripts/policy_engine.py --action push_force --resource refs/heads/main --tier T4

# Dry-run (no audit log write)
python scripts/policy_engine.py --action read --resource docs/ --tier T1 --dry-run

# Use a custom policy file
python scripts/policy_engine.py --action write --resource src/ --tier T2 \
    --policy-file path/to/custom_policy.yaml
```

### Output format

```json
{
  "effect": "allow",
  "matched_rule": "allow-t2-scripts",
  "action": "write",
  "resource": "scripts/",
  "tier": "T2",
  "timestamp": "2026-06-01T00:00:00Z",
  "rationale": "Utility scripts are T2 always-allow.",
  "audit_ref": "07_LOGS_AND_AUDIT/policy_engine.jsonl:42"
}
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | `allow` — action is permitted |
| `1` | `deny` — action is forbidden |
| `2` | `ask` — action requires human confirmation |

---

## Audit log

Every invocation (unless `--dry-run`) appends a JSON line to:

```
07_LOGS_AND_AUDIT/policy_engine.jsonl
```

Each line contains: `effect`, `matched_rule`, `action`, `resource`, `tier`,
`timestamp`, `rationale`, and `audit_ref` (sequential line number).

---

## Override workflow

When the engine returns `effect: ask` or `deny` and a human decides to proceed:

1. Record the override reason in the commit message or PR body.
2. Re-invoke the relevant workflow with an explicit approval token or via the
   `verifier_agent.py` T4 escalation path.
3. The override is audited in `07_LOGS_AND_AUDIT/verifier/` via
   `02_RUNTIME/orchestrator/verifier_agent.py`.

For programmatic overrides, combine with the verifier agent:

```bash
python 02_RUNTIME/orchestrator/verifier_agent.py \
    --mutation-file mutation.json \
    --dry-run
```

A T4 verdict from the verifier always escalates to human review regardless of
the policy engine output.

---

## Adding or modifying rules

1. Edit `00_SOURCE_OF_TRUTH/governance_policy.yaml`.
2. Verify the desired behaviour with `--dry-run`:
   ```bash
   python scripts/policy_engine.py --action <action> --resource <resource> \
       --tier <tier> --dry-run
   ```
3. Commit the YAML change with a rationale comment.
4. The engine picks up the new rules on the next invocation (no restart needed).

---

## Related files

| File | Purpose |
|------|---------|
| `00_SOURCE_OF_TRUTH/governance_policy.yaml` | Declarative rule source |
| `scripts/policy_engine.py` | Engine implementation |
| `07_LOGS_AND_AUDIT/policy_engine.jsonl` | Audit log (append-only) |
| `02_RUNTIME/orchestrator/verifier_agent.py` | T3+ mutation verifier |
| `scripts/consensus_workflow.py` | Multi-agent review consensus |
| `docs/governance/CONSENSUS_WORKFLOW.md` | Consensus workflow reference |
