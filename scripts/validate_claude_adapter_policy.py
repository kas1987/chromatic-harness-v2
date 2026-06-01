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


def load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"PyYAML is required to validate {path}: {exc}") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def main() -> int:
    registry_path = ROOT / "config" / "claude_command_registry.yaml"
    rules_path = ROOT / "config" / "claude_adapter_rules.yaml"
    if not registry_path.exists():
        fail("missing config/claude_command_registry.yaml")
    if not rules_path.exists():
        fail("missing config/claude_adapter_rules.yaml")

    registry = load_yaml(registry_path)
    rules = load_yaml(rules_path)

    for doc in rules.get("required_docs", []):
        if not (ROOT / doc).exists():
            fail(f"missing required doc: {doc}")

    commands = registry.get("commands", [])
    by_name = {cmd.get("name"): cmd for cmd in commands}
    for name in rules.get("required_commands", []):
        if name not in by_name:
            fail(f"missing command registry entry: {name}")

    if len(commands) != len(by_name):
        fail("duplicate command names found in registry")

    forbidden_terms = set(rules.get("forbidden_logic_terms", []))
    for cmd in commands:
        name = cmd.get("name")
        if not cmd.get("allowed", False):
            fail(f"command is not marked allowed: {name}")
        if not cmd.get("authority_source"):
            fail(f"command missing authority_source: {name}")
        if "mutation" not in cmd:
            fail(f"command missing mutation declaration: {name}")
        forbidden = set(cmd.get("forbidden_logic", []))
        unknown = forbidden - forbidden_terms
        if unknown:
            fail(f"command {name} has unknown forbidden_logic terms: {sorted(unknown)}")
        if cmd.get("mutation") in {"conditional", "yes"}:
            gates = set(cmd.get("required_gates", []))
            if name == "/ship":
                needed = {"confidence", "verifier", "tests", "collision", "ci"}
                missing = needed - gates
                if missing:
                    fail(f"/ship missing required gates: {sorted(missing)}")
            if name == "/go" and "confidence" not in gates:
                fail("/go must require confidence gate")

        script = cmd.get("script")
        if script is not None and script != "bd":
            script_path = ROOT / script
            if not script_path.exists():
                fail(f"command {name} script not found: {script}")

        fallback = cmd.get("fallback_script")
        if fallback is not None:
            fallback_path = ROOT / fallback
            if not fallback_path.exists():
                fail(f"command {name} fallback_script not found: {fallback}")

        logs_to = cmd.get("logs_to")
        if logs_to is not None:
            log_path = Path(logs_to)
            if log_path.is_absolute():
                log_dir = log_path.parent
            else:
                log_dir = ROOT / log_path.parent
            if not log_dir.exists():
                fail(f"command {name} logs_to directory does not exist: {log_dir}")

    policy = (ROOT / "docs/governance/CLAUDE_WORKFLOW_ADAPTER_POLICY.md").read_text(encoding="utf-8")
    required_phrases = [
        "Claude workflow and slash commands are **adapters only**",
        "Harness scripts are authority",
        "GitHub issues and bd queue are the source of work",
        "CI and verifier gates are the source of promotion",
    ]
    for phrase in required_phrases:
        if phrase not in policy:
            fail(f"policy missing required phrase: {phrase}")

    print("PASS: Claude adapter policy and registry are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
