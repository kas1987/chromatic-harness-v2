"""Tests for PolicyLoader: YAML loading, defaults, caching, route resolution."""

from __future__ import annotations

import pytest
import yaml

from router.policy import PolicyLoader


# ── Fixture: PolicyLoader backed by real config ──────────────────────────────

@pytest.fixture
def loader():
    return PolicyLoader()


# ── Fixture: PolicyLoader backed by temp YAML files ─────────────────────────

@pytest.fixture
def loader_from(tmp_path):
    """Factory: create a PolicyLoader with custom YAML content."""
    def _make(**files) -> PolicyLoader:
        for fname, content in files.items():
            (tmp_path / fname).write_text(yaml.dump(content), encoding="utf-8")
        return PolicyLoader(config_dir=tmp_path)
    return _make


# ── Empty-directory fallback ─────────────────────────────────────────────────

class TestEmptyDirectory:
    def test_providers_returns_empty_dict(self, tmp_path):
        pl = PolicyLoader(config_dir=tmp_path)
        assert pl.providers() == {}

    def test_routes_returns_empty_dict(self, tmp_path):
        pl = PolicyLoader(config_dir=tmp_path)
        assert pl.routes() == {}

    def test_privacy_returns_empty_dict(self, tmp_path):
        pl = PolicyLoader(config_dir=tmp_path)
        assert pl.privacy() == {}

    def test_budget_returns_empty_dict(self, tmp_path):
        pl = PolicyLoader(config_dir=tmp_path)
        assert pl.budget() == {}

    def test_provider_costs_returns_empty_dict(self, tmp_path):
        pl = PolicyLoader(config_dir=tmp_path)
        assert pl.provider_costs() == {}


# ── providers() ──────────────────────────────────────────────────────────────

class TestProviders:
    def test_returns_dict(self, loader):
        providers = loader.providers()
        assert isinstance(providers, dict)

    def test_providers_yaml_custom(self, loader_from):
        pl = loader_from(**{
            "providers.yaml": {
                "providers": {
                    "ollama": {"enabled": True, "privacy_max": "P5"},
                    "openai": {"enabled": True, "privacy_max": "P2"},
                }
            }
        })
        providers = pl.providers()
        assert "ollama" in providers
        assert "openai" in providers
        assert providers["ollama"]["enabled"] is True

    def test_provider_cfg_returns_dict(self, loader_from):
        pl = loader_from(**{
            "providers.yaml": {
                "providers": {
                    "gemini": {"enabled": True, "model": "gemini-pro"}
                }
            }
        })
        cfg = pl.provider_cfg("gemini")
        assert cfg["model"] == "gemini-pro"

    def test_provider_cfg_missing_returns_empty(self, loader_from):
        pl = loader_from(**{
            "providers.yaml": {"providers": {}}
        })
        assert pl.provider_cfg("nonexistent") == {}

    def test_missing_yaml_key_returns_empty(self, loader_from):
        pl = loader_from(**{"providers.yaml": {}})
        assert pl.providers() == {}


# ── routes() ─────────────────────────────────────────────────────────────────

class TestRoutes:
    def test_returns_dict(self, loader):
        routes = loader.routes()
        assert isinstance(routes, dict)

    def test_routing_yaml_custom(self, loader_from):
        pl = loader_from(**{
            "routing-table.yaml": {
                "routes": {
                    "coding": {"default": "ollama", "fallback": ["lmstudio"]},
                    "planning": {"default": "anthropic", "fallback": []},
                }
            }
        })
        routes = pl.routes()
        assert "coding" in routes
        assert routes["coding"]["default"] == "ollama"
        assert routes["coding"]["fallback"] == ["lmstudio"]

    def test_route_for_task_existing(self, loader_from):
        pl = loader_from(**{
            "routing-table.yaml": {
                "routes": {
                    "classification": {"default": "ollama", "fallback": ["mock"]}
                }
            }
        })
        route = pl.route_for_task("classification")
        assert route["default"] == "ollama"

    def test_route_for_task_missing_returns_empty(self, loader_from):
        pl = loader_from(**{
            "routing-table.yaml": {"routes": {}}
        })
        assert pl.route_for_task("nonexistent_task") == {}

    def test_missing_routes_key_returns_empty(self, loader_from):
        pl = loader_from(**{"routing-table.yaml": {}})
        assert pl.routes() == {}


