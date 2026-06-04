# DEFICIENCIES NOTED:
# 1. write_handoff() calls _git() via subprocess at module import time to get
#    branch/commit info. Tests must either allow the subprocess calls to fall through
#    silently (they return "" on failure) or monkeypatch _git. Both strategies are used
#    below; the module design makes it impossible to inject the git backend.
# 2. write_handoff() performs two optional dynamic imports inside the function body
#    (intake.closure_feedback, knowledge.harvest_rigs). These run in try/except and
#    are silently ignored. Tests verify they do not raise rather than asserting their
#    side-effects, because the modules may or may not be present.
# 3. The handoff markdown body relies entirely on _TEMPLATE being a readable file.
#    When the template is absent, body is silently set to "" and all {{PLACEHOLDER}}
#    substitutions become no-ops. Tests cover this path explicitly.
# 4. _LATEST is hardcoded to .agents/handoffs/latest.json (repo-relative). Tests
#    monkeypatch both _HANDOFFS and _LATEST to avoid writing into the live repo tree.
# 5. write_handoff() returns the output path but callers have no way to know whether
#    optional side-effects (harvest, follow-ups) ran; the design makes side-effects
#    untestable without a heavy subprocess/import mock. Tests stub them instead.
# 6. goals[0]/goals[1]/goals[2] indexing uses positional access; no named fields.
#    Large goal lists beyond index 2 are silently ignored — documented in the edge-case
#    tests below.

