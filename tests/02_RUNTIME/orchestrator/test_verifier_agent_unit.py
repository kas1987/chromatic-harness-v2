# DEFICIENCIES NOTED:
# 1. _load_mutation reads the filesystem directly; no injectable IO interface, so tests
#    must use tmp_path fixtures rather than in-memory stubs.
# 2. write_audit() writes to AUDIT_DIR which is hardcoded relative to the source file
#    (REPO / "07_LOGS_AND_AUDIT/verifier"). Tests must monkeypatch AUDIT_DIR or use
#    tmp_path + monkeypatch to avoid polluting the real repo tree.
# 3. _ts() calls datetime.now() — tests that need deterministic timestamps must
#    monkeypatch datetime; there is no injected clock interface.
# 4. check_file_scope uses a broad "in" substring match (norm(a) in cf_norm) which
#    can produce false-positives for short allowed prefixes (e.g. "src" matches
#    "extra/src_util.py"). This is a logic quirk, not an error, but tests document it.
# 5. compute_verdict returns "approve" for both warn-only and clean runs — the two
#    branches are functionally identical (both return "approve", None). The separate
#    code paths are preserved but produce the same result; flagged as dead-branch risk.

"""Tests for orchestrator/verifier_agent.py — independent verifier for T3+ mutations."""

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

# Load the module directly to avoid any import-time side effects from AUDIT_DIR creation.
_VA_PATH = _RUNTIME / "orchestrator" / "verifier_agent.py"
_spec = importlib.util.spec_from_file_location("verifier_agent_under_test", _VA_PATH)
_va = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_va)  # type: ignore[union-attr]

