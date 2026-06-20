# Review-Intake Loop Closure Metrics

**Document Version:** 1.0  
**Created:** 2026-06-20  
**Status:** Baseline measurement active

## Executive Summary

Track end-to-end latency for the review-intake loop: from PR comment ingestion through beads creation to response comment posting. This document records baseline timings and optimization targets.

## Loop Phases

The review-intake loop consists of five sequential phases:

1. **Comment Ingestion** (Phase 0)
   - GitHub webhook receives PR comment
   - Event queued in GitHub Actions

2. **Findings Normalization** (Phase 1)
   - `review_intake.py` parses event
   - Creates `review_finding` record
   - Appends to `findings.jsonl`

3. **Confidence Classification** (Phase 2)
   - `classify_review_finding.py` enriches finding
   - Computes confidence score
   - Creates `next_work_item`

4. **Beads Registration** (Phase 3)
   - `dispatch_review_work.py` with `--emit-beads` flag
   - Calls `bd create` for each ready item
   - Item enters `bd ready` queue

5. **Response Comment** (Phase 4)
   - Orchestrator checks `bd ready`
   - Generates response comment
   - Posts back to PR

## Measurement Protocol

### Comment Trigger Format

All measurements use the standardized trigger:

```
review-intake: analyze
```

This tag in a PR comment signals the review-intake system to process and measure loop closure.

### Timestamp Markers

Each phase records UTC timestamps:

- **T0:** GitHub webhook receives comment (GitHub-provided `created_at`)
- **T1:** `review_intake.py` writes `created_at` to `review_finding`
- **T2:** `classify_review_finding.py` completes enrichment
- **T3:** `dispatch_review_work.py` calls `bd create`
- **T4:** `bd create` returns; bead ID written to log
- **T5:** Response comment posted to PR

### Latency Definitions

| Latency | Calculation | Target | Threshold |
|---------|-------------|--------|-----------|
| Ingest Latency | T1 - T0 | < 10 sec | ≥ 60 sec = alert |
| Classification Latency | T2 - T1 | < 5 sec | ≥ 30 sec = alert |
| Dispatch Latency | T3 - T2 | < 3 sec | ≥ 20 sec = alert |
| Beads Write Latency | T4 - T3 | < 5 sec | ≥ 30 sec = alert |
| Response Latency | T5 - T4 | < 30 sec | ≥ 120 sec = alert |
| **Total Loop Latency** | **T5 - T0** | **< 60 sec** | **≥ 300 sec (5 min) = optimize** |

## Baseline Measurements (Deployed 2026-06-20)

### Test Run 1: PR #275 Comment Intake

**Setup:** Single comment with `review-intake: analyze` tag on PR #275

**Results:** (To be populated on first measurement)

| Phase | Start | Duration | Status |
|-------|-------|----------|--------|
| Ingest (T0→T1) | TBD | TBD | Pending |
| Classify (T1→T2) | TBD | TBD | Pending |
| Dispatch (T2→T3) | TBD | TBD | Pending |
| Beads Write (T3→T4) | TBD | TBD | Pending |
| Response (T4→T5) | TBD | TBD | Pending |
| **Total (T0→T5)** | **TBD** | **TBD** | **Pending** |

**Analysis:**

- Expected bottleneck: GitHub Actions queue time (T0→T1)
- Second risk: `bd create` latency (T3→T4)
- Optimization target: Parallelization of classification and dispatch phases

### Test Run 2: Multiple Comments (Pending)

Will measure burst behavior when multiple PRs receive comments simultaneously.

## Optimization Checklist

If total loop latency > 5 minutes:

- [ ] Check GitHub Actions job queue time (`workflow_run.started_at - created_at`)
- [ ] Verify `bd` process is not orphaned or locked
- [ ] Profile `classify_review_finding.py` execution time
- [ ] Check artifact upload latency in workflow
- [ ] Confirm no pre-push gate blocking the workflow
- [ ] Measure network latency to GitHub API
- [ ] Consider parallel classification and dispatch streams

## Integration Points

### GitHub Actions Workflow

File: `.github/workflows/review-intake.yml`

Triggers on:
- `pull_request_review` (submitted, edited, dismissed)
- `pull_request_review_comment` (created, edited)
- `pull_request.synchronize`
- `issue_comment` (created, edited) — filtered to PRs only
- `check_run` (completed)
- `workflow_run` (completed)

### Beads Integration

File: `scripts/dispatch_review_work.py` (line 94-120)

The `create_bead()` function:
1. Builds `bd create` command with title, priority, labels
2. Runs subprocess call to `bd`
3. Captures bead ID from stdout
4. Writes to dispatch log for traceability

### Comment Parsing

File: `scripts/review_intake.py` (line 115-140)

The `normalize_issue_comment()` function:
1. Extracts `body` from GitHub event
2. Checks for special tags (future: `review-intake:` directive parsing)
3. Routes to classifier based on tag presence

**TODO:** Implement tag-based routing for `review-intake: analyze` to enable fast-path processing.

## Response Comment Template

File: `templates/REVIEW_RESOLUTION_COMMENT.md`

Posted back to PR when a finding is resolved:

```markdown
## Review Intake Resolution

**Finding ID:** {{finding_id}}
**Status:** {{status}}
**Agent:** {{agent}}
**Patch Applied:** {{patch_link}}

**Validation:**
{{validation_evidence}}

---
_Review-intake loop closed at {{resolved_at}}_
_Total latency: {{total_latency}}_
```

## Dashboard & Monitoring

### Real-Time Metrics

Metrics are published to GitHub Actions artifacts:

- `07_LOGS_AND_AUDIT/review_intake/state.json` — latest event processed
- `07_LOGS_AND_AUDIT/review_intake/queue.json` — current queue state
- `07_LOGS_AND_AUDIT/review_intake/findings.jsonl` — all findings

### Automated Dashboard

Script: `scripts/generate_review_intake_dashboard.py`

Generates markdown summary:
- Open findings count
- Queue readiness distribution
- Average loop latency (rolling 24h)
- Stale lock detection

To generate: `python scripts/generate_review_intake_dashboard.py > docs/review-intake/DASHBOARD.md`

## Known Limitations

1. **GitHub Actions Lag:** Cannot measure T0 precisely. GitHub provides `created_at` from webhook, but job start time introduces ~5–30 sec variance.
2. **bd Process Fragility:** Windows embedded Dolt can hang. May require process reaping before measurements.
3. **No Central Collector Yet:** Phase 5 central collector (`review_intake_webhook_app.py`) not deployed. Metrics currently isolated per-repo.

## Next Steps

1. ✅ Deploy baseline measurement infrastructure
2. ⏳ Run PR #275 measurement (target: <60 sec total latency)
3. ⏳ Run burst test (3 simultaneous comments)
4. ⏳ If latency >5 min, implement tag-based fast-path
5. ⏳ Deploy central collector for multi-repo metrics
6. ⏳ Create automated SLA dashboard

## References

- PDR: `08_PDRS/PDR_REVIEW_INTAKE_2026-06-01.md`
- Implementation: `docs/retros/2026-06-02-review-intake-re-engineer.md`
- Acceptance Criteria: `docs/pdr/review_intake/ACCEPTANCE_PROOF.md`
