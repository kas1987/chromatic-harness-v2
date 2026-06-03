"""Tests for ProviderSelector: routing table lookup, availability filter,
privacy filter, blocklist, preference override, and fallback logic."""

from __future__ import annotations

import pytest
import yaml

from router.provider_selector import ProviderSelector, ProviderChoice, SelectionResult
from router.complexity_classifier import ComplexityClassifier, ComplexityResult
from router.context_detector import RuntimeContext


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _complexity(level: str = "C1") -> ComplexityResult:
    return ComplexityResult(
        level=level,  # type: ignore[arg-type]
        name=level,
        confidence=1.0,
        matched_keywords=[],
        reasoning_depth="light",
    )


def _context(
    *,
    device_type: str = "laptop",
    internet: bool = True,
    ollama_local: bool = False,
    is_battery: bool = False,
    gpu_available: bool = False,
    remote_ollama_endpoints: list | None = None,
) -> RuntimeContext:
    return RuntimeContext(
        device_type=device_type,
        gpu_model="RTX 4090" if gpu_available else None,
        gpu_vram_gb=24.0 if gpu_available else None,
        gpu_available=gpu_available,
        ollama_local_reachable=ollama_local,
        ollama_local_models=["llama3.2:3b"] if ollama_local else [],
        remote_ollama_endpoints=remote_ollama_endpoints or [],
        internet_reachable=internet,
        connectivity="full" if internet else "offline",
        memory_pressure="medium",
        os_family="linux",
        cpu_count=8,
        is_battery=is_battery,
    )


@pytest.fixture
def selector():
    return ProviderSelector()


@pytest.fixture
def selector_from(tmp_path):
    """Create a ProviderSelector with custom YAML configs."""

    def _make(routing_table: dict, providers: dict | None = None, prefs: dict | None = None) -> ProviderSelector:
        rt_path = tmp_path / "routing-table.yaml"
        rt_path.write_text(yaml.dump(routing_table), encoding="utf-8")

        providers_path = tmp_path / "providers.yaml"
        providers_path.write_text(yaml.dump({"providers": providers or {}}), encoding="utf-8")

        prefs_path = tmp_path / "user-preferences.yaml"
        if prefs:
            prefs_path.write_text(yaml.dump(prefs), encoding="utf-8")
        else:
            prefs_path.write_text("{}", encoding="utf-8")

        openrouter_path = tmp_path / "openrouter-models.yaml"
        openrouter_path.write_text(yaml.dump({"models": []}), encoding="utf-8")

        from router.policy import PolicyLoader

        pl = PolicyLoader(config_dir=tmp_path)

        return ProviderSelector(
            routing_table_path=rt_path,
            prefs_path=prefs_path,
            openrouter_models_path=openrouter_path,
            policy_loader=pl,
        )

    return _make


# ── SelectionResult structure ─────────────────────────────────────────────────


class TestSelectionResultStructure:
    def test_returns_selection_result(self, selector):
        result = selector.select(_complexity("C1"), _context())
        assert isinstance(result, SelectionResult)

    def test_has_ranked_choices_list(self, selector):
        result = selector.select(_complexity("C1"), _context())
        assert isinstance(result.ranked_choices, list)

    def test_has_context_key_str(self, selector):
        result = selector.select(_complexity("C1"), _context())
        assert isinstance(result.context_key, str)

    def test_has_speed_mode(self, selector):
        result = selector.select(_complexity("C1"), _context())
        assert result.speed_mode in ("speed", "balance", "low")

    def test_has_c_level(self, selector):
        result = selector.select(_complexity("C2"), _context())
        assert result.c_level == "C2"


# ── Speed mode resolution ─────────────────────────────────────────────────────


class TestSpeedModeResolution:
    def test_offline_forces_low(self, selector):
        result = selector.select(_complexity("C1"), _context(internet=False))
        assert result.speed_mode == "low"

    def test_battery_forces_low(self, selector):
        result = selector.select(_complexity("C1"), _context(is_battery=True))
        assert result.speed_mode == "low"

    def test_explicit_speed_mode_respected(self, selector):
        result = selector.select(_complexity("C1"), _context(), speed_mode="speed")
        assert result.speed_mode == "speed"

    def test_explicit_balance_respected(self, selector):
        result = selector.select(_complexity("C1"), _context(), speed_mode="balance")
        assert result.speed_mode == "balance"

    def test_default_connected_is_balance(self, selector):
        result = selector.select(_complexity("C1"), _context(internet=True, is_battery=False))
        assert result.speed_mode == "balance"


# ── Context key resolution ────────────────────────────────────────────────────


