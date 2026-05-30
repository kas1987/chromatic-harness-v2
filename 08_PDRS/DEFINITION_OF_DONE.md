# DEFINITION OF DONE

> A bead is **NOT done** when the PR merges. It is done when every line below
> is checked and the evidence exists. review-daemon must see this checklist
> satisfied before approving the PR gate.

---

## Checklist

Each item requires **evidence** — a file path, test name, log line, or
bead comment. "I think it works" is not evidence.

### 1. CAPTURE
- [ ] Bead created via `bd create` before any code written.
  - Evidence: `bd show <id>` shows the bead with correct title and parent epic.

### 2. SPEC
- [ ] PDR exists in `08_PDRS/` with: objective, integration edge (what calls
  this?), reuse survey (what existing asset does this build on?), and
  the fail-open strategy.
  - Evidence: path to `08_PDRS/<NAME>.md`, section "Integration Edge" populated.

### 3. PRE-MORTEM
- [ ] `/pre-mortem` or council ran; verdict recorded.
  - Evidence: council output saved in bead comments or `.agents/tmp/`.
  - BLOCK if verdict was "not yet" and no design change was made.

### 4. TDD
- [ ] Tests written before or alongside implementation (not after).
- [ ] All tests pass: `pytest` / `bats` / test runner output attached.
  - Evidence: test file path + run output (not agent claim — actual output).
  - Zero skipped tests without a bead-commented justification.

### 5. VERIFY (self)
- [ ] You ran the tests yourself. Agent claim of "passing" is not sufficient.
  - Evidence: terminal output or CI log showing green suite.

### 6. HARDEN
- [ ] `review-daemon` ran and approved (or findings fixed and re-run).
- [ ] `/security` scan ran; no unmitigated HIGH findings.
- [ ] Fail-open verified: if this component crashes, the runtime degrades
  gracefully (no hard dependency blocks the hot path).
  - Evidence: `review-daemon` approval ID + security scan output path.

### 7. LEAN
- [ ] `python ~/.claude/bin/agent_token_audit.py` ran; no new always-on pollers.
- [ ] Any new background work is event-driven (Magnet at inflection point),
  not a timer/poller unless explicitly justified in the PDR.
- [ ] Boot-tax delta documented: does this add latency to cold start?
  - Evidence: audit output confirming no new scheduled poll; OR PDR section
    "Lean justification" explaining the exception.

### 8. SHIP
- [ ] Session branch created; PR opened against `main`.
- [ ] PR description references the bead ID and links the PDR.
- [ ] E2E gate passed (CI green or manual smoke confirmed).
- [ ] `bd close <id>` run after merge.
  - Evidence: PR URL in bead comments; `bd show <id>` shows status CLOSED.

### 9. LIVE (wired)
- [ ] Something in the **runtime path** calls this code. Prove it.
  - Accepted evidence (choose one):
    - Log line captured from a live run showing the entry point invoked.
    - Magnet registered in `magnets/plugin.py:default_registry` and a
      real event triggered it (show the Magnet log line).
    - Integration test that exercises the wired path end-to-end (not a
      unit test of the module in isolation).
  - **NOT acceptable:** "it's imported", "the function exists", a unit test
    that calls the function directly without the runtime wiring.

### 10. OBSERVE
- [ ] A Magnet or telemetry hook watches this in production.
  - Evidence: Magnet name + registration point; OR a note in the PDR
    explaining why observability is not applicable (rare).

---

## The Three Gaps This Closes

| Gap | How the checklist catches it |
|-----|------------------------------|
| **Implemented-but-not-wired** | Step 9 (LIVE) requires live-runtime evidence that the integration edge fires. A unit test or import statement does not satisfy it. The PDR spec (step 2) must name the integration edge before code starts, so there is no ambiguity about what "wired" means. |
| **Works-but-not-hardened** | Steps 6 (HARDEN) and 5 (VERIFY) are separate. You cannot check HARDEN without a review-daemon approval ID and a security scan path. Agent confidence is rejected as evidence. |
| **Ships-but-bloats** | Step 7 (LEAN) requires the token audit to run and any new always-on work to be event-driven. The PDR's "Integration Edge" section names the inflection point, not a polling interval. Boot-tax delta is documented, not assumed zero. |

---

## review-daemon / PR Gate Integration

The review-daemon pre-merge check reads this file and enforces:

1. Steps 1–8 must be checked or the PR is held.
2. Step 9 (LIVE) must have a non-empty evidence string — the daemon rejects
   "[ ]" (unchecked) or evidence that matches the NOT-acceptable patterns
   ("it's imported", "unit test").
3. Step 6 must include the review-daemon approval ID from the *current run*
   (not a prior run on an older diff).

To satisfy the gate, paste the filled checklist into the PR description or
attach it as a bead comment and reference it in the PR body.

---

## "NOT done if nothing calls it" Rule

> **If you cannot show a log line, Magnet registration, or end-to-end
> integration test that proves the runtime invokes your code — the bead
> stays OPEN.**

This rule is not negotiable. Merged code that nothing calls is dead weight.
The LIVE step exists precisely because "code merged" historically meant
"done" and left half the harness unexercised. Do not close the bead, do not
mark the epic child complete, until live-runtime evidence exists.
