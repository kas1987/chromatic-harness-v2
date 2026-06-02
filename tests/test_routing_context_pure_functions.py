"""Unit tests for RoutingContext sealed contract and pure-function stages.

Validates:
  - RoutingContext dataclass construction and immutability
  - OllamaEndpoint typed field (no dict[str,Any])
  - ComplexityClassifier.classify_context() pure function
  - ProviderSelector.select_context() pure function
  - ContextDetector.build_routing_context() I/O→value pipeline
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from router.complexity_classifier import ComplexityClassifier
from router.context_detector import ContextDetector, RuntimeContext
from router.contracts import OllamaEndpoint, PrivacyClass, RoutingContext
from router.provider_selector import ProviderSelector

EMPTY_PREFS = Path(__file__).resolve().parent / "fixtures" / "empty_prefs.yaml"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def classifier():
    return ComplexityClassifier()


@pytest.fixture
def selector():
    return ProviderSelector(prefs_path=EMPTY_PREFS)


def _make_ctx(**overrides) -> RoutingContext:
    base = dict(
        objective="test objective",
        task_description="format this json",
        prompt="convert to a table",
        device_type="laptop",
        gpu_available=False,
        ollama_local_reachable=True,
        ollama_local_models=("llama3.2:3b",),
        internet_reachable=True,
        privacy_class=PrivacyClass.P1,
        speed_mode="balance",
    )
    base.update(overrides)
    return RoutingContext(**base)


# ── OllamaEndpoint ────────────────────────────────────────────────────────────


def test_ollama_endpoint_defaults():
    ep = OllamaEndpoint(host="desktop.local")
    assert ep.port == 11434
    assert ep.enabled is True


def test_ollama_endpoint_frozen():
    ep = OllamaEndpoint(host="desktop.local")
    with pytest.raises(Exception):
        ep.host = "other"  # type: ignore[misc]


def test_ollama_endpoint_custom_port():
    ep = OllamaEndpoint(host="192.168.1.50", port=8080, enabled=False)
    assert ep.port == 8080
    assert ep.enabled is False


# ── RoutingContext ────────────────────────────────────────────────────────────


def test_routing_context_frozen():
    ctx = _make_ctx()
    with pytest.raises(Exception):
        ctx.objective = "changed"  # type: ignore[misc]


def test_routing_context_typed_endpoints():
    ep = OllamaEndpoint(host="desktop.local", port=11434)
    ctx = _make_ctx(remote_ollama_endpoints=(ep,))
    assert isinstance(ctx.remote_ollama_endpoints[0], OllamaEndpoint)
    assert ctx.remote_ollama_endpoints[0].host == "desktop.local"


def test_routing_context_privacy_class_enum():
    ctx = _make_ctx(privacy_class=PrivacyClass.P2)
    assert ctx.privacy_class == PrivacyClass.P2
    assert ctx.privacy_class.value == "P2"


def test_routing_context_defaults_conservative():
    ctx = RoutingContext(objective="do something")
    assert ctx.privacy_class == PrivacyClass.P1
    assert ctx.speed_mode == "balance"
    assert ctx.gpu_available is False
    assert ctx.ollama_local_reachable is False
    assert ctx.remote_ollama_endpoints == ()


def test_routing_context_models_tuple():
    ctx = _make_ctx(ollama_local_models=("llama3.2:3b", "qwen2.5-coder:14b"))
    assert isinstance(ctx.ollama_local_models, tuple)
    assert len(ctx.ollama_local_models) == 2


# ── ComplexityClassifier.classify_context ────────────────────────────────────


def test_classify_context_c1(classifier):
    ctx = _make_ctx(task_description="format this json", prompt="convert to a table")
    result = classifier.classify_context(ctx)
    assert result.level == "C1"


def test_classify_context_c3(classifier):
    ctx = _make_ctx(
        task_description="debug the failing request path",
        prompt="root cause the 500 error",
    )
    result = classifier.classify_context(ctx)
    assert result.level == "C3"


def test_classify_context_c4_default(classifier):
    ctx = _make_ctx(task_description="do something completely novel", prompt="")
    result = classifier.classify_context(ctx)
    assert result.level == "C4"


def test_classify_context_impact_fan_out_bumps(classifier):
    ctx = _make_ctx(
        task_description="format this config",
        prompt="convert to a table",
        impact_fan_out=25,
    )
    result = classifier.classify_context(ctx)
    assert result.level == "C3"
    assert result.evidence_source == "codegraph_impact"


def test_classify_context_pure_no_io(classifier):
    """classify_context must not perform any I/O — patch network to prove it."""
    import urllib.request as _urllib

    ctx = _make_ctx(task_description="format this json", prompt="")

    with patch.object(_urllib, "urlopen", side_effect=AssertionError("I/O in pure stage")):
        result = classifier.classify_context(ctx)
    assert result.level == "C1"


def test_classify_context_matches_classify_direct(classifier):
    ctx = _make_ctx(
        task_description="scaffold a new module",
        prompt="scaffold the directory layout",
        max_files_hint=None,
        impact_fan_out=None,
    )
    via_ctx = classifier.classify_context(ctx)
    direct = classifier.classify(
        description=ctx.task_description,
        prompt=ctx.prompt,
    )
    assert via_ctx.level == direct.level
    assert via_ctx.matched_keywords == direct.matched_keywords


# ── ProviderSelector.select_context ──────────────────────────────────────────


def test_select_context_c1_ollama_local(selector, classifier):
    ctx = _make_ctx(
        task_description="format this json",
        prompt="convert to a table",
        ollama_local_reachable=True,
        ollama_local_models=("llama3.2:3b",),
        internet_reachable=True,
        speed_mode="balance",
    )
    complexity = classifier.classify_context(ctx)
    result = selector.select_context(ctx, complexity)
    assert result.c_level == "C1"
    assert len(result.ranked_choices) > 0
    assert result.ranked_choices[0].provider == "ollama_local"


def test_select_context_c3_cloud(selector, classifier):
    ctx = _make_ctx(
        task_description="debug the failing request path",
        prompt="root cause the 500 error",
        speed_mode="speed",
        internet_reachable=True,
    )
    complexity = classifier.classify_context(ctx)
    result = selector.select_context(ctx, complexity)
    assert result.c_level == "C3"
    assert len(result.ranked_choices) > 0
    assert result.ranked_choices[0].provider in ("gemini", "claude_api", "openrouter")


def test_select_context_offline_forces_local(selector, classifier):
    ctx = _make_ctx(
        task_description="brainstorm architecture options",
        prompt="brainstorm design tradeoffs",
        internet_reachable=False,
        connectivity="offline",
        ollama_local_reachable=True,
        ollama_local_models=("qwen2.5-coder:14b",),
    )
    complexity = classifier.classify_context(ctx)
    result = selector.select_context(ctx, complexity)
    assert result.speed_mode == "low"
    assert result.ranked_choices[0].provider == "ollama_local"


def test_select_context_respects_privacy_p3(selector, classifier):
    ctx = _make_ctx(
        task_description="format this json",
        prompt="convert to table",
        privacy_class=PrivacyClass.P3,
        internet_reachable=True,
        ollama_local_reachable=True,
    )
    complexity = classifier.classify_context(ctx)
    result = selector.select_context(ctx, complexity)
    cloud_providers = {"gemini", "claude_api", "openai", "openrouter", "together_ai"}
    for choice in result.ranked_choices:
        assert choice.provider not in cloud_providers, f"P3 task should not route to cloud provider {choice.provider}"


def test_select_context_typed_endpoints_forwarded(selector, classifier):
    """OllamaEndpoint in RoutingContext is converted to dict for _probe_remote_ollama.

    Use a C2 scaffold task so routing-table/context_laptop_remote/balance/C2
    includes ollama_remote_desktop, which triggers _probe_remote_ollama.
    """
    ep = OllamaEndpoint(host="desktop.local", port=11434, enabled=True)
    ctx = _make_ctx(
        task_description="scaffold a new module",
        prompt="scaffold the directory layout",
        device_type="laptop",
        remote_ollama_endpoints=(ep,),
        ollama_local_reachable=False,
    )
    complexity = classifier.classify_context(ctx)
    assert complexity.level == "C2"
    with patch.object(
        ProviderSelector,
        "_probe_remote_ollama",
        return_value=True,
    ) as mock_probe:
        result = selector.select_context(ctx, complexity)
        assert mock_probe.called
        probed_endpoints = mock_probe.call_args[0][0]
        assert probed_endpoints[0]["host"] == "desktop.local"
        assert probed_endpoints[0]["port"] == 11434
        assert probed_endpoints[0]["enabled"] is True
    assert any(c.provider == "ollama_remote_desktop" for c in result.ranked_choices)


# ── ContextDetector.build_routing_context ────────────────────────────────────


@patch("router.context_detector.ContextDetector._probe_gpu", return_value=(None, None))
@patch(
    "router.context_detector.ContextDetector._probe_ollama_local",
    return_value=(True, ["llama3.2:3b"]),
)
@patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
@patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
def test_build_routing_context_fields(*_mocks):
    ctx = ContextDetector().build_routing_context(
        objective="write a formatter",
        task_description="format the json output",
        prompt="convert to table",
        privacy_class=PrivacyClass.P2,
        speed_mode="speed",
    )
    assert isinstance(ctx, RoutingContext)
    assert ctx.objective == "write a formatter"
    assert ctx.task_description == "format the json output"
    assert ctx.privacy_class == PrivacyClass.P2
    assert ctx.speed_mode == "speed"
    assert ctx.ollama_local_reachable is True
    assert "llama3.2:3b" in ctx.ollama_local_models
    assert ctx.internet_reachable is True


@patch("router.context_detector.ContextDetector._probe_gpu", return_value=(None, None))
@patch(
    "router.context_detector.ContextDetector._probe_ollama_local",
    return_value=(False, []),
)
@patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
@patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
def test_build_routing_context_returns_frozen(*_mocks):
    ctx = ContextDetector().build_routing_context(objective="x")
    with pytest.raises(Exception):
        ctx.objective = "changed"  # type: ignore[misc]


@patch("router.context_detector.ContextDetector._probe_gpu", return_value=(None, None))
@patch(
    "router.context_detector.ContextDetector._probe_ollama_local",
    return_value=(False, []),
)
@patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
@patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
def test_build_routing_context_dict_endpoints_converted(*_mocks):
    """Dict entries in RuntimeContext.remote_ollama_endpoints become OllamaEndpoint."""
    det = ContextDetector()
    with patch.object(
        det,
        "detect",
        return_value=RuntimeContext(
            device_type="laptop",
            gpu_model=None,
            gpu_vram_gb=None,
            gpu_available=False,
            ollama_local_reachable=False,
            ollama_local_models=[],
            remote_ollama_endpoints=[{"host": "desktop.local", "port": 11434}],
            internet_reachable=True,
            connectivity="full",
            memory_pressure="low",
            os_family="windows",
            cpu_count=8,
            is_battery=False,
        ),
    ):
        ctx = det.build_routing_context(objective="x")
    assert len(ctx.remote_ollama_endpoints) == 1
    ep = ctx.remote_ollama_endpoints[0]
    assert isinstance(ep, OllamaEndpoint)
    assert ep.host == "desktop.local"
    assert ep.port == 11434