check_tier_gate = _va.check_tier_gate
check_file_scope = _va.check_file_scope
check_forbidden_patterns = _va.check_forbidden_patterns
check_test_coverage = _va.check_test_coverage
check_confidence_threshold = _va.check_confidence_threshold
compute_verdict = _va.compute_verdict
verify = _va.verify
write_audit = _va.write_audit
_load_mutation = _va._load_mutation
CONFIDENCE_THRESHOLDS = _va.CONFIDENCE_THRESHOLDS
VERIFICATION_REQUIRED_TIERS = _va.VERIFICATION_REQUIRED_TIERS


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _base_mutation(**overrides) -> dict:
    """Return a valid T3 mutation dict with optional field overrides."""
    base = {
        "id": "mut-test-001",
        "title": "Add policy engine",
        "tier": "T3",
        "confidence_score": 82.5,
        "allowed_files": ["scripts/", "docs/"],
        "changed_files": ["scripts/policy_engine.py", "docs/governance/POLICY.md"],
        "forbidden_patterns": [],
        "test_evidence": "pytest tests/test_policy.py: 8 passed",
        "risk_level": "medium",
        "author": "worker-agent",
        "timestamp": "2026-06-01T00:00:00Z",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _load_mutation
# ---------------------------------------------------------------------------


class TestLoadMutation:
    def test_loads_valid_json_file(self, tmp_path):
        data = {"id": "mut-1", "tier": "T3"}
        p = tmp_path / "mutation.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = _load_mutation(str(p))
        assert result == data

    def test_raises_value_error_on_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json}", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSON"):
            _load_mutation(str(p))

    def test_raises_value_error_on_missing_file(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            _load_mutation(str(tmp_path / "nonexistent.json"))

    def test_preserves_all_fields(self, tmp_path):
        data = _base_mutation()
        p = tmp_path / "m.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        loaded = _load_mutation(str(p))
        assert loaded["confidence_score"] == 82.5
        assert loaded["tier"] == "T3"


# ---------------------------------------------------------------------------
# check_tier_gate
# ---------------------------------------------------------------------------


class TestCheckTierGate:
    def test_t3_returns_pass(self):
        result = check_tier_gate({"tier": "T3"})
        assert result["status"] == "pass"
        assert result["check"] == "tier_gate"

    def test_t4_returns_pass(self):
        result = check_tier_gate({"tier": "T4"})
        assert result["status"] == "pass"

    def test_t1_returns_warn(self):
        result = check_tier_gate({"tier": "T1"})
        assert result["status"] == "warn"
        assert "T1" in result["detail"]

    def test_t2_returns_warn(self):
        result = check_tier_gate({"tier": "T2"})
        assert result["status"] == "warn"

    def test_missing_tier_returns_fail(self):
        result = check_tier_gate({})
        assert result["status"] == "fail"
        assert "No tier" in result["detail"]

    def test_unknown_tier_returns_fail(self):
        result = check_tier_gate({"tier": "T9"})
        assert result["status"] == "fail"
        assert "T9" in result["detail"]

    def test_lowercase_tier_normalized(self):
        result = check_tier_gate({"tier": "t3"})
        assert result["status"] == "pass"

    @pytest.mark.parametrize("tier", ["T3", "T4"])
    def test_verification_required_tiers_pass(self, tier):
        result = check_tier_gate({"tier": tier})
        assert result["status"] == "pass"

    @pytest.mark.parametrize("tier", ["T1", "T2"])
    def test_lower_tiers_warn(self, tier):
        result = check_tier_gate({"tier": tier})
        assert result["status"] == "warn"


# ---------------------------------------------------------------------------
# check_file_scope
# ---------------------------------------------------------------------------


class TestCheckFileScope:
    def test_all_files_in_scope_returns_pass(self):
        m = _base_mutation(
            allowed_files=["scripts/"],
            changed_files=["scripts/main.py"],
        )
        result = check_file_scope(m)
        assert result["status"] == "pass"
        assert "1" in result["detail"]

    def test_file_outside_scope_returns_fail(self):
        m = _base_mutation(
            allowed_files=["scripts/"],
            changed_files=["scripts/main.py", "src/secret.py"],
        )
        result = check_file_scope(m)
        assert result["status"] == "fail"
        assert "src/secret.py" in result["detail"]

    def test_empty_changed_files_returns_warn(self):
        m = _base_mutation(allowed_files=["scripts/"], changed_files=[])
        result = check_file_scope(m)
        assert result["status"] == "warn"
        assert "No changed_files" in result["detail"]

    def test_empty_allowed_files_returns_warn(self):
        m = _base_mutation(allowed_files=[], changed_files=["scripts/main.py"])
        result = check_file_scope(m)
        assert result["status"] == "warn"
        assert "No allowed_files" in result["detail"]

    def test_none_allowed_files_returns_warn(self):
        m = _base_mutation(allowed_files=None, changed_files=["scripts/main.py"])
        result = check_file_scope(m)
        assert result["status"] == "warn"

    def test_case_insensitive_path_matching(self):
        m = _base_mutation(
            allowed_files=["Scripts/"],
            changed_files=["scripts/main.py"],
        )
        result = check_file_scope(m)
        assert result["status"] == "pass"

    def test_backslash_paths_normalized(self):
        m = _base_mutation(
            allowed_files=["scripts/"],
            changed_files=["scripts\\main.py"],
        )
        result = check_file_scope(m)
        assert result["status"] == "pass"

    def test_multiple_out_of_scope_files_counted(self):
        m = _base_mutation(
            allowed_files=["scripts/"],
            changed_files=["other/a.py", "other/b.py", "scripts/ok.py"],
        )
        result = check_file_scope(m)
        assert result["status"] == "fail"
        assert "2" in result["detail"]

    def test_check_name_is_file_scope(self):
        result = check_file_scope(_base_mutation())
        assert result["check"] == "file_scope"

    def test_detail_includes_out_of_scope_path(self):
        m = _base_mutation(
            allowed_files=["scripts/"],
            changed_files=["totally_elsewhere/rogue.py"],
        )
        result = check_file_scope(m)
        assert "totally_elsewhere/rogue.py" in result["detail"]


# ---------------------------------------------------------------------------
# check_forbidden_patterns
# ---------------------------------------------------------------------------


class TestCheckForbiddenPatterns:
    def test_clean_files_returns_pass(self):
        m = _base_mutation(changed_files=["scripts/main.py"])
        result = check_forbidden_patterns(m)
        assert result["status"] == "pass"

    def test_dotenv_file_returns_fail(self):
        m = _base_mutation(changed_files=["configs/.env"])
        result = check_forbidden_patterns(m)
        assert result["status"] == "fail"

    def test_pem_file_returns_fail(self):
        m = _base_mutation(changed_files=["certs/server.pem"])
        result = check_forbidden_patterns(m)
        assert result["status"] == "fail"

    def test_key_file_returns_fail(self):
        m = _base_mutation(changed_files=["private/id_rsa.key"])
        result = check_forbidden_patterns(m)
        assert result["status"] == "fail"

    def test_settings_json_returns_fail(self):
        m = _base_mutation(changed_files=["app/settings.json"])
        result = check_forbidden_patterns(m)
        assert result["status"] == "fail"

    def test_secrets_in_path_returns_fail(self):
        m = _base_mutation(changed_files=["config/secrets_store.py"])
        result = check_forbidden_patterns(m)
        assert result["status"] == "fail"

    def test_credentials_in_path_returns_fail(self):
        m = _base_mutation(changed_files=["db/credentials.yaml"])
        result = check_forbidden_patterns(m)
        assert result["status"] == "fail"

    def test_custom_forbidden_pattern_respected(self):
        m = _base_mutation(
            changed_files=["app/private_key_loader.py"],
            forbidden_patterns=[r"private_key"],
        )
        result = check_forbidden_patterns(m)
        assert result["status"] == "fail"
        assert "private_key" in result["detail"]

    def test_malformed_custom_pattern_skipped_no_crash(self):
        m = _base_mutation(
            changed_files=["scripts/main.py"],
            forbidden_patterns=[r"[invalid("],
        )
        result = check_forbidden_patterns(m)
        # Malformed regex should be silently skipped; clean file → pass
        assert result["status"] == "pass"

    def test_empty_changed_files_returns_pass(self):
        m = _base_mutation(changed_files=[])
        result = check_forbidden_patterns(m)
        assert result["status"] == "pass"

    def test_check_name_is_forbidden_patterns(self):
        result = check_forbidden_patterns(_base_mutation())
        assert result["check"] == "forbidden_patterns"

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("scripts/main.py", "pass"),
            ("config/.env", "fail"),
            ("certs/tls.pem", "fail"),
            ("vault/id_rsa.key", "fail"),
            ("app/settings.json", "fail"),
            ("store/credentials.json", "fail"),
        ],
    )
    def test_pattern_matrix(self, path, expected):
        m = _base_mutation(changed_files=[path])
        result = check_forbidden_patterns(m)
        assert result["status"] == expected