class TestContextKeyResolution:
    def test_laptop_no_remote(self, selector):
        key = ProviderSelector._resolve_context_key(_context(device_type="laptop"))
        assert key == "context_laptop"

    def test_desktop_with_gpu(self, selector):
        key = ProviderSelector._resolve_context_key(_context(device_type="desktop", gpu_available=True))
        assert key == "context_desktop"

    def test_server(self, selector):
        key = ProviderSelector._resolve_context_key(_context(device_type="server"))
        assert key == "context_server"

    def test_laptop_with_remote_ollama(self, selector):
        ctx = _context(
            device_type="laptop",
            remote_ollama_endpoints=[{"host": "remote-host", "port": 11434, "enabled": True}],
        )
        key = ProviderSelector._resolve_context_key(ctx)
        assert key == "context_laptop_remote"


# ── Tier inference ────────────────────────────────────────────────────────────


class TestTierInference:
    def test_ollama_local_is_tier_0(self):
        assert ProviderSelector._infer_tier("ollama_local") == 0

    def test_ollama_remote_is_tier_0(self):
        assert ProviderSelector._infer_tier("ollama_remote_desktop") == 0

    def test_lmstudio_is_tier_0(self):
        assert ProviderSelector._infer_tier("lmstudio") == 0

    def test_native_claude_is_tier_0(self):
        assert ProviderSelector._infer_tier("native_claude") == 0

    def test_openai_is_tier_2(self):
        assert ProviderSelector._infer_tier("openai") == 2

    def test_gemini_is_tier_3(self):
        assert ProviderSelector._infer_tier("gemini") == 3

    def test_claude_api_is_tier_4(self):
        assert ProviderSelector._infer_tier("claude_api") == 4

    def test_unknown_provider_is_tier_4(self):
        assert ProviderSelector._infer_tier("my_custom_provider") == 4


# ── Routing table lookup ──────────────────────────────────────────────────────


class TestRoutingTableLookup:
    def test_providers_returned_from_table(self, selector_from):
        sel = selector_from(
            routing_table={"context_laptop": {"balance": {"C1": ["ollama_local:llama3.2:3b", "lmstudio"]}}}
        )
        choices = sel._lookup_routing_table("context_laptop", "balance", "C1")
        assert len(choices) == 2
        assert choices[0].provider == "ollama_local"
        assert choices[0].model == "llama3.2:3b"
        assert choices[1].provider == "lmstudio"
        assert choices[1].model is None

    def test_missing_context_key_returns_empty(self, selector_from):
        sel = selector_from(routing_table={})
        choices = sel._lookup_routing_table("context_missing", "balance", "C1")
        assert choices == []

    def test_missing_mode_returns_empty(self, selector_from):
        sel = selector_from(routing_table={"context_laptop": {"speed": {"C1": ["ollama_local"]}}})
        choices = sel._lookup_routing_table("context_laptop", "balance", "C1")
        assert choices == []

    def test_provider_without_model_suffix(self, selector_from):
        sel = selector_from(routing_table={"context_laptop": {"balance": {"C2": ["lmstudio"]}}})
        choices = sel._lookup_routing_table("context_laptop", "balance", "C2")
        assert choices[0].provider == "lmstudio"
        assert choices[0].model is None


# ── Availability filtering ────────────────────────────────────────────────────


class TestAvailabilityFiltering:
    def test_ollama_local_removed_when_not_reachable(self, selector_from):
        sel = selector_from(routing_table={"context_laptop": {"balance": {"C1": ["ollama_local:llama3.2:3b"]}}})
        choices = [ProviderChoice(provider="ollama_local", model="llama3.2:3b", tier=0, reason="test")]
        ctx = _context(ollama_local=False, internet=True)
        result = sel._filter_by_availability(choices, ctx)
        assert all(c.provider != "ollama_local" for c in result)

    def test_ollama_local_kept_when_reachable(self, selector_from):
        sel = selector_from(routing_table={})
        choices = [ProviderChoice(provider="ollama_local", model="llama3.2:3b", tier=0, reason="test")]
        ctx = _context(ollama_local=True)
        result = sel._filter_by_availability(choices, ctx)
        assert any(c.provider == "ollama_local" for c in result)

    def test_cloud_providers_removed_when_offline(self, selector_from):
        sel = selector_from(routing_table={})
        choices = [
            ProviderChoice(provider="gemini", model=None, tier=3, reason="test"),
            ProviderChoice(provider="openai", model=None, tier=2, reason="test"),
        ]
        ctx = _context(internet=False)
        result = sel._filter_by_availability(choices, ctx)
        assert result == [] or all(c.provider not in ("gemini", "openai") for c in result)

    def test_fallback_ollama_when_all_removed(self, selector_from):
        sel = selector_from(routing_table={})
        choices = [
            ProviderChoice(provider="gemini", model=None, tier=3, reason="test"),
        ]
        ctx = _context(internet=False, ollama_local=True)
        result = sel._filter_by_availability(choices, ctx)
        assert any(c.provider == "ollama_local" for c in result)


