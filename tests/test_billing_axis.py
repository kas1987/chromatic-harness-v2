"""BEAD B2: billing-axis 3-way classifier (P / D / F) over providers.yaml.

Asserts the axis for EVERY provider id in ``config/routing/providers.yaml`` per
``08_PDRS/TOKEN_ECONOMY_SPEC.md`` section 2: native->P, local->F, cloud->D.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from router.billing_axis import billing_axis, classify
from router.policy import PolicyLoader

_REPO = Path(__file__).resolve().parent.parent


def _providers_path() -> Path:
    canonical = _REPO / "config" / "routing" / "providers.yaml"
    if canonical.exists():
        return canonical
    return _REPO / "09_DEPLOYMENT" / "config" / "routing" / "providers.yaml"


def _registry() -> dict:
    with open(_providers_path(), "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("providers", {})


# type -> expected axis (mirror of billing_axis._TYPE_TO_AXIS).
_EXPECTED_BY_TYPE = {
    "native": "P",
    "local": "F",
    "frontier": "D",
    "broker": "D",
    "sidecar": "D",
    "cross_project": "D",
    "cloud": "D",
}


def _all_provider_cases() -> list[tuple[str, str]]:
    cases = []
    for pid, cfg in _registry().items():
        ptype = str(cfg.get("type", "")).lower()
        assert ptype in _EXPECTED_BY_TYPE, f"unmapped type {ptype!r} for {pid!r}"
        cases.append((pid, _EXPECTED_BY_TYPE[ptype]))
    return cases


@pytest.mark.parametrize("provider_id,expected", _all_provider_cases())
def test_axis_for_every_provider_in_yaml(provider_id: str, expected: str) -> None:
    """Every provider id in providers.yaml resolves to its spec axis."""
    assert classify(provider_id) == expected
    assert billing_axis(provider_id) == expected


def test_native_claude_is_prepaid() -> None:
    assert classify("native_claude") == "P"


def test_local_providers_are_free() -> None:
    for pid in ("ollama", "ollama_local", "ollama_remote_desktop", "lmstudio"):
        assert classify(pid) == "F"


def test_cloud_routing_ids_are_dollar() -> None:
    # routing-table ids (not registry keys) still resolve via the static sets.
    for pid in ("claude_api", "gemini", "openai", "openrouter", "together_ai"):
        assert classify(pid) == "D"


def test_unknown_provider_defaults_to_dollar_ceiling() -> None:
    # Conservative: never silently book unknown spend as free.
    assert classify("some_unknown_provider") == "D"


def test_returns_only_pdf() -> None:
    for pid in _registry():
        assert classify(pid) in {"P", "D", "F"}


def test_registry_injection_path() -> None:
    # The data-driven path resolves a registry key not in the static sets.
    reg = {"custom_frontier": {"type": "frontier"}}
    assert classify("custom_frontier", registry=reg) == "D"
    assert classify("custom_local", registry={"custom_local": {"type": "local"}}) == "F"


def test_policy_loader_keys_covered() -> None:
    # Sanity: PolicyLoader (what billing_axis uses internally) sees same ids.
    loaded = set(PolicyLoader().providers())
    direct = set(_registry())
    assert loaded == direct
