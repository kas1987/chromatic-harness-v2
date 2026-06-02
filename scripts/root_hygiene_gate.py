#!/usr/bin/env python3
"""root_hygiene_gate.py — keep the repo root clean (OMH-7).

A root-allowlist gate: the top level of the repo holds only an explicit, curated
set of files (config, canonical entry-point docs, manifests). Anything else — scratch
dumps, one-off audit JSON, stray test files — is a violation. This stops top-level
clutter from accreting (the recurring `_v3_*.json`, `hook_audit.json`,
`INTEGRATION_TEST.ts` problem).

Usage:
    python scripts/root_hygiene_gate.py            # check tracked top-level files
    python scripts/root_hygiene_gate.py --staged   # check git-staged top-level files (pre-commit)
    python scripts/root_hygiene_gate.py --json

Exit 0 if the root is clean, 1 if any non-allowlisted top-level file is present.
New legitimate root files must be added to ALLOWLIST in this file — that friction is
the point.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Explicitly allowed top-level files. Dotfiles (names starting with ".") are always
# allowed as config and are not listed here.
ALLOWLIST = {
    # build / tooling config
    "mypy.ini",
    "pyproject.toml",
    "pytest.ini",
    "requirements.txt",
    # canonical entry-point docs
    "AGENT_OPERATIONS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "REPO_LAYERS.md",
    "DEPLOYMENT_GUIDE.md",
    "CHROMATIC_TREES.md",
    "CHROMATIC_VISUAL_CONTROL_PLANE_INDEX.md",
    "GOVERNANCE_AND_ROUTING_ARCHITECTURE.md",
    "GOVERNANCE_EXPANSION_GATE.md",
    "HARNESS_HEALTH_DASHBOARD.md",
    "OPTION_C_COMPLETE.md",
    "VALIDATION_MATRIX.md",
    # manifests / registries
    "ARTIFACT_MANIFEST.json",
    "PACKAGE_FILE_INDEX.txt",
    "visual_node_registry.json",
}


def _tracked_top_level() -> list[str]:
    r = subprocess.run(["git", "ls-files"], cwd=str(REPO), capture_output=True, text=True, timeout=30)
    return [line for line in r.stdout.splitlines() if line and "/" not in line]


def _staged_top_level() -> list[str]:
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [line for line in r.stdout.splitlines() if line and "/" not in line]


def find_violations(top_level_files: list[str]) -> list[str]:
    """Top-level files that are neither dotfiles nor allowlisted."""
    return sorted(f for f in top_level_files if not f.startswith(".") and f not in ALLOWLIST)


def main() -> int:
    parser = argparse.ArgumentParser(description="Root-allowlist hygiene gate")
    parser.add_argument(
        "--staged", action="store_true", help="Check git-staged additions (pre-commit use) instead of all tracked"
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    files = _staged_top_level() if args.staged else _tracked_top_level()
    violations = find_violations(files)

    if args.json:
        print(json.dumps({"clean": not violations, "violations": violations, "checked": len(files)}, indent=2))
    elif violations:
        print("Root hygiene violations (move these out of the repo root or add to ALLOWLIST):")
        for v in violations:
            print(f"  - {v}")
    else:
        print(f"Root clean: {len(files)} top-level file(s), all allowlisted.")

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
