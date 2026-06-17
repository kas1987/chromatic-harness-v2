# PDR: Auditor Command Prompt

| Field | Value |
|---|---|
| PDR ID | CHCC-PROMPT-002 |
| Mode | Auditor |
| Purpose | Evidence review, drift detection, deterministic reporting |
| Default Autonomy | L0-L2 |

## 1. Executive Summary

The Auditor Command Prompt inspects the harness, repo, workflows, traces, Beads, Magnets, and agent outputs. It is optimized for evidence quality, traceability, contradictions, risk classification, and remediation queues.

## 2. Best For

- repo audits
- PR reviews
- incident reviews
- drift checks
- confidence scoring validation
- Magnets report synthesis
- evidence bundles
- final report generation

## 3. Required Inputs

| Input | Required | Source |
|---|---:|---|
| Audit target | Yes | User / Bead / Incident |
| Evidence sources | Yes | Repo / events / logs |
| Scoring rubric | Yes | Playbook / CMP |
| Risk taxonomy | Recommended | Security / governance docs |
| Output destination | Conditional | PDR / report / Bead |

## 4. Output Shape

```markdown
# Audit: [Target]

## Executive Summary
[score, top risk, best next action]

## Scope
[reviewed / not reviewed]

## Evidence Quality
[direct, partial, inferred, missing]

## Findings
| Rank | Finding | Evidence | Risk | Fix |

## Scorecard
| Domain | Score | % | Status |

## Remediation Queue
| Priority | Fix | Owner | Acceptance Test |

## Best Next Action
[one action]
```

## 5. UI Behavior

Primary panels:

- Evidence Viewer
- Risk Register
- Scorecard
- Magnet Reports
- Reviewer Consensus
- Remediation Queue
- Audit Log

Primary buttons:

- Run Audit
- Compare Evidence
- Create Beads
- Export Report
- Request Independent Review
- Mark Finding Resolved

## 6. Prompt Template

```text
You are the Auditor layer for Chromatic Harness.

Goal: inspect the target system and produce evidence-grounded findings.

Rules:
- Separate observed evidence from inference.
- Do not claim files exist unless verified.
- Score each domain from 0-5.
- Identify contradictions and drift.
- Convert findings into Beads.
- Do not mutate repo state unless explicitly promoted by CMP.
- End with one best next action.

Return: executive summary, scope, evidence quality, findings, scorecard, risks, remediation queue, next action.
```

## 7. Acceptance Criteria

- [ ] Every major claim has evidence or is marked as inferred/missing.
- [ ] Produces absolute score and percentage.
- [ ] Lists risks and remediation.
- [ ] Does not execute implementation work by default.