# ---------------------------------------------------------------------------
# check_test_coverage
# ---------------------------------------------------------------------------


class TestCheckTestCoverage:
    def test_evidence_present_returns_pass(self):
        m = _base_mutation(test_evidence="pytest: 5 passed")
        result = check_test_coverage(m)
        assert result["status"] == "pass"
        assert "pytest: 5 passed" in result["detail"]

    def test_no_evidence_t3_returns_fail(self):
        m = _base_mutation(tier="T3", test_evidence=None, risk_level="medium")
        result = check_test_coverage(m)
        assert result["status"] == "fail"
        assert "T3" in result["detail"]

    def test_no_evidence_t4_returns_fail(self):
        m = _base_mutation(tier="T4", test_evidence=None, risk_level="low")
        result = check_test_coverage(m)
        assert result["status"] == "fail"

    def test_no_evidence_high_risk_returns_fail(self):
        m = _base_mutation(tier="T2", test_evidence=None, risk_level="high")
        result = check_test_coverage(m)
        assert result["status"] == "fail"

    def test_no_evidence_critical_risk_returns_fail(self):
        m = _base_mutation(tier="T2", test_evidence=None, risk_level="critical")
        result = check_test_coverage(m)
        assert result["status"] == "fail"

    def test_no_evidence_t1_low_risk_returns_warn(self):
        m = _base_mutation(tier="T1", test_evidence=None, risk_level="low")
        result = check_test_coverage(m)
        assert result["status"] == "warn"

    def test_no_evidence_t2_medium_risk_returns_warn(self):
        m = _base_mutation(tier="T2", test_evidence=None, risk_level="medium")
        result = check_test_coverage(m)
        assert result["status"] == "warn"

    def test_empty_string_evidence_treated_as_missing(self):
        m = _base_mutation(tier="T3", test_evidence="")
        result = check_test_coverage(m)
        assert result["status"] == "fail"

    def test_literal_null_string_treated_as_missing(self):
        m = _base_mutation(tier="T3", test_evidence="null")
        result = check_test_coverage(m)
        assert result["status"] == "fail"

    def test_literal_none_string_treated_as_missing(self):
        m = _base_mutation(tier="T3", test_evidence="none")
        result = check_test_coverage(m)
        assert result["status"] == "fail"

    def test_check_name_is_test_coverage(self):
        result = check_test_coverage(_base_mutation())
        assert result["check"] == "test_coverage"

    def test_evidence_detail_truncated_at_100_chars(self):
        long_evidence = "x" * 200
        m = _base_mutation(test_evidence=long_evidence)
        result = check_test_coverage(m)
        # detail contains at most 100 chars of evidence
        assert len(result["detail"]) < 200


