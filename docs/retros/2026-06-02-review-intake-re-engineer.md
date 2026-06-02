# Session Retrospective — Review-Intake PDR Re-Engineer

**Date:** 2026-06-02
**PRs:** [#157](https://github.com/kas1987/chromatic-harness-v2/pull/157) (open)
**Epics closed:** `chromatic-harness-v2-tmx5` (9/9)

## What shipped

Re-engineered the review-intake epic that earlier PRs (`5gk1`/`2irx`/`maaf`) had
delivered as a copy-paste of the canonical PDR zip and marked done.

- **Phase-3 dispatcher** (`scripts/dispatch_review_work.py`) — net new; the prior
  `next_work.py` was only a `bd ready` viewer. Queue → mission packet → schema-valid
  `agent_dispatch`, branch-lock-aware.
- **`pull_request.synchronize`** stale-finding invalidation (PDR §6) — was absent.
- **Lock refactor** — importable `acquire/release/status`, wired into the dispatcher.
- **Resolution evidence enforced** — `post_review_resolution.py` rejects evidence-free
  `Resolved`; added `schemas/review_resolution.schema.json`.
- **Reviewer-pattern learning** (`scripts/review_learning.py`) — was missing.
- **GitHub Action fixed** — added `synchronize` trigger; publishes artifacts instead of
  pushing to a protected branch; new `harness-review-intake-check.yml` CI smoke.
- **Test isolation fixed** — existing suite wrote to tracked `07_LOGS_AND_AUDIT/review_intake/`
  paths; moved to temp dirs.
- **Live-loop bridge** — `--emit-beads` registers each dispatched finding as a bead so it
  enters `bd ready` and the GitHub-issue mirror. Idempotent + degrades gracefully.
- 5 event-source fixtures; 15-test acceptance suite validating every emitted record against
  the JSON schemas; AC→test traceability in `docs/pdr/review_intake/ACCEPTANCE_PROOF.md`.
  41 review-intake tests pass; wired into the `run-all-e2e` gate.

## Learnings

### 1. "Marked done" ≠ engineered — diff shipped artifacts against the source spec
The merged PRs left `review_intake.py` **byte-identical** to the PDR bundle (only 3 path
strings differed). Tests passed because they only exercised the classifier, not the
acceptance criteria. The fastest way to expose a stub epic was diffing repo files against
the canonical bundle's MANIFEST sha256 list, then mapping each PDR acceptance criterion to
a test and finding which had none.
**Action:** for "redo this epic" requests, treat the PDR's acceptance section as the audit
checklist; a criterion with no test is unproven regardless of green CI.

### 2. The real entry to the live loop is beads, not the queue file
A dispatcher that writes mission packets + `agent_dispatch` records is a dead end — nothing
consumes them. The harness's live loop is `bd ready` → agent, with `AGENT_HANDOFF_QUEUE.md`
mirroring beads to GitHub. Wiring meant bridging dispatch → `bd create` (idempotent via
`bead_id` write-back, graceful when `bd` absent).
**Action:** when adding a producer, trace the consumer before declaring it "wired."

### 3. Existing tests were polluting tracked repo state
The prior suite used `BASE = REPO_ROOT/07_LOGS_AND_AUDIT/review_intake` and an autouse
fixture that *deleted* those tracked files, surfacing as phantom `git status` deletions
after every test run.
**Action:** test artifacts always go to `tmp_path`/`mktemp`; never the tracked tree.

### 4. The pre-push intake suite flakes right after closing beads
First push was blocked solely on `issue->bead intake pipeline`; a direct re-run passed 25/25
and a retry pushed clean — the Dolt-backed bead DB was mid-write from the 10 `bd close` calls.
**Action:** captured to memory ([[prepush-intake-suite-flake-after-bead-close]]); retry the
push, don't "fix" passing tests.

## Follow-up
- Merge [#157](https://github.com/kas1987/chromatic-harness-v2/pull/157) (gate green; user decision).
- Mirror dispatched beads to GitHub via `sync_queue_to_github.py` after a live `--emit-beads` run.
- Next: `bd ready`.
