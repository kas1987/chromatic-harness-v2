# Harness Execution Flow

## Purpose

This is the canonical high-level flow for Chromatic Harness v2. It explains how a session starts, how work is selected, how agents route and execute tasks, how events become beads, and how the session ends.

Agents should use this file as the conceptual map, then load deeper docs only when required by the current task.

---

## One-Line Flow

```text
Pre-session -> Beads -> Mission Packet -> Governance Gates -> Routing -> Execution -> Magnets -> Beads Update -> Validation -> Push -> Handoff
```

---

## 1. Pre-Session Boot

The agent starts with the minimum required context.

Required actions:

```bash
cat .agents/handoffs/latest.json 2>/dev/null || true
bd prime
bd ready
git branch --show-current
git status --short
python scripts/session_context_report.py --log --invoked-by harness
python scripts/audit_mcp_context.py --profile harness_dev
python scripts/pre_session_manifest.py --write
# Or: powershell -File scripts/session_preflight.ps1
```

Expected result:

- Current branch known.
- Git dirtiness known.
- Active work queue visible.
- Prior session handoff visible.
- MCP/tool context cost visible.
- **Pre-session manifest** written to `07_LOGS_AND_AUDIT/pre_session/latest.json`.
- Agent does not assume chat memory is authoritative.

---

## 2. Work Discovery

The source of work truth is beads (`bd`).

Use:

```bash
bd ready
bd show <id>
bd update <id> --claim
```

Rules:

- Do not use TodoWrite, TaskCreate, or markdown TODOs as authoritative state.
- If work appears in chat but not beads, create or update a bead.
- If multiple tasks are available, choose the highest-priority unblocked task.

---

## 3. Mission Packet Creation

Before execution, convert the selected bead into a mission packet.

A valid mission packet includes:

| Field | Required |
|---|---:|
| Mission ID | Yes |
| Objective | Yes |
| Scope | Yes |
| Allowed files | Yes |
| Forbidden files | Yes |
| Required gates | Yes |
| Confidence threshold | Yes |
| Stop conditions | Yes |
| Validation checks | Yes |

Minimal shape:

```json
{
  "mission_id": "route-001-context-detector-tests",
  "objective": "Add tests for runtime context detection",
  "scope": ["02_RUNTIME/router", "tests"],
  "confidence_required": 0.75,
  "required_gates": ["intent", "scope", "confidence"],
  "stop_conditions": ["missing file", "destructive change", "test failure after one retry"]
}
```

---

## 4. Governance Gates

Every mission passes through gates before action.

| Gate | Question |
|---|---|
| Intent Gate | Is the requested objective clear? |
| Scope Gate | Are allowed files/actions bounded? |
| Confidence Gate | Is confidence high enough to act? |
| Privacy Gate | Is provider choice allowed for this data? |
| Cost Gate | Is route within budget/speed mode? |
| Tool Gate | Are tools/MCPs appropriate and not excessive? |

If any gate fails, the mission does not execute. It is updated as blocked or requires human review.

---

## 5. Complexity Classification

Classify the task before routing.

| Level | Meaning | Examples |
|---|---|---|
| C1 | Mechanical | format, extract, convert, summarize short text |
| C2 | Structured | single-file edit, bounded code review, small refactor |
| C3 | Reasoning | architecture, root cause, multi-file integration |
| C4 | Creative/Novel | strategy, invention, research synthesis, deep design |

Complexity is not cost. Complexity describes the work. Provider routing comes after.

---

## 6. Provider Routing

Provider selection considers:

- Runtime environment: laptop, desktop, server, cloud VM.
- GPU availability and VRAM.
- Local Ollama / LM Studio availability.
- Remote Ollama desktop availability.
- Connectivity.
- Speed mode: speed, balance, low.
- Privacy class.
- Budget.
- Model capability registry.

Preferred order:

```text
Local T0 when sufficient
  -> remote desktop T0 when available
  -> direct API provider
  -> OpenRouter broker fallback
  -> premium/RunPod only when justified
```

---

## 7. Execution

Execution must be bounded.

Rules:

- Use the smallest safe next step.
- Stay inside mission scope.
- Do not edit forbidden files.
- Do not spawn subagents for C1/C2 unless explicitly justified.
- Do not run destructive commands without human approval.
- Log tool use and meaningful events.

---

## 8. Magnet Observation

During execution, magnets observe:

- Tool calls.
- Cost anomalies.
- Confidence shifts.
- Scope creep.
- Retry loops.
- Safety events.
- Interesting learnings.

A magnet event can become a runtime bead, alert bead, or learning bead.

---

## 9. Beads Update

After execution, update beads.

Possible outcomes:

| Result | Action |
|---|---|
| Complete | close bead with evidence |
| Partial | update bead with remaining work |
| Blocked | mark blocked and explain blocker |
| Failed | mark failed and create diagnosis bead |
| Learning found | create learning bead |
| Policy issue found | create governance bead |

---

## 10. Validation

Validation depends on risk.

| Risk | Minimum validation |
|---|---|
| Low | self-review and state update |
| Medium | targeted tests or diff review |
| High | tests, audit evidence, human-readable report |
| Critical | human gate required |

If code changed, run relevant tests before closing work.

---

## 11. Commit, Push, Sync

Work is not complete until durable state is pushed/synced.

```bash
git pull --rebase
git status --short
git add <changed-files>
git commit -m "<message>"
git push
bd dolt push
```

If no code changed, still update beads and handoff state.

---

## 12. Session Compact and Handoff

At phase boundaries, 50-65% context pressure, or session end:

- Update beads.
- Write human-readable handoff in `12_HANDOFFS/sessions/`.
- Update `.agents/handoffs/latest.json`.
- Record active branch, active beads, changed files, risks, and next step.

The next session starts from the handoff, not from chat memory.

---

## 13. Canonical Rule

Agents do not infer owner intent.

Agents execute against explicit artifacts:

- beads
- mission packets
- PDRs
- playbooks
- governance policies
- routing config
- handoffs
- tests
