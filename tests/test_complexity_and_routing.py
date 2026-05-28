"""Tests for complexity classifier + provider selector.
Run with: pytest tests/test_complexity_and_routing.py -v
"""

import pytest
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO / "02_RUNTIME"))

from router.complexity_classifier import ComplexityClassifier
from router.context_detector import ContextDetector, RuntimeContext
from router.provider_selector import ProviderSelector, SelectionResult

# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def classifier():
    return ComplexityClassifier()

@pytest.fixture
def selector():
    return ProviderSelector()

# ── Complexity: Known task descriptions ────────────────────────────────────

KNOWN_TASKS = [
    ("json-to-table converter", "format the json-to-table output", "C1"),
    ("parse frontmatter fields", "extract frontmatter from this file", "C1"),
    ("scaffold a new module", "scaffold the directory layout", "C2"),
    ("generate boilerplate code", "boilerplate for new plugin", "C2"),
    ("run smoke test against endpoint", "smoke test the login flow", "C2"),
    ("PR #42 single-file code quality review", "", "C2"),
    ("debug the failing request path", "root cause the 500 error", "C3"),
    ("multi-file integration review", "trace cross-file dependencies", "C3"),
    ("brainstorm architecture options", "brainstorm design tradeoffs", "C4"),
    ("random task with zero pattern matches xyz123", "", "C4"),  # default fallback
    ("write a haiku about documentation", "", "C4"),  # no keywords → fallback
]

@pytest.mark.parametrize("desc,prompt,expected", KNOWN_TASKS)
def test_classify_known_tasks(classifier, desc, prompt, expected):
    result = classifier.classify(desc, prompt)
    assert result.level == expected, f"'{desc}' expected {expected}, got {result.level}"

# ── Context detector sanity checks ──────────────────────────────────────────

def test_context_detector_runs_without_crash():
    det = ContextDetector()
    ctx = det.detect()
    assert ctx.device_type in ("laptop", "desktop", "server", "unknown")
    assert isinstance(ctx.ollama_local_reachable, bool)
    assert isinstance(ctx.internet_reachable, bool)

# ── Provider selector: routing table returns choices ────────────────────────

def test_provider_selector_balance_laptop_c1(selector, classifier):
    result = classifier.classify("json-to-table converter", "format output")
    ctx = RuntimeContext(
        device_type="laptop",
        gpu_model=None, gpu_vram_gb=None, gpu_available=False,
        ollama_local_reachable=True,
        ollama_local_models=["llama3.2:3b"],
        remote_ollama_endpoints=[],
        internet_reachable=True, connectivity="full",
        memory_pressure="medium", os_family="windows",
        cpu_count=8, is_battery=False,
    )
    sel = selector.select(result, ctx, speed_mode="balance")
    assert sel.c_level == "C1"
    assert len(sel.ranked_choices) > 0
    # On balance + laptop + C1, first choice should be Ollama local
    assert sel.ranked_choices[0].provider == "ollama_local"


def test_provider_selector_speed_laptop_c3(selector, classifier):
    result = classifier.classify("debug the failing request path", "root cause the 500 error")
    ctx = RuntimeContext(
        device_type="laptop",
        gpu_model=None, gpu_vram_gb=None, gpu_available=False,
        ollama_local_reachable=True,
        ollama_local_models=["qwen2.5-coder:14b"],
        remote_ollama_endpoints=[],
        internet_reachable=True, connectivity="full",
        memory_pressure="medium", os_family="windows",
        cpu_count=8, is_battery=False,
    )
    sel = selector.select(result, ctx, speed_mode="speed")
    assert sel.c_level == "C3"
    assert len(sel.ranked_choices) > 0
    # Speed mode on laptop C3: first choice should be cloud (Gemini or Claude)
    first = sel.ranked_choices[0].provider
    assert first in ("gemini", "claude_api")


def test_provider_selector_offline_forces_low(selector, classifier):
    result = classifier.classify("brainstorm architecture options", "brainstorm design tradeoffs")
    ctx = RuntimeContext(
        device_type="laptop",
        gpu_model=None, gpu_vram_gb=None, gpu_available=False,
        ollama_local_reachable=True,
        ollama_local_models=["qwen2.5-coder:14b"],
        remote_ollama_endpoints=[],
        internet_reachable=False, connectivity="offline",
        memory_pressure="medium", os_family="windows",
        cpu_count=8, is_battery=False,
    )
    sel = selector.select(result, ctx)  # no explicit speed_mode
    # Offline + no explicit mode → auto-detect forces "low"
    assert sel.speed_mode == "low"
    assert sel.ranked_choices[0].provider == "ollama_local"


def test_provider_selector_desktop_gpu_c2(selector, classifier):
    result = classifier.classify("scaffold a new module", "scaffold the directory layout")
    ctx = RuntimeContext(
        device_type="desktop",
        gpu_model="RTX 4070", gpu_vram_gb=12.0, gpu_available=True,
        ollama_local_reachable=True,
        ollama_local_models=["llama3.1:8b", "qwen2.5-coder:14b"],
        remote_ollama_endpoints=[],
        internet_reachable=True, connectivity="full",
        memory_pressure="medium", os_family="windows",
        cpu_count=12, is_battery=False,
    )
    sel = selector.select(result, ctx, speed_mode="balance")
    assert sel.context_key == "context_desktop"
    assert sel.c_level == "C2"
    # Desktop + balance + C2: first choice should be Ollama local (GPU)
    assert sel.ranked_choices[0].provider == "ollama_local"
