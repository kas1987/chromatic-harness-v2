#!/usr/bin/env python3
"""
Chromatic Harness v2: New Session Bootstrap

Generates .agents/context/BOOT_CONTEXT.md from context_rebuild_manifest.json.
Uses Python standard library only.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def findings_text(findings: list[dict[str, Any]], limit: int = 12) -> str:
    if not findings:
        return "No audit findings available."
    lines: list[str] = []
    for finding in findings[:limit]:
        path = finding.get("path", "unknown")
        severity = finding.get("severity", "unknown")
        kind = finding.get("kind", "finding")
        message = finding.get("message", "")
        lines.append(f"- **{severity}** `{kind}` — `{path}`: {message}")
    if len(findings) > limit:
        lines.append(f"- ... {len(findings) - limit} more findings omitted from boot context.")
    return "\n".join(lines)


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / ".agents" / "context" / "context_rebuild_manifest.json"
    if not path.exists():
        return {
            "generated_at": utc_now(),
            "mode": "missing-manifest",
            "repo_root": str(root),
            "git": {"branch": "unknown", "status_short": []},
            "handoff": {"latest_pointer_exists": False, "handoff_path": None},
            "beads": {"available": False, "ready_summary": "No context manifest found; run context_rebuild.py first."},
            "context_policy": {"always_load": [], "load_if_relevant": [], "never_auto_load": []},
            "audit": {"risk_level": "unknown", "findings": []},
            "next_action": "Run python scripts/context_rebuild.py --root . --mode hard",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def transfer_section(handoff: dict[str, Any]) -> str:
    if not handoff.get("transfer_packet_exists"):
        return ""
    decision = handoff.get("budget_decision") or "unknown"
    boot = handoff.get("boot_commands") or []
    boot_lines = "\n".join(f"- `{c}`" for c in boot) if boot else "- (none in packet)"
    halt = ""
    if decision == "halt_human":
        halt = "\n\n**HALT:** Budget exhausted — human lane only. Do not auto-spawn or burn cloud tokens."
    return f"""
## Agent Transfer (successor bootstrap)

| Field | Value |
|---|---|
| Transfer packet | `{handoff.get("transfer_packet_path", ".agents/handoffs/transfer_packet.json")}` |
| Budget decision | `{decision}` |
{halt}

### Boot commands (from ATP)

{boot_lines}
"""


def render_boot_context(manifest: dict[str, Any]) -> str:
    git = manifest.get("git", {})
    handoff = manifest.get("handoff", {})
    beads = manifest.get("beads", {})
    policy = manifest.get("context_policy", {})
    audit = manifest.get("audit", {})
    transfer = transfer_section(handoff)

    status_lines = git.get("status_short") or []
    status_text = "\n".join(status_lines) if status_lines else "clean or unavailable"

    return f"""# Harness Boot Context

> Operational snapshot for a clean Chromatic Harness v2 session. This is not permanent canon.

## Session Status

| Field | Value |
|---|---|
| Generated At | {utc_now()} |
| Manifest Generated At | {manifest.get('generated_at', 'unknown')} |
| Rebuild Mode | {manifest.get('mode', 'unknown')} |
| Repo Root | {manifest.get('repo_root', 'unknown')} |
| Context Risk | {audit.get('risk_level', 'unknown')} |

## Active Mission

Select the highest-priority active bead or mission. Do not infer from old chat history.

## Git State

```text
Branch: {git.get('branch', 'unknown')}
Status:
{status_text}
Last Commit: {git.get('last_commit', 'unknown')}
```

## Active Handoff

```text
Latest pointer exists: {handoff.get('latest_pointer_exists', False)}
Latest pointer path: {handoff.get('latest_pointer_path')}
Handoff path: {handoff.get('handoff_path')}
```
{transfer}
## Active Beads

```text
{str(beads.get('ready_summary', 'bd unavailable'))[:4000]}
```

## Allowed Pre-Session Context

### Always Load

{bullet_list(policy.get('always_load', []))}

### Load Only If Relevant

{bullet_list(policy.get('load_if_relevant', []))}

### Never Auto-Load

{bullet_list(policy.get('never_auto_load', []))}

## Context Audit Findings

{findings_text(audit.get('findings', []))}

## Next Action

{manifest.get('next_action', 'Select one active bead and proceed with bounded scope.')}

## Stop Conditions

Stop and rebuild again if:

- Context reaches 75%+.
- Required task context is missing.
- Agent starts reading unrelated logs, archives, or old handoffs.
- Active bead/mission is unclear.
- A destructive action is required.

## Operating Reminder

Use this boot packet to start clean. Then load only the selected bead, required source files, and the smallest relevant governance document.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate BOOT_CONTEXT.md from context rebuild manifest.")
    parser.add_argument("--root", default=".", help="Repository root. Default: current directory.")
    parser.add_argument("--out", default=".agents/context/BOOT_CONTEXT.md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(root)
    out_path.write_text(render_boot_context(manifest), encoding="utf-8")
    print(f"Boot context written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
