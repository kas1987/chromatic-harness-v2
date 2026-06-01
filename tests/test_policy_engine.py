#!/usr/bin/env python3
"""Tests for scripts/policy_engine.py (bead gh-64). Network-free."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "policy_engine",
    Path(__file__).resolve().parents[1] / "scripts" / "policy_engine.py",
)
pe = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(pe)


def _good_policy() -> dict:
    return {
        "version": "1.0.0",
        "name": "p",
        "rules": [
            {
                "id": "big",
                "description": "too big",
                "severity": "warn",
                "when": {"field": "changed_files", "op": ">", "value": 50},
                "message": "too many files",
            },
            {
                "id": "protected",
                "description": "protected touched",
                "severity": "block",
                "when": {"field": "protected_touched", "op": "==", "value": True},
                "message": "protected path",
            },
        ],
    }


# --- validate_policy --------------------------------------------------------


def test_validate_policy_good():
    assert pe.validate_policy(_good_policy()) == []


def test_validate_policy_missing_version():
    p = _good_policy()
    del p["version"]
    errs = pe.validate_policy(p)
    assert any("version" in e for e in errs)


def test_validate_policy_bad_severity_and_op():
    p = _good_policy()
    p["rules"][0]["severity"] = "fatal"
    p["rules"][0]["when"]["op"] = "~="
    errs = pe.validate_policy(p)
    assert any("severity" in e for e in errs)
    assert any("op" in e for e in errs)


def test_validate_policy_duplicate_ids():
    p = _good_policy()
    p["rules"][1]["id"] = "big"
    errs = pe.validate_policy(p)
    assert any("duplicate" in e for e in errs)


def test_validate_policy_not_a_dict():
    assert pe.validate_policy(["nope"]) == ["policy must be a dict"]


def test_validate_policy_missing_value():
    p = _good_policy()
    del p["rules"][0]["when"]["value"]
    errs = pe.validate_policy(p)
    assert any("value is required" in e for e in errs)


# --- evaluate ---------------------------------------------------------------


def test_evaluate_block_on_protected():
    res = pe.evaluate(_good_policy(), {"changed_files": 5, "protected_touched": True})
    assert res["decision"] == "block"
    assert res["by_severity"]["block"] == 1
    assert {v["id"] for v in res["violations"]} == {"protected"}


def test_evaluate_allow_with_warn():
    res = pe.evaluate(_good_policy(), {"changed_files": 80, "protected_touched": False})
    assert res["decision"] == "allow"
    assert res["by_severity"]["warn"] == 1
    assert len(res["violations"]) == 1


def test_evaluate_multiple_rules_and_rollup():
    res = pe.evaluate(_good_policy(), {"changed_files": 80, "protected_touched": True})
    assert res["decision"] == "block"
    assert len(res["violations"]) == 2
    assert res["by_severity"] == {"info": 0, "warn": 1, "block": 1}


@pytest.mark.parametrize(
    "op,actual,value,expected",
    [
        ("==", 5, 5, True),
        ("!=", 5, 6, True),
        (">", 6, 5, True),
        ("<", 4, 5, True),
        (">=", 5, 5, True),
        ("<=", 5, 6, True),
        ("in", "main", ["main", "master"], True),
        ("contains", ["a", "b"], "a", True),
        (">", "x", 5, False),  # type mismatch -> no match
        ("==", 5, 6, False),
    ],
)
def test_evaluate_each_op(op, actual, value, expected):
    policy = {
        "version": "1.0.0",
        "rules": [
            {
                "id": "r",
                "description": "d",
                "severity": "block",
                "when": {"field": "f", "op": op, "value": value},
                "message": "m",
            }
        ],
    }
    res = pe.evaluate(policy, {"f": actual})
    assert (res["decision"] == "block") is expected


# --- load_policy ------------------------------------------------------------


def test_load_policy_default_when_missing(tmp_path):
    p = pe.load_policy(tmp_path / "nope.json")
    assert p["version"] == "0.1.0"
    assert pe.validate_policy(p) == []


def test_load_policy_from_file(tmp_path):
    f = tmp_path / "active.json"
    f.write_text(json.dumps(_good_policy()), encoding="utf-8")
    p = pe.load_policy(f)
    assert p["version"] == "1.0.0"


def test_load_policy_corrupt_falls_back(tmp_path):
    f = tmp_path / "active.json"
    f.write_text("{not json", encoding="utf-8")
    p = pe.load_policy(f)
    assert p["version"] == "0.1.0"


# --- apply_override ---------------------------------------------------------


def test_apply_override_flips_block():
    res = pe.evaluate(_good_policy(), {"protected_touched": True})
    assert res["decision"] == "block"
    out = pe.apply_override(res, "approved hotfix", "alice")
    assert out["decision"] == "allow-with-override"
    assert out["override"]["applied"] is True
    assert out["override"]["actor"] == "alice"
    assert out["override"]["original_decision"] == "block"
    # original result untouched
    assert res["decision"] == "block"


def test_apply_override_keeps_allow():
    res = pe.evaluate(_good_policy(), {"changed_files": 1})
    out = pe.apply_override(res, "noop", "bob")
    assert out["decision"] == "allow"
    assert out["override"]["applied"] is True


# --- audit + artifact + summarize ------------------------------------------


def test_append_audit_writes_line(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(pe, "AUDIT_LOG", tmp_path / "audit.jsonl")
    res = pe.evaluate(_good_policy(), {"protected_touched": True})
    pe.append_audit(res, "20260601T000000Z")
    pe.append_audit(res, "20260601T000001Z")
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["decision"] == "block"
    assert rec["violation_count"] == 1
    assert rec["policy_version"] == "1.0.0"


def test_write_artifact_and_summarize(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(pe, "LATEST_ARTIFACT", tmp_path / "latest.json")
    res = pe.evaluate(_good_policy(), {"changed_files": 80})
    pe.write_artifact(res, "20260601T000000Z")
    assert (tmp_path / "latest.json").exists()
    s = pe.summarize()
    assert s["status"] == "ok"
    assert s["decision"] == "allow"
    assert s["violations"] == 1
    assert s["policy_version"] == "1.0.0"


def test_summarize_fail_open_no_run(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "LATEST_ARTIFACT", tmp_path / "missing.json")
    s = pe.summarize()
    assert s["status"] == "no_run"
    assert s["decision"] is None
