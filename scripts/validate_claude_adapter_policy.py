#!/usr/bin/env python3
"""Validate Claude adapter policy docs and registry.

This script is intentionally dependency-light. It uses PyYAML if installed and
falls back with a clear error if YAML parsing is unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PHRASES = (
    "Claude workflow and slash commands are **adapters only**",
    "Harness scripts are authority",
    "GitHub issues and bd queue are the source of work",
    "CI and verifier gates are the source of promotion",
)

REQUIRED_GATES: dict[str, set[str]] = {
    "/ship": {"confidence", "verifier", "tests", "collision", "ci"},
}


def load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"PyYAML is required to validate {path}: {exc}") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate(
    root: Path,
    registry: dict[str, Any],
    rules: dict[str, Any],
    policy_text: str,
) -> list[str]:
    errors: list[str] = []
    for doc in rules.get("required_docs", []):
        if not (root / doc).exists():
            errors.append(f"missing required doc: {doc}")

    commands = registry.get("commands", [])
    by_name = {cmd.get("name"): cmd for cmd in commands}
    for name in rules.get("required_commands", []):
        if name not in by_name:
            errors.append(f"missing command registry entry: {name}")

    forbidden_terms = set(rules.get("forbidden_logic_terms", []))
    for cmd in commands:
        name = cmd.get("name")
        if not cmd.get("allowed", False):
            errors.append(f"command is not marked allowed: {name}")
        if not cmd.get("authority_source"):
            errors.append(f"command missing authority_source: {name}")
        if "mutation" not in cmd:
            errors.append(f"command missing mutation declaration: {name}")
        forbidden = set(cmd.get("forbidden_logic", []))
        unknown = forbidden - forbidden_terms
        if unknown:
            errors.append(f"command {name} has unknown forbidden_logic terms: {sorted(unknown)}")
        if cmd.get("mutation") in {"conditional", "yes"}:
            gates = set(cmd.get("required_gates", []))
            needed = REQUIRED_GATES.get(name, set())
            missing = needed - gates
            if missing:
                errors.append(f"{name} missing required gates: {sorted(missing)}")
            if name == "/go" and "confidence" not in gates:
                errors.append("/go must require confidence gate")

    for phrase in REQUIRED_PHRASES:
        if phrase not in policy_text:
            errors.append(f"policy missing required phrase: {phrase}")

    return errors


def main() -> int:
    registry_path = ROOT / "config" / "claude_command_registry.yaml"
    rules_path = ROOT / "config" / "claude_adapter_rules.yaml"
    policy_path = ROOT / "docs/governance/CLAUDE_WORKFLOW_ADAPTER_POLICY.md"
    if not registry_path.exists():
        print("FAIL: missing config/claude_command_registry.yaml")
        return 1
    if not rules_path.exists():
        print("FAIL: missing config/claude_adapter_rules.yaml")
        return 1
    if not policy_path.exists():
        print("FAIL: missing docs/governance/CLAUDE_WORKFLOW_ADAPTER_POLICY.md")
        return 1

    registry = load_yaml(registry_path)
    rules = load_yaml(rules_path)
    policy_text = policy_path.read_text(encoding="utf-8")

    errors = validate(ROOT, registry, rules, policy_text)
    if errors:
        for err in errors:
            print(f"FAIL: {err}")
        return 1

    print("PASS: Claude adapter policy and registry are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
