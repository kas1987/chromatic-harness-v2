"""PreToolUse hook: read Agent tool call → classify → select → emit + log.

Usage (in settings.json / PreToolUse):
    cd <repo>/02_RUNTIME && python -m router.gate
    # or:
    python <repo>/02_RUNTIME/router/gate.py
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Self-contained loader ────────────────────────────────────────────────────
_ROUTER_DIR = Path(__file__).resolve().parent
_RUNTIME_DIR = _ROUTER_DIR.parent
_REPO = _ROUTER_DIR.parent.parent

# 02_RUNTIME must be first so `router` resolves as a real package when gate.py
# is invoked as a bare script (the PreToolUse hook invocation style).
for _p in (str(_RUNTIME_DIR), str(_REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if "router" not in sys.modules:
    try:
        importlib.import_module("router")
    except Exception:
        pass


def _load_submodule(name: str, fname: str):
    path = _ROUTER_DIR / fname
    spec = importlib.util.spec_from_file_location(f"router.{name}", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules.setdefault(f"router.{name}", mod)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_context = _load_submodule("context_detector", "context_detector.py")
_complexity = _load_submodule("complexity_classifier", "complexity_classifier.py")
_selector = _load_submodule("provider_selector", "provider_selector.py")
_loop_guard = _load_submodule("loop_guard", "loop_guard.py")

ContextDetector = _context.ContextDetector
RuntimeContext = _context.RuntimeContext
ComplexityClassifier = _complexity.ComplexityClassifier
ProviderSelector = _selector.ProviderSelector
ProviderChoice = _selector.ProviderChoice

# ── Gate-level constants ─────────────────────────────────────────────────────
BLOCK_ENABLED = os.environ.get("ROUTER_BLOCK_ENABLED", "true").lower() == "true"
CONTEXT_MAX_TOKENS = int(os.environ.get("ROUTER_CONTEXT_MAX_TOKENS", "128000"))
TOOL_USE_PATTERN = os.environ.get(
    "TOOL_USE_PATTERN",
    "bash|glob|grep|install|execute|curl|npm |pip |webfetch|websearch",
)

# ── Pipeline stage imports ───────────────────────────────────────────────────
from router.pipeline.io import emit_advisory, emit_deny, read_stdin  # noqa: E402
from router.pipeline.impact import (  # noqa: E402
    count_impacted,
    extract_file_refs,
    impact_fan_out,
)
from router.pipeline.billing import billing_for_route, cost_estimate_usd  # noqa: E402
from router.pipeline.advisory import context_gate_advisory  # noqa: E402
from router.pipeline.audit import audit_router_decision, log_entry  # noqa: E402

# Backward-compat aliases — existing tests reference gate._foo directly.
_read_stdin = read_stdin
_emit_advisory = emit_advisory
_emit_deny = emit_deny
_extract_file_refs = extract_file_refs
_count_impacted = count_impacted
_impact_fan_out = impact_fan_out
_billing_for_route = billing_for_route
_cost_estimate_usd = cost_estimate_usd
_context_gate_advisory = context_gate_advisory
_log_entry = log_entry
_audit_router_decision = audit_router_decision


def _overlay_advisory() -> str:
    """Backward-compat wrapper; reads from module-level _REPO so tests can monkeypatch it."""
    import json

    overlay_path = _REPO / "07_LOGS_AND_AUDIT" / "control_plane" / "routing_policy_overlay.json"
    if not overlay_path.is_file():
        return ""
    try:
        data = json.loads(overlay_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return ""
        thr = data.get("c_to_t_threshold")
        spill = data.get("allow_paid_spill")
        if data.get("staleness_fallback"):
            return f" | overlay STALE-FALLBACK: C->T>={thr} paid_spill={spill}"
        return f" | overlay: C->T>={thr} paid_spill={spill}"
    except Exception:  # noqa: BLE001
        return ""


def _has_tool_use(haystack: str) -> bool:
    import re

    return bool(re.search(TOOL_USE_PATTERN, haystack, re.IGNORECASE))


def main() -> None:
    data = read_stdin()
    tool_name = data.get("tool_name", "")
    if tool_name != "Agent":
        emit_advisory("ROUTER: non-Agent tool, passing through")
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    description = tool_input.get("description", "")
    prompt = tool_input.get("prompt", "")
    sub_type = tool_input.get("subagent_type", "general-purpose")
    model_requested = tool_input.get("model", "")

    classifier = ComplexityClassifier()
    context = ContextDetector().detect()
    selector = ProviderSelector()

    complexity = classifier.classify(description, prompt, impact_fan_out=impact_fan_out(description, prompt))
    selection = selector.select(complexity, context)

    ranked: list[Any] = selection.ranked_choices
    chosen = (
        ranked[0]
        if ranked
        else ProviderChoice(
            provider="native_claude",
            model=None,
            tier=4,
            reason="no providers available",
        )
    )

    haystack = f"{description}\n{prompt}".lower()
    speed_mode = selection.speed_mode

    if speed_mode == "speed":
        should_block = False
    elif speed_mode == "low":
        should_block = chosen.provider not in (
            "ollama_local",
            "ollama_remote_desktop",
            "lmstudio",
            "native_claude",
        )
    else:
        should_block = (
            BLOCK_ENABLED and chosen.tier < 4 and sub_type == "general-purpose" and not _has_tool_use(haystack)
        )

    override_note = ""
    if model_requested.lower() == "haiku" and chosen.tier > 1:
        should_block = True
        override_note = " | caller specified haiku - cap at tier-1"
    if model_requested.lower() == "opus":
        chosen = ProviderChoice(
            provider="native_claude",
            model="opus",
            tier=4,
            reason="caller specified opus - tier-4 (native)",
        )
        should_block = False
        override_note = ""

    loop_verdict = _loop_guard.bump_and_check(description, sub_type)
    loop_note = _loop_guard.advisory_note(loop_verdict)
    if loop_verdict.get("level") == "block":
        should_block = True

    ctx_note = context_gate_advisory(description, prompt, complexity.level)
    advisory = (
        f"ROUTER C={complexity.level} speed={selection.speed_mode} "
        f"provider={chosen.provider} model={chosen.model} — "
        f"{chosen.reason}{override_note}{ctx_note}{loop_note}"
    )

    if should_block:
        emit_deny(advisory)
    else:
        emit_advisory(advisory)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "description": description[:200],
        "subagent_type": sub_type,
        "model_requested": model_requested,
        "c_level": complexity.level,
        "c_confidence": complexity.confidence,
        "speed_mode": selection.speed_mode,
        "context": selection.context_key,
        "provider": chosen.provider,
        "target_model": chosen.model,
        "tier": chosen.tier,
        "reason": chosen.reason,
        "blocked": should_block,
        "loop_count": loop_verdict.get("count", 0),
        "loop_level": loop_verdict.get("level", "ok"),
    }
    log_entry(entry)
    audit_router_decision(entry)
    sys.exit(0)


if __name__ == "__main__":
    main()
