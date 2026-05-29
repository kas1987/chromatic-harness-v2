"""gate.py CRG advisory should not false-block at default ROUTER_CONTEXT_MAX_TOKENS."""

import importlib.util
import os
import sys
from pathlib import Path

_ROUTER = Path(__file__).resolve().parents[1] / "02_RUNTIME" / "router"
_REPO = _ROUTER.parent.parent


def _load_gate():
    os.environ.setdefault("ROUTER_CONTEXT_MAX_TOKENS", "128000")
    path = _ROUTER / "gate.py"
    spec = importlib.util.spec_from_file_location("gate_test", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["gate_test"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_context_gate_advisory_not_blocked_for_coding():
    gate = _load_gate()
    advisory = gate._context_gate_advisory(
        "implement auth fix",
        "fix coding task",
        "C3",
    )
    assert "CRG BLOCKED" not in advisory
    assert "CRG" in advisory
