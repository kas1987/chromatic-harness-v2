---
name: ship-idea
description: 'Run the 11-stage idea-to-production pipeline end-to-end for one idea. Delegates to /discovery, /pre-mortem, /implement or /crank, /security, review-daemon, /push. Stages 8 (lean gate) and 10 (wire-live + PROVE) are non-skippable. Triggers: ship idea, ship this, idea to prod, end-to-end idea, pipeline this idea, run the pipeline.'
skill_api_version: 1
context:
  window: inherit
  intent:
    mode: none
  intel_scope: none
metadata:
  tier: orchestration
  dependencies:
    - discovery
    - pre-mortem
    - implement
    - crank
    - security
    - push
---

# ship-idea Skill

> **Quick Ref:** Run the 11-stage idea-to-production pipeline for one idea. Stages 8 and 10 are hard gates — never skip them. Output: tracked bead, PDR, impl, hardened PR, live wiring proven.

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## Efficiency Doctrine (enforce on every subagent dispatch)

Read `~/.claude/governance/subagent-token-efficiency.md` before fanning out. Rules:
- Route C1/C2 mechanical work to `haiku`/local-OL; C3 reasoning to `sonnet`; C4 synthesis to `opus`.
- Pass file **references** (paths), not payload dumps, to subagents.
- One artifact per agent dispatch.
- Use `codegraph_context` / `Explore` for read-only discovery; never grep loops.
- Audit sprawl with `~/.claude/bin/agent_token_audit.py` after heavy fan-out.

---

## Execution

Given `/ship-idea <idea text or bead-id>`:

### Stage 1 — Capture

Track the idea as a bead so it is never lost.

```bash
# If not already a bead:
bd create "<idea-title>" --body "<idea text>"
# Note the bead ID (e.g. B42) for all subsequent steps.
BEAD_ID=$(bd current | awk '{print $1}')
```

Log: `[S1] Bead $BEAD_ID created.`

---

### Stage 2 — Reuse-survey + PDR spec

**Non-negotiable:** the PDR must live in `08_PDRS/` and use the canonical template.

1. Survey existing assets (codegraph or Glob) — build on, do not rebuild.
2. Copy the template:

```bash
cp 08_PDRS/_PDR_TEMPLATE.md 08_PDRS/PDR_<SLUG>.md
```

   Template path: `C:/Users/kas41/chromatic-harness-v2/08_PDRS/_PDR_TEMPLATE.md`

3. Fill in: problem, reuse candidates, integration/actuation edge (required — this closes the "implemented-but-not-wired" gap), success criteria, and the live-observation plan (referenced in Stage 10).

Log: `[S2] PDR written → 08_PDRS/PDR_<SLUG>.md`

---

### Stage 3 — Pre-mortem gate

Invoke the skill; do not skip even for small ideas.

```
/pre-mortem   # reviews 08_PDRS/PDR_<SLUG>.md
```

- **PASS:** continue.
- **WARN:** log risk, continue.
- **BLOCK:** address the blocker, re-run pre-mortem, then continue.

Log: `[S3] Pre-mortem result: <PASS|WARN|BLOCK> — <one-line summary>`

---

### Stage 4 — Decompose

Create child beads B1…Bn, dependency-ordered.

```bash
/plan   # generates child beads from the PDR
```

Verify with `bd list --parent $BEAD_ID`.

Log: `[S4] N child beads created.`

---

### Stage 5 — Implement (TDD)

Choose the right delegator based on complexity (from PDR):

| Complexity | Delegator |
|---|---|
| C1–C2 (single file / mechanical) | `/implement` |
| C3–C4 (multi-module / systemic) | `/crank` |

Apply efficiency doctrine on all subagent dispatches. Tests must be written first; never trust agent claims of "passing" — run them yourself (Stage 6).

Log: `[S5] Implementation delegated via /<implement|crank>.`

---

### Stage 6 — Verify yourself

Run the test suite; do not accept agent output as ground truth.

```bash
# Example — adapt to project runner:
python -m pytest -q   # or: bd test / npm test / etc.
```

All tests must be green before proceeding. Fix failures before Stage 7.

Log: `[S6] Tests: <N passed, 0 failed>`

---

### Stage 7 — Harden gate

```bash
# review-daemon (mechanical — C1, route haiku/local)
mcp__review-daemon__review_run   # or: bd review-daemon run

# security scan
/security
```

Both must pass (or findings addressed) before Stage 8.

