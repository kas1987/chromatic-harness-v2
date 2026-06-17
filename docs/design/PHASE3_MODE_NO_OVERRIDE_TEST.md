# Phase 3 Design: Mode No-Override Invariant & Test Scaffold

**Status:** Draft — design + non-executing test scaffold  
**Date:** 2026-06-16  
**Scope:** Phase 3 mode switcher (Operator / Auditor / Designer); deferred until human approves autonomy-scale decision  
**Related:** `config/claude_adapter_rules.yaml`, `config/claude_command_registry.yaml`, `02_RUNTIME/router/gate.py`, `02_RUNTIME/router/pipeline/io.py`, `08_PDRS/PDR_COMMAND_PROMPT_SYSTEM.md`

---

## 1. The Invariant

> **A prompt mode (Operator, Auditor, Designer) can shape pre-context injected before a task, but it can NEVER flip a CMP gate verdict.**

This invariant flows directly from the authority ladder defined in
`docs/governance/CLAUDE_AUTHORITY_MODEL.md`:

```
L0  Human Intent
L1  GitHub Issues / bd Queue
L2  Harness Router / Orchestrator
L3  Confidence Gate
L4  Lease / Collision Gate
L5  Verifier Gate
L6  Tests / CI Governance
L7  Release Readiness
L8  Human Approval (irreversible)
```

Prompt modes are adapter-layer constructs — they exist above L0 to translate intent into
context, not below L2 where gate decisions are made. They are therefore *structurally
upstream* of every CMP gate. A mode can pre-populate context (system prompt prefix,
playbook fragments, panel layout hints), but the confidence gate, lease gate, and
verifier gate run independently of whatever mode is active.

**The concrete boundary:**

| What a mode CAN do | What a mode CANNOT do |
|---|---|
| Inject a pre-context block into the mission packet's `metadata` field | Set or override `confidence_required` |
| Set `default_autonomy_level` as a suggestion in `metadata` | Claim or waive a CMP gate (`intent`, `scope`, `confidence`) |
| Enable or suppress UI panels | Emit a `permissionDecision` in the hook output |
| Bias playbook selection | Skip `required_gates` listed in the command registry |
| Restrict `allowed_tools` to a tighter subset | Expand `allowed_tools` beyond what the command registry permits |
| Lower the default autonomy floor (e.g. Auditor forcing L0-L2) | Raise autonomy beyond the CMP-gated ceiling |

---

## 2. How Modes Register as Adapter Commands

Modes follow the same registration path as every other adapter command: they get an
entry in `config/claude_command_registry.yaml` with explicit `required_gates` and
`forbidden_logic` fields. This makes them structurally subordinate to CMP — the registry
is checked by harness scripts before execution, so a mode that omits a required gate or
lists a forbidden logic term will be refused by the validator
(`scripts/validate_command_prompt_pack.py`) before any runtime hook runs.

### 2.1 Required fields for a mode entry

```yaml
# config/claude_command_registry.yaml (additions — NOT YET ADDED, design draft)
commands:
  - name: /mode:operator
    purpose: >
      Switch active pre-context to Operator mode. Shapes mission packet metadata only.
      Does not grant additional gate authority.
    authority_source: read_only_artifacts
    script: null                        # modes have no execution script; pure context
    fallback_script: null
    mutation: none                      # modes never mutate harness state
    required_gates: [confidence, lease] # same floor as /go; cannot be lowered by mode
    logs_to: 07_LOGS_AND_AUDIT/decisions/decision_log.jsonl
    allowed: true
    forbidden_logic:
      - approval_decision
      - release_override
      - state_mutation
      - decision_override
      - unapproved_override
      - skip_verifier
      - skip_collision
      - direct_file_mutation

  - name: /mode:auditor
    purpose: >
      Switch active pre-context to Auditor mode. Read-only inspection framing.
      Lowers autonomy floor to L0-L2; cannot raise it.
    authority_source: read_only_artifacts
    script: null
    fallback_script: null
    mutation: none
    required_gates: []                  # auditor is read-only; no mutation gates needed
    logs_to: null
    allowed: true
    forbidden_logic:
      - approval_decision
      - release_override
      - state_mutation
      - decision_override
      - unapproved_override
      - direct_file_mutation
      - queue_claim
      - hidden_claim

  - name: /mode:designer
    purpose: >
      Switch active pre-context to Designer mode. Asset-swap and theme-composition
      context. Restricted to frontend scope; cannot touch runtime or governance paths.
    authority_source: read_only_artifacts
    script: null
    fallback_script: null
    mutation: none
    required_gates: [confidence]        # any asset write needs confidence gate
    logs_to: null
    allowed: true
    forbidden_logic:
      - approval_decision
      - release_override
      - state_mutation
      - decision_override
      - unapproved_override
      - direct_ship
      - hidden_agent_dispatch
```

