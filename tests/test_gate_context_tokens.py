"""gate.py CRG advisory should not false-block at default ROUTER_CONTEXT_MAX_TOKENS."""

import importlib
import os


def _load_gate():
    os.environ.setdefault("ROUTER_CONTEXT_MAX_TOKENS", "128000")
    import router.gate as gate_mod

    importlib.reload(gate_mod)
    return gate_mod


def test_context_gate_advisory_not_blocked_for_coding():
    gate = _load_gate()
    advisory = gate._context_gate_advisory(
        "implement auth fix",
        "fix coding task",
        "C3",
    )
    assert "CRG BLOCKED" not in advisory
    assert "CRG" in advisory
