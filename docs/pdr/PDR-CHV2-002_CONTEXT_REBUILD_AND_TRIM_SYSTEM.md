# PDR-CHV2-002: Context Rebuild and Trim System

## 0. Executive Summary

Chromatic Harness v2 needs a controlled reset layer for overfull or polluted agent context. The current pre-session system is strong, but long chats, duplicated instruction files, old handoffs, heavy MCP schemas, and broad documentation loads can push agents into red-zone context before meaningful work begins.

This PDR defines a three-script system:

1. `context_trim_audit.py` — detects context-bloat risks.
2. `context_rebuild.py` — rebuilds minimal session state from approved artifacts.
3. `new_session_bootstrap.py` — creates `BOOT_CONTEXT.md` for the next clean agent session.

The system preserves durable state in beads, handoffs, git status, and approved governance docs while preventing old conversations, logs, and archives from becoming implicit context.

---

## 1. Problem Statement

Agents are currently at risk of starting sessions with too much inherited context. A typical overloaded session can include:

- Long conversation history.
- Repeated planning decisions.
- Duplicated `AGENTS.md` and `CLAUDE.md` governance blocks.
- Old handoff chains.
- MCP tool schemas not relevant to the current mission.
- Bulk logs and historical traces.
- Broad docs loaded before the active task is known.

This creates reasoning drift, contradictory instruction weight, higher tool misuse risk, and weak pre-session focus.

---

## 2. Objective

Create a reproducible context rebuild protocol that lets any agent or human operator move from overloaded context to a clean boot packet.

The system must:

- Audit repo files that are likely to bloat pre-session context.
- Detect duplicate instruction sections.
- Identify risky files that should never be auto-loaded.
- Preserve durable state from handoffs, beads, and git.
- Create a machine-readable context manifest.
- Create a human-readable `BOOT_CONTEXT.md`.
- Provide clear stop conditions for red-zone context.

---

## 3. Non-Goals

This system does not:

- Delete project files automatically.
- Rewrite `AGENTS.md` or `CLAUDE.md` automatically.
- Replace beads or session compact protocols.
- Replace MCP audit tooling.
- Decide model routing by itself.
- Execute agent tasks.

It only audits, compacts, rebuilds, and prepares clean boot context.

---

## 4. Context Levels

| Level | Usage | Status | Required Behavior |
|---|---:|---|---|
| Green | 0-40% | Healthy | Normal work allowed |
| Yellow | 40-60% | Watch | Load focused docs only |
| Orange | 60-75% | Risk | Compact soon; avoid broad reads |
| Red | 75%+ | Stop | No new architecture, dispatch, or repo-wide reads; rebuild first |

### Red-Zone Rule

If the session reaches red context, the agent must not continue expanding the project plan. It should:

1. Run or recommend `context_trim_audit.py`.
2. Run or recommend `context_rebuild.py --mode hard`.
3. Create `BOOT_CONTEXT.md`.
4. Restart or continue only from the boot context.

---

## 5. Operating Modes

### 5.1 Soft Compact

Use when context is yellow/orange and the session can continue.

Behavior:

- Produce audit report.
- Summarize active state.
- Recommend docs to avoid.
- Do not archive or quarantine anything.

Command:

```bash
python scripts/context_rebuild.py --root . --mode soft
```

### 5.2 Hard Compact

Use when context is red or before starting a major new phase.

Behavior:

- Produce manifest.
- Generate `context_rebuild_summary.md`.
- Identify auto-load denylist.
- Build next-session inputs only from approved artifacts.

Command:

```bash
python scripts/context_rebuild.py --root . --mode hard
```

### 5.3 Nuclear Rebuild

Use when context has become unreliable, contradictory, or contaminated by stale decisions.

Behavior:

- Preserve beads, latest handoff, active RPI packet, and git state.
- Treat old handoffs/logs/traces as archive-only.
- Require human confirmation before destructive cleanup.

Command:

```bash
python scripts/context_rebuild.py --root . --mode nuclear
```

Note: the initial implementation does not delete files. Nuclear mode only marks strict exclusions and outputs a quarantine plan.

---

## 6. Files to Add

| File | Purpose |
|---|---|
| `scripts/context_trim_audit.py` | Audit context bloat and duplicate governance risk |
| `scripts/context_rebuild.py` | Build context manifest and rebuild summary |
| `scripts/new_session_bootstrap.py` | Generate `BOOT_CONTEXT.md` |
| `docs/governance/CONTEXT_REBUILD_POLICY.md` | Canonical policy for context reset behavior |
| `templates/BOOT_CONTEXT_TEMPLATE.md` | Human-readable boot context template |
| `beads/CONTEXT_REBUILD_BEADS.md` | Suggested beads backlog for implementation/validation |