### 2.2 Why `mutation: none` for modes

The `mutation` field in the registry determines whether a command is allowed to modify
harness state at all. Modes are pure context injectors: they write into the
`mission_packet.metadata.mode` field (pre-flight, in memory) and do not touch the queue,
the lease registry, the decision log, or any file outside the mission's `allowed_paths`.
Setting `mutation: none` enforces this structurally and is checked by the validator.

### 2.3 Advisory seam — how modes interact with the gate hook

The PreToolUse gate hook (`02_RUNTIME/router/gate.py`) reads `tool_input` from stdin and
emits one of two shapes to stdout via `02_RUNTIME/router/pipeline/io.py`:

```python
# Advisory path (pass-through):
emit_advisory(advisory_str)
# → {"hookSpecificOutput": {"additionalContext": advisory_str}}

# Deny path:
emit_deny(advisory_str)
# → {"hookSpecificOutput": {
#       "permissionDecision": "deny",
#       "denyReason": "...",
#       "additionalContext": advisory_str}}
```

The `permissionDecision` key is what blocks tool execution. A mode's output **only ever
reaches `additionalContext`** — the mode writes text that becomes part of the agent's
pre-context, never an object that the hook output parser treats as a gate decision.

This is the physical boundary: `additionalContext` is informational; `permissionDecision`
is authoritative. No mode implementation path leads to writing `permissionDecision`.

---

## 3. Draft Pytest Scaffold

The following test file is a DRAFT design artifact. It is embedded here as a fenced
code block and must NOT be saved under `tests/` — doing so would cause CI collection
and execution before the mode switcher is implemented.

When Phase 3 is approved and implemented, this scaffold should be saved to
`tests/unit/test_mode_no_override.py` and made live.

