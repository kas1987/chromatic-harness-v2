# LLM Governance Intelligence Loop

## Purpose

Keep routing matrix and governance policy aligned with real execution behavior and official vendor guidance.

## Inputs

- Runtime telemetry:
  - `docs/workflows/WORKFLOW_RUN_LOG.jsonl`
  - `07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl`
- Internal audit outputs:
  - `07_LOGS_AND_AUDIT/token_governance/latest.json`
  - `.agents/audits/latest_audit.json`
- Official vendor sources (minimum set):
  - OpenAI API docs/changelog and eval guidance
  - VS Code release updates and agent telemetry guidance
  - Cursor official docs and changelog/release notes
  - Anthropic Claude Code docs and release notes
  - Google Gemini API models, changelog, deprecations, and best practices

## Canonical telemetry fields (required)

- `timestamp`
- `task_id`
- `provider`
- `model`
- `task_type`
- `execution_status`
- `confidence_score`
- `cost_usd`
- `latency_ms`

## Operational cadence

### Per session

1. Run unified session guard.
2. Run token governance closed loop.
3. If work is substantial, run governance intelligence report.

### Daily

1. Run strict daily audit.
2. Run governance intelligence report with write mode.
3. Record any routing policy drift findings.

### Weekly

1. Review provider/model outcome trends from latest intelligence report.
2. Compare routing decisions vs. observed success/failure and cost behavior.
3. Propose updates to routing matrix and provider allowlists.

### Biweekly external refresh

1. Review official vendor update pages.
2. Capture changes that impact routing, eval, tools, safety, cost, or deprecations.
3. Open beads for any required policy, config, or test updates.

## Required commands

- `python scripts/llm_governance_intelligence.py --write`
- `python scripts/vendor_guidance_refresh.py --write-latest`
- `python scripts/token_governance_closed_loop.py --enqueue-suggestions --drain-intake`
- `python scripts/daily_harness_audit.py --root . --report --strict`

## Policy update triggers

Update routing matrix and related policies when any of the following occur:

- Canonical field coverage below 60% for `provider`, `model`, or `execution_status`.
- New model/provider becomes default in official vendor guidance.
- Significant provider reliability drift (failures increase week-over-week).
- Cost profile drift exceeds expected thresholds.
- Deprecation or API behavior change from official vendor channels.

## Artifacts

- `07_LOGS_AND_AUDIT/governance_intelligence/latest.json`
- `07_LOGS_AND_AUDIT/governance_intelligence/latest.md`
- `07_LOGS_AND_AUDIT/governance_intelligence/history.jsonl`

## Ownership

- Primary: harness governance maintainer.
- Secondary: routing policy maintainer.
- Escalation: if critical telemetry gaps persist for 2 consecutive weekly reviews.
