# Expansion Gate — Chromatic Harness v2

> **Status:** Enforced  
> **Enforcer script:** `scripts/check_expansion_gate.sh`  
> **Evidence matrix:** [VALIDATION_MATRIX.md](VALIDATION_MATRIX.md)

---

## The Rule

**No new layer, subsystem, protocol, playbook, agent, or integration may be added unless the existing operational spine is proven.**

A layer is "proven" when ALL THREE of the following are present:

1. **Passing runtime test** — at least one automated test in `tests/` that exercises the layer and passes in CI/local pytest.
2. **Visible frontend/operator evidence** — an operator or agent can observe the layer functioning via the frontend console (`05_FRONTEND_CONSOLE`) or a logged operator event.
3. **Replayable telemetry or event evidence** — the layer emits structured events to `07_LOGS_AND_AUDIT` or another telemetry sink that can be replayed or queried post-hoc.

If any one of the three is missing, the layer is **partial** and expansion is blocked until the gap is closed.

---

## What Counts as "New Layer" (blocked without proof)

The following additions require gate proof before creation:

- A new numbered directory (e.g., `12_*`, `13_*`) or top-level subsystem directory
- A new protocol under `01_PROTOCOLS/`
- A new agent definition or agent role under `03_AGENTS/`
- A new playbook under `04_PLAYBOOKS/` that introduces a new operational mode
- A new runtime adapter, engine, or orchestrator under `02_RUNTIME/`
- A new integration with an external service (MCP, API, webhook, queue)
- A new deployment target or docker service under `09_DEPLOYMENT/`
- Any new data pipeline or data layer under `06_DATA/`

---

## What Is Explicitly Allowed Without Gate

The following do NOT require gate proof and may proceed immediately:

- Bug fixes to existing, already-proven layers
- New or improved tests for existing layers
- Updates to this governance document or `VALIDATION_MATRIX.md`
- Updates to existing playbooks that do not introduce new operational modes
- Refactoring within an already-proven layer (no new external surface)
- Documentation updates, README edits, comment improvements
- Changes to `scripts/` audit and validation tooling (not new subsystems)
- Closing open beads within an already-proven layer

---

## Compliance Checklist for New Layer Proposals

Before opening a bead to create a new layer, the proposer must answer:

```
[ ] 1. RUNTIME TEST: Which existing test file covers this layer, or what new test will be added?
        File: _______________________________________________
        Test name/ID: _______________________________________

[ ] 2. FRONTEND EVIDENCE: How will an operator observe this layer working in the console or event log?
        Evidence type: [ ] Console UI  [ ] Operator log  [ ] Dashboard widget  [ ] Other: _____
        Location: ___________________________________________

[ ] 3. TELEMETRY: What structured event does this layer emit, and where is it stored?
        Event name/schema: __________________________________
        Sink (log path, audit file, Redis channel): _________

[ ] 4. SPINE CHECK: All layers in VALIDATION_MATRIX.md that are prerequisites of this new layer
        are marked ✓ (proven). List them:
        ____________________________________________________
```

All four boxes must be checked before a bead for the new layer is opened. If the spine check reveals a prerequisite is ⚠️ or ✗, that prerequisite must be fixed first.

---

## Gate Scope and Override

- **Override authority:** Repository owner only, documented in a bead comment with rationale.
- **Gate applies to:** All contributors, agents (Claude, Pi, Codex), and automated workflows.
- **Review cadence:** Gate status is audited each session via `scripts/check_expansion_gate.sh` and the daily harness audit.

---

## Reference

- Evidence matrix: [VALIDATION_MATRIX.md](VALIDATION_MATRIX.md)
- Governance architecture: [GOVERNANCE_AND_ROUTING_ARCHITECTURE.md](GOVERNANCE_AND_ROUTING_ARCHITECTURE.md)
- Harness execution flow: [00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md](00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md)
- Issue #53 (bead: mc-kr2e): the bead that introduced this gate
