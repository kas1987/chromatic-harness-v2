#!/usr/bin/env python3
"""Generate pre-session tool/MCP inventory docs from live Cursor MCP descriptors.

Usage:
    python scripts/generate_pre_session_inventory.py
    python scripts/generate_pre_session_inventory.py --mcps-path /path/to/mcps

Outputs:
    config/pre_session/inventory.snapshot.json
    docs/PRE_SESSION_AND_TOOLS.md
    12_HANDOFFS/PRE_SESSION_INVENTORY.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"
sys.path.insert(0, str(_RUNTIME))

from router.context_manifest import ContextResourceManifest  # noqa: E402

NATIVE_TOOLS = [
    ("Shell", "Run terminal commands (git, bd, pytest, docker)"),
    ("Read", "Read files including images"),
    ("Write / StrReplace / Delete", "Create and edit files"),
    ("Grep", "Ripgrep search"),
    ("Glob", "Find files by pattern"),
    ("WebSearch / WebFetch", "Web lookup when enabled"),
    ("GenerateImage", "Image generation when explicitly requested"),
    ("ReadLints", "IDE linter diagnostics"),
    ("EditNotebook", "Jupyter cell edits"),
    ("CallMcpTool", "Invoke MCP server tools"),
    ("FetchMcpResource", "Read MCP resources"),
    ("Task", "Spawn subagents (explore, shell, ci-investigator, etc.)"),
    ("SwitchMode", "Plan vs agent mode"),
    ("AskQuestion", "Structured user multiple-choice"),
    ("Await", "Poll background shells"),
]

SUBAGENTS = [
    "generalPurpose",
    "explore",
    "shell",
    "cursor-guide",
    "ci-investigator",
    "best-of-n-runner",
    "granola-engineer",
    "devsecops",
    "investigator",
]

HARNESS_MCP_FAMILIES = [
    ("filesystem.read", "Inspect files", "Low"),
    ("filesystem.patch", "Patch scoped files", "Medium"),
    ("github.read", "Issues, PRs, repo content", "Low"),
    ("github.write", "Issues, branches, PRs", "Medium"),
    ("shell.execute", "Run tests/scripts", "High"),
    ("database.read", "Inspect state", "Low"),
    ("database.write", "Update state", "Medium"),
    ("browser.search", "Current research", "Low"),
    ("secrets.read", "Secret access", "Critical"),
    ("deploy.production", "Production deploy", "Critical"),
]

CRG_TO_CURSOR_MAP = [
    ("read", "Read", "Native"),
    ("write", "Write", "Native"),
    ("edit", "StrReplace", "Native"),
    ("bash", "Shell", "Native"),
    ("audit", "Skills (on-demand Read)", "Pull"),
    ("test", "Skills (on-demand Read)", "Pull"),
    ("security", "Skills + Opsera MCP", "Pull / MCP"),
    ("council", "Skills (on-demand Read)", "Pull"),
    ("github_read", "plugin-github-github", "MCP (auth required)"),
    ("github_write", "plugin-github-github", "MCP (auth required)"),
    ("web_search", "WebSearch / Playwright", "Native / MCP"),
    ("shell_execute", "Shell / remote MCP", "Native"),
    ("secrets_read", "Blocked by policy", "Critical — gate"),
    ("browser", "plugin-playwright-playwright", "MCP"),
    ("codex_team", "Task subagents", "Native"),
]


def _load_settings() -> dict:
    for name in ("settings.local.yaml", "settings.example.yaml"):
        path = _REPO / "config" / "pre_session" / name
        if not path.exists():
            continue
        try:
            import yaml  # type: ignore[import-untyped]

            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {}


def scan_mcp_servers(mcps_path: Path) -> list[dict]:
    servers: list[dict] = []
    if not mcps_path.is_dir():
        return servers
    for server_dir in sorted(mcps_path.iterdir()):
        if not server_dir.is_dir():
            continue
        tools_dir = server_dir / "tools"
        tools: list[str] = []
        if tools_dir.is_dir():
            tools = sorted(p.stem for p in tools_dir.glob("*.json"))
        meta_path = server_dir / "SERVER_METADATA.json"
        display = server_dir.name
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                display = meta.get("serverName", display)
            except Exception:
                pass
        servers.append(
            {
                "id": server_dir.name,
                "display_name": display,
                "tool_count": len(tools),
                "tools": tools,
                "status": "active" if tools else "registered_no_descriptors",
            }
        )
    return servers


def crg_manifest_rows() -> list[dict]:
    manifest = ContextResourceManifest.build_defaults()
    rows = []
    for rid, res in sorted(manifest.resources.items()):
        rows.append(
            {
                "id": rid,
                "type": res.resource_type,
                "description": res.description,
                "estimated_tokens": res.estimated_tokens,
                "risk_level": res.risk_level,
                "task_types": [t.value for t in res.task_types] or ["any"],
                "privacy_classes": [p.value for p in res.privacy_classes] or ["any"],
            }
        )
    return rows


def build_snapshot(mcps_path: Path) -> dict:
    servers = scan_mcp_servers(mcps_path)
    total_mcp_tools = sum(s["tool_count"] for s in servers)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(_REPO),
        "mcp_descriptors_path": str(mcps_path),
        "summary": {
            "native_tool_count": len(NATIVE_TOOLS),
            "subagent_count": len(SUBAGENTS),
            "mcp_server_count": len(servers),
            "mcp_tool_count": total_mcp_tools,
            "crg_resource_count": len(crg_manifest_rows()),
        },
        "native_tools": [{"name": n, "purpose": p} for n, p in NATIVE_TOOLS],
        "subagents": SUBAGENTS,
        "mcp_servers": servers,
        "crg_manifest": crg_manifest_rows(),
        "harness_mcp_families": [
            {"family": f, "purpose": p, "risk": r} for f, p, r in HARNESS_MCP_FAMILIES
        ],
        "crg_to_cursor_mapping": [
            {"crg_id": a, "cursor_surface": b, "notes": c} for a, b, c in CRG_TO_CURSOR_MAP
        ],
    }


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_full_doc(snapshot: dict) -> str:
    s = snapshot["summary"]
    lines = [
        "# Pre-Session Tools, Resources, and MCP Inventory",
        "",
        f"> **Generated:** `{snapshot['generated_at']}`  ",
        "> **Regenerate:** `python scripts/generate_pre_session_inventory.py`  ",
        f"> **MCP path scanned:** `{snapshot['mcp_descriptors_path']}`",
        "",
        "Baseline documentation before changing tool exposure, MCP plugins, or CRG policy.",
        "See also: [12_HANDOFFS/SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md)",
        "**Lean Cursor context:** [docs/CURSOR_CONTEXT_HYGIENE.md](../docs/CURSOR_CONTEXT_HYGIENE.md) — `python scripts/audit_mcp_context.py`",
        "",
        "---",
        "",
        "## Summary",
        "",
        _md_table(
            ["Category", "Count"],
            [
                ["Native Cursor tools", str(s["native_tool_count"])],
                ["Subagent types", str(s["subagent_count"])],
                ["MCP servers (registered)", str(s["mcp_server_count"])],
                ["MCP tools (descriptors)", str(s["mcp_tool_count"])],
                ["CRG manifest resources", str(s["crg_resource_count"])],
            ],
        ),
        "",
        "---",
        "",
        "## Three layers (do not confuse)",
        "",
        "| Layer | What it is | Loaded when |",
        "|-------|------------|-------------|",
        "| **Instruction context** | Rules, AGENTS.md, tool schemas, skill catalog summaries | Every turn |",
        "| **Invoked tools** | Shell, Read, MCP calls, skill file reads | On use |",
        "| **Harness CRG** | Router manifest of allowed pre-context resources | Per task via ContextGate |",
        "",
        "---",
        "",
        "## Native Cursor tools",
        "",
        _md_table(
            ["Tool", "Purpose"],
            [[t["name"], t["purpose"]] for t in snapshot["native_tools"]],
        ),
        "",
        "### Subagents (`Task` tool)",
        "",
        ", ".join(f"`{a}`" for a in snapshot["subagents"]),
        "",
        "**Repo rule:** Use `bd` for task tracking — not `TodoWrite`.",
        "",
        "---",
        "",
        "## MCP servers (Cursor workspace)",
        "",
    ]
    for server in snapshot["mcp_servers"]:
        status = server["status"]
        lines.append(f"### `{server['id']}` ({server['display_name']}) — {server['tool_count']} tools")
        lines.append("")
        if status == "registered_no_descriptors":
            lines.append(
                "*Registered but no tool descriptors — likely needs authentication or plugin not connected.*"
            )
            lines.append("")
        elif server["tools"]:
            # Group long tool lists
            tools = server["tools"]
            if len(tools) <= 15:
                lines.append(", ".join(f"`{t}`" for t in tools))
            else:
                lines.append(f"**Categories:** {', '.join(f'`{t}`' for t in tools[:8])}, … (+{len(tools)-8} more)")
                lines.append("")
                lines.append("<details><summary>Full tool list</summary>")
                lines.append("")
                lines.append(", ".join(f"`{t}`" for t in tools))
                lines.append("")
                lines.append("</details>")
            lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Harness CRG manifest (Context Resource Governance)",
            "",
            "What the router may allow into pre-context for Pi / governed Claude sessions.",
            "Filtered by `09_DEPLOYMENT/config/routing/context-policy.yaml`.",
            "",
            _md_table(
                ["ID", "Type", "Tokens", "Risk", "Description"],
                [
                    [
                        r["id"],
                        r["type"],
                        str(r["estimated_tokens"]),
                        r["risk_level"],
                        r["description"][:50],
                    ]
                    for r in snapshot["crg_manifest"]
                ],
            ),
            "",
            "---",
            "",
            "## Harness MCP families (spec — not yet implemented as servers)",
            "",
            "From `01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md`:",
            "",
            _md_table(
                ["Family", "Purpose", "Risk"],
                [
                    [f["family"], f["purpose"], f["risk"]]
                    for f in snapshot["harness_mcp_families"]
                ],
            ),
            "",
            "---",
            "",
            "## CRG → Cursor mapping (baseline)",
            "",
            _md_table(
                ["CRG resource", "Cursor surface", "Notes"],
                [
                    [m["crg_id"], m["cursor_surface"], m["notes"]]
                    for m in snapshot["crg_to_cursor_mapping"]
                ],
            ),
            "",
            "---",
            "",
            "## Skills policy",
            "",
            "Skills are **not** pre-loaded. The agent sees a catalog in instructions;",
            "full content loads only when `Read` on a `SKILL.md` path.",
            "",
            "Categories include: RPI/beads, package-ingest, security, Grafana, SDK, email, etc.",
            "",
            "---",
            "",
            "## Session start checklist",
            "",
            "```bash",
            "cat .agents/handoffs/latest.json    # if exists",
            "bd prime && bd ready",
            "git branch --show-current && git status --short",
            "python scripts/generate_pre_session_inventory.py   # after MCP changes",
            "```",
            "",
            "---",
            "",
            "## Change control (read before altering tools)",
            "",
            "1. Run `python scripts/generate_pre_session_inventory.py` and commit the diff.",
            "2. Update `09_DEPLOYMENT/config/routing/context-policy.yaml` if CRG rules change.",
            "3. Update `02_RUNTIME/router/context_manifest.py` if resource IDs change.",
            "4. Re-run `pytest tests/test_context_*.py` for CRG.",
            "5. Note changes in beads / handoff for the next session.",
            "",
        ]
    )
    return "\n".join(lines)


def render_handoffs_index(snapshot: dict) -> str:
    s = snapshot["summary"]
    return f"""# Pre-Session Inventory (Quick Reference)