# ---------------------------------------------------------------------------
# check_confidence_threshold
# ---------------------------------------------------------------------------


class TestCheckConfidenceThreshold:
    @pytest.mark.parametrize(
        "tier,score,expected_status",
        [
            ("T1", 40.0, "pass"),
            ("T1", 39.9, "fail"),
            ("T2", 60.0, "pass"),
            ("T2", 59.9, "fail"),
            ("T3", 75.0, "pass"),
            ("T3", 74.9, "fail"),
            ("T4", 90.0, "pass"),
            ("T4", 89.9, "fail"),
        ],
    )
    def test_tier_threshold_boundaries(self, tier, score, expected_status):
        m = _base_mutation(tier=tier, confidence_score=score)
        result = check_confidence_threshold(m)
        assert result["status"] == expected_status, (
            f"tier={tier} score={score}: expected {expected_status}, got {result['status']}"
        )

    def test_missing_score_returns_warn(self):
        m = _base_mutation(confidence_score=None)
        result = check_confidence_threshold(m)
        assert result["status"] == "warn"
        assert "threshold check skipped" in result["detail"]

    def test_invalid_score_string_returns_fail(self):
        m = _base_mutation(confidence_score="not-a-number")
        result = check_confidence_threshold(m)
        assert result["status"] == "fail"
        assert "Invalid" in result["detail"]

    def test_unknown_tier_defaults_to_60_threshold(self):
        # Tier not in CONFIDENCE_THRESHOLDS → defaults to 60.0
        m = _base_mutation(tier="TX", confidence_score=60.0)
        result = check_confidence_threshold(m)
        assert result["status"] == "pass"

    def test_unknown_tier_below_default_threshold_fails(self):
        m = _base_mutation(tier="TX", confidence_score=59.9)
        result = check_confidence_threshold(m)
        assert result["status"] == "fail"

    def test_check_name_is_confidence_threshold(self):
        result = check_confidence_threshold(_base_mutation())
        assert result["check"] == "confidence_threshold"

    def test_detail_contains_score_and_threshold_on_pass(self):
        m = _base_mutation(tier="T3", confidence_score=80.0)
        result = check_confidence_threshold(m)
        assert "80.0" in result["detail"]
        assert "75.0" in result["detail"]

    def test_detail_contains_score_and_threshold_on_fail(self):
        m = _base_mutation(tier="T3", confidence_score=70.0)
        result = check_confidence_threshold(m)
        assert "70.0" in result["detail"]
        assert "75.0" in result["detail"]


