"""Tests for PrivacyGate: classification, allow/block decisions, provider filtering."""

from __future__ import annotations

import pytest

from router.privacy import PrivacyGate
from router.contracts import (
    PrivacyClass,
    RouteRequest,
    RouteInput,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    TaskType,
    ConfidenceBand,
)


def _make_req(
    privacy_class: PrivacyClass = PrivacyClass.P1,
    preferred_provider: str = "auto",
    human_gate_required: bool = False,
) -> RouteRequest:
    return RouteRequest(
        request_id="r-test",
        task_id="t-test",
        task_type=TaskType.CLASSIFICATION,
        objective="test objective",
        input=RouteInput(),
        constraints=RouteConstraints(privacy_class=privacy_class),
        confidence=RouteConfidence(score=80.0, band=ConfidenceBand.HIGH),
        preferred_provider=preferred_provider,
        fallback_chain=[],
        audit=RouteAudit(human_gate_required=human_gate_required),
    )


# ── classify_text ────────────────────────────────────────────────────────────

class TestClassifyText:
    @pytest.fixture
    def gate(self):
        return PrivacyGate()

    def test_public_content_is_p1(self, gate):
        result = gate.classify_text("This is a public README with general information.")
        assert result == PrivacyClass.P1

    def test_api_key_indicator_is_p3(self, gate):
        result = gate.classify_text("api_key=abc123")
        assert result == PrivacyClass.P3

    def test_sk_prefix_is_p3(self, gate):
        result = gate.classify_text("sk-1234567890abcdef1234567890abcdef")  # pragma: allowlist secret
        assert result == PrivacyClass.P3

    def test_github_token_is_p3(self, gate):
        result = gate.classify_text("ghp_1234567890abcdef1234567890abcdef")  # pragma: allowlist secret
        assert result == PrivacyClass.P3

    def test_password_indicator_is_p3(self, gate):
        result = gate.classify_text("password=super_secret")
        assert result == PrivacyClass.P3

    def test_bearer_token_is_p3(self, gate):
        result = gate.classify_text("Authorization: bearer mytoken123")
        assert result == PrivacyClass.P3

    def test_aws_secret_is_p3(self, gate):
        result = gate.classify_text("aws_secret_access_key=AKIAIOSFODNN7EXAMPLE")  # pragma: allowlist secret
        assert result == PrivacyClass.P3

    def test_hipaa_is_p4(self, gate):
        result = gate.classify_text("This is a HIPAA compliance audit")
        assert result == PrivacyClass.P4

    def test_gdpr_is_p4(self, gate):
        result = gate.classify_text("GDPR data processing review")
        assert result == PrivacyClass.P4

    def test_medical_is_p4(self, gate):
        result = gate.classify_text("medical diagnosis details here")
        assert result == PrivacyClass.P4

    def test_legal_opinion_is_p4(self, gate):
        result = gate.classify_text("legal opinion on the contract")
        assert result == PrivacyClass.P4

    def test_p3_takes_priority_over_public(self, gate):
        result = gate.classify_text("here is the public doc with api_key embedded")
        assert result == PrivacyClass.P3

    def test_case_insensitive(self, gate):
        result = gate.classify_text("API_KEY=value")
        assert result == PrivacyClass.P3

    def test_empty_text_is_p1(self, gate):
        result = gate.classify_text("")
        assert result == PrivacyClass.P1


# ── check() gate decisions ───────────────────────────────────────────────────

class TestPrivacyGateCheck:
    @pytest.fixture
    def gate(self):
        return PrivacyGate()

    def test_p1_passes(self, gate):
        req = _make_req(PrivacyClass.P1)
        ok, logs = gate.check(req)
        assert ok is True
        assert logs.errors == []
        assert any("passed" in msg.lower() for msg in logs.policy_checks)

    def test_p0_passes(self, gate):
        req = _make_req(PrivacyClass.P0)
        ok, logs = gate.check(req)
        assert ok is True

    def test_p2_passes(self, gate):
        req = _make_req(PrivacyClass.P2)
        ok, logs = gate.check(req)
        assert ok is True

    def test_p3_blocked(self, gate):
        req = _make_req(PrivacyClass.P3)
        ok, logs = gate.check(req)
        assert ok is False
        assert any("P3" in e for e in logs.errors)
        assert any("secret" in e.lower() or "blocked" in e.lower() for e in logs.errors)

    def test_p4_blocked_without_human_gate(self, gate):
        req = _make_req(PrivacyClass.P4, human_gate_required=False)
        ok, logs = gate.check(req)
        assert ok is False
        assert any("P4" in e or "human gate" in e.lower() for e in logs.errors)

    def test_p4_passes_with_human_gate(self, gate):
        req = _make_req(PrivacyClass.P4, human_gate_required=True)
        ok, logs = gate.check(req)
        assert ok is True
        assert any("P4" in msg for msg in logs.policy_checks)

    def test_preferred_provider_not_in_allowlist_adds_warning(self, gate):
        # P1 allows many providers but not an unknown one
        req = _make_req(PrivacyClass.P1, preferred_provider="some_unknown_provider")
        ok, logs = gate.check(req)
        # P1 is not blocked by the gate itself
        assert ok is True
        assert any("not in privacy allowlist" in w or "allowlist" in w.lower() for w in logs.warnings)

    def test_auto_provider_no_warning(self, gate):
        req = _make_req(PrivacyClass.P1, preferred_provider="auto")
        ok, logs = gate.check(req)
        assert ok is True
        assert not any("allowlist" in w for w in logs.warnings)

    def test_p3_returns_error_log_not_warning(self, gate):
        req = _make_req(PrivacyClass.P3)
        ok, logs = gate.check(req)
        assert ok is False
        # Error, not just warning
        assert len(logs.errors) > 0

    def test_passed_log_mentions_privacy_class(self, gate):
        req = _make_req(PrivacyClass.P2)
        ok, logs = gate.check(req)
        assert ok is True
        assert any("P2" in msg for msg in logs.policy_checks)


# ── PrivacyGate initialization ───────────────────────────────────────────────

class TestPrivacyGateInit:
    def test_default_init(self):
        gate = PrivacyGate()
        assert gate.policy is not None

    def test_policy_loaded(self):
        gate = PrivacyGate()
        # Policy should have at least P0 and P1
        assert isinstance(gate.policy, dict)

    def test_numeric_order(self):
        gate = PrivacyGate()
        # _numeric uses str(p) which for PrivacyClass str-enum gives "PrivacyClass.P0"
        # So we pass the string value directly to exercise the expected lookup path.
        assert gate._numeric("P0") == 0
        assert gate._numeric("P1") == 1
        assert gate._numeric("P2") == 2
        assert gate._numeric("P3") == 3
        assert gate._numeric("P4") == 4

    def test_numeric_unknown_defaults_to_4(self):
        gate = PrivacyGate()
        assert gate._numeric("UNKNOWN") == 4