---

## 7. Inputs

Scripts should inspect, when present:

```text
AGENTS.md
CLAUDE.md
AGENT_OPERATIONS.md
.agents/handoffs/latest.json
.agents/rpi/execution-packet.json
12_HANDOFFS/
07_LOGS_AND_AUDIT/
docs/
04_PLAYBOOKS/
09_DEPLOYMENT/config/routing/
```

Shell-based data, when available:

```bash
git branch --show-current
git status --short
bd ready
bd prime
```

Scripts must degrade gracefully when `git` or `bd` is unavailable.

---

## 8. Outputs

All generated state should land in:

```text
.agents/context/
```

Required outputs:

```text
context_trim_audit.json
context_rebuild_manifest.json
context_rebuild_summary.md
BOOT_CONTEXT.md
```

---

## 9. Context Manifest Schema

```json
{
  "generated_at": "ISO-8601 timestamp",
  "mode": "soft|hard|nuclear",
  "repo_root": ".",
  "git": {
    "branch": "main",
    "status_short": []
  },
  "handoff": {
    "latest_pointer_exists": true,
    "latest_pointer_path": ".agents/handoffs/latest.json",
    "handoff_path": "12_HANDOFFS/sessions/example.md"
  },
  "beads": {
    "available": true,
    "ready_summary": "..."
  },
  "context_policy": {
    "always_load": [],
    "load_if_relevant": [],
    "never_auto_load": []
  },
  "audit": {
    "risk_level": "green|yellow|orange|red",
    "findings": []
  },
  "next_action": "..."
}
```

---

## 10. Pre-Session Loading Policy

### Always load

- `.agents/handoffs/latest.json`
- Referenced active handoff file
- Selected active bead details
- Git branch/status
- Generated `BOOT_CONTEXT.md`

### Load only if relevant

- `AGENT_OPERATIONS.md`
- `docs/governance/PRE_SESSION_CONTEXT_POLICY.md`
- `docs/governance/OPENROUTER_BROKER_POLICY.md`
- `docs/BEADS_OBJECT_MODEL.md`
- Routing config files
- Specific playbooks for the selected mission

### Never auto-load

- Old session handoff chains.
- Bulk `.jsonl` traces.
- Full `~/.claude/projects/**/*.jsonl` logs.
- Archived docs.
- Whole `docs/` folder.
- Whole repo search results.
- Full deployment guide unless deployment is the selected mission.

---

## 11. Acceptance Criteria

- [ ] Scripts run on Windows/Linux/macOS using Python standard library only.
- [ ] Scripts do not delete files.
- [ ] Audit flags large files and duplicated instruction blocks.
- [ ] Rebuild manifest is machine-readable JSON.
- [ ] Boot context is concise and human-readable.
- [ ] System degrades gracefully without `bd`.
- [ ] System degrades gracefully outside git repo.
- [ ] Red-zone behavior is documented.
- [ ] Generated files are safe to commit or ignore according to repo policy.

---

## 12. Implementation Plan

### Phase 1 — Add docs and scripts

- Add this PDR.
- Add context rebuild policy.
- Add scripts.
- Add boot context template.
- Add validation beads.

### Phase 2 — Run local audit

```bash
python scripts/context_trim_audit.py --root .
python scripts/context_rebuild.py --root . --mode hard
python scripts/new_session_bootstrap.py --root .
```

### Phase 3 — Integrate into Agent Operations

Add to session-start checklist:

```bash
python scripts/context_trim_audit.py --root .
python scripts/context_rebuild.py --root . --mode soft
```

Add red-zone rule:

```text
If context >75%, run hard rebuild and restart from BOOT_CONTEXT.md.
```

### Phase 4 — CI guard

Add optional CI check that warns if:

- `AGENTS.md` exceeds threshold.
- `CLAUDE.md` exceeds threshold.
- Generated Beads block duplicates drift.
- Boot context template missing.

---

## 13. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Agent treats generated boot context as canon | Medium | Mark boot context as operational snapshot, not canon |
| Agent deletes files during rebuild | High | Initial scripts are read-only/write-output-only |
| Beads unavailable | Medium | Scripts degrade gracefully and record unavailable status |
| Over-aggressive denylist hides useful docs | Medium | Allow explicit human override |
| Duplicated governance remains | Medium | Add wrapper proposal and CI duplicate check later |

---

## 14. Final Recommendation

Implement this system before expanding agent autonomy. A clean boot context is now a prerequisite for reliable GO-mode behavior.

The Harness should adopt this operating law:

> Agents do not continue from red-zone context. They compact, rebuild, and restart from a governed boot packet.
