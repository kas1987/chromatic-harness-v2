"""Tests for validate_claude_adapter_policy.py (nprv / gh-109).

Covers:
- subprocess smoke test (validate_claude_adapter_policy passes on real repo)
- direct policy-doc content checks
- unit tests using validate() with targeted registry mutations
"""

from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Module loader (importlib isolation; no sys.path pollution)
# ---------------------------------------------------------------------------


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_claude_adapter_policy",
        ROOT / "scripts" / "validate_claude_adapter_policy.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["validate_claude_adapter_policy"] = mod
    spec.loader.exec_module(mod)
    return mod


def _validate(registry, rules, policy):
    """Call validate() on the real ROOT with the supplied data."""
    mod = _load_validator()
    return mod.validate(ROOT, registry, rules, policy)


# ---------------------------------------------------------------------------
# Fixture: load real inputs once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def loaded_inputs():
    import yaml

    registry = yaml.safe_load((ROOT / "config/claude_command_registry.yaml").read_text(encoding="utf-8"))
    rules = yaml.safe_load((ROOT / "config/claude_adapter_rules.yaml").read_text(encoding="utf-8"))
    policy = (ROOT / "docs/governance/CLAUDE_WORKFLOW_ADAPTER_POLICY.md").read_text(encoding="utf-8")
    return registry, rules, policy


# ---------------------------------------------------------------------------
# Test 1: subprocess smoke (already in repo, kept for regression)
# ---------------------------------------------------------------------------


def test_validator_passes() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/validate_claude_adapter_policy.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


# ---------------------------------------------------------------------------
# Test 2: policy doc content (direct file read)
# ---------------------------------------------------------------------------


def test_policy_contains_adapter_only_rule() -> None:
    text = (ROOT / "docs/governance/CLAUDE_WORKFLOW_ADAPTER_POLICY.md").read_text(encoding="utf-8")
    assert "adapters only" in text
    assert "Harness scripts are authority" in text


# ---------------------------------------------------------------------------
# Test 3: /ship gates in raw registry YAML
# ---------------------------------------------------------------------------


def test_ship_command_requires_core_gates() -> None:
    import yaml

    data = yaml.safe_load((ROOT / "config/claude_command_registry.yaml").read_text(encoding="utf-8"))
    ship = next(c for c in data["commands"] if c["name"] == "/ship")
    gates = set(ship["required_gates"])
    assert {"confidence", "verifier", "tests", "collision", "ci"}.issubset(gates)


# ---------------------------------------------------------------------------
# Tests 4–10: unit tests via validate() with targeted mutations
# ---------------------------------------------------------------------------


def test_validator_catches_missing_ci_gate_on_ship(loaded_inputs):
    registry, rules, policy = loaded_inputs
    reg = copy.deepcopy(registry)
    ship = next(c for c in reg["commands"] if c["name"] == "/ship")
    ship["required_gates"] = [g for g in ship["required_gates"] if g != "ci"]
    errors = _validate(reg, rules, policy)
    assert any("/ship" in e and "ci" in e for e in errors), errors


def test_validator_catches_missing_confidence_on_go(loaded_inputs):
    registry, rules, policy = loaded_inputs
    reg = copy.deepcopy(registry)
    go = next(c for c in reg["commands"] if c["name"] == "/go")
    go["required_gates"] = [g for g in go["required_gates"] if g != "confidence"]
    errors = _validate(reg, rules, policy)
    assert any("confidence" in e for e in errors), errors


def test_validator_catches_missing_required_command(loaded_inputs):
    registry, rules, policy = loaded_inputs
    reg = copy.deepcopy(registry)
    reg["commands"] = [c for c in reg["commands"] if c["name"] != "/go"]
    errors = _validate(reg, rules, policy)
    assert any("/go" in e for e in errors), errors


def test_validator_catches_unknown_forbidden_logic_term(loaded_inputs):
    registry, rules, policy = loaded_inputs
    reg = copy.deepcopy(registry)
    go = next(c for c in reg["commands"] if c["name"] == "/go")
    go["forbidden_logic"] = list(go.get("forbidden_logic", [])) + ["bogus_invented_term"]
    errors = _validate(reg, rules, policy)
    assert any("bogus_invented_term" in e for e in errors), errors


def test_validator_catches_missing_mutation_declaration(loaded_inputs):
    registry, rules, policy = loaded_inputs
    reg = copy.deepcopy(registry)
    go = next(c for c in reg["commands"] if c["name"] == "/go")
    del go["mutation"]
    errors = _validate(reg, rules, policy)
    assert any("mutation declaration" in e for e in errors), errors


def test_validator_catches_missing_policy_phrase(loaded_inputs):
    registry, rules, policy = loaded_inputs
    # Strip one required phrase from the policy text
    broken_policy = policy.replace("Harness scripts are authority", "Harness scripts are a thing")
    errors = _validate(registry, rules, broken_policy)
    assert any("Harness scripts are authority" in e for e in errors), errors


def test_real_inputs_validate_clean(loaded_inputs):
    registry, rules, policy = loaded_inputs
    errors = _validate(registry, rules, policy)
    assert errors == [], f"unexpected validation errors: {errors}"
