"""Unit tests for scripts/validate_workflow_token_governance.py.

Constructs a synthetic .claude/workflows/ directory via monkeypatching so no
actual workflow files are required. Tests happy path (exit 0) and each failure
mode (missing file, forbidden pattern, missing governance doc, missing HEAVY bak).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "validate_workflow_token_governance.py"

_spec = importlib.util.spec_from_file_location("validate_workflow_token_governance", _SCRIPT)
vtg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vtg)  # type: ignore[union-attr]

# Canonical lite workflow names (from the script)
LITE = ("ship.js", "qa.js", "close-issue.js", "go.js", "hotfix.js")

# Minimal compliant workflow content
_COMPLIANT_CONTENT = 'import "_budget.js";\nassertion: assertBudgetAllows();\n'


def _build_compliant_workflows(base: Path) -> Path:
    """Write compliant lite workflows + HEAVY bak + governance docs under base."""
    wf = base / ".claude" / "workflows"
    wf.mkdir(parents=True)
    for name in LITE:
        (wf / name).write_text(_COMPLIANT_CONTENT, encoding="utf-8")
    (wf / "ship.HEAVY.js.bak").write_text("// archived", encoding="utf-8")

    gov = base / "docs" / "governance"
    gov.mkdir(parents=True)
    for doc in ("00_WORKFLOW_GOVERNANCE.md", "HANDOFF_PACKET_SCHEMA.md", "COST_INCIDENT_TEMPLATE.md"):
        (gov / doc).write_text("# doc", encoding="utf-8")
    return wf


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_main_passes_with_compliant_setup(tmp_path, monkeypatch):
    _build_compliant_workflows(tmp_path)
    monkeypatch.setattr(vtg, "WORKFLOWS", tmp_path / ".claude" / "workflows")
    monkeypatch.setattr(vtg, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_workflow_token_governance.py"])
    rc = vtg.main()
    assert rc == 0


# ---------------------------------------------------------------------------
# Missing lite workflow
# ---------------------------------------------------------------------------


def test_main_fails_when_workflow_file_missing(tmp_path, monkeypatch):
    _build_compliant_workflows(tmp_path)
    # Remove one workflow file
    (tmp_path / ".claude" / "workflows" / "ship.js").unlink()
    monkeypatch.setattr(vtg, "WORKFLOWS", tmp_path / ".claude" / "workflows")
    monkeypatch.setattr(vtg, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_workflow_token_governance.py"])
    rc = vtg.main()
    assert rc == 1


# ---------------------------------------------------------------------------
# Missing _budget.js import / assertBudgetAllows
# ---------------------------------------------------------------------------


def test_main_fails_when_budget_import_missing(tmp_path, monkeypatch):
    _build_compliant_workflows(tmp_path)
    # Overwrite ship.js without the required import
    (tmp_path / ".claude" / "workflows" / "ship.js").write_text("// no budget import\n", encoding="utf-8")
    monkeypatch.setattr(vtg, "WORKFLOWS", tmp_path / ".claude" / "workflows")
    monkeypatch.setattr(vtg, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_workflow_token_governance.py"])
    rc = vtg.main()
    assert rc == 1


# ---------------------------------------------------------------------------
# Forbidden discovery.slice(4000) pattern
# ---------------------------------------------------------------------------


def test_main_fails_when_forbidden_pattern_present(tmp_path, monkeypatch):
    _build_compliant_workflows(tmp_path)
    content = _COMPLIANT_CONTENT + "\ndiscovery.slice(4000);\n"
    (tmp_path / ".claude" / "workflows" / "qa.js").write_text(content, encoding="utf-8")
    monkeypatch.setattr(vtg, "WORKFLOWS", tmp_path / ".claude" / "workflows")
    monkeypatch.setattr(vtg, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_workflow_token_governance.py"])
    rc = vtg.main()
    assert rc == 1


# ---------------------------------------------------------------------------
# Missing HEAVY bak file
# ---------------------------------------------------------------------------


def test_main_fails_when_heavy_bak_missing(tmp_path, monkeypatch):
    _build_compliant_workflows(tmp_path)
    (tmp_path / ".claude" / "workflows" / "ship.HEAVY.js.bak").unlink()
    monkeypatch.setattr(vtg, "WORKFLOWS", tmp_path / ".claude" / "workflows")
    monkeypatch.setattr(vtg, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_workflow_token_governance.py"])
    rc = vtg.main()
    assert rc == 1


# ---------------------------------------------------------------------------
# Missing governance docs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_doc",
    ["00_WORKFLOW_GOVERNANCE.md", "HANDOFF_PACKET_SCHEMA.md", "COST_INCIDENT_TEMPLATE.md"],
)
def test_main_fails_when_governance_doc_missing(tmp_path, monkeypatch, missing_doc):
    _build_compliant_workflows(tmp_path)
    (tmp_path / "docs" / "governance" / missing_doc).unlink()
    monkeypatch.setattr(vtg, "WORKFLOWS", tmp_path / ".claude" / "workflows")
    monkeypatch.setattr(vtg, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_workflow_token_governance.py"])
    rc = vtg.main()
    assert rc == 1


# ---------------------------------------------------------------------------
# ~/.claude/projects guard
# ---------------------------------------------------------------------------


def test_main_fails_when_projects_referenced_without_guard(tmp_path, monkeypatch):
    _build_compliant_workflows(tmp_path)
    bad_content = _COMPLIANT_CONTENT + "\nconst logs = glob('~/.claude/projects/**');\n"
    (tmp_path / ".claude" / "workflows" / "go.js").write_text(bad_content, encoding="utf-8")
    monkeypatch.setattr(vtg, "WORKFLOWS", tmp_path / ".claude" / "workflows")
    monkeypatch.setattr(vtg, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_workflow_token_governance.py"])
    rc = vtg.main()
    assert rc == 1


def test_main_passes_when_projects_ref_has_forbidden_guard(tmp_path, monkeypatch):
    """If '~/.claude/projects' appears but 'forbidden' is also in the text, it's allowed."""
    _build_compliant_workflows(tmp_path)
    guarded_content = _COMPLIANT_CONTENT + "\n// forbidden: do not use ~/.claude/projects\n"
    (tmp_path / ".claude" / "workflows" / "go.js").write_text(guarded_content, encoding="utf-8")
    monkeypatch.setattr(vtg, "WORKFLOWS", tmp_path / ".claude" / "workflows")
    monkeypatch.setattr(vtg, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["validate_workflow_token_governance.py"])
    rc = vtg.main()
    assert rc == 0
