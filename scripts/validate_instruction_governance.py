#!/usr/bin/env python3
"""Fail CI if instruction wrappers re-introduce duplicate governance prose."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Thin wrappers — full policy lives in AGENT_OPERATIONS.md
MAX_LINES = {
    "AGENTS.md": 55,
    "CLAUDE.md": 45,
}

# Must not appear in both wrappers (canonical copy in AGENT_OPERATIONS.md)
FORBIDDEN_IN_WRAPPERS = [
    "Session Completion",
    "Session Compact",
    "Work is NOT complete until",
    "MANDATORY WORKFLOW:",
    "PRE_SESSION_AND_TOOLS.md` — regenerate",
    "Do not trust CRG for Cursor MCP",
]

REQUIRED_IN_AGENTS = [
    "AGENT_OPERATIONS",
    "SESSION_COMPACT",
    "bd ready",
    "bd prime",
]

REQUIRED_IN_CLAUDE = [
    "AGENT_OPERATIONS",
    "BEGIN BEADS INTEGRATION",
    "audit_mcp_context",
]


def main() -> int:
    errors: list[str] = []

    for rel, max_lines in MAX_LINES.items():
        path = REPO / rel
        if not path.is_file():
            errors.append(f"Missing {rel}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > max_lines:
            errors.append(
                f"{rel} has {len(lines)} lines (max {max_lines}); "
                "move prose to AGENT_OPERATIONS.md"
            )
        text = "\n".join(lines)
        for needle in FORBIDDEN_IN_WRAPPERS:
            if needle in text:
                errors.append(f"{rel} must not contain duplicate block: {needle!r}")

    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8") if (REPO / "AGENTS.md").is_file() else ""
    for needle in REQUIRED_IN_AGENTS:
        if needle not in agents:
            errors.append(f"AGENTS.md missing required reference: {needle!r}")

    claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8") if (REPO / "CLAUDE.md").is_file() else ""
    for needle in REQUIRED_IN_CLAUDE:
        if needle not in claude:
            errors.append(f"CLAUDE.md missing required reference: {needle!r}")

    # Wrappers should point at ops, not duplicate beads session-completion essay
    if agents.count("git push") > 1:
        errors.append("AGENTS.md duplicates git push session-completion prose")

    if errors:
        print("INSTRUCTION GOVERNANCE FAILED", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Instruction governance OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
