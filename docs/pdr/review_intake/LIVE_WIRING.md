# Review Intake — Live Wiring (OMH-4)

Bead: `chromatic-harness-v2-w1bf.4` — *Wire review-intake live (comments back)*.
Epic: `chromatic-harness-v2-w1bf` — Operating-Model Hardening (OMH).

This closes the review-intake loop **end-to-end against a real PR**, not a fixture:

1. a real review finding becomes a governed queue item,
2. `dispatch_review_work.py --emit-beads` dispatches it and registers a **real bead**
   so the finding enters the live `bd ready` loop,
3. the agent makes the scoped change, then
4. `post_review_resolution.py` emits an **evidence-gated** resolution comment that is
   posted **back to the PR** via `gh pr comment`.

The two halves (`--emit-beads` and comments-back) were built and unit-proven in the
PDR re-engineer (see [ACCEPTANCE_PROOF.md](ACCEPTANCE_PROOF.md), AC4/AC6). What was
missing — and what OMH-4 adds — is a **live run on a real PR** demonstrating the loop
closes without manual JSON surgery.

## The loop, live

```mermaid
flowchart LR
  RF[review_finding] --> Q[next_work_item<br/>queue.json]
  Q -->|dispatch_review_work.py --emit-beads| BD[(bd ready<br/>real bead)]
  Q --> MP[mission_packet.md]
  BD --> AG[agent makes scoped change]
  AG -->|post_review_resolution.py + gh pr comment| PR[(PR comment<br/>evidence-gated)]
  PR --> RL[resolution_log.jsonl]
```

### Step 1 — dispatch with bead emission

```bash
python scripts/dispatch_review_work.py \
  --queue 07_LOGS_AND_AUDIT/review_intake/queue.json \
  --emit-beads --limit 1
```

`--emit-beads` calls `create_bead()` which shells out to `bd create` with the finding's
risk/confidence mapped to a bd priority (`_bd_priority`), labels it `review-intake`, and
back-fills `bead_id` onto the queue item (idempotent — a re-run does not double-create).
The dispatch record (`dispatch_log.jsonl`) carries the `bead_id`, `lock_id`, and the
rendered `mission_packet` path. One mutating agent per PR is enforced by
`lock_pr_branch.acquire`.

### Step 2 — resolution comment back to the PR

```bash
python scripts/post_review_resolution.py \
  --finding <RF> --task <NW> --agent Auditor \
  --status Resolved \
  --files docs/pdr/review_intake/LIVE_WIRING.md \
  --validation "python -m pytest tests/test_review_intake_acceptance.py -q" \
  | gh pr comment <PR> --body-file -
```

`post_review_resolution.py` **rejects a `Resolved` status that lacks evidence** (at least
one changed file AND one validation command, AC6) before any comment is printed, then
appends a schema-valid `review_resolution` record to `resolution_log.jsonl`.

## Captured live run

<!-- LIVE_RUN_CAPTURE -->
_Filled in by the live run on the OMH-4 PR — see "Captured live run" values below._
<!-- /LIVE_RUN_CAPTURE -->

## Why self-referential

The live run targets the OMH-4 PR itself: the *finding* is this wiring task, the *change*
is this branch, and the *validation* is the review-intake acceptance suite. Every field in
the posted comment is therefore truthful — the demonstration does not post a fabricated
resolution onto an unrelated PR. The demonstration bead is closed after the run so the
tracker is not polluted with a synthetic work item.
