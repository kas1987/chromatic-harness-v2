"""OpenRouter broker policy + privacy enforcement on provider_selector.

Policy: docs/governance/OPENROUTER_BROKER_POLICY.md
Allowlist: 09_DEPLOYMENT/config/routing/openrouter-models.yaml
"""

from __future__ import annotations

from pathlib import Path

import pytest

from router.complexity_classifier import ComplexityClassifier
from router.context_detector import RuntimeContext
from router.provider_selector import ProviderSelector

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ROUTING_TABLE = _REPO_ROOT / "09_DEPLOYMENT" / "config" / "routing" / "routing-table.yaml"
_OPENROUTER_MODELS = (
    _REPO_ROOT / "09_DEPLOYMENT" / "config" / "routing" / "openrouter-models.yaml"
)
@pytest.fixture
def selector(tmp_path):
    prefs = tmp_path / "prefs.yaml"
    prefs.write_text("{}\n", encoding="utf-8")
    return ProviderSelector(
        routing_table_path=_ROUTING_TABLE,
        prefs_path=prefs,
        openrouter_models_path=_OPENROUTER_MODELS,
    )


@pytest.fixture
def classifier():
    return ComplexityClassifier()


@pytest.fixture
def online_laptop_ctx():
    return RuntimeContext(
        device_type="laptop",
        gpu_model=None,
        gpu_vram_gb=None,
        gpu_available=False,
        ollama_local_reachable=True,
        ollama_local_models=["llama3.2:3b", "qwen2.5-coder:14b"],
        remote_ollama_endpoints=[],
        internet_reachable=True,
        connectivity="full",
        memory_pressure="medium",
        os_family="windows",
        cpu_count=8,
        is_battery=False,
    )


def _providers(sel) -> list[str]:
    return [c.provider for c in sel.ranked_choices]


def test_openrouter_allowlist_file_present():
    assert _OPENROUTER_MODELS.exists(), "openrouter-models.yaml required by ROUTE-005"


def test_p4_blocks_cloud_and_openrouter(selector, classifier, online_laptop_ctx):
    complexity = classifier.classify(
        "debug the failing request path", "root cause the 500 error"
    )
    result = selector.select(
        complexity, online_laptop_ctx, speed_mode="speed", privacy_class="P4"
    )
    names = _providers(result)
    assert "openrouter" not in names
    assert "gemini" not in names
    assert "openai" not in names
    assert "claude_api" not in names
    assert len(names) > 0
    assert names[0] in ("ollama_local", "native_claude", "lmstudio")


def test_p5_blocks_cloud_and_openrouter(selector, classifier, online_laptop_ctx):
    complexity = classifier.classify(
        "brainstorm architecture options", "brainstorm design tradeoffs"
    )
    result = selector.select(
        complexity, online_laptop_ctx, speed_mode="balance", privacy_class="P5"
    )
    names = _providers(result)
    assert not (set(names) & {"openrouter", "gemini", "openai", "claude_api", "together_ai"})


def test_p3_blocks_all_cloud_routes(selector, classifier, online_laptop_ctx):
    complexity = classifier.classify(
        "multi-file integration review", "trace cross-file dependencies"
    )
    result = selector.select(
        complexity, online_laptop_ctx, speed_mode="speed", privacy_class="P3"
    )
    names = _providers(result)
    assert not (set(names) & {"openrouter", "gemini", "openai", "claude_api"})


def test_p1_allows_allowlisted_openrouter(selector, classifier, online_laptop_ctx):
    complexity = classifier.classify(
        "debug the failing request path", "root cause the 500 error"
    )
    result = selector.select(
        complexity, online_laptop_ctx, speed_mode="balance", privacy_class="P1"
    )
    names = _providers(result)
    assert "openrouter" in names
    or_choice = next(c for c in result.ranked_choices if c.provider == "openrouter")
    assert or_choice.model in selector._openrouter_allowlist


def test_p2_blocks_openrouter_keeps_frontier(selector, classifier, online_laptop_ctx):
    complexity = classifier.classify(
        "debug the failing request path", "root cause the 500 error"
    )
    result = selector.select(
        complexity, online_laptop_ctx, speed_mode="balance", privacy_class="P2"
    )
    names = _providers(result)
    assert "openrouter" not in names
    assert "gemini" in names or "claude_api" in names


def test_non_allowlisted_openrouter_model_removed(selector, classifier, online_laptop_ctx):
    complexity = classifier.classify(
        "debug the failing request path", "root cause the 500 error"
    )
    table = selector._table.copy()
    ctx = table.setdefault("context_laptop", {})
    bal = ctx.setdefault("balance", {})
    bal["C3"] = ["openrouter:vendor/unknown-model", "gemini:gemini-2.5-pro"]
    selector._table = table
    result = selector.select(
        complexity, online_laptop_ctx, speed_mode="balance", privacy_class="P1"
    )
    names = _providers(result)
    assert "openrouter" not in names
    assert "gemini" in names
