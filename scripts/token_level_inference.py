#!/usr/bin/env python3
"""Infer C-level / T-level for a token-ledger event from its model name.

Token-governance telemetry recorded the model name (e.g. ``claude-opus-4-8``)
but left ``c_level``/``t_level`` null, so ~71% of ledger events classified as
``confidence: "unknown"`` — which penalised the weekly spend target and put the
control plane in staleness fallback. This module maps a model name to the
complexity tier (C) and provider/cost tier (T) it represents, so events can be
classified without re-running the router.

Mapping reflects the harness routing reference (Opus→C4/T4, Sonnet→C3/T3,
Haiku→C2/T2, small local/Featherless→C1/T0-T1). It is intentionally a coarse
*representative* tier per model, not a per-request routing decision.

Fail-open: an unrecognised model returns (None, None, "unknown") so callers can
keep the prior behaviour for genuinely unknown models rather than guessing.

    from token_level_inference import infer_levels
    c, t, conf = infer_levels("claude-opus-4-8[1m]")   # ("C4", "T4", "inferred")
"""
from __future__ import annotations

import re

# Ordered (substring, c_level, t_level). First match wins, so put more specific
# tokens before generic ones.
_RULES: list[tuple[str, str, str]] = [
    ("opus", "C4", "T4"),
    ("sonnet", "C3", "T3"),
    ("haiku", "C2", "T2"),
    # Featherless / mid open-weight providers (router tier T1–T3)
    ("kimi", "C3", "T3"),
    ("hermes", "C2", "T2"),
    ("qwen", "C2", "T1"),
    ("mistral", "C2", "T1"),
    # Small local models (Ollama T0)
    ("llama3.2", "C1", "T0"),
    ("llama", "C1", "T1"),
    ("native", "C1", "T0"),
    ("ollama", "C1", "T0"),
]


def infer_levels(model: str | None) -> tuple[str | None, str | None, str]:
    """Return (c_level, t_level, confidence) for a model name.

    confidence is "inferred" on a match, "unknown" otherwise. Never raises.
    """
    try:
        if not model:
            return (None, None, "unknown")
        name = str(model).lower()
        for token, c, t in _RULES:
            if token in name:
                return (c, t, "inferred")
        # Bare provider hints with no model family
        if re.search(r"\bgpt|openai\b", name):
            return ("C3", "T3", "inferred")
        return (None, None, "unknown")
    except Exception:  # fail-open
        return (None, None, "unknown")


def classify_event(event: dict) -> dict:
    """Return a shallow copy of *event* with c_level/t_level/confidence filled
    in from its model name **only when currently missing/null/unknown**.

    Existing non-null levels are preserved (router decisions win over inference).
    """
    try:
        out = dict(event)
        has_c = out.get("c_level") not in (None, "", "unknown")
        has_t = out.get("t_level") not in (None, "", "unknown")
        if has_c and has_t:
            return out
        model = out.get("model") or out.get("model_name") or out.get("provider_model")
        c, t, conf = infer_levels(model)
        if not has_c and c:
            out["c_level"] = c
        if not has_t and t:
            out["t_level"] = t
        if out.get("confidence") in (None, "", "unknown") and conf == "inferred":
            out["confidence"] = "inferred"
        return out
    except Exception:  # fail-open
        return event


if __name__ == "__main__":  # tiny smoke CLI
    import sys
    for m in sys.argv[1:] or ["claude-opus-4-8", "claude-sonnet-4-6", "qwen2.5-14b", "???"]:
        print(m, "->", infer_levels(m))
