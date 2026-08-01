"""Tests for orchestrator/verifier_agent.py — boost coverage from 60% to 80%+."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from orchestrator.verifier_agent import (
    check_confidence_threshold,
    check_file_scope,
    check_forbidden_patterns,
    check_test_coverage,
    check_tier_gate,
    compute_verdict,
    verify,
    write_audit,
    _load_mutation,
    _ts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mut(**overrides) -> dict:
    base = {
        "id": "mut-test",
        "title": "Test mutation",
        "tier": "T3",
        "confidence_score": 82.0,
        "allowed_files": ["scripts/"],
        "changed_files": ["scripts/x.py"],
        "forbidden_patterns": [],
        "test_evidence": "pytest: 5 passed",
        "risk_level": "medium",
        "author": "tester",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# check_tier_gate
# ---------------------------------------------------------------------------


class TestCheckTierGate:
    def test_t3_passes(self):
        r = check_tier_gate(_mut(tier="T3"))
        assert r["status"] == "pass"
        assert "T3" in r["detail"]

    def test_t4_passes(self):
        r = check_tier_gate(_mut(tier="T4"))
        assert r["status"] == "pass"

    def test_t1_warns(self):
        r = check_tier_gate(_mut(tier="T1"))
        assert r["status"] == "warn"

    def test_t2_warns(self):
        r = check_tier_gate(_mut(tier="T2"))
        assert r["status"] == "warn"

    def test_missing_tier_fails(self):
        r = check_tier_gate({})
        assert r["status"] == "fail"
        assert "No tier" in r["detail"]

    def test_unknown_tier_fails(self):
        r = check_tier_gate(_mut(tier="T9"))
        assert r["status"] == "fail"
        assert "Unknown tier" in r["detail"]


# ---------------------------------------------------------------------------
# check_file_scope
# ---------------------------------------------------------------------------


class TestCheckFileScope:
    def test_all_in_scope_passes(self):
        r = check_file_scope(_mut(allowed_files=["scripts/"], changed_files=["scripts/foo.py"]))
        assert r["status"] == "pass"

    def test_out_of_scope_fails(self):
        r = check_file_scope(_mut(allowed_files=["docs/"], changed_files=["scripts/secret.py"]))
        assert r["status"] == "fail"
        assert "outside declared scope" in r["detail"]

    def test_no_changed_files_warns(self):
        r = check_file_scope(_mut(changed_files=[]))
        assert r["status"] == "warn"
        assert "No changed_files" in r["detail"]

    def test_no_allowed_files_warns(self):
        r = check_file_scope(_mut(allowed_files=[], changed_files=["x.py"]))
        assert r["status"] == "warn"
        assert "No allowed_files" in r["detail"]


# ---------------------------------------------------------------------------
# check_forbidden_patterns
# ---------------------------------------------------------------------------


class TestCheckForbiddenPatterns:
    def test_no_violations_passes(self):
        r = check_forbidden_patterns(_mut(changed_files=["scripts/regular.py"]))
        assert r["status"] == "pass"

    def test_env_file_fails(self):
        r = check_forbidden_patterns(_mut(changed_files=["config/.env"]))
        assert r["status"] == "fail"
        assert "Forbidden pattern" in r["detail"]

    def test_pem_file_fails(self):
        r = check_forbidden_patterns(_mut(changed_files=["certs/server.pem"]))
        assert r["status"] == "fail"

    def test_custom_pattern_fails(self):
        r = check_forbidden_patterns(_mut(changed_files=["src/admin_token.py"], forbidden_patterns=["admin_token"]))
        assert r["status"] == "fail"

    def test_malformed_custom_pattern_skipped(self):
        # Invalid regex should be skipped (fail-safe)
        r = check_forbidden_patterns(_mut(changed_files=["scripts/x.py"], forbidden_patterns=["[invalid"]))
        # Should still pass since the valid default patterns don't match
        assert r["status"] == "pass"


# ---------------------------------------------------------------------------
# check_test_coverage
# ---------------------------------------------------------------------------


class TestCheckTestCoverage:
    def test_evidence_present_passes(self):
        r = check_test_coverage(_mut(test_evidence="pytest: 5 passed"))
        assert r["status"] == "pass"

    def test_no_evidence_t3_fails(self):
        r = check_test_coverage(_mut(tier="T3", test_evidence=None))
        assert r["status"] == "fail"
        assert "T3" in r["detail"] or "Required" in r["detail"]

    def test_no_evidence_high_risk_fails(self):
        r = check_test_coverage(_mut(tier="T1", test_evidence="", risk_level="high"))
        assert r["status"] == "fail"

    def test_no_evidence_low_risk_t1_warns(self):
        r = check_test_coverage(_mut(tier="T1", test_evidence="", risk_level="low"))
        assert r["status"] == "warn"

    def test_evidence_null_string_fails_for_t3(self):
        r = check_test_coverage(_mut(tier="T3", test_evidence="null"))
        assert r["status"] == "fail"


# ---------------------------------------------------------------------------
# check_confidence_threshold
# ---------------------------------------------------------------------------


class TestCheckConfidenceThreshold:
    def test_above_threshold_passes(self):
        r = check_confidence_threshold(_mut(tier="T3", confidence_score=80.0))
        assert r["status"] == "pass"

    def test_below_threshold_fails(self):
        r = check_confidence_threshold(_mut(tier="T3", confidence_score=50.0))
        assert r["status"] == "fail"

    def test_no_score_warns(self):
        r = check_confidence_threshold(_mut(confidence_score=None))
        assert r["status"] == "warn"

    def test_invalid_score_fails(self):
        r = check_confidence_threshold(_mut(confidence_score="not-a-number"))
        assert r["status"] == "fail"

    def test_t4_threshold_90(self):
        # T4 needs 90+ to pass
        r = check_confidence_threshold(_mut(tier="T4", confidence_score=89.0))
        assert r["status"] == "fail"
        r2 = check_confidence_threshold(_mut(tier="T4", confidence_score=90.0))
        assert r2["status"] == "pass"


# ---------------------------------------------------------------------------
# compute_verdict
# ---------------------------------------------------------------------------


class TestComputeVerdict:
    def test_all_pass_approves(self):
        checks = [
            {"status": "pass", "check": "file_scope"},
            {"status": "pass", "check": "tier_gate"},
        ]
        verdict, rem = compute_verdict(checks, _mut(tier="T3"))
        assert verdict == "approve"
        assert rem is None

    def test_t4_all_pass_escalates(self):
        checks = [{"status": "pass", "check": "tier_gate"}]
        verdict, rem = compute_verdict(checks, _mut(tier="T4"))
        assert verdict == "escalate"
        assert "human_review_required" in rem["action"]

    def test_fails_reject(self):
        checks = [{"status": "fail", "check": "file_scope"}]
        verdict, rem = compute_verdict(checks, _mut(tier="T3"))
        assert verdict == "reject"
        assert rem is not None
        assert "file_scope" in rem["failed_checks"]

    def test_critical_risk_escalates(self):
        checks = [{"status": "fail", "check": "file_scope"}]
        verdict, rem = compute_verdict(checks, _mut(tier="T3", risk_level="critical"))
        assert verdict == "escalate"

    def test_warns_still_approve(self):
        checks = [
            {"status": "warn", "check": "test_coverage"},
            {"status": "pass", "check": "tier_gate"},
        ]
        verdict, rem = compute_verdict(checks, _mut(tier="T3"))
        assert verdict == "approve"


# ---------------------------------------------------------------------------
# _load_mutation
# ---------------------------------------------------------------------------


class TestLoadMutation:
    def test_valid_file_loads(self, tmp_path):
        f = tmp_path / "mut.json"
        data = {"id": "x", "tier": "T3"}
        f.write_text(json.dumps(data), encoding="utf-8")
        result = _load_mutation(str(f))
        assert result["id"] == "x"

    def test_invalid_json_raises(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSON"):
            _load_mutation(str(f))

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            _load_mutation(str(tmp_path / "missing.json"))


# ---------------------------------------------------------------------------
# write_audit
# ---------------------------------------------------------------------------


class TestWriteAudit:
    def test_writes_file(self, tmp_path):
        result = verify(_mut(), dry_run=True)
        with patch("orchestrator.verifier_agent.AUDIT_DIR", tmp_path / "verifier"):
            path = write_audit(result)
        assert path.is_file()
        saved = json.loads(path.read_text())
        assert saved["verdict"] == result["verdict"]

    def test_writes_latest_json(self, tmp_path):
        result = verify(_mut(), dry_run=True)
        audit_dir = tmp_path / "verifier"
        with patch("orchestrator.verifier_agent.AUDIT_DIR", audit_dir):
            write_audit(result)
        latest = audit_dir / "latest.json"
        assert latest.is_file()


# ---------------------------------------------------------------------------
# main() via subprocess (key exit codes)
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_approve_exit_0(self, tmp_path):
        import subprocess

        mut_file = tmp_path / "mut.json"
        mut_file.write_text(json.dumps(_mut()), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(_RUNTIME / "orchestrator" / "verifier_agent.py"),
                "--mutation-file",
                str(mut_file),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["verdict"] == "approve"

    def test_main_reject_exit_1(self, tmp_path):
        import subprocess

        mut_file = tmp_path / "mut.json"
        mut_file.write_text(
            json.dumps(
                _mut(
                    allowed_files=["docs/"],
                    changed_files=["scripts/secret.py"],
                    test_evidence=None,
                    confidence_score=10.0,
                )
            ),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(_RUNTIME / "orchestrator" / "verifier_agent.py"),
                "--mutation-file",
                str(mut_file),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode in {1, 2}  # reject or escalate

    def test_main_example_flag(self):
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(_RUNTIME / "orchestrator" / "verifier_agent.py"), "--example"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert "tier" in data

    def test_main_no_args_exits_1(self):
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(_RUNTIME / "orchestrator" / "verifier_agent.py")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 1

    def test_main_missing_file_exits_1(self, tmp_path):
        import subprocess

        proc = subprocess.run(
            [
                sys.executable,
                str(_RUNTIME / "orchestrator" / "verifier_agent.py"),
                "--mutation-file",
                str(tmp_path / "nonexistent.json"),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 1

    def test_main_invalid_json_exits_1(self, tmp_path):
        import subprocess

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(_RUNTIME / "orchestrator" / "verifier_agent.py"), "--mutation-file", str(bad_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 1
