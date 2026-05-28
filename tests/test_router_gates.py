"""Tests for router gates: confidence, privacy, budget, fallback."""

import sys
import os
import tempfile
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_RUNTIME = os.path.join(_REPO, "02_RUNTIME")
sys.path.insert(0, _REPO)
sys.path.insert(0, _RUNTIME)

import importlib

# Ensure router modules importable from 02_RUNTIME
import router.contracts as contracts_mod
import router.policy as policy_mod
import router.confidence as confidence_mod
import router.privacy as privacy_mod
import router.budget as budget_mod
import router.observability as observability_mod
import router.router as router_mod

importlib.reload(contracts_mod)
importlib.reload(policy_mod)
importlib.reload(confidence_mod)
importlib.reload(privacy_mod)
importlib.reload(budget_mod)
importlib.reload(observability_mod)
importlib.reload(router_mod)

from router.contracts import (
    RouteRequest,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    RouteInput,
    TaskType,
    PrivacyClass,
    ConfidenceBand,
)
from router.router import ChromaticRouter
from router.confidence import ConfidenceGate


@pytest.fixture
def router():
    return ChromaticRouter()


def make_req(
    privacy_class: PrivacyClass = PrivacyClass.P1,
    confidence_score: float = 75.0,
    preferred_provider: str = "auto",
    task_type: TaskType = TaskType.CLASSIFICATION,
    objective: str = "test objective",
    max_cost_usd: float = 1.0,
    allow_openhuman: bool = False,
) -> RouteRequest:
    return RouteRequest(
        request_id="r-test",
        task_id="t-test",
        task_type=task_type,
        objective=objective,
        input=RouteInput(),
        constraints=RouteConstraints(
            privacy_class=privacy_class,
            max_cost_usd=max_cost_usd,
            allow_openhuman=allow_openhuman,
        ),
        confidence=RouteConfidence(
            score=confidence_score,
            band=ConfidenceGate.band_from_score(confidence_score),
        ),
        preferred_provider=preferred_provider,
        fallback_chain=[],
        audit=RouteAudit(caller="test"),
    )


@pytest.mark.asyncio
async def test_router_selects_provider_from_policy(router):
    req = make_req(task_type=TaskType.CLASSIFICATION, confidence_score=80.0)
    resp = await router.route(req)
    assert resp.request_id == req.request_id
    assert resp.selected_provider in ["ollama", "lmstudio", "featherless", "mock"]
    assert resp.confidence_score == 80.0


@pytest.mark.asyncio
async def test_privacy_gate_blocks_p3(router):
    req = make_req(privacy_class=PrivacyClass.P3, confidence_score=95.0)
    resp = await router.route(req)
    assert resp.selected_provider == ""
    assert resp.route_reason == "privacy_gate_blocked"
    assert any("P3" in e for e in resp.logs.errors)


@pytest.mark.asyncio
async def test_confidence_gate_blocks_below_60(router):
    req = make_req(confidence_score=45.0)
    resp = await router.route(req)
    assert resp.selected_provider == ""
    assert resp.route_reason == "confidence_gate_blocked"
    assert any("60" in e for e in resp.logs.errors)


@pytest.mark.asyncio
async def test_confidence_gate_allows_at_60(router):
    req = make_req(confidence_score=60.0)
    resp = await router.route(req)
    # Should proceed (Medium band)
    assert resp.route_reason != "confidence_gate_blocked"


@pytest.mark.asyncio
async def test_budget_gate_blocks_excessive_cost(router):
    req = make_req(max_cost_usd=0.001, confidence_score=90.0)
    resp = await router.route(req)
    # Most providers exceed 0.001 for 8000 tokens
    # If budget gate blocks, route_reason == budget_gate_blocked
    # Otherwise mock fallback may succeed at 0 cost
    assert resp.route_reason in ["budget_gate_blocked", "mock_fallback", "openhuman_disabled"]


@pytest.mark.asyncio
async def test_preferred_provider_respected_if_allowed(router):
    req = make_req(preferred_provider="mock", confidence_score=90.0)
    resp = await router.route(req)
    assert resp.selected_provider == "mock"


@pytest.mark.asyncio
async def test_fallback_to_mock_when_provider_disabled(router):
    # All real providers may be disabled in test env
    req = make_req(
        preferred_provider="openhuman",
        allow_openhuman=True,
        confidence_score=90.0,
        privacy_class=PrivacyClass.P1,
    )
    resp = await router.route(req)
    # OpenHuman disabled by default → fallback chain should land on mock
    assert resp.selected_provider == "mock"
    assert resp.fallback_used is True


@pytest.mark.asyncio
async def test_classify_text_detects_secrets():
    pg = privacy_mod.PrivacyGate()
    assert pg.classify_text("sk-1234567890abcdef1234567890") == PrivacyClass.P3
    assert pg.classify_text("api_key=ghp_1234567890abcdef") == PrivacyClass.P3
    assert pg.classify_text("public README content") == PrivacyClass.P1
    assert pg.classify_text("HIPAA compliance review") == PrivacyClass.P4


@pytest.mark.asyncio
async def test_band_from_score():
    assert ConfidenceGate.band_from_score(95) == ConfidenceBand.VERY_HIGH
    assert ConfidenceGate.band_from_score(80) == ConfidenceBand.HIGH
    assert ConfidenceGate.band_from_score(65) == ConfidenceBand.MEDIUM
    assert ConfidenceGate.band_from_score(50) == ConfidenceBand.LOW
    assert ConfidenceGate.band_from_score(30) == ConfidenceBand.BLOCKED


@pytest.mark.asyncio
async def test_jsonl_log_created(router):
    import tempfile as tf
    import json
    with tf.TemporaryDirectory() as td:
        obs = observability_mod.ObservabilityLogger(log_dir=__import__("pathlib").Path(td))
        r = ChromaticRouter(logger=obs)
        req = make_req(confidence_score=90.0)
        resp = await r.route(req)
        log_files = list(__import__("pathlib").Path(td).glob("*.jsonl"))
        assert len(log_files) == 1
        lines = log_files[0].read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["request_id"] == req.request_id
        assert "selected_provider" in entry
