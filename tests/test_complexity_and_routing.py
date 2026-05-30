"""Tests for complexity classifier + provider selector.

Run with: pytest tests/test_complexity_and_routing.py -v
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
import yaml

from router.complexity_classifier import ComplexityClassifier
from router.context_detector import ContextDetector, RuntimeContext
from router.provider_selector import ProviderSelector

FIXTURES = Path(__file__).resolve().parent / "fixtures"
COMPLEXITY_CASES = FIXTURES / "complexity_cases.yaml"
EMPTY_PREFS = Path(__file__).resolve().parent / "fixtures" / "empty_prefs.yaml"


@pytest.fixture
def classifier():
    return ComplexityClassifier()


@pytest.fixture
def selector():
    return ProviderSelector(prefs_path=EMPTY_PREFS)


@pytest.fixture(scope="module")
def complexity_matrix() -> list[dict]:
    with open(COMPLEXITY_CASES, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["cases"]


def test_complexity_fixture_has_fifty_cases(complexity_matrix):
    assert len(complexity_matrix) == 50
    counts = Counter(c["expected"] for c in complexity_matrix)
    assert counts["C1"] >= 10
    assert counts["C2"] >= 15
    assert counts["C3"] >= 15
    assert counts["C4"] >= 10


@pytest.mark.parametrize(
    "case_id",
    [
        c["id"]
        for c in yaml.safe_load(COMPLEXITY_CASES.read_text(encoding="utf-8"))["cases"]
    ],
    ids=lambda cid: cid,
)
def test_classify_matrix_case(classifier, complexity_matrix, case_id):
    case = next(c for c in complexity_matrix if c["id"] == case_id)
    result = classifier.classify(
        case["description"],
        case.get("prompt", ""),
        max_files_hint=case.get("max_files"),
    )
    expected = case["expected"]
    assert result.level == expected, (
        f"{case_id}: expected {expected}, got {result.level} "
        f"(matched {result.matched_keywords})"
    )


def test_batch_classify_matches_individual(classifier, complexity_matrix):
    batch = classifier.batch_classify(complexity_matrix)
    assert len(batch) == len(complexity_matrix)
    for case, result in zip(complexity_matrix, batch):
        assert result.level == case["expected"], case["id"]


# ── codegraph impact-fan-out evidence signal (bead chromatic-harness-v2-9lih) ──


def test_no_impact_is_keyword_only_no_regression(classifier):
    """Omitting impact_fan_out must behave exactly like the keyword path."""
    base = classifier.classify("format this json", "convert to a table")
    assert base.level == "C1"
    assert base.evidence_source == "none"


def test_impact_fan_out_bumps_c1_to_c2(classifier):
    """A mechanical task that actually touches several files is not C1."""
    result = classifier.classify(
        "format the config", "convert to a table", impact_fan_out=8
    )
    assert result.level == "C2"
    assert result.evidence_source == "codegraph_impact"


def test_large_impact_reaches_reasoning_tier(classifier):
    """Very large blast radius reaches C3 even from a mechanical description."""
    result = classifier.classify(
        "format the config", "convert to a table", impact_fan_out=25
    )
    assert result.level == "C3"
    assert result.evidence_source == "codegraph_impact"


def test_impact_evidence_overrides_keyword_guess(classifier):
    """Real fan-out (small) takes precedence over an inflated max_files guess."""
    result = classifier.classify(
        "format the config",
        "convert to a table",
        max_files_hint=99,
        impact_fan_out=1,
    )
    assert result.level == "C1"
    assert result.evidence_source == "none"


def test_keyword_hint_still_works_without_impact(classifier):
    """max_files_hint path is unchanged and reports keyword evidence."""
    result = classifier.classify(
        "format the config", "convert to a table", max_files_hint=8
    )
    assert result.level == "C2"
    assert result.evidence_source == "keyword"


# ── Context detector sanity checks ──────────────────────────────────────────


def test_context_detector_runs_without_crash():
    det = ContextDetector()
    ctx = det.detect()
    assert ctx.device_type in ("laptop", "desktop", "server", "unknown")
    assert isinstance(ctx.ollama_local_reachable, bool)
    assert isinstance(ctx.internet_reachable, bool)


# ── Provider selector: routing table returns choices ────────────────────────


def _laptop_ctx(**overrides) -> RuntimeContext:
    base = dict(
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
    base.update(overrides)
    return RuntimeContext(**base)


def test_provider_selector_balance_laptop_c1(selector, classifier):
    result = classifier.classify("json-to-table converter", "format output")
    ctx = _laptop_ctx(ollama_local_models=["llama3.2:3b"])
    sel = selector.select(result, ctx, speed_mode="balance", privacy_class="P1")
    assert sel.c_level == "C1"
    assert len(sel.ranked_choices) > 0
    assert sel.ranked_choices[0].provider == "ollama_local"


def test_provider_selector_speed_laptop_c3(selector, classifier):
    result = classifier.classify(
        "debug the failing request path", "root cause the 500 error"
    )
    ctx = _laptop_ctx(ollama_local_models=["qwen2.5-coder:14b"])
    sel = selector.select(result, ctx, speed_mode="speed", privacy_class="P1")
    assert sel.c_level == "C3"
    assert len(sel.ranked_choices) > 0
    first = sel.ranked_choices[0].provider
    assert first in ("gemini", "claude_api", "openrouter")


def test_provider_selector_offline_forces_low(selector, classifier):
    result = classifier.classify(
        "brainstorm architecture options", "brainstorm design tradeoffs"
    )
    ctx = _laptop_ctx(
        ollama_local_models=["qwen2.5-coder:14b"],
        internet_reachable=False,
        connectivity="offline",
    )
    sel = selector.select(result, ctx, privacy_class="P1")
    assert sel.speed_mode == "low"
    assert sel.ranked_choices[0].provider == "ollama_local"


def test_provider_selector_desktop_gpu_c2(selector, classifier):
    result = classifier.classify(
        "scaffold a new module", "scaffold the directory layout"
    )
    ctx = RuntimeContext(
        device_type="desktop",
        gpu_model="RTX 4070",
        gpu_vram_gb=12.0,
        gpu_available=True,
        ollama_local_reachable=True,
        ollama_local_models=["llama3.1:8b", "qwen2.5-coder:14b"],
        remote_ollama_endpoints=[],
        internet_reachable=True,
        connectivity="full",
        memory_pressure="medium",
        os_family="windows",
        cpu_count=12,
        is_battery=False,
    )
    sel = selector.select(result, ctx, speed_mode="balance", privacy_class="P1")
    assert sel.context_key == "context_desktop"
    assert sel.c_level == "C2"
    assert sel.ranked_choices[0].provider == "ollama_local"
