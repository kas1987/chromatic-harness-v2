#!/usr/bin/env python3
"""Audit lifecycle hooks: repo, Claude Code, Cursor, scheduled tasks, CI guards.

Usage:
    python scripts/audit_hooks.py
    python scripts/audit_hooks.py --json
    python scripts/audit_hooks.py --markdown > docs/audit/HOOK_AUDIT_LATEST.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()

CLAUDE_SETTINGS_PATHS = [
    HOME / ".claude" / "settings.json",
    HOME / ".claude" / "settings.local.json",
    REPO / ".claude" / "settings.json",
    REPO / ".claude" / "settings.local.json",
]

CURSOR_HOOK_PATHS = [
    REPO / ".cursor" / "hooks.json",
    HOME / ".cursor" / "hooks.json",
]

REPO_HOOK_SCRIPTS = [
    "scripts/session_start.py",
    "scripts/session_boot_automation.py",
    ".cursor/hooks/session_boot.py",
    "02_RUNTIME/router/gate.py",
]

SCHEDULED_TASK_NAMES = [
    "ChromaticIntakeCycle",
    "ChromaticSmokeDaily",
    "ChromaticSessionBoot",
    "ChromaticSessionPreflight",
]

CI_GUARDS = [
    ("Agent operations", "scripts/check_agent_operations.py"),
    ("Intake loop", "scripts/validate_intake_loop.py"),
    ("MCP audit fixture", "scripts/audit_mcp_context.py --mcps-path tests/fixtures/mcp_minimal"),
]


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_error": "invalid JSON"}


def _extract_claude_hooks(settings: dict, source: str) -> list[dict]:
    rows: list[dict] = []
    hooks = settings.get("hooks") or {}
    for event, blocks in hooks.items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            matcher = block.get("matcher", "") if isinstance(block, dict) else ""
            inner = block.get("hooks", [block]) if isinstance(block, dict) else [block]
            for h in inner:
                if not isinstance(h, dict):
                    continue
                cmd = h.get("command", "")
                rows.append(
                    {
                        "platform": "claude_code",
                        "source": source,
                        "event": event,
                        "matcher": matcher or "(all)",
                        "type": h.get("type", "command"),
                        "command": cmd,
                        "timeout": h.get("timeout"),
                        "fail_open": "|| true" in cmd or "||true" in cmd,
                    }
                )
    return rows


def _extract_cursor_hooks(doc: dict, source: str) -> list[dict]:
    rows: list[dict] = []
    hooks = doc.get("hooks") or {}
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rows.append(
                {
                    "platform": "cursor",
                    "source": source,
                    "event": event,
                    "matcher": entry.get("matcher", "(all)"),
                    "type": entry.get("type", "command"),
                    "command": entry.get("command", ""),
                    "timeout": entry.get("timeout"),
                    "fail_closed": entry.get("failClosed"),
                }
            )
    return rows


def _resolve_exists(command: str) -> bool | None:
    if not command:
        return None
    # First token that looks like a path
    for part in re.split(r"\s+", command.strip()):
        if part.endswith((".py", ".sh", ".ps1", ".js")):
            p = Path(part.replace("~", str(HOME)))
            if p.is_file():
                return True
            if (REPO / part).is_file():
                return True
        if "chromatic-harness-v2" in part and part.endswith(".py"):
            return Path(part).is_file()
    return None


def _query_schtasks(name: str) -> dict:
    try:
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", name, "/FO", "LIST", "/V"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return {"name": name, "installed": r.returncode == 0, "detail": (r.stdout or "")[:500]}
    except (OSError, subprocess.TimeoutExpired):
        return {"name": name, "installed": False, "detail": ""}


def _list_workflows() -> list[str]:
    wf = REPO / ".claude" / "workflows"
    if not wf.is_dir():
        return []
    return sorted(p.name for p in wf.iterdir() if p.is_file())


def _findings(rows: list[dict]) -> list[dict]:
    findings: list[dict] = []
    agent_cmds = [
        r["command"]
        for r in rows
        if r.get("event") in ("PreToolUse", "preToolUse")
        and "Agent" in str(r.get("matcher", ""))
    ]
    if len(agent_cmds) > 1:
        findings.append(
            {
                "severity": "HIGH",
                "title": "Duplicate PreToolUse Agent hooks",
                "detail": f"{len(agent_cmds)} Agent gate hooks configured — may run gate.py twice per agent dispatch.",
                "commands": agent_cmds,
            }
        )

    session_starts = [r for r in rows if r.get("event") in ("SessionStart", "sessionStart")]
    if len(session_starts) > 3:
        findings.append(
            {
                "severity": "MED",
                "title": "Many SessionStart hooks",
                "detail": f"{len(session_starts)} SessionStart hooks — additive latency at every session open.",
                "count": len(session_starts),
            }
        )

    cursor_boot = [r for r in rows if r.get("platform") == "cursor" and r.get("event") == "sessionStart"]
    if not cursor_boot:
        findings.append(
            {
                "severity": "MED",
                "title": "No Cursor sessionStart hook",
                "detail": "Add .cursor/hooks.json sessionStart for automated pre-session boot.",
            }
        )

    tasks = [_query_schtasks(n) for n in SCHEDULED_TASK_NAMES]
    if not any(t["installed"] for t in tasks):
        findings.append(
            {
                "severity": "LOW",
                "title": "Chromatic Task Scheduler tasks not installed",
                "detail": "Run scripts/install_automation_tasks.ps1 for hands-off intake/boot.",
            }
        )

    return findings


def build_report() -> dict[str, Any]:
    rows: list[dict] = []
    sources: list[dict] = []

    for path in CLAUDE_SETTINGS_PATHS:
        doc = _load_json(path)
        sources.append({"path": str(path), "exists": doc is not None})
        if doc and "hooks" in doc:
            rows.extend(_extract_claude_hooks(doc, str(path)))

    for path in CURSOR_HOOK_PATHS:
        doc = _load_json(path)
        sources.append({"path": str(path), "exists": doc is not None})
        if doc and "hooks" in doc:
            rows.extend(_extract_cursor_hooks(doc, str(path)))

    for rel in REPO_HOOK_SCRIPTS:
        p = REPO / rel
        rows.append(
            {
                "platform": "repo_script",
                "source": str(p.relative_to(REPO)),
                "event": "(referenced)",
                "matcher": "",
                "command": rel,
                "exists": p.is_file(),
            }
        )

    for r in rows:
        if "command" in r and "exists" not in r:
            r["script_exists"] = _resolve_exists(r.get("command", ""))

    scheduled = [_query_schtasks(n) for n in SCHEDULED_TASK_NAMES]
    workflows = _list_workflows()
    always_rules = list((REPO / ".cursor" / "rules").glob("*.mdc")) if (REPO / ".cursor" / "rules").is_dir() else []

    return {
        "repo": str(REPO),
        "generated_by": "scripts/audit_hooks.py",
        "settings_sources": sources,
        "hook_registry": rows,
        "repo_workflows": workflows,
        "cursor_always_rules": [p.name for p in always_rules],
        "scheduled_tasks": scheduled,
        "ci_guards": CI_GUARDS,
        "findings": _findings(rows),
        "ide_summary": {
            "cursor": "sessionStart hook + alwaysApply rules (not full lifecycle)",
            "claude_code": "Global ~/.claude/settings.json stacks with project .claude/settings.json",
            "vscode": "No repo hooks — relies on Cursor/Claude extensions",
            "terminal": "No repo shell profile hooks — use Task Scheduler or manual scripts",
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hook Audit Report",
        "",
        f"Repo: `{report['repo']}`",
        "",
        "## Executive summary",
        "",
        "| Surface | Hook count | Notes |",
        "|---------|------------|-------|",
    ]
    by_platform: dict[str, int] = {}
    for r in report["hook_registry"]:
        p = r.get("platform", "?")
        by_platform[p] = by_platform.get(p, 0) + 1
    for p, n in sorted(by_platform.items()):
        lines.append(f"| {p} | {n} | |")

    lines.extend(["", "## Findings", ""])
    if not report["findings"]:
        lines.append("No automated findings.")
    else:
        for f in report["findings"]:
            lines.append(f"### {f['severity']}: {f['title']}")
            lines.append("")
            lines.append(f["detail"])
            lines.append("")

    lines.extend(["## Claude Code + Cursor hook registry", ""])
    lines.append("| Platform | Source | Event | Matcher | Timeout | Command |")
    lines.append("|----------|--------|-------|---------|---------|---------|")
    for r in report["hook_registry"]:
        if r.get("platform") == "repo_script":
            continue
        cmd = (r.get("command") or "")[:80].replace("|", "\\|")
        lines.append(
            f"| {r.get('platform')} | `{Path(r.get('source','')).name}` | "
            f"{r.get('event')} | {r.get('matcher')} | {r.get('timeout','')} | `{cmd}` |"
        )

    lines.extend(["", "## Repo workflows (slash commands, not lifecycle hooks)", ""])
    for w in report["repo_workflows"]:
        lines.append(f"- `{w}`")

    lines.extend(["", "## Cursor always-on rules", ""])
    for name in report["cursor_always_rules"]:
        lines.append(f"- `.cursor/rules/{name}`")

    lines.extend(["", "## Windows Task Scheduler", ""])
    for t in report["scheduled_tasks"]:
        status = "installed" if t["installed"] else "not installed"
        lines.append(f"- **{t['name']}**: {status}")

    lines.extend(["", "## CI guards (GitHub Actions)", ""])
    for name, cmd in report["ci_guards"]:
        lines.append(f"- {name}: `{cmd}`")

    lines.extend(["", "## IDE / CLI matrix", ""])
    for k, v in report["ide_summary"].items():
        lines.append(f"- **{k}**: {v}")

    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "1. **Claude Code:** Global `~/.claude/settings.json` and project `.claude/settings.json` **stack** — every event runs both. Keep harness hooks only in the project file; avoid duplicating `gate.py` on `PreToolUse` / `Agent`.",
            "2. **Cursor:** Only `sessionStart` is wired — no `preToolUse` / `stop` hooks. Use `.cursor/rules/context-hygiene.mdc` for policy; add hooks only when you need hard gates.",
            "3. **Terminal / hands-off:** Install Task Scheduler tasks: `install_automation_tasks.ps1` (boot, intake, smoke).",
            "4. **Re-audit:** `python scripts/audit_hooks.py --markdown > docs/audit/HOOK_AUDIT_LATEST.md`",
            "5. **Workflows:** `.claude/workflows/*.js` are slash-command prompts, not lifecycle hooks — audit separately for token cost (`docs/AGENT_ANTIPATTERNS.md`).",
            "",
            "## What is NOT a hook (but acts like one)",
            "",
            "- `.cursor/rules/*.mdc` with `alwaysApply: true` — injected rules every turn",
            "- `AGENTS.md` / `CLAUDE.md` — entry instructions",
            "- GitHub Actions on push/PR — CI guards, not IDE session hooks",
            "- MCP server tools — schema injection per turn when enabled in Cursor",
            "",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit hooks across repo and IDEs")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.markdown:
        print(render_markdown(report))
    else:
        print(render_markdown(report))
        print("\n---\nJSON: python scripts/audit_hooks.py --json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
