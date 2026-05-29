#!/usr/bin/env python3
"""Verify mandatory agent-operations docs and cross-links are present.

Exit 0 if OK, 1 if harness onboarding docs were removed or broken.
Used in CI so nothing critical gets deleted silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "AGENT_OPERATIONS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "12_HANDOFFS/SESSION_COMPACT.md",
    "12_HANDOFFS/PRE_SESSION_INVENTORY.md",
    "docs/PRE_SESSION_AND_TOOLS.md",
    "docs/CURSOR_CONTEXT_HYGIENE.md",
    "config/pre_session/inventory.snapshot.json",
    "config/pre_session/mcp.profile.yaml",
    "scripts/generate_pre_session_inventory.py",
    "scripts/audit_mcp_context.py",
    "scripts/session_start.py",
    ".claude/settings.json",
    ".cursor/rules/context-hygiene.mdc",
]

REQUIRED_STRINGS_IN_AGENTS = [
    "SESSION_COMPACT",
    "PRE_SESSION_AND_TOOLS",
    "CURSOR_CONTEXT_HYGIENE",
    "generate_pre_session_inventory",
    "audit_mcp_context",
    "check_agent_operations",
    "AGENT_OPERATIONS",
]

REQUIRED_SNAPSHOT_KEYS = [
    "generated_at",
    "summary",
    "native_tools",
    "mcp_servers",
    "crg_manifest",
]


def main() -> int:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        path = REPO / rel
        if not path.is_file():
            errors.append(f"Missing required file: {rel}")

    agents_md = REPO / "AGENTS.md"
    if agents_md.is_file():
        text = agents_md.read_text(encoding="utf-8")
        for needle in REQUIRED_STRINGS_IN_AGENTS:
            if needle not in text:
                errors.append(f"AGENTS.md missing required reference: {needle!r}")

    snapshot_path = REPO / "config/pre_session/inventory.snapshot.json"
    if snapshot_path.is_file():
        try:
            data = json.loads(snapshot_path.read_text(encoding="utf-8"))
            for key in REQUIRED_SNAPSHOT_KEYS:
                if key not in data:
                    errors.append(f"inventory.snapshot.json missing key: {key}")
            summary = data.get("summary", {})
            if summary.get("native_tool_count", 0) < 1:
                errors.append("inventory.snapshot.json: native_tool_count invalid")
            if summary.get("crg_resource_count", 0) < 1:
                errors.append("inventory.snapshot.json: crg_resource_count invalid")
        except json.JSONDecodeError as exc:
            errors.append(f"inventory.snapshot.json invalid JSON: {exc}")

    claude_md = REPO / "CLAUDE.md"
    if claude_md.is_file():
        text = claude_md.read_text(encoding="utf-8")
        if "AGENT_OPERATIONS" not in text:
            errors.append("CLAUDE.md missing AGENT_OPERATIONS reference")
        if "CURSOR_CONTEXT_HYGIENE" not in text and "audit_mcp_context" not in text:
            errors.append("CLAUDE.md missing MCP hygiene reference")

    ops_md = REPO / "AGENT_OPERATIONS.md"
    if ops_md.is_file():
        text = ops_md.read_text(encoding="utf-8")
        if "audit_mcp_context" not in text:
            errors.append("AGENT_OPERATIONS.md missing audit_mcp_context reference")

    if errors:
        print("AGENT OPERATIONS CHECK FAILED", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nRestore docs per AGENT_OPERATIONS.md before merging.",
            file=sys.stderr,
        )
        return 1

    print("Agent operations check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