# ── privacy() ────────────────────────────────────────────────────────────────

class TestPrivacy:
    def test_returns_dict(self, loader):
        privacy = loader.privacy()
        assert isinstance(privacy, dict)

    def test_privacy_yaml_custom(self, loader_from):
        pl = loader_from(**{
            "privacy-policy.yaml": {
                "privacy_classes": {
                    "P0": {"allowed_providers": ["ollama", "openai"]},
                    "P3": {"allowed_providers": []},
                }
            }
        })
        privacy = pl.privacy()
        assert "P0" in privacy
        assert "P3" in privacy
        assert privacy["P0"]["allowed_providers"] == ["ollama", "openai"]
        assert privacy["P3"]["allowed_providers"] == []

    def test_missing_privacy_classes_key_returns_empty(self, loader_from):
        pl = loader_from(**{"privacy-policy.yaml": {}})
        assert pl.privacy() == {}


# ── budget() and provider_costs() ────────────────────────────────────────────

class TestBudget:
    def test_budget_returns_dict(self, loader):
        budget = loader.budget()
        assert isinstance(budget, dict)

    def test_budget_yaml_custom(self, loader_from):
        pl = loader_from(**{
            "budget-policy.yaml": {
                "budget": {"default_max_cost_usd": 0.50},
                "provider_cost_estimates": {"openai": 0.002, "anthropic": 0.003},
            }
        })
        budget = pl.budget()
        costs = pl.provider_costs()
        assert budget["default_max_cost_usd"] == 0.50
        assert costs["openai"] == 0.002
        assert costs["anthropic"] == 0.003

    def test_missing_budget_key_returns_empty(self, loader_from):
        pl = loader_from(**{"budget-policy.yaml": {}})
        assert pl.budget() == {}
        assert pl.provider_costs() == {}


# ── Caching ───────────────────────────────────────────────────────────────────

class TestCaching:
    def test_second_call_uses_cache(self, tmp_path):
        yaml_content = {"providers": {"ollama": {"enabled": True}}}
        path = tmp_path / "providers.yaml"
        path.write_text(yaml.dump(yaml_content), encoding="utf-8")
        pl = PolicyLoader(config_dir=tmp_path)

        result1 = pl.providers()
        # Modify the file after first load
        path.write_text(yaml.dump({"providers": {"changed": {}}}), encoding="utf-8")
        result2 = pl.providers()

        # Second call should return cached value
        assert result1 == result2
        assert "ollama" in result2

    def test_cache_keyed_by_filename(self, tmp_path):
        (tmp_path / "providers.yaml").write_text(
            yaml.dump({"providers": {"p1": {}}}), encoding="utf-8"
        )
        (tmp_path / "routing-table.yaml").write_text(
            yaml.dump({"routes": {"classification": {}}}), encoding="utf-8"
        )
        pl = PolicyLoader(config_dir=tmp_path)
        pl.providers()
        pl.routes()
        # Both files should be separately cached
        assert "providers.yaml" in pl._cache
        assert "routing-table.yaml" in pl._cache


# ── Real config dir (integration) ────────────────────────────────────────────

class TestRealConfig:
    def test_real_routes_include_expected_tasks(self, loader):
        routes = loader.routes()
        # The real routing table must have at least classification
        if routes:
            assert any(k in routes for k in ("classification", "coding", "planning"))

    def test_real_privacy_has_p1_and_p3(self, loader):
        privacy = loader.privacy()
        if privacy:
            assert "P1" in privacy
            assert "P3" in privacy

    def test_real_p3_has_no_allowed_providers(self, loader):
        privacy = loader.privacy()
        if "P3" in privacy:
            allowed = privacy["P3"].get("allowed_providers", [])
            assert allowed == []

    def test_real_providers_returns_dict(self, loader):
        providers = loader.providers()
        assert isinstance(providers, dict)