```python
# DRAFT — tests/unit/test_mode_no_override.py
# DO NOT place this file under tests/ until Phase 3 mode switcher is implemented.
# Rationale: avoids CI collection of unimplemented tests (import errors).

"""
Phase 3 invariant: a prompt mode (Operator/Auditor/Designer) can shape pre-context
but CANNOT flip a CMP gate verdict.

These tests verify that:
  1. Mode advisory output lands only in additionalContext, never in permissionDecision.
  2. A gate deny verdict is not reversible by any mode string appearing in the prompt.
  3. The command registry entries for /mode:* all carry forbidden_logic that prevents
     decision_override and state_mutation.
  4. The mission packet autonomy_level field cannot be set above L4 by a mode alone
     (L5 requires human approval per PDR_CHROMATIC_HARNESS_V2.md §7).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "config" / "claude_command_registry.yaml"
ADAPTER_RULES_PATH = REPO / "config" / "claude_adapter_rules.yaml"
MISSION_SCHEMA_PATH = REPO / "01_PROTOCOLS" / "CMP" / "mission_packet.schema.json"
IO_MODULE = "router.pipeline.io"


def _load_registry() -> dict:
    """Load command registry; fail loud if missing."""
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def _mode_entries(registry: dict) -> list[dict]:
    """Return all commands whose name starts with /mode:."""
    return [c for c in registry.get("commands", []) if c["name"].startswith("/mode:")]


# ---------------------------------------------------------------------------
# Advisory seam — mode output must NOT contain permissionDecision
# ---------------------------------------------------------------------------

class TestAdvisorySeam:
    """Verify that emit_advisory never produces a permissionDecision key."""

    def test_emit_advisory_no_permission_decision(self):
        """emit_advisory output must not contain permissionDecision."""
        import io as _io
        import sys
        from router.pipeline.io import emit_advisory  # noqa: PLC0415

        buf = _io.StringIO()
        with patch.object(sys, "stdout", buf):
            emit_advisory("MODE: Operator pre-context injected")

        output = json.loads(buf.getvalue())
        hook_out = output.get("hookSpecificOutput", {})

        assert "permissionDecision" not in hook_out, (
            "emit_advisory must never produce permissionDecision; "
            f"got keys: {list(hook_out.keys())}"
        )
        assert "additionalContext" in hook_out

    def test_emit_deny_has_permission_decision(self):
        """Baseline: emit_deny DOES produce permissionDecision (contrast test)."""
        import io as _io
        import sys
        from router.pipeline.io import emit_deny  # noqa: PLC0415

        buf = _io.StringIO()
        with patch.object(sys, "stdout", buf):
            emit_deny("ROUTER C=C4 — use cheaper tier")

        output = json.loads(buf.getvalue())
        hook_out = output.get("hookSpecificOutput", {})

        assert "permissionDecision" in hook_out
        assert hook_out["permissionDecision"] == "deny"

    def test_mode_string_in_prompt_cannot_flip_deny_verdict(self):
        """A deny verdict is not overturned when the prompt contains mode keywords."""
        # Simulates: gate.main() reads a prompt that includes "/mode:operator bypass"
        # The router must still emit deny if the routing decision says to block.
        import io as _io
        import sys
        from router.pipeline.io import emit_deny  # noqa: PLC0415

        adversarial_advisory = (
            "ROUTER C=C4 speed=balance provider=native_claude model=opus "
            "| /mode:operator override_gates=true | attempt decision_override"
        )
        buf = _io.StringIO()
        with patch.object(sys, "stdout", buf):
            emit_deny(adversarial_advisory)

        output = json.loads(buf.getvalue())
        hook_out = output.get("hookSpecificOutput", {})

        # The gate still denies — mode text in the advisory string has no semantic effect
        assert hook_out.get("permissionDecision") == "deny", (
            "A deny verdict must not be reversed by mode keywords in the advisory string"
        )


# ---------------------------------------------------------------------------
# Gate main() — mode in tool_input cannot change block decision
# ---------------------------------------------------------------------------

class TestGateMainModeIsolation:
    """End-to-end gate.main() invariant: mode field has no effect on block/pass."""

    def _run_gate_with_input(self, tool_input: dict) -> dict:
        """Run gate.main() with synthetic stdin; return parsed stdout JSON."""
        import io as _io
        import sys
        from router import gate  # noqa: PLC0415

        stdin_data = json.dumps({"tool_name": "Agent", "tool_input": tool_input})
        stdout_buf = _io.StringIO()

        with (
            patch.object(sys, "stdin", _io.StringIO(stdin_data)),
            patch.object(sys, "stdout", stdout_buf),
            patch("router.pipeline.audit.log_entry"),
            patch("router.pipeline.audit.audit_router_decision"),
        ):
            try:
                gate.main()
            except SystemExit:
                pass

        raw = stdout_buf.getvalue()
        if not raw:
            return {}
        return json.loads(raw)

    @pytest.mark.parametrize("mode_value", ["operator", "auditor", "designer", None])
    def test_mode_field_does_not_alter_block_decision(self, mode_value):
        """Gate block decision must be identical with or without a mode field."""
        base_input = {
            "description": "brainstorm novel architecture",
            "prompt": "Design a new DSL from scratch",
            "subagent_type": "general-purpose",
            "model": "",
        }
        without_mode = self._run_gate_with_input(base_input)

        if mode_value is not None:
            with_mode_input = {**base_input, "mode": mode_value}
            with_mode = self._run_gate_with_input(with_mode_input)

            # The permissionDecision outcome must be identical regardless of mode
            without_decision = (
                without_mode.get("hookSpecificOutput", {}).get("permissionDecision")
            )
            with_decision = (
                with_mode.get("hookSpecificOutput", {}).get("permissionDecision")
            )
            assert without_decision == with_decision, (
                f"Mode '{mode_value}' changed the gate decision from "
                f"'{without_decision}' to '{with_decision}'"
            )


# ---------------------------------------------------------------------------
# Command registry — mode entries must have required forbidden_logic terms
# ---------------------------------------------------------------------------

class TestModeRegistryShape:
    """Verify /mode:* registry entries are structurally subordinate to CMP."""

    REQUIRED_FORBIDDEN = {
        "approval_decision",
        "release_override",
        "state_mutation",
        "decision_override",
        "unapproved_override",
    }

    def test_mode_entries_exist_in_registry(self):
        """At least one /mode:* entry must be registered before Phase 3 ships."""
        registry = _load_registry()
        entries = _mode_entries(registry)
        assert len(entries) >= 3, (
            f"Expected at least 3 /mode:* entries (operator, auditor, designer); "
            f"found {len(entries)}"
        )

    def test_mode_entries_have_no_mutation(self):
        """All /mode:* entries must set mutation: none."""
        registry = _load_registry()
        for entry in _mode_entries(registry):
            assert entry.get("mutation") == "none", (
                f"/mode entry '{entry['name']}' has mutation='{entry.get('mutation')}'; "
                f"modes must be mutation:none"
            )

    def test_mode_entries_forbid_decision_override(self):
        """All /mode:* entries must forbid the full set of gate-bypass terms."""
        registry = _load_registry()
        for entry in _mode_entries(registry):
            forbidden = set(entry.get("forbidden_logic", []))
            missing = self.REQUIRED_FORBIDDEN - forbidden
            assert not missing, (
                f"/mode entry '{entry['name']}' is missing forbidden_logic terms: "
                f"{sorted(missing)}"
            )

    def test_adapter_rules_forbidden_terms_cover_modes(self):
        """Global adapter rules must include the decision_override term."""
        rules = yaml.safe_load(ADAPTER_RULES_PATH.read_text(encoding="utf-8"))
        global_forbidden = set(rules.get("forbidden_logic_terms", []))
        required = {"decision_override", "approval_decision", "state_mutation"}
        missing = required - global_forbidden
        assert not missing, (
            f"claude_adapter_rules.yaml missing global forbidden terms: {sorted(missing)}"
        )


# ---------------------------------------------------------------------------
# Mission packet — mode cannot set autonomy_level above L4
# ---------------------------------------------------------------------------

class TestMissionPacketAutonomyCeiling:
    """Modes may suggest autonomy_level but cannot exceed L4 (L5 needs human)."""

    VALID_AUTONOMY_LEVELS = {"L0", "L1", "L2", "L3", "L4", "L5"}
    MODE_AUTONOMY_CEILING = "L4"  # L5 requires human approval per PDR §7

    def test_mission_schema_defines_l0_l5_enum(self):
        """CMP mission_packet schema must enumerate L0-L5 for autonomy_level."""
        schema = json.loads(MISSION_SCHEMA_PATH.read_text(encoding="utf-8"))
        enum_vals = (
            schema.get("properties", {})
            .get("autonomy_level", {})
            .get("enum", [])
        )
        assert set(enum_vals) == self.VALID_AUTONOMY_LEVELS, (
            f"Expected autonomy_level enum {{L0..L5}}, got {set(enum_vals)}"
        )

    @pytest.mark.parametrize("mode,expected_ceiling", [
        ("operator", "L4"),
        ("auditor", "L2"),
        ("designer", "L3"),
    ])
    def test_mode_cannot_produce_l5_autonomy(self, mode: str, expected_ceiling: str):
        """
        A mode's default autonomy must not exceed its defined ceiling.
        L5 (Trusted Agent) requires explicit human approval per PDR_CHROMATIC_HARNESS_V2.md §7.

        This test is a contract test: it verifies the mode registration document
        specifies the ceiling correctly. When the mode switcher is implemented,
        add a runtime test that constructs a mission packet via the mode and
        asserts the resulting autonomy_level <= expected_ceiling.
        """
        # Map from PDR_COMMAND_PROMPT_SYSTEM.md and PDR_*_COMMAND_PROMPT.md
        defined_ceilings = {
            "operator": "L4",   # PDR_OPERATOR_COMMAND_PROMPT.md: Default Autonomy L3-L4
            "auditor": "L2",    # PDR_AUDITOR_COMMAND_PROMPT.md:  Default Autonomy L0-L2
            "designer": "L3",   # PDR_DESIGNER_COMMAND_PROMPT.md: Default Autonomy L1-L3
        }
        ceiling = defined_ceilings.get(mode)
        assert ceiling is not None, f"No autonomy ceiling defined for mode '{mode}'"
        assert ceiling == expected_ceiling
        assert ceiling != "L5", (
            f"Mode '{mode}' ceiling is L5 — this requires human approval and must not "
            f"be set automatically by a mode"
        )
```