> Full doc: [docs/PRE_SESSION_AND_TOOLS.md](../docs/PRE_SESSION_AND_TOOLS.md)  
> Generated: `{snapshot['generated_at']}`

## At a glance

| Category | Count |
|----------|------:|
| Native tools | {s['native_tool_count']} |
| MCP servers | {s['mcp_server_count']} |
| MCP tools | {s['mcp_tool_count']} |
| CRG resources | {s['crg_resource_count']} |

## Before changing tools or MCP

1. `python scripts/generate_pre_session_inventory.py`
2. Review diff in `config/pre_session/inventory.snapshot.json`
3. Update CRG policy if needed

## Lean Cursor context (disable heavy MCPs)

`python scripts/audit_mcp_context.py --profile harness_dev`  
See [docs/CURSOR_CONTEXT_HYGIENE.md](../docs/CURSOR_CONTEXT_HYGIENE.md)

## Session start

```bash
cat .agents/handoffs/latest.json
bd ready
```

See [SESSION_COMPACT.md](SESSION_COMPACT.md) for compaction protocol.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate pre-session inventory docs")
    parser.add_argument("--mcps-path", type=Path, help="Cursor mcps descriptors directory")
    args = parser.parse_args()

    settings = _load_settings()
    mcps_path = args.mcps_path
    if mcps_path is None:
        raw = settings.get("mcp_descriptors_path", "")
        mcps_path = Path(raw).expanduser() if raw else None
    if mcps_path is None or not mcps_path.is_dir():
        print(
            "ERROR: MCP descriptors path not found.\n"
            "  cp config/pre_session/settings.example.yaml config/pre_session/settings.local.yaml\n"
            "  Edit mcp_descriptors_path, or pass --mcps-path",
            file=sys.stderr,
        )
        return 1

    snapshot = build_snapshot(mcps_path)

    out_json = _REPO / "config" / "pre_session" / "inventory.snapshot.json"
    out_doc = _REPO / "docs" / "PRE_SESSION_AND_TOOLS.md"
    out_handoffs = _REPO / "12_HANDOFFS" / "PRE_SESSION_INVENTORY.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    out_doc.write_text(render_full_doc(snapshot), encoding="utf-8")
    out_handoffs.write_text(render_handoffs_index(snapshot), encoding="utf-8")

    print(f"Wrote {out_json}")
    print(f"Wrote {out_doc}")
    print(f"Wrote {out_handoffs}")
    print(
        f"Summary: {snapshot['summary']['mcp_server_count']} servers, "
        f"{snapshot['summary']['mcp_tool_count']} MCP tools"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
