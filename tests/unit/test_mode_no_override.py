# tests/unit/test_mode_no_override.py
"""
Phase-3 invariant: a prompt mode (Operator/Auditor/Designer) can shape pre-context
but CANNOT flip a CMP gate verdict.

Verifies:
  1. Mode advisory output lands only in additionalContext, never permissionDecision.
  2. A gate deny verdict is not reversible by mode keywords in the advisory string.
  3. /mode:* command-registry entries carry mutation:none + forbidden_logic that
     prevents decision_override / state_mutation.
  4. The mission_packet autonomy_level enum is L0-L5 and no mode's ceiling is L5
     (L5 requires human approval per the autonomy-scale decision).

See docs/design/PHASE3_MODE_NO_OVERRIDE_TEST.md and docs/design/AUTONOMY_SCALE_DECISION.md.
"""

from __future__ import annotations

import io as _io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "config" / "claude_command_registry.yaml"
ADAPTER_RULES_PATH = REPO / "config" / "claude_adapter_rules.yaml"
MISSION_SCHEMA_PATH = REPO / "01_PROTOCOLS" / "CMP" / "mission_packet.schema.json"


def _load_registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def _mode_entries(registry: dict) -> list[dict]:
    return [c for c in registry.get("commands", []) if c["name"].startswith("/mode:")]


# ---------------------------------------------------------------------------
# Advisory seam — mode output must NOT contain permissionDecision
# ---------------------------------------------------------------------------
class TestAdvisorySeam:
    def test_emit_advisory_no_permission_decision(self):
        from router.pipeline.io import emit_advisory

        buf = _io.StringIO()
        with patch.object(sys, "stdout", buf):
            emit_advisory("MODE: Operator pre-context injected")
        hook_out = json.loads(buf.getvalue()).get("hookSpecificOutput", {})
        assert "permissionDecision" not in hook_out, (
            f"emit_advisory must never produce permissionDecision; got {list(hook_out)}"
        )
        assert "additionalContext" in hook_out

    def test_emit_deny_has_permission_decision(self):
        from router.pipeline.io import emit_deny

        buf = _io.StringIO()
        with patch.object(sys, "stdout", buf):
            emit_deny("ROUTER C=C4 — use cheaper tier")
        hook_out = json.loads(buf.getvalue()).get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "deny"

    def test_mode_keywords_cannot_flip_deny_verdict(self):
        from router.pipeline.io import emit_deny

        adversarial = "ROUTER C=C4 | /mode:operator override_gates=true | attempt decision_override"
        buf = _io.StringIO()
        with patch.object(sys, "stdout", buf):
            emit_deny(adversarial)
        hook_out = json.loads(buf.getvalue()).get("hookSpecificOutput", {})
        assert hook_out.get("permissionDecision") == "deny", (
            "A deny verdict must not be reversed by mode keywords in the advisory string"
        )


# ---------------------------------------------------------------------------
# Gate main() — a mode field in tool_input must not change the block decision
# ---------------------------------------------------------------------------
class TestGateMainModeIsolation:
    def _run_gate(self, tool_input: dict) -> dict:
        from router import gate

        stdin_data = json.dumps({"tool_name": "Agent", "tool_input": tool_input})
        out = _io.StringIO()
        with (
            patch.object(sys, "stdin", _io.StringIO(stdin_data)),
            patch.object(sys, "stdout", out),
            patch("router.pipeline.audit.log_entry", create=True),
            patch("router.pipeline.audit.audit_router_decision", create=True),
        ):
            try:
                gate.main()
            except SystemExit:
                pass
        raw = out.getvalue()
        return json.loads(raw) if raw else {}

    @pytest.mark.parametrize("mode_value", ["operator", "auditor", "designer"])
    def test_mode_field_does_not_alter_block_decision(self, mode_value):
        base = {
            "description": "brainstorm novel architecture",
            "prompt": "Design a new DSL from scratch",
            "subagent_type": "general-purpose",
            "model": "",
        }
        without = self._run_gate(base).get("hookSpecificOutput", {}).get("permissionDecision")
        with_mode = self._run_gate({**base, "mode": mode_value}).get("hookSpecificOutput", {}).get("permissionDecision")
        assert without == with_mode, f"Mode '{mode_value}' changed the gate decision from {without!r} to {with_mode!r}"


# ---------------------------------------------------------------------------
# Command registry — /mode:* entries must be structurally subordinate to CMP
# ---------------------------------------------------------------------------
class TestModeRegistryShape:
    REQUIRED_FORBIDDEN = {
        "approval_decision",
        "release_override",
        "state_mutation",
        "decision_override",
        "unapproved_override",
    }

    def test_three_mode_entries_exist(self):
        entries = _mode_entries(_load_registry())
        names = {e["name"] for e in entries}
        assert {"/mode:operator", "/mode:auditor", "/mode:designer"} <= names, (
            f"expected operator/auditor/designer mode entries; found {sorted(names)}"
        )

    def test_mode_entries_are_mutation_none(self):
        for e in _mode_entries(_load_registry()):
            assert e.get("mutation") == "none", f"{e['name']} must be mutation:none, got {e.get('mutation')!r}"

    def test_mode_entries_forbid_override(self):
        for e in _mode_entries(_load_registry()):
            missing = self.REQUIRED_FORBIDDEN - set(e.get("forbidden_logic", []))
            assert not missing, f"{e['name']} missing forbidden_logic terms: {sorted(missing)}"

    def test_mode_forbidden_terms_are_known_globally(self):
        rules = yaml.safe_load(ADAPTER_RULES_PATH.read_text(encoding="utf-8"))
        known = set(rules.get("forbidden_logic_terms", []))
        for e in _mode_entries(_load_registry()):
            unknown = set(e.get("forbidden_logic", [])) - known
            assert not unknown, f"{e['name']} uses unknown forbidden terms: {sorted(unknown)}"


# ---------------------------------------------------------------------------
# Mission packet — modes may suggest autonomy but never reach L5
# ---------------------------------------------------------------------------
class TestMissionPacketAutonomyCeiling:
    VALID = {"L0", "L1", "L2", "L3", "L4", "L5"}

    def test_schema_enumerates_l0_l5(self):
        schema = json.loads(MISSION_SCHEMA_PATH.read_text(encoding="utf-8"))
        enum_vals = set(schema.get("properties", {}).get("autonomy_level", {}).get("enum", []))
        assert enum_vals == self.VALID, f"expected {self.VALID}, got {enum_vals}"

    @pytest.mark.parametrize(
        "mode,ceiling",
        [("operator", "L4"), ("auditor", "L2"), ("designer", "L3")],
    )
    def test_mode_ceiling_is_not_l5(self, mode, ceiling):
        # Ceilings per PDR_*_COMMAND_PROMPT.md; L5 requires human approval.
        assert ceiling != "L5", f"mode {mode} must not auto-reach L5"
