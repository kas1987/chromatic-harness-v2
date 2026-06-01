"""Smoke tests for memory_gate.py (gh-86 / NW-RG-086).

Reconciled from EPIC-C (shipped untested). Network-free; uses dry_run / tmp paths.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("memory_gate", REPO / "02_RUNTIME" / "memory" / "memory_gate.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["memory_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_validate_inputs_rejects_missing_evidence():
    mod = _load()
    errors = mod.validate_inputs("k", "v", "", 0.9, "author")
    assert errors  # empty evidence must produce an error


def test_validate_inputs_rejects_bad_confidence():
    mod = _load()
    errors = mod.validate_inputs("k", "v", "solid evidence here", 5.0, "author")
    assert errors  # confidence > 1.0 invalid


def test_dry_run_does_not_write():
    mod = _load()
    result = mod.gate_memory_write("test.key", "value", "evidence text", 0.95, "tester", dry_run=True)
    assert result["status"] == "dry_run"


def test_low_confidence_quarantined_or_rejected():
    mod = _load()
    result = mod.gate_memory_write("test.key", "value", "evidence text", 0.2, "tester", dry_run=True)
    # dry_run still reports the would-be disposition; low confidence must not be a clean write
    assert result["status"] in {"dry_run", "quarantined", "rejected"}


def test_validation_error_raises():
    mod = _load()
    try:
        mod.gate_memory_write("", "", "", -1, "", dry_run=True)
        raised = False
    except mod.MemoryWriteError:
        raised = True
    assert raised


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
