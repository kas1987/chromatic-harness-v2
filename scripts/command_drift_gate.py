#!/usr/bin/env python3
"""command_drift_gate.py — command drift detection (ulos / gh-107).

Detects drift between the declared Claude command registry
(config/claude_command_registry.yaml) and filesystem reality: a command whose
backing script or fallback_script no longer exists, or duplicate command names.
Surfaced as a governance gate (artifact + fail-open summarize()), complementing
validate_claude_adapter_policy.py (which checks policy *correctness*, not drift).

Deliberately does NOT flag missing `logs_to` directories — those are
runtime-generated and absent in a fresh checkout, so checking them produces
false drift locally vs CI.

Dependency-light: PyYAML if available, clear error otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "claude_command_registry.yaml"
ARTIFACT_DIR = ROOT / "07_LOGS_AND_AUDIT" / "command_drift"
ARTIFACT_PATH = ARTIFACT_DIR / "latest.json"

# script values that are not filesystem paths (external tools)
NON_PATH_SCRIPTS = {"bd"}


def load_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or REGISTRY_PATH
    try:
        import yaml  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"PyYAML is required to read {p}: {exc}") from exc
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _check_path(root: Path, value: str | None) -> bool:
    """True if value is a present file (or an allowed non-path tool)."""
    if value is None or value in NON_PATH_SCRIPTS:
        return True
    return (root / value).exists()


def detect_drift(registry: dict[str, Any], root: Path | None = None) -> list[dict[str, Any]]:
    """Return drift findings between the registry and filesystem reality."""
    root = root or ROOT
    commands = registry.get("commands", []) or []
    findings: list[dict[str, Any]] = []

    seen: set[str] = set()
    for cmd in commands:
        name = cmd.get("name", "<unnamed>")
        if name in seen:
            findings.append(
                {
                    "kind": "duplicate_name",
                    "command": name,
                    "detail": f"command name {name} declared more than once",
                    "severity": "high",
                }
            )
        seen.add(name)

        script = cmd.get("script")
        if not _check_path(root, script):
            findings.append(
                {
                    "kind": "missing_script",
                    "command": name,
                    "detail": f"script not found: {script}",
                    "severity": "high",
                }
            )

        fallback = cmd.get("fallback_script")
        if not _check_path(root, fallback):
            findings.append(
                {
                    "kind": "missing_fallback",
                    "command": name,
                    "detail": f"fallback_script not found: {fallback}",
                    "severity": "high",
                }
            )

    return findings


def run_gate(registry_path: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    registry = load_registry(registry_path)
    findings = detect_drift(registry, root)
    high = [f for f in findings if f["severity"] == "high"]
    return {
        "status": "drift" if high else "ok",
        "command_count": len(registry.get("commands", []) or []),
        "drift_count": len(findings),
        "high_severity": len(high),
        "findings": findings,
    }


def summarize(registry_path: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Fail-open summary + artifact write for the harness health dashboard."""
    try:
        result = run_gate(registry_path, root)
    except Exception as exc:  # noqa: BLE001
        result = {"status": "error", "error": str(exc), "drift_count": None, "high_severity": None}
    try:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Command drift detection gate (ulos)")
    parser.add_argument("--registry", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("summarize")

    args = parser.parse_args()
    registry_path = Path(args.registry) if args.registry else None

    if args.command == "check":
        result = run_gate(registry_path)
        print(json.dumps(result, indent=2))
        return 1 if result["high_severity"] else 0
    if args.command == "summarize":
        print(json.dumps(summarize(registry_path), indent=2))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