# ── Privacy filtering ─────────────────────────────────────────────────────────


class TestPrivacyFiltering:
    def test_cloud_blocked_for_p3(self, selector_from):
        sel = selector_from(routing_table={})
        choices = [
            ProviderChoice(provider="gemini", model=None, tier=3, reason="test"),
            ProviderChoice(provider="openai", model=None, tier=2, reason="test"),
        ]
        result = sel._filter_by_privacy(choices, "P3")
        assert all(c.provider not in ("gemini", "openai") for c in result)

    def test_cloud_blocked_for_p4(self, selector_from):
        sel = selector_from(routing_table={})
        choices = [
            ProviderChoice(provider="claude_api", model=None, tier=4, reason="test"),
        ]
        result = sel._filter_by_privacy(choices, "P4")
        assert result == []

    def test_cloud_allowed_for_p1(self, selector_from):
        sel = selector_from(routing_table={})
        choices = [
            ProviderChoice(provider="gemini", model=None, tier=3, reason="test"),
        ]
        result = sel._filter_by_privacy(choices, "P1")
        # Should pass through (privacy_max >= P1 for standard providers)
        assert result  # at least the gemini entry should not be blocked for P1

    def test_local_always_allowed_for_p5(self, selector_from):
        sel = selector_from(routing_table={})
        choices = [
            ProviderChoice(provider="ollama_local", model="llama3.2:3b", tier=0, reason="test"),
        ]
        result = sel._filter_by_privacy(choices, "P5")
        assert any(c.provider == "ollama_local" for c in result)


# ── Blocklist ────────────────────────────────────────────────────────────────


class TestBlocklist:
    def test_blocklisted_provider_removed(self, selector_from):
        sel = selector_from(
            routing_table={},
            prefs={"provider_blocklist": ["gemini", "openai"]},
        )
        choices = [
            ProviderChoice(provider="gemini", model=None, tier=3, reason="test"),
            ProviderChoice(provider="openai", model=None, tier=2, reason="test"),
            ProviderChoice(provider="lmstudio", model=None, tier=0, reason="test"),
        ]
        result = sel._apply_blocklist(choices)
        assert all(c.provider not in ("gemini", "openai") for c in result)
        assert any(c.provider == "lmstudio" for c in result)

    def test_empty_blocklist_keeps_all(self, selector_from):
        sel = selector_from(routing_table={}, prefs={})
        choices = [ProviderChoice(provider="gemini", model=None, tier=3, reason="test")]
        result = sel._apply_blocklist(choices)
        assert len(result) == 1


# ── Preference override ──────────────────────────────────────────────────────


class TestPreferenceOverride:
    def test_preferred_moved_to_front(self, selector_from):
        sel = selector_from(
            routing_table={},
            prefs={"provider_preference": "lmstudio"},
        )
        choices = [
            ProviderChoice(provider="gemini", model=None, tier=3, reason="test"),
            ProviderChoice(provider="lmstudio", model=None, tier=0, reason="test"),
        ]
        result = sel._apply_preference_override(choices)
        assert result[0].provider == "lmstudio"

    def test_no_preference_keeps_order(self, selector_from):
        sel = selector_from(routing_table={}, prefs={})
        choices = [
            ProviderChoice(provider="gemini", model=None, tier=3, reason="test"),
            ProviderChoice(provider="lmstudio", model=None, tier=0, reason="test"),
        ]
        result = sel._apply_preference_override(choices)
        assert result[0].provider == "gemini"

    def test_preferred_not_in_list_unchanged(self, selector_from):
        sel = selector_from(
            routing_table={},
            prefs={"provider_preference": "nonexistent"},
        )
        choices = [
            ProviderChoice(provider="gemini", model=None, tier=3, reason="test"),
        ]
        result = sel._apply_preference_override(choices)
        assert result[0].provider == "gemini"


# ── Speed-mode prefs ──────────────────────────────────────────────────────────


class TestSpeedModeFromPrefs:
    def test_prefs_speed_mode_respected(self, selector_from):
        sel = selector_from(
            routing_table={},
            prefs={"speed_mode": "speed"},
        )
        mode = sel._resolve_speed_mode(None, _context(internet=True))
        assert mode == "speed"

    def test_invalid_prefs_speed_mode_ignored(self, selector_from):
        sel = selector_from(
            routing_table={},
            prefs={"speed_mode": "invalid_mode"},
        )
        mode = sel._resolve_speed_mode(None, _context(internet=True))
        assert mode in ("speed", "balance", "low")