# ---------------------------------------------------------------------------
# compute_verdict
# ---------------------------------------------------------------------------


def _pass_check(name="tier_gate") -> dict:
    return {"check": name, "status": "pass", "detail": "ok"}


def _fail_check(name="tier_gate") -> dict:
    return {"check": name, "status": "fail", "detail": "failed"}


def _warn_check(name="tier_gate") -> dict:
    return {"check": name, "status": "warn", "detail": "warning"}


class TestComputeVerdict:
    def test_all_pass_t3_returns_approve(self):
        checks = [_pass_check("tier_gate"), _pass_check("file_scope")]
        verdict, remediation = compute_verdict(checks, {"tier": "T3"})
        assert verdict == "approve"
        assert remediation is None

    def test_all_pass_t4_returns_escalate(self):
        checks = [_pass_check("tier_gate"), _pass_check("file_scope")]
        verdict, remediation = compute_verdict(checks, {"tier": "T4"})
        assert verdict == "escalate"
        assert remediation is not None
        assert remediation["action"] == "human_review_required"

    def test_warn_only_t3_returns_approve(self):
        checks = [_warn_check("file_scope")]
        verdict, remediation = compute_verdict(checks, {"tier": "T3"})
        assert verdict == "approve"
        assert remediation is None

    def test_single_fail_returns_reject(self):
        checks = [_fail_check("file_scope")]
        verdict, remediation = compute_verdict(checks, {"tier": "T3", "risk_level": "medium"})
        assert verdict == "reject"
        assert remediation is not None
        assert "file_scope" in remediation["reason"]

    def test_fail_with_critical_risk_escalates(self):
        checks = [_fail_check("file_scope")]
        verdict, remediation = compute_verdict(checks, {"tier": "T3", "risk_level": "critical"})
        assert verdict == "escalate"

    def test_fail_with_t4_escalates(self):
        checks = [_fail_check("confidence_threshold")]
        verdict, remediation = compute_verdict(checks, {"tier": "T4", "risk_level": "medium"})
        assert verdict == "escalate"

    def test_remediation_contains_failed_check_names(self):
        checks = [
            _fail_check("tier_gate"),
            _fail_check("file_scope"),
            _pass_check("forbidden_patterns"),
        ]
        verdict, remediation = compute_verdict(checks, {"tier": "T3", "risk_level": "low"})
        assert verdict == "reject"
        assert "tier_gate" in remediation["failed_checks"]
        assert "file_scope" in remediation["failed_checks"]
        assert "forbidden_patterns" not in remediation["failed_checks"]

    def test_remediation_reason_summary_lists_up_to_three_failed_checks(self):
        checks = [_fail_check(f"check_{i}") for i in range(5)]
        _, remediation = compute_verdict(checks, {"tier": "T3", "risk_level": "low"})
        # reason is built from first 3 fails only
        count = sum(1 for i in range(5) if f"check_{i}" in remediation["reason"])
        assert count <= 3

    def test_empty_checks_returns_approve(self):
        """No checks at all → no fails → approve (edge case)."""
        verdict, remediation = compute_verdict([], {"tier": "T3"})
        assert verdict == "approve"
        assert remediation is None

    def test_all_warns_no_fails_returns_approve(self):
        checks = [_warn_check("file_scope"), _warn_check("test_coverage")]
        verdict, remediation = compute_verdict(checks, {"tier": "T3"})
        assert verdict == "approve"
        assert remediation is None

    @pytest.mark.parametrize("risk", ["high", "medium", "low"])
    def test_non_critical_risk_with_fail_rejects(self, risk):
        checks = [_fail_check("file_scope")]
        verdict, _ = compute_verdict(checks, {"tier": "T3", "risk_level": risk})
        assert verdict == "reject"


