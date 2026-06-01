# AI Review Gate — Risk-Scoring Governance Layer (GH #59)

## Overview

The AI review gate provides heuristic diff analysis and risk scoring as part of the
governance pipeline. It is implemented in `scripts/ai_review_gate.py` and orchestrated
by `scripts/governance_review.py`.

**Network-free:** all analysis is deterministic heuristics over the git diff — no live
LLM calls are made.

## Acceptance Criteria Status

| Requirement | Status | Detail |
|------------|--------|--------|
| AI review generates findings and recommendations | DONE | `generate_findings()` produces typed findings with rule, severity, message, recommendation |
| Risk score calculated per change set | DONE | `risk_score()` returns 0-100 composite score from size + finding severities |
| Large PR detection and warning thresholds | DONE | Configurable `WARN_FILES` (30) and `FAIL_FILES` (100) thresholds; env-overridable |
| Governance report attached to PR workflow | DONE | `write_report()` writes Markdown report to `07_LOGS_AND_AUDIT/ai_review/report.md` + JSON artifact |
| Human override path logged | DONE | `apply_override()` flips fail→override-allow; appends auditable record to `overrides.jsonl` |

All five acceptance criteria from GH #59 are met by `scripts/ai_review_gate.py`.
`scripts/ai_review_gate.py` is **not** a wrapper — it is the full implementation.
`scripts/governance_review.py` chains it into the larger governance pipeline.

## How It Works

### 1. Diff Metrics Collection

`collect_diff_metrics(base)` runs `git diff --numstat` against the merge base and
returns:

- `changed_files` — number of changed files
- `added_lines` / `deleted_lines` / `total_lines`
- `todo_hits` — `+` lines containing TODO/FIXME/HACK/XXX
- `new_scripts` — new `scripts/*.py` files
- `test_files_changed` — changed test files

### 2. Heuristic Findings

`generate_findings(diff_metrics)` applies six deterministic rules:

| Rule | Severity | Trigger |
|------|----------|---------|
| `large-pr-critical` | critical | changed_files >= 100 (FAIL_FILES) |
| `large-pr-warn` | warn | changed_files >= 30 (WARN_FILES) |
| `large-file-churn` | warn | single file >= 500 lines changed |
| `high-deletion-ratio` | warn | deletions > 70% of total churn |
| `todo-fixme-added` | warn | TODO/FIXME/HACK/XXX added in diff |
| `missing-tests` | error | new scripts/ files with no matching test |
| `additions-absent` | error | deletions > 0, additions == 0 |

### 3. Risk Score (0–100)

```
risk_score = min(40, size_component) + min(60, finding_component)

size_component  = (changed_files / FAIL_FILES * 20) + (total_lines / 3000 * 20)
finding_component = sum(severity_weights)
  info=1, warn=5, error=15, critical=30
```

### 4. Level Classification

| Level | Condition |
|-------|-----------|
| `fail` | changed_files >= 100 OR score >= 70 |
| `warn` | changed_files >= 30 OR score >= 40 |
| `ok` | otherwise |

### 5. Artifacts

- `07_LOGS_AND_AUDIT/ai_review/report.md` — Markdown report
- `07_LOGS_AND_AUDIT/ai_review/latest.json` — machine-readable latest result
- `07_LOGS_AND_AUDIT/ai_review/<TIMESTAMP>.json` — timestamped copy
- `07_LOGS_AND_AUDIT/ai_review/overrides.jsonl` — override audit log (append-only)

### 6. Human Override Path

```bash
python scripts/ai_review_gate.py \
  --override-reason "hotfix approved by lead" \
  --actor alice
```

This flips `level: fail` → `level: override-allow` and appends to `overrides.jsonl`:

```json
{
  "timestamp": "2026-06-01T00:00:00Z",
  "actor": "alice",
  "reason": "hotfix approved by lead",
  "original_level": "fail",
  "original_score": 82
}
```

## Usage

```bash
# Standard run against default base
python scripts/ai_review_gate.py

# Against a specific base ref
python scripts/ai_review_gate.py --base main

# JSON output
python scripts/ai_review_gate.py --json

# With human override (only applies if level is fail)
python scripts/ai_review_gate.py --override-reason "approved" --actor ops-lead

# Via governance orchestrator (chains policy + AI review + consensus)
python scripts/governance_review.py
python scripts/governance_review.py --base main --json
```

## Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `AI_REVIEW_WARN_FILES` | `30` | File count threshold for warn-level |
| `AI_REVIEW_FAIL_FILES` | `100` | File count threshold for fail-level |
| `AI_REVIEW_BASE` | `origin/session/chromatic-harness-v2-initial` | Default base ref |

## Integration with Governance Pipeline

`governance_review.py` calls `ai_review_gate` as one of three stages:

```
policy_engine.evaluate(context)   -> policy decision
ai_review_gate.collect_diff_metrics() + generate_findings() + risk_score()
review_consensus.build_result(reviews) -> confidence-weighted final decision
```

The AI review level maps to a reviewer verdict fed into the consensus engine:
- `ok` → approve (confidence 0.7)
- `warn` → abstain (confidence 0.5)
- `fail` → reject (confidence 0.85)

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | ok or warn (advisory) — or overridden |
| `1` | fail (blocking) |

The governance pipeline is fail-open by design: a gate error produces `ok/0` rather than
blocking the pipeline.
