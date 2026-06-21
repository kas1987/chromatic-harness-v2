"""Tests for harness_swot.py — SWOT analysis generator.

All tests are network-free and filesystem-isolated via tmp_path.
The module's HARNESS_ROOT and REPORT_FILE globals are patched so
production paths are never touched.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "harness_swot.py"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _load(harness_root: Path | None = None):
    """Load harness_swot as an isolated module.

    If harness_root is given the module's HARNESS_ROOT, REPORT_DIR, and
    REPORT_FILE are patched to point at the supplied tmp directory so no
    production files are read or written.
    """
    mod_name = f"harness_swot_{id(harness_root)}"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT)
    assert spec and spec.loader, f"Could not load {SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    if harness_root is not None:
        mod.HARNESS_ROOT = harness_root
        mod.REPORT_DIR = harness_root / "05_REPORTS"
        mod.REPORT_FILE = harness_root / "05_REPORTS" / "HARNESS_SWOT_REPORT.md"

    return mod


# ---------------------------------------------------------------------------
# Minimal fixture factories
# ---------------------------------------------------------------------------


def _minimal_strengths() -> dict:
    return {
        "ci_workflow_count": 2,
        "ci_workflows": ["ci.yml", "deploy.yml"],
        "governance_docs_found": ["README.md", "CLAUDE.md"],
        "governance_docs_missing": ["pytest.ini"],
        "validated_scripts": 3,
        "unvalidated_scripts": 1,
        "unvalidated_list": ["orphan.py"],
        "test_file_count": 5,
        "git_clean_worktree": True,
        "git_current_branch": "main",
        "git_up_to_date": True,
    }


def _minimal_weaknesses() -> dict:
    return {
        "scripts_without_tests": 1,
        "scripts_without_tests_list": ["orphan.py"],
        "pyc_in_gitignore": True,
        "tracked_pyc_count": 0,
        "tracked_pyc_files": [],
        "empty_dir_count": 0,
        "empty_dirs": [],
        "stale_branch_count": 0,
        "stale_branches": [],
        "old_docs_count": 0,
        "old_docs": [],
    }


def _minimal_opportunities() -> dict:
    return {
        "scripts_with_todos": 2,
        "top_todo_scripts": [("fix_me.py", 3), ("hack_it.py", 1)],
        "top_test_gap_targets": ["orphan.py"],
        "current_script_coverage_pct": 75.0,
        "potential_coverage_pct": 100.0,
        "remote_branch_count": 1,
        "mergeable_remote_branches": [],
        "mergeable_count": 0,
    }


def _minimal_threats() -> dict:
    return {
        "large_files": [],
        "large_file_count": 0,
        "secret_hit_count": 0,
        "secret_files": [],
        "syntax_error_count": 0,
        "syntax_errors": [],
        "missing_required_files": [],
    }


# ---------------------------------------------------------------------------
# Test 1 — render_report does not crash and returns a non-empty string
# ---------------------------------------------------------------------------


def test_render_report_does_not_crash():
    """render_report must return a non-empty Markdown string without raising."""
    mod = _load()
    report = mod.render_report(
        _minimal_strengths(),
        _minimal_weaknesses(),
        _minimal_opportunities(),
        _minimal_threats(),
    )
    assert isinstance(report, str)
    assert len(report) > 100, "Report should be a substantial Markdown document"


# ---------------------------------------------------------------------------
# Test 2 — report file is written to the correct location inside tmp_path
# ---------------------------------------------------------------------------


def test_report_written_to_correct_location(tmp_path, monkeypatch):
    """main() must write the report to <harness_root>/05_REPORTS/HARNESS_SWOT_REPORT.md."""
    mod = _load(harness_root=tmp_path)

    # Stub out git and filesystem-heavy measure functions so the test is fast
    # and deterministic — we only care that the file ends up in the right place.
    monkeypatch.setattr(mod, "measure_strengths", lambda: _minimal_strengths())
    monkeypatch.setattr(mod, "measure_weaknesses", lambda: _minimal_weaknesses())
    monkeypatch.setattr(mod, "assess_opportunities", lambda: _minimal_opportunities())
    monkeypatch.setattr(mod, "detect_threats", lambda: _minimal_threats())

    mod.main()

    expected = tmp_path / "05_REPORTS" / "HARNESS_SWOT_REPORT.md"
    assert expected.exists(), f"Expected report at {expected}"
    assert expected.stat().st_size > 0, "Written report file must not be empty"


# ---------------------------------------------------------------------------
# Test 3 — all four SWOT section headers appear in the rendered output
# ---------------------------------------------------------------------------


def test_all_swot_sections_present_in_output(tmp_path, monkeypatch):
    """The rendered Markdown must contain all four S/W/O/T section headers."""
    mod = _load(harness_root=tmp_path)

    monkeypatch.setattr(mod, "measure_strengths", lambda: _minimal_strengths())
    monkeypatch.setattr(mod, "measure_weaknesses", lambda: _minimal_weaknesses())
    monkeypatch.setattr(mod, "assess_opportunities", lambda: _minimal_opportunities())
    monkeypatch.setattr(mod, "detect_threats", lambda: _minimal_threats())

    mod.main()

    report_text = (tmp_path / "05_REPORTS" / "HARNESS_SWOT_REPORT.md").read_text(encoding="utf-8")

    assert "## S — Strengths" in report_text, "Missing Strengths section"
    assert "## W — Weaknesses" in report_text, "Missing Weaknesses section"
    assert "## O — Opportunities" in report_text, "Missing Opportunities section"
    assert "## T — Threats" in report_text, "Missing Threats section"


# ---------------------------------------------------------------------------
# Test 4 — script exits with code 0 on success (subprocess integration)
# ---------------------------------------------------------------------------


def test_exit_code_zero_on_success(tmp_path):
    """Running harness_swot.py as a subprocess must exit with code 0."""
    # We inject a tiny monkey-patch via PYTHONPATH so that subprocess-level
    # imports of the real harness paths are redirected to tmp_path.
    # The simplest approach: override the three module-level path constants
    # by injecting a sitecustomize shim.
    shim = tmp_path / "sitecustomize.py"
    reports_dir = tmp_path / "05_REPORTS"
    reports_dir.mkdir(parents=True, exist_ok=True)

    shim.write_text(
        f"""