Log: `[S7] Review-daemon: <result>. Security: <result>.`

---

### Stage 8 — Lean gate [NON-SKIPPABLE]

This gate is mandatory. Answer each question explicitly in the log.

Run the token audit:

```bash
python ~/.claude/bin/agent_token_audit.py
```

Answer in order:
1. **Boot tax** — does this add always-on overhead? If yes, is it justified?
2. **Poll vs event** — is any polling replaceable with an event-driven Magnet at an inflection point?
3. **On-demand vs always-injected** — is context injection on-demand or always loaded?
4. **Swappable** — is the heavy capture component swappable (thin interface, not hardwired)?

If any answer is "yes, unjustified" — fix it before Stage 9. A WARN is logged and you continue only after the fix.

Log: `[S8-LEAN] boot-tax=<ok|WARN> poll=<ok|WARN> inject=<ok|WARN> swappable=<ok|WARN>`

---

### Stage 9 — Ship (PR)

```bash
/push   # session branch + PR + E2E gate
bd close $BEAD_ID
```

Confirm PR URL and that the bead is closed.

Log: `[S9] PR: <url>. Bead $BEAD_ID closed.`

---

### Stage 10 — Make it LIVE + PROVE [NON-SKIPPABLE]

This is the #1 missed step. Shipping a PR is not live wiring.

1. Wire the artifact into the runtime path. Concretely:
   - Register in the relevant registry/plugin/magnets list (e.g. `magnets/plugin.py:default_registry`).
   - Add the integration/actuation edge described in the PDR (Stage 2).

2. PROVE it is called — via **live observation**, not a unit test:
   - Trigger the real runtime path (run the harness, fire an event, invoke the CLI hook).
   - Capture evidence: log line, trace output, or Magnet event showing the new code executed.

```bash
# Example proof pattern — adapt to the actuation edge in the PDR:
python 02_RUNTIME/main.py --dry-run   # or fire the relevant event
# Look for the log line / trace confirming invocation
```

If you cannot produce live evidence, the stage is not done. Fix the wiring and re-verify.

Log: `[S10-LIVE] wired=<where>. proof=<log line or observation summary>`

Definition of Done gate: check `08_PDRS/DEFINITION_OF_DONE.md` before marking complete.
Path: `C:/Users/kas41/chromatic-harness-v2/08_PDRS/DEFINITION_OF_DONE.md`

---

### Stage 11 — Observe

Wire a Magnet or telemetry watch so production behavior is visible.

- Prefer event-driven Magnets at inflection points over pollers.
- At minimum: confirm an existing Magnet covers this path, or create a new one.
- Document the observation plan in the PDR.

Log: `[S11] Observer: <Magnet name or telemetry sink>.`

---

## Completion Report

After all 11 stages, output:

```
ship-idea complete for <IDEA>

  Bead:     <ID> (closed)
  PDR:      08_PDRS/PDR_<SLUG>.md
  PR:       <url>
  Live at:  <registration point>
  Proof:    <one-line live observation>
  Observer: <Magnet / telemetry>

  Gate log:
    S3  pre-mortem:  <result>
    S7  harden:      <result>
    S8  lean:        boot-tax=<> poll=<> inject=<> swappable=<>
    S10 live:        wired=<> proof=<>

<promise>DONE</promise>
```

---

## Key Rules

- **Stages 8 and 10 are non-skippable.** If blocked, fix the blocker and re-run the stage. Never mark either done without the required evidence.
- **Stage 2 PDR must use** `08_PDRS/_PDR_TEMPLATE.md` and must specify the integration/actuation edge.
- **Stage 10 proof must be live observation**, not a unit test assertion.
- **Efficiency doctrine** applies to every subagent dispatch — route cheap work cheap, pass refs not payloads.
- **Stage 6 self-verify** — never trust agent claims; run tests yourself.
- Never open a PR without review-daemon + security passing (Stage 7).

## Reference Docs

| Doc | Purpose |
|---|---|
| `.agents/tmp/idea-to-prod-pipeline.md` | Canonical 11-stage pipeline brief |
| `08_PDRS/_PDR_TEMPLATE.md` | Mandatory PDR template (Stage 2) |
| `08_PDRS/DEFINITION_OF_DONE.md` | DoD gate (Stage 10) |
| `~/.claude/governance/subagent-token-efficiency.md` | Efficiency doctrine for all dispatches |
| `~/.claude/bin/agent_token_audit.py` | Token audit (Stage 8) |
