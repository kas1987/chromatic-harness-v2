#!/usr/bin/env python3
"""Detect drift between live Claude command deployments and claude_command_registry.yaml.

Drift sources checked:
  1. rules_not_in_registry   — command required by claude_adapter_rules.yaml but absent
                               from the registry.                         [ERROR]
  2. script_missing          — registry entry points to a script that does not exist.
                                                                          [ERROR]
  3. duplicate_names         — duplicate command names in the registry.   [ERROR]
  4. registry_not_in_rules   — registry entry not in required_commands list (extra
                               command; may be intentional).              [WARN]
  5. deployed_ungoverned     — .claude/commands/*.md file whose command name
                               is not present in the registry.            [WARN]
  6. matrix_stale            — CLAUDE_COMMAND_MATRIX.md table row missing for a
                               registry command, or vice versa.           [WARN]

Output:
  07_LOGS_AND_AUDIT/command_drift/latest.json  (always written)
  stdout: JSON summary
  exit 0 = clean or warn-only; exit 1 = any ERROR present.

Call summarize() to get a one-line governance composable string.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "config" / "claude_command_registry.yaml"
RULES_PATH = REPO / "config" / "claude_adapter_rules.yaml"
COMMANDS_DIR = REPO / ".claude" / "commands"
MATRIX_PATH = REPO / "docs" / "governance" / "CLAUDE_COMMAND_MATRIX.md"
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "command_drift"
ARTIFACT_PATH = ARTIFACT_DIR / "latest.json"


# ---------------------------------------------------------------------------
# YAML loader (PyYAML required; already a harness dependency)
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit(f"PyYAML is required: {exc}") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Source scanners
# ---------------------------------------------------------------------------


def registry_commands(registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of command dicts from the registry."""
    return registry.get("commands", [])


def required_command_names(rules: dict[str, Any]) -> list[str]:
    """Return the required_commands list from the adapter rules."""
    return rules.get("required_commands", [])


def deployed_command_names() -> list[str]:
    """Scan .claude/commands/*.md and return command names (e.g. /go from go.md)."""
    if not COMMANDS_DIR.exists():
        return []
    names = []
    for md in sorted(COMMANDS_DIR.glob("*.md")):
        names.append("/" + md.stem)
    return names


def matrix_command_names() -> list[str]:
    """Parse CLAUDE_COMMAND_MATRIX.md table and return command names."""
    if not MATRIX_PATH.exists():
        return []
    names = []
    for line in MATRIX_PATH.read_text(encoding="utf-8").splitlines():
        # Table rows look like: | `/go` | … | or | /go | … |
        m = re.match(r"\|\s*`?(/[\w/-]+)`?\s*\|", line)
        if m:
            names.append(m.group(1))
    return names


# ---------------------------------------------------------------------------
# Drift checks
# ---------------------------------------------------------------------------


