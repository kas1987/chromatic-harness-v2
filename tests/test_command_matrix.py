"""Tests for generate_command_matrix.py (j5ik / gh-109). Network-free, tmp-isolated."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "generate_command_matrix", REPO / "scripts" / "generate_command_matrix.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["generate_command_matrix"] = mod
    spec.loader.exec_module(mod)
    return mod


def _registry():
    return {
        "version": "0.1.0",
        "commands": [
            {
                "name": "/go",
                "purpose": "Do the thing.",
                "authority_source": "queue",
                "script": "scripts/go.py",
                "fallback_script": None,
                "mutation": "conditional",
                "required_gates": ["confidence"],
                "allowed": True,
                "forbidden_logic": ["direct_ship"],
            }
        ],
    }


def test_render_contains_command_and_gates():
    m = _mod()
    out = m.render_matrix(_registry())
    assert "`/go`" in out
    assert "confidence" in out
    assert "Conditional" in out
    assert "direct_ship" in out  # forbidden-logic section
    assert "DO NOT EDIT" in out  # generated banner


def test_render_is_deterministic():
    m = _mod()
    reg = _registry()
    assert m.render_matrix(reg) == m.render_matrix(reg)


def test_pipe_in_value_is_escaped():
    m = _mod()
    reg = _registry()
    reg["commands"][0]["purpose"] = "a | b"
    out = m.render_matrix(reg)
    assert "a \\| b" in out


def test_write_then_check_roundtrips(tmp_path):
    m = _mod()
    p = tmp_path / "MATRIX.md"
    m.write_matrix(_registry(), path=p)
    assert m.check_matrix(_registry(), path=p) is True


def test_check_detects_drift(tmp_path):
    m = _mod()
    p = tmp_path / "MATRIX.md"
    m.write_matrix(_registry(), path=p)
    p.write_text("stale content", encoding="utf-8")
    assert m.check_matrix(_registry(), path=p) is False


def test_check_missing_file_is_drift(tmp_path):
    m = _mod()
    p = tmp_path / "absent.md"
    assert m.check_matrix(_registry(), path=p) is False


def test_summarize_fail_open_on_bad_registry(tmp_path):
    m = _mod()
    out = m.summarize(registry_path=tmp_path / "nope.yaml", matrix_path=tmp_path / "nope.md")
    assert out["status"] in {"ok", "error"}


def test_committed_matrix_in_sync_with_real_registry():
    """The shipped CLAUDE_COMMAND_MATRIX.md MUST match the real registry (anti-drift)."""
    m = _mod()
    assert m.check_matrix(), "CLAUDE_COMMAND_MATRIX.md drifted — run python scripts/generate_command_matrix.py"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