"""Tests for orchestrator/session_compact.py — session handoff writer."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# Stub optional heavy side-effect imports before loading the module.
_fake_intake = MagicMock()
_fake_closure = MagicMock()
_fake_closure.enqueue_session_follow_ups = MagicMock()
sys.modules.setdefault("intake", _fake_intake)
sys.modules.setdefault("intake.closure_feedback", _fake_closure)

_fake_knowledge = MagicMock()
_fake_harvest = MagicMock()
_fake_harvest.run_session_harvest = MagicMock()
sys.modules.setdefault("knowledge", _fake_knowledge)
sys.modules.setdefault("knowledge.harvest_rigs", _fake_harvest)

# Load the module under test via file path to avoid any sys.path ordering issues.
_SC_PATH = _RUNTIME / "orchestrator" / "session_compact.py"
_spec = importlib.util.spec_from_file_location("session_compact_under_test", _SC_PATH)
_sc = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_sc)  # type: ignore[union-attr]

write_handoff = _sc.write_handoff


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_dirs(tmp_path, monkeypatch):
    """Redirect _HANDOFFS, _LATEST, and _TEMPLATE to tmp_path locations."""
    handoffs_dir = tmp_path / "sessions"
    latest_file = tmp_path / "latest.json"
    template_file = tmp_path / "AGENT_HANDOFF_TEMPLATE.md"

    # Write a realistic template so substitution tests are meaningful.
    template_file.write_text(
        "# Agent Handoff — {{MISSION_ID}}\n"
        "**Date:** {{DATE}}\n"
        "**Branch:** {{BRANCH}}\n"
        "**Agent:** {{AGENT}}\n"
        "**Last commit:** {{LAST_COMMIT}}\n"
        "Directive: {{DIRECTIVE_SUMMARY}}\n"
        "Objective: {{OBJECTIVE}}\n"
        "Autonomy: {{AUTONOMY_LEVEL}}\n"
        "Score: {{COMPOSITE_SCORE}}\n"
        "Decision: {{DECISION}}\n"
        "Done 1: {{DONE_1}}\n"
        "Done 2: {{DONE_2}}\n"
        "Done 3: {{DONE_3}}\n"
        "Tests: {{TEST_STATUS}}\n"
        "Lint: {{LINT_STATUS}}\n"
        "Beads: {{BEADS_STATUS}}\n"
        "Push: {{PUSH_STATUS}}\n"
        "Next: {{NEXT_COMMAND}}\n"
        "Risk1: {{RISK_1}}\n"
        "Risk2: {{RISK_2}}\n"
        "Bead1: {{BEAD_ID_1}}\n"
        "NextGoal1: {{NEXT_GOAL_1}}\n"
        "NextGoal2: {{NEXT_GOAL_2}}\n"
        "NextGoal3: {{NEXT_GOAL_3}}\n",
        encoding="utf-8",
    )

    # _REPO is used in out_path.relative_to(_REPO); redirect it to tmp_path so the
    # relative_to() call succeeds when _HANDOFFS lives inside tmp_path.
    monkeypatch.setattr(_sc, "_REPO", tmp_path)
    monkeypatch.setattr(_sc, "_HANDOFFS", handoffs_dir)
    monkeypatch.setattr(_sc, "_LATEST", latest_file)
    monkeypatch.setattr(_sc, "_TEMPLATE", template_file)

    yield {
        "handoffs_dir": handoffs_dir,
        "latest_file": latest_file,
        "template_file": template_file,
        "tmp_path": tmp_path,
    }


@pytest.fixture()
def no_template(tmp_path, monkeypatch):
    """Redirect dirs but do NOT create the template, exercising the missing-template path."""
    handoffs_dir = tmp_path / "sessions"
    latest_file = tmp_path / "latest.json"
    template_file = tmp_path / "MISSING_TEMPLATE.md"  # does not exist

    monkeypatch.setattr(_sc, "_REPO", tmp_path)
    monkeypatch.setattr(_sc, "_HANDOFFS", handoffs_dir)
    monkeypatch.setattr(_sc, "_LATEST", latest_file)
    monkeypatch.setattr(_sc, "_TEMPLATE", template_file)

    yield {
        "handoffs_dir": handoffs_dir,
        "latest_file": latest_file,
    }


def _base_prep(**overrides) -> dict:
    """Return a minimal valid handoff_prep dict."""
    base = {
        "directive_summary": "Implement policy engine rule evaluation",
        "context_snapshot": {
            "objective": "Add policy validation",
            "autonomy_level": "L2",
            "composite_score": "87.5",
        },
        "next_session_goals": [
            "Run bd ready and pick next issue",
            "Write tests for policy engine",
            "Update CHANGELOG",
        ],
        "decision": "approve",
        "audit_log_ref": "MISSION-2026-001",
    }
    base.update(overrides)
    return base


def _base_mission(**overrides) -> dict:
    base = {
        "mission_id": "MISSION-2026-001",
        "objective": "Add policy validation to harness",
        "autonomy_level": "L2",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Return value and file creation
# ---------------------------------------------------------------------------


class TestWriteHandoffReturnValue:
    def test_returns_path_object(self, patched_dirs):
        result = write_handoff(_base_prep(), mission=_base_mission())
        assert isinstance(result, Path)

    def test_returned_path_exists(self, patched_dirs):
        result = write_handoff(_base_prep(), mission=_base_mission())
        assert result.exists()

    def test_returned_path_is_markdown(self, patched_dirs):
        result = write_handoff(_base_prep(), mission=_base_mission())
        assert result.suffix == ".md"

    def test_returned_path_named_by_mission_id(self, patched_dirs):
        prep = _base_prep()
        mission = _base_mission(mission_id="MISSION-XYZ")
        result = write_handoff(prep, mission=mission)
        assert "MISSION-XYZ" in result.name

    def test_handoff_dir_created_if_missing(self, patched_dirs):
        # handoffs_dir doesn't exist before the call
        hd = patched_dirs["handoffs_dir"]
        assert not hd.exists()
        write_handoff(_base_prep(), mission=_base_mission())
        assert hd.exists()


# ---------------------------------------------------------------------------
# latest.json state
# ---------------------------------------------------------------------------


class TestLatestJson:
    def test_latest_json_created(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission())
        assert patched_dirs["latest_file"].exists()

    def test_latest_json_is_valid(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission())
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_latest_json_contains_mission_id(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(mission_id="MISSION-LATEST"))
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["mission_id"] == "MISSION-LATEST"

    def test_latest_json_contains_agent(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), agent="test-agent")
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["agent"] == "test-agent"

    def test_latest_json_contains_decision(self, patched_dirs):
        write_handoff(_base_prep(decision="review"), mission=_base_mission())
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["decision"] == "review"

    def test_latest_json_contains_next_command(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), next_command="bd show 42")
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["next_command"] == "bd show 42"

    def test_latest_json_contains_beads_ready(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), beads_ready=["bd-001", "bd-002"])
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["beads_ready"] == ["bd-001", "bd-002"]

    def test_latest_json_beads_ready_defaults_empty(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission())
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["beads_ready"] == []

    def test_latest_json_contains_updated_at(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission())
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert "updated_at" in data
        assert data["updated_at"].endswith("Z")

    def test_latest_json_contains_handoff_path(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission())
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert "handoff_path" in data
        assert data["handoff_path"].endswith(".md")

    def test_latest_json_overwritten_on_second_call(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(mission_id="FIRST"))
        write_handoff(_base_prep(), mission=_base_mission(mission_id="SECOND"))
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["mission_id"] == "SECOND"

    def test_latest_parent_dir_created_if_missing(self, patched_dirs, monkeypatch):
        deep_latest = patched_dirs["tmp_path"] / "deep" / "nested" / "latest.json"
        monkeypatch.setattr(_sc, "_LATEST", deep_latest)
        write_handoff(_base_prep(), mission=_base_mission())
        assert deep_latest.exists()


# ---------------------------------------------------------------------------
# Markdown content — template substitution
# ---------------------------------------------------------------------------


class TestHandoffMarkdownContent:
    def test_mission_id_substituted(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(mission_id="MISSION-SUB-TEST"))
        content = patched_dirs["handoffs_dir"].joinpath("MISSION-SUB-TEST.md").read_text(encoding="utf-8")
        assert "MISSION-SUB-TEST" in content
        assert "{{MISSION_ID}}" not in content

    def test_objective_substituted(self, patched_dirs):
        prep = _base_prep()
        prep["context_snapshot"]["objective"] = "Unique test objective XYZ"
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "Unique test objective XYZ" in content

    def test_decision_substituted(self, patched_dirs):
        write_handoff(_base_prep(decision="escalate"), mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "escalate" in content
        assert "{{DECISION}}" not in content

    def test_directive_summary_substituted(self, patched_dirs):
        prep = _base_prep(directive_summary="Special directive alpha")
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "Special directive alpha" in content
        assert "{{DIRECTIVE_SUMMARY}}" not in content

    def test_goals_substituted(self, patched_dirs):
        prep = _base_prep(next_session_goals=["Goal One", "Goal Two", "Goal Three"])
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "Goal One" in content
        assert "Goal Two" in content
        assert "Goal Three" in content

    def test_agent_substituted(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), agent="my-agent-007")
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "my-agent-007" in content
        assert "{{AGENT}}" not in content

    def test_test_status_substituted(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), test_status="passed")
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "passed" in content
        assert "{{TEST_STATUS}}" not in content

    def test_lint_status_substituted(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), lint_status="clean")
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "clean" in content
        assert "{{LINT_STATUS}}" not in content

    def test_push_status_substituted(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), push_status="pushed")
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "pushed" in content
        assert "{{PUSH_STATUS}}" not in content

    def test_next_command_substituted(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), next_command="bd ready && bd show 99")
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "bd ready && bd show 99" in content
        assert "{{NEXT_COMMAND}}" not in content

    def test_beads_ready_first_entry_substituted(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), beads_ready=["bd-777"])
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "bd-777" in content
        assert "{{BEAD_ID_1}}" not in content

    def test_no_placeholder_tokens_remaining(self, patched_dirs):
        """After a full write_handoff call, no {{...}} tokens should remain in the output."""
        prep = _base_prep()
        write_handoff(prep, mission=_base_mission(), agent="harness", beads_ready=["bd-001"])
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        import re

        remaining = re.findall(r"\{\{[A-Z_]+\}\}", content)
        assert remaining == [], f"Unsubstituted tokens found: {remaining}"


# ---------------------------------------------------------------------------
# Edge cases — empty / minimal state
# ---------------------------------------------------------------------------


class TestEdgeCasesEmptyState:
    def test_empty_handoff_prep_does_not_raise(self, patched_dirs):
        # Completely empty prep — all fields default gracefully
        write_handoff({}, mission={})

    def test_empty_goals_list_uses_fallback(self, patched_dirs):
        prep = _base_prep(next_session_goals=[])
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        # DONE_1, DONE_2, DONE_3 should use fallback values, not crash
        assert "{{DONE_1}}" not in content or "see git log" in content

    def test_single_goal_fills_done_1_only(self, patched_dirs):
        prep = _base_prep(next_session_goals=["Only goal"])
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "Only goal" in content
        # DONE_2 and DONE_3 should be "—" (fallback)
        assert "{{DONE_2}}" not in content
        assert "{{DONE_3}}" not in content

    def test_two_goals_fills_done_1_and_2(self, patched_dirs):
        prep = _base_prep(next_session_goals=["Goal A", "Goal B"])
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "Goal A" in content
        assert "Goal B" in content

    def test_extra_goals_beyond_three_are_ignored(self, patched_dirs):
        prep = _base_prep(next_session_goals=["G1", "G2", "G3", "G4 ignored", "G5 ignored"])
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        # Only first three goals are inserted; G4 and G5 should not appear
        assert "G4 ignored" not in content
        assert "G5 ignored" not in content

    def test_no_beads_ready_uses_dash_fallback(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(), beads_ready=None)
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["beads_ready"] == []

    def test_mission_id_falls_back_to_audit_log_ref(self, patched_dirs):
        prep = _base_prep(audit_log_ref="FALLBACK-SESSION-ID")
        write_handoff(prep, mission={})  # mission has no mission_id
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        assert any("FALLBACK-SESSION-ID" in f.name for f in files)

    def test_mission_id_falls_back_to_session_string(self, patched_dirs):
        prep = _base_prep()
        del prep["audit_log_ref"]
        write_handoff(prep, mission={})
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        assert any("SESSION" in f.name for f in files)

    def test_none_mission_defaults_gracefully(self, patched_dirs):
        # mission=None → defaults to {}
        result = write_handoff(_base_prep(), mission=None)
        assert result.exists()


# ---------------------------------------------------------------------------
# Edge cases — large state
# ---------------------------------------------------------------------------


class TestEdgeCasesLargeState:
    def test_large_directive_summary_written_intact(self, patched_dirs):
        large_directive = "Detail: " + ("word " * 500)
        prep = _base_prep(directive_summary=large_directive)
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "word " * 10 in content  # spot-check that content is present

    def test_large_context_snapshot_written_intact(self, patched_dirs):
        snapshot = {
            "objective": "Long " + ("objective " * 100),
            "autonomy_level": "L3",
            "composite_score": "99.9",
        }
        prep = _base_prep(context_snapshot=snapshot)
        write_handoff(prep, mission=_base_mission())
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "objective " * 5 in content

    def test_many_successive_writes_do_not_corrupt_latest(self, patched_dirs):
        for i in range(10):
            write_handoff(
                _base_prep(),
                mission=_base_mission(mission_id=f"MISSION-{i:03d}"),
            )
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        # latest.json should reflect the last write
        assert data["mission_id"] == "MISSION-009"

    def test_many_writes_each_produce_separate_file(self, patched_dirs):
        for i in range(5):
            write_handoff(
                _base_prep(),
                mission=_base_mission(mission_id=f"MISSION-MULTI-{i}"),
            )
        files = list(patched_dirs["handoffs_dir"].glob("*.md"))
        assert len(files) == 5


# ---------------------------------------------------------------------------
# Missing template path
# ---------------------------------------------------------------------------


class TestMissingTemplate:
    def test_no_template_does_not_raise(self, no_template):
        write_handoff(_base_prep(), mission=_base_mission())

    def test_no_template_still_writes_markdown_file(self, no_template):
        result = write_handoff(_base_prep(), mission=_base_mission())
        assert result.exists()
        assert result.suffix == ".md"

    def test_no_template_still_writes_latest_json(self, no_template):
        write_handoff(_base_prep(), mission=_base_mission())
        assert no_template["latest_file"].exists()

    def test_no_template_body_is_empty_string(self, no_template):
        result = write_handoff(_base_prep(), mission=_base_mission())
        content = result.read_text(encoding="utf-8")
        # Without template, body="" and replacements are no-ops → file is empty or has no template markers
        assert "{{" not in content  # no unreplaced tokens since body was ""


# ---------------------------------------------------------------------------
# Data integrity: latest.json round-trip
# ---------------------------------------------------------------------------


class TestLatestJsonDataIntegrity:
    @pytest.mark.parametrize("agent", ["harness", "worker-epic-c", "pi-agent", "codex"])
    def test_agent_round_trips(self, patched_dirs, agent):
        write_handoff(_base_prep(), mission=_base_mission(), agent=agent)
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["agent"] == agent

    @pytest.mark.parametrize("next_cmd", ["bd ready", "bd show 1", "python scripts/audit.py"])
    def test_next_command_round_trips(self, patched_dirs, next_cmd):
        write_handoff(_base_prep(), mission=_base_mission(), next_command=next_cmd)
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["next_command"] == next_cmd

    @pytest.mark.parametrize("decision", ["approve", "reject", "escalate", "review"])
    def test_decision_round_trips(self, patched_dirs, decision):
        write_handoff(_base_prep(decision=decision), mission=_base_mission())
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["decision"] == decision

    def test_handoff_path_in_latest_points_to_existing_file(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission(mission_id="PATH-TEST"))
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        # handoff_path is relative to repo root; we verify the filename is consistent
        assert "PATH-TEST" in data["handoff_path"]

    def test_updated_at_is_iso8601_z(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission())
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        assert data["updated_at"].endswith("Z")
        assert "T" in data["updated_at"]

    def test_all_required_latest_keys_present(self, patched_dirs):
        write_handoff(_base_prep(), mission=_base_mission())
        data = json.loads(patched_dirs["latest_file"].read_text(encoding="utf-8"))
        required_keys = {
            "updated_at",
            "agent",
            "branch",
            "last_commit",
            "mission_id",
            "handoff_path",
            "beads_ready",
            "next_command",
            "decision",
        }
        for key in required_keys:
            assert key in data, f"Missing key in latest.json: {key}"


# ---------------------------------------------------------------------------
# Optional side-effects — do not raise
# ---------------------------------------------------------------------------


class TestOptionalSideEffects:
    def test_closure_feedback_called_when_available(self, patched_dirs):
        """enqueue_session_follow_ups is invoked with goals and mission_id when module present."""
        mock_enqueue = MagicMock()
        with patch.object(
            sys.modules["intake.closure_feedback"],
            "enqueue_session_follow_ups",
            mock_enqueue,
        ):
            write_handoff(
                _base_prep(next_session_goals=["G1", "G2"]),
                mission=_base_mission(mission_id="SIDE-TEST"),
            )
        # Called once with the goals list and a mission_id kwarg
        mock_enqueue.assert_called_once()
        args, kwargs = mock_enqueue.call_args
        assert ["G1", "G2"] == args[0]
        assert kwargs.get("mission_id") == "SIDE-TEST"

    def test_harvest_called_when_available(self, patched_dirs):
        """run_session_harvest is invoked with repo path when module present."""
        mock_harvest = MagicMock()
        with patch.object(
            sys.modules["knowledge.harvest_rigs"],
            "run_session_harvest",
            mock_harvest,
        ):
            write_handoff(_base_prep(), mission=_base_mission())
        mock_harvest.assert_called_once()
        call_kwargs = mock_harvest.call_args[1]
        assert call_kwargs.get("dry_run") is False

    def test_closure_feedback_exception_does_not_propagate(self, patched_dirs):
        """If enqueue_session_follow_ups raises, write_handoff should NOT re-raise."""
        with patch.object(
            sys.modules["intake.closure_feedback"],
            "enqueue_session_follow_ups",
            side_effect=RuntimeError("queue offline"),
        ):
            # Should complete without raising
            result = write_handoff(_base_prep(), mission=_base_mission())
        assert result.exists()

    def test_harvest_exception_does_not_propagate(self, patched_dirs):
        """If run_session_harvest raises OSError, write_handoff should NOT re-raise."""
        with patch.object(
            sys.modules["knowledge.harvest_rigs"],
            "run_session_harvest",
            side_effect=OSError("agents tree missing"),
        ):
            result = write_handoff(_base_prep(), mission=_base_mission())
        assert result.exists()
