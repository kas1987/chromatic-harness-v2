"""Shared helpers for pre-session inventory, audit, and context reports."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPO / "config" / "pre_session" / "mcp.profile.yaml"

RULE_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "AGENT_OPERATIONS.md",
    ".cursor/rules/context-hygiene.mdc",
    "12_HANDOFFS/SESSION_COMPACT.md",
    "00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md",
    "docs/governance/PRE_SESSION_CONTEXT_POLICY.md",
]

RUNTIME_DOCS = {
    "cursor": {
        "label": "Cursor IDE",
        "injects": [
            "Workspace rules (AGENTS.md, .cursor/rules)",
            "Enabled MCP tool JSON schemas",
            "Agent skill catalog (names/blurbs)",
            "Native tool schemas",
        ],
        "hooks": [".cursor/rules/context-hygiene.mdc (alwaysApply)"],
    },
    "claude": {
        "label": "Claude Code (project)",
        "injects": [
            "CLAUDE.md + AGENTS.md",
            "Same MCP/schemas as Cursor when using this workspace",
        ],
        "hooks": [
            ".claude/settings.json SessionStart -> session_start.py",
            "PreToolUse Agent -> gate.py",
            "PreCompact -> bd prime",
        ],
    },
    "harness": {
        "label": "Chromatic Harness runtime",
        "injects": [
            "CRG ContextGate resource estimates (router/API)",
            "Mission packet / execution-packet when in RPI",
            "Handoff files under .agents/handoffs/",
        ],
        "hooks": ["POST /route ContextGate", "Agent Lead synthesize handoff"],
    },
}


def tok(chars: int) -> int:
    return chars // 4


def load_settings() -> dict:
    for name in ("settings.local.yaml", "settings.example.yaml"):
        path = REPO / "config" / "pre_session" / name
        if path.exists():
            try:
                import yaml  # type: ignore[import-untyped]

                return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass
    return {}


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        return {}
    import yaml  # type: ignore[import-untyped]

    return yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8")) or {}


def resolve_mcps_path(cli_path: str | None) -> Path:
    if cli_path:
        return Path(cli_path)
    settings = load_settings()
    if settings.get("mcp_descriptors_path"):
        return Path(settings["mcp_descriptors_path"])
    return REPO / "tests" / "fixtures" / "mcp_minimal"


def scan_mcps(mcps_path: Path) -> tuple[int, int, dict[str, int]]:
    """Return (tool_count, total_chars, per_server_chars)."""
    per_server: dict[str, int] = {}
    tool_count = 0
    for f in mcps_path.rglob("tools/*.json"):
        tool_count += 1
        chars = len(f.read_text(encoding="utf-8"))
        server = f.parts[-3] if len(f.parts) >= 3 else "unknown"
        per_server[server] = per_server.get(server, 0) + chars
    return tool_count, sum(per_server.values()), per_server


def measure_rule_files(extra_paths: list[Path] | None = None) -> list[dict]:
    rows: list[dict] = []
    paths = [REPO / p for p in RULE_FILES]
    if extra_paths:
        paths.extend(extra_paths)
    home_agents = Path.home() / "AGENTS.md"
    if home_agents.is_file():
        paths.append(home_agents)
    seen: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        chars = len(path.read_text(encoding="utf-8"))
        try:
            rel = str(path.relative_to(REPO))
        except ValueError:
            rel = str(path)
        rows.append(
            {
                "path": rel,
                "chars": chars,
                "estimated_tokens": tok(chars),
                "auto_injected": rel
                in (
                    "AGENTS.md",
                    "CLAUDE.md",
                    ".cursor/rules/context-hygiene.mdc",
                )
                or "AGENTS.md" in rel,
            }
        )
    return rows


def scan_skills_catalog(skills_path: Path | None) -> dict:
    if not skills_path or not skills_path.is_dir():
        return {
            "path": str(skills_path) if skills_path else None,
            "skill_files": 0,
            "chars": 0,
            "estimated_tokens": 0,
            "note": "Set cursor_skills_path in config/pre_session/settings.local.yaml",
        }
    files = list(skills_path.rglob("SKILL.md"))
    chars = sum(len(f.read_text(encoding="utf-8")) for f in files)
    return {
        "path": str(skills_path),
        "skill_files": len(files),
        "chars": chars,
        "estimated_tokens": tok(chars),
        "note": "Catalog blurbs in Cursor may be smaller than full SKILL.md bodies",
    }


def read_handoff() -> dict:
    latest = REPO / ".agents" / "handoffs" / "latest.json"
    if not latest.is_file():
        return {"present": False, "path": str(latest.relative_to(REPO))}
    import json

    data = json.loads(latest.read_text(encoding="utf-8"))
    handoff_md = REPO / data.get("handoff_path", "")
    md_chars = 0
    if handoff_md.is_file():
        md_chars = len(handoff_md.read_text(encoding="utf-8"))
    return {
        "present": True,
        "path": str(latest.relative_to(REPO)),
        "data": data,
        "handoff_md_tokens": tok(md_chars),
        "handoff_md_loaded_automatically": False,
    }


def crg_estimates() -> list[dict]:
    import sys

    sys.path.insert(0, str(REPO / "02_RUNTIME"))
    from router.context_gate import ContextGate  # noqa: E402
    from router.contracts import (  # noqa: E402
        PrivacyClass,
        RouteConstraints,
        RouteRequest,
        TaskType,
    )

    gate = ContextGate()
    rows = []
    for task in TaskType:
        for max_tokens in (8000, 128_000):
            req = RouteRequest(
                request_id="ctx-report",
                task_id="ctx-report",
                task_type=task,
                objective="session context report",
                constraints=RouteConstraints(
                    privacy_class=PrivacyClass.P1,
                    max_tokens=max_tokens,
                    allow_tools=True,
                    allow_skills=True,
                    allow_mcp=True,
                ),
            )
            result = gate.check(req, complexity_level="C3")
            rows.append(
                {
                    "task": task.value,
                    "max_tokens": max_tokens,
                    "budget_tokens": int(max_tokens * 0.25),
                    "allowed_resources": len(result.allowed_resources),
                    "estimated_tokens": result.estimated_context_tokens,
                    "ok": result.ok,
                }
            )
    return rows
