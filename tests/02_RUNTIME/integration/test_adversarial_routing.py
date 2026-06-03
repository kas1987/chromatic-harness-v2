"""Adversarial routing tests — probe the failure modes of the privacy gate,
confidence validation, provider blocklist, complexity reclassification, and
fallback-chain exhaustion.

All tests are unit-level (no real network calls, no real LLM) and run fully
offline using mocks/monkeypatches.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure 02_RUNTIME is importable (mirrors the conftest at the subtree root)
_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from router.contracts import (
    ConfidenceBand,
    OutputType,
    PrivacyClass,
    RouteAudit,
    RouteConfidence,
    RouteConstraints,
    RouteInput,
    RouteRequest,
    TaskType,
)
from router.privacy import PrivacyGate
from router.confidence import ConfidenceGate
from router.complexity_classifier import ComplexityClassifier
from router.provider_selector import ProviderSelector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_req(
    *,
    privacy_class: PrivacyClass = PrivacyClass.P1,
    preferred_provider: str = "auto",
    human_gate_required: bool = False,
    confidence_score: float = 80.0,
    confidence_band: ConfidenceBand = ConfidenceBand.HIGH,
    max_cost_usd: float = 0.25,
    max_tokens: int = 4000,
    fallback_chain: list[str] | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id="r-adv-test",
        task_id="t-adv-test",
        task_type=TaskType.CODING,
        objective="adversarial test task",
        input=RouteInput(),
        constraints=RouteConstraints(
            privacy_class=privacy_class,
            max_cost_usd=max_cost_usd,
            max_tokens=max_tokens,
        ),
        confidence=RouteConfidence(score=confidence_score, band=confidence_band),
        preferred_provider=preferred_provider,
        fallback_chain=fallback_chain or [],
        audit=RouteAudit(human_gate_required=human_gate_required),
    )


# ---------------------------------------------------------------------------
# 1. P3/P4 content is BLOCKED by the privacy gate
# ---------------------------------------------------------------------------


class TestPrivacyGateBlocks:
    """P3 and P4 (without human gate) must never pass to an unsafe provider."""

    def test_p3_is_always_blocked(self):
        gate = PrivacyGate()
        req = _make_req(privacy_class=PrivacyClass.P3)
        ok, logs = gate.check(req)
        assert ok is False, "P3 content must be blocked unconditionally"
        assert logs.errors, "blocked request must populate logs.errors"
        assert any("P3" in e for e in logs.errors)

    def test_p3_blocked_even_with_human_gate(self):
        """P3 = secrets/tokens; human gate is not a bypass for P3."""
        gate = PrivacyGate()
        req = _make_req(privacy_class=PrivacyClass.P3, human_gate_required=True)
        ok, logs = gate.check(req)
        assert ok is False, "P3 must be blocked regardless of human_gate_required"

    def test_p4_blocked_without_human_gate(self):
        gate = PrivacyGate()
        req = _make_req(privacy_class=PrivacyClass.P4, human_gate_required=False)
        ok, logs = gate.check(req)
        assert ok is False, "P4 without human gate must be blocked"
        assert logs.errors

    def test_p4_passes_only_with_human_gate(self):
        gate = PrivacyGate()
        req = _make_req(privacy_class=PrivacyClass.P4, human_gate_required=True)
        ok, logs = gate.check(req)
        assert ok is True, "P4 with human gate should pass"

    def test_p3_classified_from_secret_text_then_blocked(self):
        """Classify secret text → P3, then confirm the gate rejects it."""
        gate = PrivacyGate()
        text = "export API_KEY=supersecretvalue"  # pragma: allowlist secret
        pc = gate.classify_text(text)
        assert pc == PrivacyClass.P3
        req = _make_req(privacy_class=pc)
        ok, logs = gate.check(req)
        assert ok is False

    def test_p4_classified_from_hipaa_text_then_blocked_without_gate(self):
        gate = PrivacyGate()
        text = "This is a HIPAA compliance audit for patient records."
        pc = gate.classify_text(text)
        assert pc == PrivacyClass.P4
        req = _make_req(privacy_class=pc, human_gate_required=False)
        ok, _ = gate.check(req)
        assert ok is False

    def test_unsafe_provider_for_p2_generates_warning_not_block(self):
        """An unlisted preferred_provider for P2 is a *warning*, not a hard block."""
        gate = PrivacyGate()
        req = _make_req(privacy_class=PrivacyClass.P2, preferred_provider="rogue_provider")
        ok, logs = gate.check(req)
        assert ok is True, "P2 with unknown preferred provider should still pass"
        assert any("not in privacy allowlist" in w or "allowlist" in w.lower() for w in logs.warnings)


# ---------------------------------------------------------------------------
# 2. Forged confidence scores are rejected
# ---------------------------------------------------------------------------


class TestConfidenceScoreValidation:
    """The gate must reject out-of-range confidence and BLOCKED band."""

    def test_score_below_60_is_blocked(self):
        gate = ConfidenceGate()
        req = _make_req(confidence_score=30.0, confidence_band=ConfidenceBand.LOW)
        ok, logs = gate.check(req)
        assert ok is False
        assert logs.errors

    def test_score_zero_is_blocked(self):
        gate = ConfidenceGate()
        req = _make_req(confidence_score=0.0, confidence_band=ConfidenceBand.BLOCKED)
        ok, logs = gate.check(req)
        assert ok is False

    def test_band_blocked_is_rejected_even_if_score_high(self):
        """BLOCKED band takes precedence even with a seemingly high numeric score."""
        gate = ConfidenceGate()
        req = _make_req(confidence_score=99.0, confidence_band=ConfidenceBand.BLOCKED)
        ok, logs = gate.check(req)
        assert ok is False, "BLOCKED band must halt the route regardless of numeric score"

    def test_negative_score_is_blocked(self):
        """Negative scores (adversarial injection) must not pass."""
        gate = ConfidenceGate()
        req = _make_req(confidence_score=-1.0, confidence_band=ConfidenceBand.BLOCKED)
        ok, logs = gate.check(req)
        assert ok is False

    def test_score_above_100_passes_if_band_is_valid(self):
        """score > 100 is technically forged but the gate only checks < 60 / BLOCKED;
        document the current behaviour so future hardening can flip this deliberately."""
        gate = ConfidenceGate()
        req = _make_req(confidence_score=999.0, confidence_band=ConfidenceBand.VERY_HIGH)
        ok, logs = gate.check(req)
        # The gate currently passes scores > 100 with a valid band.
        assert ok is True, "gate currently passes scores > 100 with a valid band"

    def test_score_exactly_60_passes(self):
        gate = ConfidenceGate()
        req = _make_req(confidence_score=60.0, confidence_band=ConfidenceBand.MEDIUM)
        ok, logs = gate.check(req)
        assert ok is True

    def test_band_from_score_maps_very_large_to_very_high(self):
        """band_from_score(200) should not crash — maps to VERY_HIGH."""
        band = ConfidenceGate.band_from_score(200.0)
        assert band == ConfidenceBand.VERY_HIGH

    def test_band_from_score_negative_returns_blocked(self):
        band = ConfidenceGate.band_from_score(-10.0)
        assert band == ConfidenceBand.BLOCKED


# ---------------------------------------------------------------------------
# 3. Provider blocklist is enforced
# ---------------------------------------------------------------------------


class TestProviderBlocklist:
    """Providers in the user-preference blocklist must be removed from ranked results."""

    def _make_selector_with_blocklist(self, blocklisted: list[str]) -> ProviderSelector:
        """Build a ProviderSelector whose prefs dict contains a provider_blocklist."""
        sel = ProviderSelector.__new__(ProviderSelector)
        sel._table = {}
        sel._prefs = {"provider_blocklist": blocklisted}
        sel._providers_cfg = {}
        sel._openrouter_allowlist = set()
        return sel

    def test_blocklisted_provider_removed_from_choices(self):
        from router.provider_selector import ProviderChoice

        sel = self._make_selector_with_blocklist(["bad_provider"])
        choices = [
            ProviderChoice(provider="good_provider", model=None, tier=2, reason="test"),
            ProviderChoice(provider="bad_provider", model=None, tier=2, reason="test"),
        ]
        result = sel._apply_blocklist(choices)
        providers = [c.provider for c in result]
        assert "bad_provider" not in providers
        assert "good_provider" in providers

    def test_all_providers_blocklisted_returns_empty_list(self):
        from router.provider_selector import ProviderChoice

        sel = self._make_selector_with_blocklist(["p1", "p2"])
        choices = [
            ProviderChoice(provider="p1", model=None, tier=1, reason="test"),
            ProviderChoice(provider="p2", model=None, tier=1, reason="test"),
        ]
        result = sel._apply_blocklist(choices)
        assert result == []

    def test_empty_blocklist_leaves_choices_intact(self):
        from router.provider_selector import ProviderChoice

        sel = self._make_selector_with_blocklist([])
        choices = [
            ProviderChoice(provider="ollama_local", model=None, tier=0, reason="test"),
            ProviderChoice(provider="native_claude", model=None, tier=4, reason="test"),
        ]
        result = sel._apply_blocklist(choices)
        assert len(result) == 2

    def test_cloud_providers_blocked_for_p3_privacy(self):
        """Cloud providers must be pruned by _filter_by_privacy for P3 tasks."""
        from router.provider_selector import ProviderChoice, _CLOUD_ROUTING_PROVIDERS

        sel = ProviderSelector.__new__(ProviderSelector)
        sel._table = {}
        sel._prefs = {}
        sel._providers_cfg = {}
        sel._openrouter_allowlist = set()

        cloud_choices = [
            ProviderChoice(provider=p, model=None, tier=2, reason="test") for p in _CLOUD_ROUTING_PROVIDERS
        ]
        result = sel._filter_by_privacy(cloud_choices, "P3")
        assert result == [], "All cloud providers must be stripped for P3"

    def test_local_providers_allowed_for_p3_privacy(self):
        """Local providers (ollama, lmstudio, native_claude) must survive P3 filtering."""
        from router.provider_selector import ProviderChoice

        sel = ProviderSelector.__new__(ProviderSelector)
        sel._table = {}
        sel._prefs = {}
        sel._providers_cfg = {}
        sel._openrouter_allowlist = set()

        local_choices = [
            ProviderChoice(provider="ollama_local", model=None, tier=0, reason="test"),
            ProviderChoice(provider="lmstudio", model=None, tier=0, reason="test"),
            ProviderChoice(provider="native_claude", model=None, tier=0, reason="test"),
        ]
        result = sel._filter_by_privacy(local_choices, "P3")
        assert len(result) > 0, "At least one local provider must survive P3 filtering"


# ---------------------------------------------------------------------------
# 4. C1 task with C4 signals is correctly reclassified
# ---------------------------------------------------------------------------


class TestComplexityReclassification:
    """A task claiming simple keywords but containing high-complexity signals
    must be bumped to the appropriate C-level by the classifier."""

    def test_c1_description_with_large_fanout_bumped_to_c2_or_c3(self):
        """C1 keyword + impact_fan_out > 15 → should reach at least C2."""
        clf = ComplexityClassifier()
        result = clf.classify(
            description="format the JSON output",
            prompt="",
            impact_fan_out=20,  # large blast radius
        )
        assert result.level in ("C2", "C3"), f"Expected C2/C3 after large fan-out bump, got {result.level}"

    def test_c1_with_small_fanout_stays_c1_or_c2(self):
        clf = ComplexityClassifier()
        result = clf.classify(
            description="format the JSON output",
            prompt="",
            impact_fan_out=2,  # small blast radius, no bump
        )
        assert result.level in ("C1", "C2")

    def test_c4_signals_override_c1_keywords(self):
        """When a description contains both C1 and C4 keywords the classifier
        must not silently downgrade — at minimum it should not produce C1."""
        clf = ComplexityClassifier()
        result = clf.classify(
            description="format and convert the creative strategy and design tradeoffs document",
            prompt="",
        )
        # C4 keywords (brainstorm, design tradeoffs, creative, strategy) should dominate
        assert result.level in ("C3", "C4"), f"Expected C3/C4 when C4 signals present, got {result.level}"

    def test_no_keywords_defaults_to_c4_with_zero_confidence(self):
        """No matching keywords → safe fallback to C4 (never silently downgraded)."""
        clf = ComplexityClassifier()
        result = clf.classify(description="do the thing", prompt="")
        assert result.level == "C4"
        assert result.confidence == 0.0

    def test_confidence_clamped_to_1_0(self):
        """Classifier must never emit confidence > 1.0."""
        clf = ComplexityClassifier()
        # Saturate all C1 keywords
        result = clf.classify(
            description="format convert extract json-to-table boilerplate",
            prompt="",
        )
        assert result.confidence <= 1.0, f"confidence {result.confidence} exceeds 1.0"

    def test_evidence_source_set_when_fanout_bumps(self):
        clf = ComplexityClassifier()
        result = clf.classify(
            description="format data",
            prompt="",
            impact_fan_out=10,
        )
        if result.level in ("C2", "C3"):
            assert result.evidence_source == "codegraph_impact"

    def test_keyword_evidence_source_used_when_no_fanout(self):
        clf = ComplexityClassifier()
        result = clf.classify(
            description="format data",
            prompt="",
            max_files_hint=10,
        )
        if result.level in ("C2", "C3"):
            assert result.evidence_source == "keyword"


# ---------------------------------------------------------------------------
# 5. Fallback chain exhaustion returns a clear error, not silent failure
# ---------------------------------------------------------------------------


class TestFallbackChainExhaustion:
    """When every provider in the chain fails the router must surface an
    explicit error response, NOT silently return empty/partial data."""

    @pytest.mark.asyncio
    async def test_all_providers_failed_returns_error_response(self):
        """With only failing adapters and no mock the router must return ERROR.

        We bypass policy gates (privacy allowlist, context gate) by patching
        _resolve_provider and context_gate.check so the test exercises only the
        adapter-execution path.
        """
        from router.adapters.base import AdapterHealth, BaseAdapter
        from router.contracts import ContextGateResult, RouteLogs
        from router.router import ChromaticRouter

        class AlwaysFailAdapter(BaseAdapter):
            def __init__(self) -> None:
                self.name = "bad_provider"
                self.cfg = {}
                self.enabled = True

            async def health(self) -> AdapterHealth:
                return AdapterHealth(reachable=False, latency_ms=0)

            async def complete(self, req):
                raise RuntimeError("Simulated provider failure")

        router = ChromaticRouter(
            adapters={
                "bad_provider": AlwaysFailAdapter(),
            }
        )
        # Remove the mock adapter so there is no safety net
        router.adapters.pop("mock", None)

        # Bypass context gate and privacy-allowlist filtering
        router.context_gate.check = lambda req, **kw: ContextGateResult(ok=True)
        router._resolve_provider = lambda req: ("bad_provider", [], RouteLogs())

        req = _make_req(preferred_provider="bad_provider", confidence_score=80.0)

        resp = await router.route(req)
        assert resp.output.type == OutputType.ERROR, (
            "Full fallback exhaustion must surface an ERROR output, not silent success"
        )
        assert resp.output.content, "Error response must have a non-empty content field"

    @pytest.mark.asyncio
    async def test_fallback_chain_tried_in_order(self):
        """Router must try primary then each fallback, in order, before giving up.

        We patch _resolve_provider to bypass privacy-allowlist filtering so the
        test focuses solely on the fallback-iteration logic.
        """
        from router.adapters.base import AdapterHealth, BaseAdapter
        from router.contracts import OutputType as OT
        from router.contracts import RouteLogs, RouteOutput, RouteResponse
        from router.router import ChromaticRouter

        call_order: list[str] = []

        class TrackedFailAdapter(BaseAdapter):
            def __init__(self, label: str) -> None:
                self._label = label
                self.name = label
                self.cfg = {}
                self.enabled = True

            async def health(self) -> AdapterHealth:
                return AdapterHealth(reachable=False, latency_ms=0)

            async def complete(self, req):
                call_order.append(self._label)
                raise RuntimeError(f"{self._label} failed")

        class SucceedAdapter(BaseAdapter):
            def __init__(self) -> None:
                self.name = "success_provider"
                self.cfg = {}
                self.enabled = True

            async def health(self) -> AdapterHealth:
                return AdapterHealth(reachable=True, latency_ms=1)

            async def complete(self, req):
                call_order.append("success_provider")
                return RouteResponse(
                    request_id=req.request_id,
                    selected_provider="success_provider",
                    output=RouteOutput(type=OT.TEXT, content="ok"),
                )

        router = ChromaticRouter(
            adapters={
                "first_fail": TrackedFailAdapter("first_fail"),
                "second_fail": TrackedFailAdapter("second_fail"),
                "success_provider": SucceedAdapter(),
                "mock": TrackedFailAdapter("mock"),
            }
        )

        # Bypass both context gate and privacy-allowlist filtering
        from router.contracts import ContextGateResult

        router.context_gate.check = lambda req, **kw: ContextGateResult(ok=True)
        router._resolve_provider = lambda req: (
            "first_fail",
            ["second_fail", "success_provider"],
            RouteLogs(),
        )

        req = _make_req(
            preferred_provider="first_fail",
            fallback_chain=["second_fail", "success_provider"],
            confidence_score=80.0,
        )

        resp = await router.route(req)
        assert "first_fail" in call_order
        assert "second_fail" in call_order
        assert "success_provider" in call_order
        assert call_order.index("first_fail") < call_order.index("second_fail")
        assert call_order.index("second_fail") < call_order.index("success_provider")

    @pytest.mark.asyncio
    async def test_fallback_to_mock_when_all_real_providers_fail(self):
        """When all real providers fail the router falls back to mock, not silent None.

        We patch _resolve_provider to bypass privacy-allowlist filtering.
        """
        from router.adapters.base import AdapterHealth, BaseAdapter
        from router.adapters.mock import MockAdapter
        from router.contracts import RouteLogs
        from router.router import ChromaticRouter

        class AlwaysFailAdapter(BaseAdapter):
            def __init__(self) -> None:
                self.name = "failing"
                self.cfg = {}
                self.enabled = True

            async def health(self) -> AdapterHealth:
                return AdapterHealth(reachable=False, latency_ms=0)

            async def complete(self, req):
                raise RuntimeError("always fails")

        router = ChromaticRouter(
            adapters={
                "failing": AlwaysFailAdapter(),
                "mock": MockAdapter(),
            }
        )

        # Bypass both context gate and privacy-allowlist filtering
        from router.contracts import ContextGateResult

        router.context_gate.check = lambda req, **kw: ContextGateResult(ok=True)
        router._resolve_provider = lambda req: ("failing", [], RouteLogs())

        req = _make_req(preferred_provider="failing", confidence_score=80.0)
        resp = await router.route(req)
        # Mock should produce a TEXT response, not an ERROR
        assert resp.output.type != OutputType.ERROR or resp.selected_provider == "mock", (
            "Router must use mock as last-resort fallback"
        )
        assert resp.output.content is not None
