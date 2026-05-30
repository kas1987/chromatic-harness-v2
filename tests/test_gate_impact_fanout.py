"""Tests for gate.py codegraph impact fan-out (bead chromatic-harness-v2-gy7x).

Verifies the PreToolUse gate turns prompt file-references into a blast-radius
count fed to the classifier — env-gated, fail-open, and unit-testable without
codegraph installed (the runner is injectable).

Run with: pytest tests/test_gate_impact_fanout.py -v
"""

from __future__ import annotations

import importlib

import router.gate as gate

importlib.reload(gate)


def test_extract_file_refs_only_returns_existing_files():
    text = (
        "Please refactor `02_RUNTIME/router/gate.py` and "
        "02_RUNTIME/router/complexity_classifier.py, ignore does/not/exist.py"
    )
    refs = gate._extract_file_refs(text)
    assert "02_RUNTIME/router/gate.py" in refs
    assert "02_RUNTIME/router/complexity_classifier.py" in refs
    assert "does/not/exist.py" not in refs
    assert len(refs) == len(set(refs))  # de-duplicated


def test_count_impacted_dedupes_path_lines():
    stdout = "a/b.py\na/b.py\nc/d.ts\n\n  \nnotapath\n"
    # "notapath" has no slash/dot → excluded; blank lines excluded; dupes merged
    assert gate._count_impacted(stdout) == 2


def test_impact_fan_out_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(gate, "IMPACT_ENABLED", False)
    result = gate._impact_fan_out("edit 02_RUNTIME/router/gate.py", "")
    assert result is None


def test_impact_fan_out_uses_injected_runner(monkeypatch):
    monkeypatch.setattr(gate, "IMPACT_ENABLED", True)
    captured = {}

    def fake_runner(files):
        captured["files"] = files
        return "x/y.py\nx/z.py\nq/r.py\n"  # codegraph says 3 files affected

    result = gate._impact_fan_out(
        "refactor 02_RUNTIME/router/gate.py", "", runner=fake_runner
    )
    assert result == 3
    assert captured["files"] == ["02_RUNTIME/router/gate.py"]


def test_impact_fan_out_floor_is_referenced_count(monkeypatch):
    monkeypatch.setattr(gate, "IMPACT_ENABLED", True)
    # Runner returns nothing useful, but two real files were referenced.
    result = gate._impact_fan_out(
        "touch 02_RUNTIME/router/gate.py and "
        "02_RUNTIME/router/complexity_classifier.py",
        "",
        runner=lambda files: "",
    )
    assert result == 2


def test_impact_fan_out_no_refs_returns_none(monkeypatch):
    monkeypatch.setattr(gate, "IMPACT_ENABLED", True)
    result = gate._impact_fan_out("just brainstorm some ideas", "", runner=lambda f: "")
    assert result is None


def test_impact_fan_out_failopen_on_runner_error(monkeypatch):
    monkeypatch.setattr(gate, "IMPACT_ENABLED", True)

    def boom(files):
        raise RuntimeError("codegraph exploded")

    result = gate._impact_fan_out("edit 02_RUNTIME/router/gate.py", "", runner=boom)
    assert result is None  # never raises, falls back to keyword path