def check_duplicates(cmds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    dupes: list[dict[str, Any]] = []
    for cmd in cmds:
        name = cmd.get("name", "")
        if name in seen:
            dupes.append({"kind": "duplicate_names", "severity": "error", "command": name})
        seen.add(name)
    return dupes


def check_rules_vs_registry(required: list[str], reg_names: set[str]) -> list[dict[str, Any]]:
    findings = []
    for name in required:
        if name not in reg_names:
            findings.append(
                {
                    "kind": "rules_not_in_registry",
                    "severity": "error",
                    "command": name,
                    "detail": f"{name} is required by claude_adapter_rules.yaml but absent from registry",
                }
            )
    return findings


def check_registry_vs_rules(reg_names: set[str], required: list[str]) -> list[dict[str, Any]]:
    required_set = set(required)
    findings = []
    for name in sorted(reg_names - required_set):
        findings.append(
            {
                "kind": "registry_not_in_rules",
                "severity": "warn",
                "command": name,
                "detail": f"{name} is in registry but not in required_commands list",
            }
        )
    return findings


def check_script_missing(cmds: list[dict[str, Any]], repo: Path = REPO) -> list[dict[str, Any]]:
    findings = []
    for cmd in cmds:
        name = cmd.get("name", "?")
        script = cmd.get("script")
        if script is None or script == "bd":
            continue
        path = repo / script
        if not path.exists():
            findings.append(
                {
                    "kind": "script_missing",
                    "severity": "error",
                    "command": name,
                    "script": script,
                    "detail": f"{name} script not found: {path}",
                }
            )
    return findings


def check_deployed_ungoverned(deployed: list[str], reg_names: set[str]) -> list[dict[str, Any]]:
    findings = []
    for name in deployed:
        if name not in reg_names:
            findings.append(
                {
                    "kind": "deployed_ungoverned",
                    "severity": "warn",
                    "command": name,
                    "detail": (
                        f"{name} has a .claude/commands/ definition "
                        "but is not registered in claude_command_registry.yaml"
                    ),
                }
            )
    return findings


def check_matrix_stale(reg_names: set[str], matrix_names: list[str]) -> list[dict[str, Any]]:
    findings = []
    matrix_set = set(matrix_names)
    for name in sorted(reg_names - matrix_set):
        findings.append(
            {
                "kind": "matrix_stale",
                "severity": "warn",
                "command": name,
                "detail": f"{name} is in registry but missing from CLAUDE_COMMAND_MATRIX.md",
            }
        )
    for name in sorted(matrix_set - reg_names):
        findings.append(
            {
                "kind": "matrix_stale",
                "severity": "warn",
                "command": name,
                "detail": f"{name} is in CLAUDE_COMMAND_MATRIX.md but absent from registry",
            }
        )
    return findings


# ---------------------------------------------------------------------------
# Artifact + summarize
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_report(findings: list[dict[str, Any]], registry_count: int) -> dict[str, Any]:
    errors = [f for f in findings if f.get("severity") == "error"]
    warns = [f for f in findings if f.get("severity") == "warn"]
    return {
        "generated_at": _now_iso(),
        "registry_commands": registry_count,
        "overall_status": "error" if errors else ("warn" if warns else "clean"),
        "error_count": len(errors),
        "warn_count": len(warns),
        "findings": findings,
    }


def write_artifact(report: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def summarize() -> str:
    """Return a one-line governance summary; fail-open if artifact missing."""
    try:
        data = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
        status = data.get("overall_status", "unknown")
        errors = data.get("error_count", 0)
        warns = data.get("warn_count", 0)
        return f"command_drift: {status} ({errors} errors, {warns} warnings)"
    except Exception:  # noqa: BLE001
        return "command_drift: unknown (artifact unavailable)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_checks(
    registry_path: Path = REGISTRY_PATH,
    rules_path: Path = RULES_PATH,
    commands_dir: Path = COMMANDS_DIR,
    matrix_path: Path = MATRIX_PATH,
    repo: Path = REPO,
) -> dict[str, Any]:
    """Run all drift checks and return a report dict."""
    if not registry_path.exists():
        raise SystemExit(f"registry not found: {registry_path}")
    if not rules_path.exists():
        raise SystemExit(f"rules not found: {rules_path}")

    registry = _load_yaml(registry_path)
    rules = _load_yaml(rules_path)

    cmds = registry_commands(registry)
    reg_names: set[str] = {c.get("name", "") for c in cmds}
    required = required_command_names(rules)

    # Override module globals for deployed/matrix scanners (testability)
    global COMMANDS_DIR, MATRIX_PATH
    _orig_cd, _orig_mp = COMMANDS_DIR, MATRIX_PATH
    COMMANDS_DIR = commands_dir
    MATRIX_PATH = matrix_path
    try:
        deployed = deployed_command_names()
        matrix = matrix_command_names()
    finally:
        COMMANDS_DIR = _orig_cd
        MATRIX_PATH = _orig_mp

    findings: list[dict[str, Any]] = []
    findings.extend(check_duplicates(cmds))
    findings.extend(check_rules_vs_registry(required, reg_names))
    findings.extend(check_registry_vs_rules(reg_names, required))
    findings.extend(check_script_missing(cmds, repo=repo))
    findings.extend(check_deployed_ungoverned(deployed, reg_names))
    # Only compare matrix when the file exists; absent matrix = skip check
    if matrix_path.exists():
        findings.extend(check_matrix_stale(reg_names, matrix))

    return build_report(findings, len(cmds))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect drift in Claude command registry.",
    )
    parser.add_argument("--no-write", action="store_true", help="Skip artifact write.")
    parser.add_argument("--quiet", action="store_true", help="No stdout output.")
    args = parser.parse_args(argv)

    # Read module globals at call time so monkeypatching works in tests
    report = run_checks(
        registry_path=REGISTRY_PATH,
        rules_path=RULES_PATH,
        commands_dir=COMMANDS_DIR,
        matrix_path=MATRIX_PATH,
        repo=REPO,
    )

    if not args.no_write:
        write_artifact(report)

    if not args.quiet:
        print(json.dumps(report, indent=2, sort_keys=True))

    return 1 if report["overall_status"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
