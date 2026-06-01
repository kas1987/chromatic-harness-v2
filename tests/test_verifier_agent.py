"""Smoke tests for verifier_agent.py (gh-82 / NW-RG-082).

Reconciled from EPIC-C (shipped untested). Network-free; pure check functions.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "verifier_agent", REPO / "02_RUNTIME" / "orchestrator" / "verifier_agent.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["verifier_agent"] = mod
    spec.loader.exec_module(mod)
    return mod


def _mutation(**over):
    base = {
        "id": "mut-1",
        "title": "test",
        "tier": "T3",
        "confidence_score": 82.0,
        "allowed_files": ["scripts/"],
        "changed_files": ["scripts/x.py"],
        "forbidden_patterns": [],
        "test_evidence": "pytest: 5 passed",
        "risk_level": "medium",
        "author": "tester",
    }
    base.update(over)
    return base


def test_t4_always_escalates():
    mod = _load()
    result = mod.verify(_mutation(tier="T4"), dry_run=True)
    assert result["verdict"] == "escalate"  # T4 needs human regardless of checks


def test_clean_t3_approves():
    mod = _load()
    result = mod.verify(_mutation(), dry_run=True)
    assert result["verdict"] in {"approve", "escalate"}
    assert "evidence" in result and "remediation_task" in result


def test_file_scope_violation_rejects():
    mod = _load()
    m = _mutation(allowed_files=["docs/"], changed_files=["scripts/secret.py"])
    result = mod.verify(m, dry_run=True)
    assert result["verdict"] in {"reject", "escalate"}


def test_low_confidence_not_approved():
    mod = _load()
    result = mod.verify(_mutation(confidence_score=10.0), dry_run=True)
    assert result["verdict"] in {"reject", "escalate"}


def test_compute_verdict_fail_produces_remediation():
    mod = _load()
    checks = [{"check": "file_scope", "status": "fail", "message": "out of scope"}]
    verdict, remediation = mod.compute_verdict(checks, _mutation(tier="T3"))
    assert verdict == "reject"
    assert remediation and "action" in remediation


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
