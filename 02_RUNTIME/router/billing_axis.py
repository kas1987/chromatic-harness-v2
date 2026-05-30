"""Billing-axis classifier — the 3-way chart of accounts (P / D / F).

Per ``08_PDRS/TOKEN_ECONOMY_SPEC.md`` section 2, every usage event is arbitrated
by a single authoritative ``billing_axis`` field, derived from
``config/routing/providers.yaml`` (``type`` + ``cost``):

==== =================== ====================================== ====================
Axis Name                Members                                Unit
==== =================== ====================================== ====================
P    Prepaid quota       ``native_claude`` (type:native)        % of weekly quota
D    Dollar-billed API   cloud providers (type:frontier/broker) USD (pricing.json)
F    Free local          ``ollama``/``lmstudio`` (type:local)   $0 / quota-neutral
==== =================== ====================================== ====================

This module mirrors ``provider_selector.py``'s ``_LOCAL`` / ``_CLOUD`` frozensets
and adds a ``_PREPAID`` (native) set, so the axis can be resolved by a static
membership check OR by deriving from the providers.yaml registry's ``type`` field
(the canonical, data-driven path). Zero new infra; no request-path risk.
"""

from __future__ import annotations

from typing import Literal

from .policy import PolicyLoader

BillingAxis = Literal["P", "D", "F"]

# ── Axis frozensets (mirror provider_selector._LOCAL / _CLOUD) ──────────────
# Keyed on provider id (providers.yaml registry key AND routing-table id), so
# both naming conventions resolve. Prepaid (Axis P) is split out from local.

# Axis P — prepaid weekly Claude quota ($0 marginal in-session, booked vs %).
_PREPAID_PROVIDERS: frozenset[str] = frozenset({"native_claude"})

# Axis F — free local models (quota-neutral, tracked for offload value only).
_LOCAL_PROVIDERS: frozenset[str] = frozenset(
    {"ollama", "ollama_local", "ollama_remote_desktop", "lmstudio"}
)

# Axis D — dollar-billed API providers (hard $ ceiling per agent_budget.yaml).
_CLOUD_PROVIDERS: frozenset[str] = frozenset(
    {
        "claude_api",
        "anthropic",
        "gemini",
        "google",
        "openai",
        "openrouter",
        "together",
        "together_ai",
        "featherless",
        "kimi",
    }
)

# providers.yaml ``type`` → axis. The data-driven path: native→P, local→F,
# everything billable (frontier/broker/sidecar/cross_project) → D.
_TYPE_TO_AXIS: dict[str, BillingAxis] = {
    "native": "P",
    "local": "F",
    "frontier": "D",
    "broker": "D",
    "sidecar": "D",
    "cross_project": "D",
    "cloud": "D",
}


def _registry() -> dict:
    """Load the providers.yaml registry (cached by PolicyLoader)."""
    return PolicyLoader().providers()


def classify(provider_id: str, registry: dict | None = None) -> BillingAxis:
    """Return the billing axis ``'P'`` | ``'D'`` | ``'F'`` for ``provider_id``.

    Resolution order:
      1. Static frozenset membership (mirrors ``provider_selector``) — fast path
         and the source of truth for routing-table ids that are not registry keys.
      2. Derive from the providers.yaml ``type`` (and ``cost`` == 0 → non-dollar)
         when the id is a registry key not in the static sets.
      3. Default to Axis D (dollar-billed) — the conservative hard-ceiling choice
         for any unknown provider, so spend is never silently booked as free.
    """
    pid = str(provider_id)

    if pid in _PREPAID_PROVIDERS:
        return "P"
    if pid in _LOCAL_PROVIDERS:
        return "F"
    if pid in _CLOUD_PROVIDERS:
        return "D"

    cfg = (registry if registry is not None else _registry()).get(pid, {})
    ptype = str(cfg.get("type", "")).lower()
    if ptype in _TYPE_TO_AXIS:
        axis = _TYPE_TO_AXIS[ptype]
        # cost==0 on a non-native/non-local type still books as its type axis;
        # native/local already map to P/F. No further reclassification needed.
        return axis

    return "D"


def billing_axis(provider_id: str, registry: dict | None = None) -> BillingAxis:
    """Alias helper for :func:`classify` (spec-named accessor)."""
    return classify(provider_id, registry=registry)


__all__ = [
    "BillingAxis",
    "classify",
    "billing_axis",
    "_PREPAID_PROVIDERS",
    "_LOCAL_PROVIDERS",
    "_CLOUD_PROVIDERS",
]
