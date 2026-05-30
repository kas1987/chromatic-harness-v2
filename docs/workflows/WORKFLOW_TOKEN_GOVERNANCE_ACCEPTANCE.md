# Acceptance Checklist: Claude Workflow Token Governance

## Governance Docs

- [ ] `00_WORKFLOW_GOVERNANCE.md` exists.
- [ ] `WORKFLOW_BUDGET_CONTRACT.md` exists.
- [ ] `HANDOFF_PACKET_SCHEMA.md` exists.
- [ ] `COST_INCIDENT_TEMPLATE.md` exists.

## Workflow Code

- [ ] Every workflow has a budget header.
- [ ] Every `agent()` call has a cost gate.
- [ ] Every phase has a max output cap.
- [ ] No workflow passes raw full prior output into later phases.
- [ ] Workflows pass compressed handoff packets.

## Transcript Safety

- [ ] Normal workflows forbid `~/.claude/projects/**/*.jsonl` access.
- [ ] Audit-lite uses summary indexes or max 3 sampled files.
- [ ] Audit-deep requires explicit approval.
- [ ] No workflow runs broad transcript mining by default.

## Cost Safety

- [ ] Tool call caps exist.
- [ ] File read caps exist.
- [ ] Estimated token caps exist.
- [ ] Stop conditions are visible.
- [ ] Cost incident template can capture future events.

## Final Review

- [ ] Human operator can identify the budget class of each workflow.
- [ ] Auditor can verify whether a workflow exceeded scope.
- [ ] Future `ship` runs are bounded by policy and code guardrails.
