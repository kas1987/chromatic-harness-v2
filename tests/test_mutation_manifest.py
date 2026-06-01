"""Tests for mutation_manifest.py — pre-write declaration gate (P0-CC-002 / ju0o.2)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _mm():
    return _load("mutation_manifest", "scripts/mutation_manifest.py")


def _valid_manifest(**over):
    base = {
        "task_id": "t1",
        "issue": 95,
        "owner_agent": "Sentinel",
        "risk_tier": "T2",
        "intended_changes": ["add x"],
        "allowed_files": ["scripts/x.py"],
        "forbidden_files": ["secrets"],
        "acceptance_checks": ["pytest passes"],
    }
    base.update(over)
    return base


def test_schema_validates_sample_manifest():
    mm = _mm()
    assert mm.validate_manifest(_valid_manifest()) == []
    assert mm.is_valid(_valid_manifest())


def test_missing_required_field_is_error():
    mm = _mm()
    m = _valid_manifest()
    del m["risk_tier"]
    errors = mm.validate_manifest(m)
    assert any("risk_tier" in e for e in errors)


def test_bad_risk_tier_enum_rejected():
    mm = _mm()
    errors = mm.validate_manifest(_valid_manifest(risk_tier="T9"))
    assert any("risk_tier" in e for e in errors)


def test_confidence_out_of_range_rejected():
    mm = _mm()
    errors = mm.validate_manifest(_valid_manifest(confidence_score=150))
    assert any("confidence_score" in e for e in errors)


def test_require_manifest_read_task_exempt():
    mm = _mm()
    ok, _ = mm.require_manifest({"mode": "read"})
    assert ok is True


def test_require_manifest_write_without_manifest_rejected():
    mm = _mm()
    ok, reason = mm.require_manifest({"mode": "write"})
    assert ok is False and "no mutation manifest" in reason


def test_require_manifest_write_with_valid_manifest_allowed():
    mm = _mm()
    ok, _ = mm.require_manifest({"mode": "write", "mutation_manifest": _valid_manifest()})
    assert ok is True


def test_require_manifest_write_with_invalid_manifest_rejected():
    mm = _mm()
    bad = _valid_manifest()
    del bad["acceptance_checks"]
    ok, reason = mm.require_manifest({"mode": "write", "mutation_manifest": bad})
    assert ok is False and "invalid manifest" in reason


# ── GO-mode enforcement (FR-3) ───────────────────────────────────────────────


def test_go_mode_rejects_write_without_manifest():
    go = _load("go_mode", "scripts/go_mode.py")
    item = {
        "id": "w",
        "priority": "P0",
        "status": "ready",
        "title": "write task",
        "mode": "write",
        "acceptance_checks": ["test a", "b", "c"],
        "risk_level": "low",
    }
    rec = go.run_go([item])
    assert rec["dispatch_allowed"] is False
    assert "manifest" in rec["dispatch_reason"].lower()


def test_go_mode_allows_write_with_manifest():
    go = _load("go_mode", "scripts/go_mode.py")
    item = {
        "id": "w",
        "priority": "P0",
        "status": "ready",
        "title": "write task",
        "mode": "write",
        "acceptance_checks": ["test a", "b", "c"],
        "allowed_files": ["x.py"],
        "stop_conditions": ["s"],
        "risk_level": "low",
        "mutation_manifest": _valid_manifest(),
    }
    rec = go.run_go([item])
    assert rec["dispatch_allowed"] is True


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