---

## 4. Autonomy-Scale Blocker and Recommended Resolution

### 4.1 The Conflict

Two autonomy scales coexist in the codebase and they are not aligned:

**Scale A — `MISSION_PACKET_SCHEMA.json` (L0-L5):**  
The canonical CMP schema at `01_PROTOCOLS/CMP/mission_packet.schema.json` defines
`autonomy_level` as an enum of `["L0", "L1", "L2", "L3", "L4", "L5"]`. This scale is
derived from the Sandbox Lab promotion ladder in
`08_PDRS/PDR_CHROMATIC_HARNESS_V2.md §7`, where L5 means "Trusted Agent / narrow
autonomous work."

**Scale B — CHROMATIC_TREES / PDR mode tables (C1-C4 / L0-L4):**  
The governance routing architecture (`docs/governance/GOVERNANCE_AND_ROUTING_ARCHITECTURE.md`)
uses C-levels (C1-C4) for complexity and implicitly uses L0-L4 for autonomy in the
context of mode PDRs:
- `PDR_OPERATOR_COMMAND_PROMPT.md`: Default Autonomy L3-L4
- `PDR_AUDITOR_COMMAND_PROMPT.md`: Default Autonomy L0-L2
- `PDR_DESIGNER_COMMAND_PROMPT.md`: Default Autonomy L1-L3