import sys, types, subprocess, re, ast, os
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

_root = Path(r"{tmp_path!s}")

def _run_stub(cmd, cwd=None):
    return 0, "", ""

_patches = [
    patch("harness_swot.HARNESS_ROOT", _root),
    patch("harness_swot.REPORT_DIR", _root / "05_REPORTS"),
    patch("harness_swot.REPORT_FILE", _root / "05_REPORTS" / "HARNESS_SWOT_REPORT.md"),
    patch("harness_swot._run", _run_stub),
    patch("harness_swot._iter_tracked_files", lambda: []),
    patch("harness_swot._all_files_under", lambda *a, **kw: []),
]
for p in _patches:
    p.start()
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
        env={**__import__("os").environ, "PYTHONPATH": str(tmp_path)},
    )
    assert result.returncode == 0, (
        f"Script exited {result.returncode}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 5 — render_report includes metrics from each quadrant's data
# ---------------------------------------------------------------------------


def test_render_report_embeds_quadrant_metrics():
    """Key numeric values from each quadrant must appear verbatim in the report."""
    mod = _load()

    s = _minimal_strengths()
    w = _minimal_weaknesses()
    o = _minimal_opportunities()
    t = _minimal_threats()

    report = mod.render_report(s, w, o, t)

    # Strengths: CI workflow count
    assert "**2**" in report, "CI workflow count not found in report"
    # Weaknesses: uncovered scripts count
    assert str(w["scripts_without_tests"]) in report
    # Opportunities: coverage percentage
    assert "75.0%" in report, "Coverage percentage not found in report"
    # Threats: syntax error count
    assert str(t["syntax_error_count"]) in report


# ---------------------------------------------------------------------------
# Test 6 — _scan_secrets ignores placeholder patterns
# ---------------------------------------------------------------------------


def test_scan_secrets_ignores_placeholders(tmp_path):
    """Lines containing YOUR_/REPLACE_ME/EXAMPLE_KEY should not flag as secrets."""
    mod = _load()

    fake_file = tmp_path / "config.py"
    fake_file.write_text(
        'api_key = "YOUR_API_KEY_HERE"\ntoken = "REPLACE_ME_WITH_REAL_TOKEN"\n',
        encoding="utf-8",
    )

    hits = mod._scan_secrets(fake_file)
    assert hits == [], f"Placeholder lines must not be flagged as secrets, got: {hits}"


# ---------------------------------------------------------------------------
# Test 7 — _has_syntax_error detects bad Python and passes clean Python
# ---------------------------------------------------------------------------


def test_has_syntax_error_detection(tmp_path):
    """_has_syntax_error must return None for valid Python and a string for broken Python."""
    mod = _load()

    good = tmp_path / "good.py"
    good.write_text("def foo():\n    return 42\n", encoding="utf-8")
    assert mod._has_syntax_error(good) is None, "Valid Python should not flag a syntax error"

    bad = tmp_path / "bad.py"
    bad.write_text("def broken(\n", encoding="utf-8")
    result = mod._has_syntax_error(bad)
    assert result is not None, "Broken Python must produce an error string"
    assert isinstance(result, str) and len(result) > 0
