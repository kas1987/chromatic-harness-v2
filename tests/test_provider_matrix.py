"""ROUTE-003: Provider selector matrix — C-level, speed, runtime, privacy."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from router.complexity_classifier import ComplexityClassifier
from router.context_detector import RuntimeContext
from router.provider_selector import ProviderSelector

_REPO = Path(__file__).resolve().parent.parent
_ROUTING_TABLE = _REPO / "09_DEPLOYMENT" / "config" / "routing" / "routing-table.yaml"
_OPENROUTER_MODELS = _REPO / "09_DEPLOYMENT" / "config" / "routing" / "openrouter-models.yaml"
EMPTY_PREFS = Path(__file__).resolve().parent / "fixtures" / "empty_prefs.yaml"

CLOUD_PROVIDERS = frozenset({"gemini", "openai", "claude_api", "openrouter", "together_ai"})
LOCAL_PROVIDERS = frozenset({"ollama_local", "ollama_remote_desktop", "lmstudio", "native_claude"})

C_LEVEL_TASKS = {
    "C1": ("json-to-table converter", "format output"),
    "C2": ("scaffold a new module", "scaffold the directory layout"),
    "C3": ("debug the failing request path", "root cause the 500 error"),
    "C4": ("brainstorm architecture options", "brainstorm design tradeoffs"),
}


@pytest.fixture
def selector():
    return ProviderSelector(
        routing_table_path=_ROUTING_TABLE,
        prefs_path=EMPTY_PREFS,
        openrouter_models_path=_OPENROUTER_MODELS,
    )


@pytest.fixture
def classifier():
    return ComplexityClassifier()


def _providers(sel) -> list[str]:
    return [c.provider for c in sel.ranked_choices]


def _classify(classifier, c_level: str):
    desc, prompt = C_LEVEL_TASKS[c_level]
    result = classifier.classify(desc, prompt)
    assert result.level == c_level
    return result


def _laptop_online(**overrides) -> RuntimeContext:
    base = dict(
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
    base.update(overrides)
    return RuntimeContext(**base)


def _desktop_online(**overrides) -> RuntimeContext:
    base = dict(
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
    base.update(overrides)
    return RuntimeContext(**base)


class TestLocalFirstRouting:
    @pytest.mark.parametrize("privacy_class", ["P0", "P1", "P2"])
    @pytest.mark.parametrize("c_level", ["C1", "C2"])
    def test_balance_laptop_prefers_local(self, selector, classifier, privacy_class, c_level):
        complexity = _classify(classifier, c_level)
        ctx = _laptop_online()
        sel = selector.select(complexity, ctx, speed_mode="balance", privacy_class=privacy_class)
        assert sel.ranked_choices
        assert sel.ranked_choices[0].provider == "ollama_local"

    @pytest.mark.parametrize("privacy_class", ["P0", "P1", "P2"])
    def test_balance_desktop_prefers_local_gpu(self, selector, classifier, privacy_class):
        complexity = _classify(classifier, "C2")
        sel = selector.select(
            complexity,
            _desktop_online(),
            speed_mode="balance",
            privacy_class=privacy_class,
        )
        assert sel.context_key == "context_desktop"
        assert sel.ranked_choices[0].provider == "ollama_local"


class TestOfflineMatrix:
    @pytest.mark.parametrize("c_level", ["C1", "C2", "C3", "C4"])
    @pytest.mark.parametrize("privacy_class", ["P0", "P1", "P2"])
    def test_offline_blocks_cloud(self, selector, classifier, c_level, privacy_class):
        complexity = _classify(classifier, c_level)
        ctx = _laptop_online(
            internet_reachable=False,
            connectivity="offline",
        )
        sel = selector.select(complexity, ctx, privacy_class=privacy_class)
        names = set(_providers(sel))
        assert not (names & CLOUD_PROVIDERS)
        assert sel.speed_mode == "low"
        assert sel.ranked_choices[0].provider == "ollama_local"


class TestPrivacyClassMatrix:
    @pytest.mark.parametrize("privacy_class", ["P0", "P1", "P2"])
    def test_p0_p2_allow_cloud_on_speed_c3(self, selector, classifier, privacy_class):
        complexity = _classify(classifier, "C3")
        sel = selector.select(
            complexity,
            _laptop_online(),
            speed_mode="speed",
            privacy_class=privacy_class,
        )
        names = set(_providers(sel))
        assert names & CLOUD_PROVIDERS

    @pytest.mark.parametrize("privacy_class", ["P0", "P1"])
    def test_openrouter_allowed_p0_p1(self, selector, classifier, privacy_class):
        complexity = _classify(classifier, "C3")
        sel = selector.select(
            complexity,
            _laptop_online(),
            speed_mode="balance",
            privacy_class=privacy_class,
        )
        assert "openrouter" in _providers(sel)

    def test_p2_blocks_openrouter_keeps_frontier(self, selector, classifier):
        complexity = _classify(classifier, "C3")
        sel = selector.select(
            complexity,
            _laptop_online(),
            speed_mode="balance",
            privacy_class="P2",
        )
        names = _providers(sel)
        assert "openrouter" not in names
        assert "gemini" in names or "claude_api" in names

    @pytest.mark.parametrize("privacy_class", ["P4", "P5"])
    def test_p4_p5_blocks_cloud(self, selector, classifier, privacy_class):
        complexity = _classify(classifier, "C3")
        sel = selector.select(
            complexity,
            _laptop_online(),
            speed_mode="speed",
            privacy_class=privacy_class,
        )
        names = set(_providers(sel))
        assert not (names & CLOUD_PROVIDERS)
        assert names & LOCAL_PROVIDERS


class TestRemoteOllamaMatrix:
    def test_laptop_remote_context_key(self, selector, classifier):
        complexity = _classify(classifier, "C2")
        ctx = _laptop_online(remote_ollama_endpoints=[{"host": "desktop.local", "port": 11434}])
        sel = selector.select(complexity, ctx, speed_mode="balance", privacy_class="P1")
        assert sel.context_key == "context_laptop_remote"

    def test_remote_preferred_when_reachable(self, selector, classifier, monkeypatch):
        monkeypatch.setattr(
            ProviderSelector,
            "_probe_remote_ollama",
            staticmethod(lambda eps: True),
        )
        complexity = _classify(classifier, "C2")
        ctx = _laptop_online(remote_ollama_endpoints=[{"host": "desktop.local", "port": 11434}])
        sel = selector.select(complexity, ctx, speed_mode="balance", privacy_class="P1")
        assert sel.ranked_choices[0].provider == "ollama_remote_desktop"


class TestSpeedModeMatrix:
    @pytest.mark.parametrize("speed_mode", ["low", "balance", "speed"])
    @pytest.mark.parametrize("c_level", ["C1", "C2", "C3", "C4"])
    def test_all_speed_modes_return_choices(self, selector, classifier, speed_mode, c_level):
        complexity = _classify(classifier, c_level)
        sel = selector.select(
            complexity,
            _laptop_online(),
            speed_mode=speed_mode,
            privacy_class="P1",
        )
        assert sel.speed_mode == speed_mode
        assert len(sel.ranked_choices) > 0


class TestNativeClaudeAvailability:
    """native_claude must NOT be treated as available just because we're inside
    a Claude Code session (env vars set). WinError 2 on subprocess is the real
    failure mode that pollutes auto-path — guard against it here."""

    def test_claude_session_env_vars_do_not_make_native_available(self, monkeypatch):
        """Being inside Claude Code (CLAUDE_SESSION_ID etc.) should NOT
        make native_claude report as available if there is no relay and no CLI."""
        for var in ("CLAUDECODE", "CLAUDE_SESSION_ID", "CLAUDE_PROJECT_DIR", "CLAUDECODE_SESSION_ID"):
            monkeypatch.setenv(var, "1")
        monkeypatch.delenv("NATIVE_CLAUDE_RELAY_URL", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _: None)
        assert ProviderSelector._native_claude_available() is False

    def test_relay_url_makes_native_available(self, monkeypatch):
        monkeypatch.setenv("NATIVE_CLAUDE_RELAY_URL", "http://host-relay:9000")
        monkeypatch.setattr(shutil, "which", lambda _: None)
        assert ProviderSelector._native_claude_available() is True

    def test_cli_on_path_makes_native_available(self, monkeypatch):
        monkeypatch.delenv("NATIVE_CLAUDE_RELAY_URL", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/claude")
        assert ProviderSelector._native_claude_available() is True

    def test_no_cli_no_relay_is_unavailable(self, monkeypatch):
        monkeypatch.delenv("NATIVE_CLAUDE_RELAY_URL", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _: None)
        assert ProviderSelector._native_claude_available() is False


class TestFallbackPreference:
    """When the routing table yields no reachable providers the fallback must
    prefer Ollama (if up) over native_claude (which fails on Windows)."""

    def test_fallback_prefers_ollama_when_reachable(self, selector, classifier, monkeypatch):
        """Routing table has no providers for this artificial context; Ollama is
        up → fallback must emit ollama_local, not native_claude."""
        complexity = _classify(classifier, "C1")
        # Offline + no GPU → context_laptop / speed="low"
        # low/C1 only has ollama_local, but we simulate that being unavailable
        # by making all table entries fail availability, then Ollama comes back up
        # via the fallback path (ollama_local_reachable=True but table is empty-ish).
        # Simplest: give a context that resolves to a key not in the table.
        ctx = _laptop_online(
            ollama_local_reachable=True,
            internet_reachable=False,
            connectivity="offline",
            # Trick: inject a remote endpoint so context_key="context_laptop_remote"
            # but the remote probe fails → the table entries (ollama_remote_desktop)
            # get filtered out → we hit the fallback with Ollama still up locally.
            remote_ollama_endpoints=[{"host": "unreachable.local", "port": 11434}],
        )
        monkeypatch.setattr(ProviderSelector, "_probe_remote_ollama", staticmethod(lambda eps: False))
        monkeypatch.delenv("NATIVE_CLAUDE_RELAY_URL", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _: None)  # no CLI → native_claude unavailable

        sel = selector.select(complexity, ctx, speed_mode="balance", privacy_class="P0")
        providers = [c.provider for c in sel.ranked_choices]
        assert providers, "fallback must always yield at least one choice"
        assert providers[0] == "ollama_local", f"expected ollama_local first, got {providers}"
        assert "native_claude" not in providers

    def test_fallback_native_claude_when_ollama_down_relay_available(self, selector, classifier, monkeypatch):
        """When Ollama is down AND a relay is configured, native_claude is the
        correct fallback (relay mode works even on Windows)."""
        complexity = _classify(classifier, "C1")
        ctx = _laptop_online(
            ollama_local_reachable=False,
            internet_reachable=False,
            connectivity="offline",
            remote_ollama_endpoints=[{"host": "unreachable.local", "port": 11434}],
        )
        monkeypatch.setattr(ProviderSelector, "_probe_remote_ollama", staticmethod(lambda eps: False))
        monkeypatch.setenv("NATIVE_CLAUDE_RELAY_URL", "http://relay:9000")

        sel = selector.select(complexity, ctx, speed_mode="balance", privacy_class="P0")
        providers = [c.provider for c in sel.ranked_choices]
        assert providers, "relay available → should fall back to native_claude"
        assert providers[0] == "native_claude"

    def test_fallback_empty_when_ollama_down_and_native_unavailable(self, selector, classifier, monkeypatch):
        """When neither Ollama nor native_claude are available the selector
        returns an empty list — the router handles it via its own mock path."""
        complexity = _classify(classifier, "C1")
        ctx = _laptop_online(
            ollama_local_reachable=False,
            internet_reachable=False,
            connectivity="offline",
            remote_ollama_endpoints=[{"host": "unreachable.local", "port": 11434}],
        )
        monkeypatch.setattr(ProviderSelector, "_probe_remote_ollama", staticmethod(lambda eps: False))
        monkeypatch.delenv("NATIVE_CLAUDE_RELAY_URL", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _: None)

        sel = selector.select(complexity, ctx, speed_mode="balance", privacy_class="P0")
        assert sel.ranked_choices == [], f"expected empty fallback, got {sel.ranked_choices}"
