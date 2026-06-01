from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