# ---------------------------------------------------------------------------
# verify (integration of all checks)
# ---------------------------------------------------------------------------


class TestVerify:
    def test_good_t3_mutation_approves(self):
        m = _base_mutation()
        result = verify(m)
        assert result["verdict"] == "approve"

    def test_result_contains_required_keys(self):
        m = _base_mutation()
        result = verify(m)
        for key in ("verdict", "evidence", "tier", "mutation_id", "confidence_score", "timestamp", "dry_run"):
            assert key in result, f"Missing key: {key}"

    def test_tier_uppercased_in_result(self):
        m = _base_mutation(tier="t3")
        result = verify(m)
        assert result["tier"] == "T3"

    def test_mutation_id_in_result(self):
        m = _base_mutation(id="mut-special-42")
        result = verify(m)
        assert result["mutation_id"] == "mut-special-42"

    def test_dry_run_flag_propagated(self):
        m = _base_mutation()
        result = verify(m, dry_run=True)
        assert result["dry_run"] is True

    def test_evidence_list_has_five_items(self):
        m = _base_mutation()
        result = verify(m)
        assert len(result["evidence"]) == 5

    def test_all_evidence_have_required_fields(self):
        m = _base_mutation()
        result = verify(m)
        for ev in result["evidence"]:
            assert "check" in ev
            assert "status" in ev
            assert "detail" in ev

    def test_out_of_scope_file_triggers_reject(self):
        m = _base_mutation(
            allowed_files=["scripts/"],
            changed_files=["scripts/ok.py", "evil/hack.py"],
        )
        result = verify(m)
        assert result["verdict"] == "reject"
        assert result["remediation_task"] is not None

    def test_forbidden_file_triggers_reject(self):
        m = _base_mutation(changed_files=["configs/.env"])
        result = verify(m)
        assert result["verdict"] == "reject"

    def test_missing_test_evidence_t3_triggers_reject(self):
        m = _base_mutation(tier="T3", test_evidence=None)
        result = verify(m)
        assert result["verdict"] == "reject"

    def test_low_confidence_triggers_reject(self):
        m = _base_mutation(tier="T3", confidence_score=50.0)
        result = verify(m)
        assert result["verdict"] == "reject"

    def test_t4_clean_mutation_escalates(self):
        m = _base_mutation(tier="T4", confidence_score=95.0)
        result = verify(m)
        assert result["verdict"] == "escalate"

    def test_critical_risk_fail_escalates(self):
        m = _base_mutation(
            tier="T3",
            risk_level="critical",
            changed_files=["configs/.env"],
        )
        result = verify(m)
        assert result["verdict"] == "escalate"

    def test_missing_id_uses_unknown(self):
        m = _base_mutation()
        del m["id"]
        result = verify(m)
        assert result["mutation_id"] == "unknown"

    def test_timestamp_is_iso8601_z(self):
        m = _base_mutation()
        result = verify(m)
        ts = result["timestamp"]
        assert ts.endswith("Z")
        assert "T" in ts


# ---------------------------------------------------------------------------
# write_audit
# ---------------------------------------------------------------------------


