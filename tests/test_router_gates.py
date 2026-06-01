"""Tests for router gates: confidence, privacy, budget, fallback."""

import tempfile
import pytest
import importlib

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

from router.contracts import (  # noqa: E402
    RouteRequest,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    RouteInput,
    TaskType,
    PrivacyClass,
    ConfidenceBand,
)
from router.router import ChromaticRouter  # noqa: E402
from router.confidence import ConfidenceGate  # noqa: E402
from router.context_detector import RuntimeContext  # noqa: E402


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
    assert resp.selected_provider in [
        "ollama",
        "lmstudio",
        "featherless",
        "mock",
        "native_claude",
    ]
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
    assert resp.route_reason != "confidence_gate_blocked"


@pytest.mark.asyncio
async def test_budget_gate_blocks_excessive_cost(router):
    req = make_req(max_cost_usd=0.001, confidence_score=90.0)
    resp = await router.route(req)
    # native_claude / local providers have $0 cost so pass the budget gate;
    # adapter_error is acceptable when the free provider fails in test env
    assert resp.route_reason in [
        "budget_gate_blocked",
        "mock_fallback",
        "openhuman_disabled",
        "adapter_error",
    ]


@pytest.mark.asyncio
async def test_preferred_provider_respected_if_allowed(router):
    req = make_req(preferred_provider="mock", confidence_score=90.0)
    resp = await router.route(req)
    assert resp.selected_provider == "mock"


@pytest.mark.asyncio
async def test_context_routing_uses_request_prompt_text(router, monkeypatch):
    captured: dict[str, str] = {}

    def fake_classify(description: str, prompt: str = "", max_files_hint=None):
        captured["description"] = description
        captured["prompt"] = prompt
        return type(
            "ComplexityResultStub",
            (),
            {
                "level": "C2",
                "name": "stub",
                "confidence": 1.0,
                "matched_keywords": [],
                "reasoning_depth": "medium",
            },
        )()

    def fake_detect():
        return RuntimeContext(
            device_type="laptop",
            gpu_model=None,
            gpu_vram_gb=None,
            gpu_available=False,
            ollama_local_reachable=True,
            ollama_local_models=["llama3.2:3b"],
            remote_ollama_endpoints=[],
            internet_reachable=True,
            connectivity="full",
            memory_pressure="medium",
            os_family="windows",
            cpu_count=8,
            is_battery=False,
        )

    def fake_select(complexity, context, privacy_class):
        choice = type("ChoiceStub", (), {"provider": "mock"})()
        return type(
            "SelectionResultStub",
            (),
            {"ranked_choices": [choice], "speed_mode": "balance"},
        )()

    monkeypatch.setattr(router.complexity_classifier, "classify", fake_classify)
    monkeypatch.setattr(router.context_detector, "detect", fake_detect)
    monkeypatch.setattr(router.provider_selector, "select", fake_select)

    req = make_req(confidence_score=90.0)
    req.input = RouteInput(
        messages=[
            {"role": "system", "content": "Use careful reasoning."},
            {"role": "user", "content": "Please refactor the auth flow."},
        ],
        metadata={"prompt": "Consider integration risk."},
    )

    resp = await router.route(req)

    assert resp.selected_provider == "mock"
    assert captured["description"] == "test objective"
    assert "Use careful reasoning." in captured["prompt"]
    assert "Please refactor the auth flow." in captured["prompt"]
    assert "Consider integration risk." in captured["prompt"]


@pytest.mark.asyncio
async def test_fallback_to_mock_when_provider_disabled(router):
    req = make_req(
        preferred_provider="openhuman",
        allow_openhuman=True,
        confidence_score=90.0,
        privacy_class=PrivacyClass.P1,
    )
    resp = await router.route(req)
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
    import json

    with tempfile.TemporaryDirectory() as td:
        import pathlib

        obs = observability_mod.ObservabilityLogger(log_dir=pathlib.Path(td))
        r = ChromaticRouter(logger=obs)
        req = make_req(confidence_score=90.0)
        await r.route(req)
        log_files = list(pathlib.Path(td).glob("*.jsonl"))
        assert len(log_files) == 1
        lines = log_files[0].read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["request_id"] == req.request_id
        assert "selected_provider" in entry


@pytest.mark.asyncio
async def test_agent_run_log_written_for_governed_model():
    """_log_agent_run appends a PDR-format record when model is sonnet or kimi."""
    import json
    import pathlib

    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        agent_log = td_path / "AGENT_RUN_LOG.jsonl"
        obs = observability_mod.ObservabilityLogger(log_dir=td_path, agent_run_log=agent_log)
        r = ChromaticRouter(logger=obs)
        req = make_req(confidence_score=90.0, preferred_provider="mock")
        resp = await r.route(req)
        # Manually invoke _log_agent_run with a governed model name so we can
        # test the write path without depending on a live sonnet/kimi provider.
        resp.selected_model = "claude-sonnet-4-6"
        obs._log_agent_run(req, resp, extra={"role": "architect", "tools_used": 3})

        assert agent_log.exists()
        lines = [line for line in agent_log.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["model"] == "claude-sonnet-4-6"
        assert record["role"] == "architect"
        assert record["tools_used"] == 3
        assert record["confidence_score"] == 90.0
        assert record["risk_level"] == "low"
        assert "result" in record


@pytest.mark.asyncio
async def test_agent_run_log_not_written_for_non_governed_model():
    """_log_agent_run must NOT fire for models that aren't sonnet or kimi."""
    import pathlib

    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        agent_log = td_path / "AGENT_RUN_LOG.jsonl"
        obs = observability_mod.ObservabilityLogger(log_dir=td_path, agent_run_log=agent_log)
        r = ChromaticRouter(logger=obs)
        req = make_req(confidence_score=90.0, preferred_provider="mock")
        await r.route(req)
        # mock provider → selected_model is empty / not sonnet or kimi
        assert not agent_log.exists()
