"""Tests for validate_claude_adapter_policy.py (nprv / gh-105 follow-up).

Covers the extracted validate() unit surface plus the real-inputs sanity and the
end-to-end CLI pass. Network-free; mutates deep-copied registries only.
"""

from __future__ import annotations

import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def loaded_inputs() -> tuple[dict[str, Any], dict[str, Any], str]:
    import yaml

    registry = yaml.safe_load((ROOT / "config/claude_command_registry.yaml").read_text(encoding="utf-8"))
    rules = yaml.safe_load((ROOT / "config/claude_adapter_rules.yaml").read_text(encoding="utf-8"))
    policy = (ROOT / "docs/governance/CLAUDE_WORKFLOW_ADAPTER_POLICY.md").read_text(encoding="utf-8")
    return registry, rules, policy


def _validate(registry: dict[str, Any], rules: dict[str, Any], policy: str) -> list[str]:
    from scripts.validate_claude_adapter_policy import validate

    return validate(ROOT, registry, rules, policy)


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


def test_policy_contains_adapter_only_rule() -> None:
    text = (ROOT / "docs/governance/CLAUDE_WORKFLOW_ADAPTER_POLICY.md").read_text(encoding="utf-8")
    assert "adapters only" in text
    assert "Harness scripts are authority" in text


def test_ship_command_requires_core_gates() -> None:
    import yaml

    data = yaml.safe_load((ROOT / "config/claude_command_registry.yaml").read_text(encoding="utf-8"))
    ship = next(c for c in data["commands"] if c["name"] == "/ship")
    gates = set(ship["required_gates"])
    assert {"confidence", "verifier", "tests", "collision", "ci"}.issubset(gates)


def test_validator_catches_missing_ci_gate_on_ship(
    loaded_inputs: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    registry, rules, policy = loaded_inputs
    registry = deepcopy(registry)
    for cmd in registry["commands"]:
        if cmd["name"] == "/ship":
            cmd["required_gates"] = [g for g in cmd["required_gates"] if g != "ci"]
    errors = _validate(registry, rules, policy)
    assert any("/ship missing required gates" in e and "ci" in e for e in errors), errors


def test_validator_catches_missing_confidence_on_go(
    loaded_inputs: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    registry, rules, policy = loaded_inputs
    registry = deepcopy(registry)
    for cmd in registry["commands"]:
        if cmd["name"] == "/go":
            cmd["required_gates"] = [g for g in cmd["required_gates"] if g != "confidence"]
    errors = _validate(registry, rules, policy)
    assert any("confidence" in e for e in errors), errors


def test_validator_catches_missing_required_command(
    loaded_inputs: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    registry, rules, policy = loaded_inputs
    registry = deepcopy(registry)
    registry["commands"] = [c for c in registry["commands"] if c["name"] != "/ship"]
    errors = _validate(registry, rules, policy)
    assert any("missing command registry entry" in e and "/ship" in e for e in errors), errors


def test_validator_catches_unknown_forbidden_logic_term(
    loaded_inputs: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    registry, rules, policy = loaded_inputs
    registry = deepcopy(registry)
    for cmd in registry["commands"]:
        if cmd["name"] == "/ship":
            cmd["forbidden_logic"] = list(cmd.get("forbidden_logic", [])) + ["definitely_not_in_rules"]
    errors = _validate(registry, rules, policy)
    assert any("unknown forbidden_logic" in e for e in errors), errors


def test_validator_catches_missing_mutation_declaration(
    loaded_inputs: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    registry, rules, policy = loaded_inputs
    registry = deepcopy(registry)
    for cmd in registry["commands"]:
        if cmd["name"] == "/status":
            cmd.pop("mutation", None)
    errors = _validate(registry, rules, policy)
    assert any("missing mutation declaration" in e and "/status" in e for e in errors), errors


def test_validator_catches_missing_policy_phrase(
    loaded_inputs: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    registry, rules, _ = loaded_inputs
    bad_policy = "# stub"
    errors = _validate(registry, rules, bad_policy)
    assert any("policy missing required phrase" in e for e in errors), errors


def test_real_inputs_validate_clean(
    loaded_inputs: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    registry, rules, policy = loaded_inputs
    errors = _validate(registry, rules, policy)
    assert errors == [], errors


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
