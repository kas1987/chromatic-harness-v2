# Context Rebuild Beads Backlog

Use these as proposed beads/issues for implementing the context rebuild system.

## CTX-001: Add context trim audit script

**Priority:** p1  
**Owner:** Auditor  
**Output:** `scripts/context_trim_audit.py`

Acceptance:

- [ ] Flags large context-heavy docs.
- [ ] Flags duplicate governance sections.
- [ ] Outputs JSON report.
- [ ] Uses Python standard library only.

---

## CTX-002: Add context rebuild script

**Priority:** p1  
**Owner:** Archivist / Auditor  
**Output:** `scripts/context_rebuild.py`

Acceptance:

- [ ] Supports soft/hard/nuclear modes.
- [ ] Reads latest handoff pointer if present.
- [ ] Captures git status if available.
- [ ] Captures beads summary if `bd` is available.
- [ ] Writes manifest and summary.

---

## CTX-003: Add new session bootstrap generator

**Priority:** p1  
**Owner:** Scribe  
**Output:** `scripts/new_session_bootstrap.py`

Acceptance:

- [ ] Generates `.agents/context/BOOT_CONTEXT.md`.
- [ ] Uses manifest when available.
- [ ] Falls back gracefully if manifest missing.

---

## CTX-004: Adopt context rebuild policy

**Priority:** p1  
**Owner:** Sentinel  
**Output:** `docs/governance/CONTEXT_REBUILD_POLICY.md`

Acceptance:

- [ ] Defines context thresholds.
- [ ] Defines red-zone rule.
- [ ] Defines always/load-if-relevant/never-auto-load tiers.

---

## CTX-005: Integrate into Agent Operations

**Priority:** p2  
**Owner:** Archivist  
**Output:** Patch to `AGENT_OPERATIONS.md`

Acceptance:

- [ ] Adds context audit to session start.
- [ ] Adds hard rebuild requirement at red context.
- [ ] Links context rebuild policy.

---

## CTX-006: Add CI warning for bloated instruction files

**Priority:** p2  
**Owner:** Sentinel  
**Output:** Optional CI/test check

Acceptance:

- [ ] Warns if `AGENTS.md` or `CLAUDE.md` exceed configured line/token threshold.
- [ ] Warns on duplicated Beads blocks.
- [ ] Does not fail builds until explicitly enabled.
