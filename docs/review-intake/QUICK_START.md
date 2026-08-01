# Review-Intake Loop Quick Start

**Last Updated:** 2026-06-20  
**Status:** Ready for Measurement

## 60-Second Setup

The review-intake loop is now live. To trigger and measure it:

### 1. Post a Comment on Any PR

```markdown
review-intake: analyze
```

**Example:**
```
review-intake: analyze

Please process this PR for review findings and dispatch feedback as structured work items.
```

### 2. Wait for Workflow

GitHub Actions will automatically:
- Ingest your comment
- Create a `review_finding` record
- Add a queue item
- (Optionally) register a bead in `bd ready`

Typical time: < 60 seconds (target SLA)

### 3. Monitor Results (Optional)

```bash
# Watch the workflow run
gh run list --limit 5

# Check generated artifacts
ls -la 07_LOGS_AND_AUDIT/review_intake/

# View the findings
cat 07_LOGS_AND_AUDIT/review_intake/findings.jsonl | jq '.'

# View the queue
cat 07_LOGS_AND_AUDIT/review_intake/queue.json | jq '.items[]'
```

### 4. Measure Latency (Optional)

```bash
python scripts/measure_review_intake_loop.py --pr <PR_NUMBER> --timeout 300
```

Example:
```bash
python scripts/measure_review_intake_loop.py --pr 275
```

This outputs timing breakdown:
```
[1] Searching for 'review-intake: analyze' comment on PR #275...
   Found comment created at 2026-06-20T14:23:45Z
[2] Polling for review_finding records...
   Found 1 finding(s). Ingest latency: 8.3s
[3] Polling for queue items...
   Found 1 queue item(s). Classification latency: 4.2s
[4] Polling for beads...
   Found 1 bead(s). Dispatch latency: 2.1s

[✓] Loop closure measured successfully
   Total latency: 14.6s
   Status: ✓ PASS (target <60s)
```

## Key Artifacts

| File | Purpose | Location |
|------|---------|----------|
| `findings.jsonl` | All normalized review signals | `07_LOGS_AND_AUDIT/review_intake/` |
| `queue.json` | Dispatchable work items | `07_LOGS_AND_AUDIT/review_intake/` |
| `state.json` | Last processed event metadata | `07_LOGS_AND_AUDIT/review_intake/` |
| `timing/` | Workflow phase timestamps | `07_LOGS_AND_AUDIT/review_intake/timing/` |
| `measurement_log.jsonl` | Loop closure measurements | `07_LOGS_AND_AUDIT/review_intake/` |

## Event Types Supported

The loop automatically ingests:

| Event | Example | Queue Item |
|-------|---------|-----------|
| PR review comment | "This line has a typo" | ✓ Yes |
| PR general comment | "Please add docs" | ✓ Yes |
| PR review (changes requested) | Changes requested on review | ✓ Yes |
| CI check failure | "Test failed: expected X" | ✓ Yes |
| Workflow failure | "Deploy workflow failed" | ✓ Yes |

## Confidence Scoring

Each finding gets a score 0–100:

| Score | Action |
|-------|--------|
| 90–100 | Auto-fix allowed (if reversible) |
| 75–89 | Auto-fix allowed with validation |
| 60–74 | Plan/draft only |
| 40–59 | Investigation task |
| 0–39 | Blocked / needs clarification |

**Lower scores = more gating.** Vague feedback or unclear scope = lower confidence = no auto-patch.

## SLA Targets

| Metric | Target | Alert |
|--------|--------|-------|
| Total loop latency | < 60 sec | > 5 min |
| Ingest phase | < 10 sec | > 60 sec |
| Classification | < 5 sec | > 30 sec |
| Dispatch | < 3 sec | > 20 sec |
| Beads write | < 5 sec | > 30 sec |
| Response posting | < 30 sec | > 120 sec |

If any latency exceeds its alert threshold, check:

1. **GitHub Actions queue time** — Are other workflows running?
2. **Dolt/beads process** — Is `bd` hung? `ps aux | grep dolt`
3. **Network latency** — GitHub API slow?
4. **Classification complexity** — Unusual comment text?

## Common Questions

### Q: Can I trigger the loop without comments?

**A:** Currently, only comments with structured tags work. Comment-less triggers (e.g., API calls) require Phase 5 central collector (not yet deployed).

### Q: What if my comment doesn't get ingested?

**A:** Check:
1. Exact tag: must be `review-intake: analyze` (case-sensitive)
2. PR is open (not draft, not closed)
3. Workflow triggered: `gh run list -L 1`
4. Event type supported (PR comment, inline comment, review, CI check)

### Q: Can the loop auto-patch my code?

**A:** Only if:
- Finding type is auto-fixable (lint, docs, test, repo hygiene)
- Confidence score ≥ 75
- Scoped to allowed files (not repo-wide)
- Not security/architecture (those always gate)

### Q: What if the loop hangs?

**A:** Kill orphaned processes:
```bash
ps aux | grep -i dolt | grep -v grep | awk '{print $2}' | xargs kill -9
```

Then retry.

### Q: How do I disable auto-dispatch?

**A:** Edit `.github/workflows/review-intake.yml` and comment out the "Optionally dispatch to beads" step. Findings will still be ingested and queued; just not auto-dispatched.

### Q: Can I test locally?

**A:** Yes, run the scripts directly:
```bash
# Simulate an issue comment event
python scripts/review_intake.py \
  --event-name issue_comment \
  --event-path /path/to/github/event.json \
  --findings 07_LOGS_AND_AUDIT/review_intake/findings.jsonl \
  --queue 07_LOGS_AND_AUDIT/review_intake/queue.json

# Then dispatch
python scripts/dispatch_review_work.py \
  --queue 07_LOGS_AND_AUDIT/review_intake/queue.json \
  --emit-beads
```

## Next Steps

1. **Run baseline measurement** (target: PR #275)
2. **Run burst test** (3+ simultaneous comments)
3. **Monitor production metrics** (daily dashboard check)
4. **Optimize if needed** (tag-based fast-path, parallel dispatch)

## Getting Help

- **PDR (full spec):** `08_PDRS/PDR_REVIEW_INTAKE_2026-06-01.md`
- **Metrics & SLAs:** `docs/review-intake/LOOP_CLOSURE_METRICS.md`
- **Deployment status:** `docs/review-intake/DEPLOYMENT_CHECKLIST.md`
- **Implementation details:** `docs/retros/2026-06-02-review-intake-re-engineer.md`
- **Previous work:** `docs/retros/2026-06-01-review-intake-pdr-unpack.md`

---

**TL;DR:** Comment `review-intake: analyze` on any PR, wait <60 sec, check `07_LOGS_AND_AUDIT/review_intake/queue.json` for results.