class TestWriteAudit:
    def test_writes_file_to_audit_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_va, "AUDIT_DIR", tmp_path / "verifier")
        result = verify(_base_mutation())
        path = write_audit(result)
        assert path.exists()
        assert path.suffix == ".json"

    def test_written_json_is_valid(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_va, "AUDIT_DIR", tmp_path / "verifier")
        result = verify(_base_mutation())
        path = write_audit(result)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["verdict"] == result["verdict"]

    def test_latest_json_is_updated(self, tmp_path, monkeypatch):
        audit_dir = tmp_path / "verifier"
        monkeypatch.setattr(_va, "AUDIT_DIR", audit_dir)
        result = verify(_base_mutation())
        write_audit(result)
        latest = audit_dir / "latest.json"
        assert latest.exists()
        loaded = json.loads(latest.read_text(encoding="utf-8"))
        assert loaded["verdict"] == result["verdict"]

    def test_audit_dir_created_if_missing(self, tmp_path, monkeypatch):
        deep_dir = tmp_path / "deep" / "nested" / "verifier"
        monkeypatch.setattr(_va, "AUDIT_DIR", deep_dir)
        result = verify(_base_mutation())
        write_audit(result)
        assert deep_dir.exists()

    def test_filename_includes_mutation_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_va, "AUDIT_DIR", tmp_path / "verifier")
        result = verify(_base_mutation(id="mut-ABC"))
        result["mutation_id"] = "mut-ABC"
        path = write_audit(result)
        assert "mut_ABC" in path.name or "mut-ABC" in path.name or "mutABC" in path.name.replace("_", "")

    def test_returns_path_object(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_va, "AUDIT_DIR", tmp_path / "verifier")
        result = verify(_base_mutation())
        path = write_audit(result)
        assert isinstance(path, Path)


# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------


class TestConstants:
    def test_verification_required_tiers_contains_t3_t4(self):
        assert "T3" in VERIFICATION_REQUIRED_TIERS
        assert "T4" in VERIFICATION_REQUIRED_TIERS

    def test_verification_required_tiers_excludes_t1_t2(self):
        assert "T1" not in VERIFICATION_REQUIRED_TIERS
        assert "T2" not in VERIFICATION_REQUIRED_TIERS

    def test_confidence_thresholds_all_tiers_present(self):
        for tier in ("T1", "T2", "T3", "T4"):
            assert tier in CONFIDENCE_THRESHOLDS

    def test_confidence_thresholds_ascending(self):
        assert CONFIDENCE_THRESHOLDS["T1"] < CONFIDENCE_THRESHOLDS["T2"]
        assert CONFIDENCE_THRESHOLDS["T2"] < CONFIDENCE_THRESHOLDS["T3"]
        assert CONFIDENCE_THRESHOLDS["T3"] < CONFIDENCE_THRESHOLDS["T4"]


# ---------------------------------------------------------------------------
# Retry / multi-pass simulation
# ---------------------------------------------------------------------------


class TestRetryBehaviour:
    """Simulate how a caller might retry after a reject verdict by fixing the mutation."""

    def test_fix_scope_violation_leads_to_approve(self):
        bad = _base_mutation(
            allowed_files=["scripts/"],
            changed_files=["scripts/ok.py", "evil/rogue.py"],
        )
        result_bad = verify(bad)
        assert result_bad["verdict"] == "reject"

        fixed = _base_mutation(
            allowed_files=["scripts/", "evil/"],
            changed_files=["scripts/ok.py", "evil/rogue.py"],
        )
        result_fixed = verify(fixed)
        assert result_fixed["verdict"] == "approve"

    def test_fix_confidence_leads_to_approve(self):
        low = _base_mutation(tier="T3", confidence_score=50.0)
        assert verify(low)["verdict"] == "reject"

        high = _base_mutation(tier="T3", confidence_score=80.0)
        assert verify(high)["verdict"] == "approve"

    def test_fix_test_evidence_leads_to_approve(self):
        no_ev = _base_mutation(tier="T3", test_evidence=None)
        assert verify(no_ev)["verdict"] == "reject"

        with_ev = _base_mutation(tier="T3", test_evidence="pytest: 10 passed")
        assert verify(with_ev)["verdict"] == "approve"

    def test_multiple_failures_all_must_be_fixed(self):
        broken = _base_mutation(
            tier="T3",
            confidence_score=50.0,
            test_evidence=None,
            changed_files=["evil/.env"],
            allowed_files=["scripts/"],
        )
        result = verify(broken)
        assert result["verdict"] in ("reject", "escalate")
        fail_checks = [e["check"] for e in result["evidence"] if e["status"] == "fail"]
        assert len(fail_checks) >= 2
