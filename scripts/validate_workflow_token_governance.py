#!/usr/bin/env python3
"""Validate lite workflow token governance (budget headers, no transcript mining)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".claude" / "workflows"
LITE = ("ship.js", "qa.js", "close-issue.js", "go.js", "hotfix.js")
FORBIDDEN = re.compile(r"discovery\.slice\s*\(\s*4000", re.I)
REQUIRED_IMPORT = "_budget.js"


def main() -> int:
    errors: list[str] = []
    for name in LITE:
        path = WORKFLOWS / name
        if not path.is_file():
            errors.append(f"Missing lite workflow: {name}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if REQUIRED_IMPORT not in text and "assertBudgetAllows" not in text:
            errors.append(f"{name}: must import {REQUIRED_IMPORT} and use assertBudgetAllows")
        if FORBIDDEN.search(text):
            errors.append(f"{name}: forbidden discovery.slice(4000) pattern")
        if "~/.claude/projects" in text and "forbidden" not in text.lower():
            errors.append(f"{name}: must not reference bulk Claude JSONL without guard")

    heavy = list(WORKFLOWS.glob("*.HEAVY.js.bak"))
    if not heavy:
        errors.append("Expected archived HEAVY workflow (*.HEAVY.js.bak) for audit trail")

    gov = [
        REPO / "docs/governance/00_WORKFLOW_GOVERNANCE.md",
        REPO / "docs/governance/HANDOFF_PACKET_SCHEMA.md",
        REPO / "docs/governance/COST_INCIDENT_TEMPLATE.md",
    ]
    for p in gov:
        if not p.is_file():
            errors.append(f"Missing governance doc: {p.relative_to(REPO)}")

    if errors:
        print("Workflow token governance FAILED", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("Workflow token governance OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