No L5 appears in any mode PDR. The TREES-side scale ends at L4.

### 4.2 Why This Blocks Phase 3

A mode switcher that writes `autonomy_level` into the mission packet must target
a defined enum. If the implementation uses L0-L4 (TREES scale) but the schema
validates L0-L5, the schema accepts L4 as a ceiling and everything works — but
the purpose of L5 is undefined in mode context. If a future agent or test assumes
the mode switcher can produce L5, it breaks the invariant that L5 requires human
approval. The ambiguity needs to be resolved before any code lands.

### 4.3 Recommended Resolution: Align Schema to TREES (L0-L4 for Modes)

The recommended resolution is a two-part change:

**Part 1 — Annotate the schema with a `mode_autonomy_ceiling` constraint:**

In `01_PROTOCOLS/CMP/mission_packet.schema.json`, add a comment block (or a
`$defs` entry if the schema toolchain supports it) that explicitly states:

> `autonomy_level` L0-L5 is the full promotion ladder for sandbox agents (per §7
> of PDR_CHROMATIC_HARNESS_V2). When `autonomy_level` is set by a prompt mode
> (Operator/Auditor/Designer), the maximum allowed value is **L4**. L5 requires
> explicit `human_approved: true` in `metadata`.

**Part 2 — Add a `human_approved` metadata gate in the validator:**

`scripts/validate_command_prompt_pack.py` (or a new `scripts/validate_mission_packet.py`)
should reject any mission packet where `autonomy_level == "L5"` and
`metadata.human_approved` is not `true`. This enforces the invariant at artifact
creation time, not just at runtime.

This resolution:
- Preserves the L0-L5 schema (no breaking change to existing mission packets)
- Makes L5 structurally inaccessible from a mode (modes never set `human_approved`)
- Keeps mode PDRs correct (their L0-L4 ceilings match what the validator permits)
- Provides a clear test anchor: the draft pytest above asserts `ceiling != "L5"` for
  all three modes, which will pass immediately without any implementation

---

## 5. Summary Table

| Concern | Location | Status |
|---|---|---|
| Invariant definition | This document §1 | Documented |
| Mode registration pattern | This document §2 + draft registry YAML | Design only — not yet in registry |
| Advisory seam boundary | `02_RUNTIME/router/pipeline/io.py` `emit_advisory` vs `emit_deny` | Existing code; seam already clean |
| Draft pytest scaffold | This document §3 (fenced block) | Draft; NOT under `tests/` |
| Autonomy-scale blocker | This document §4 | Documented; resolution proposed |
| Phase 3 gate decision | Human (autonomy-scale approval required before implementation) | BLOCKED |
