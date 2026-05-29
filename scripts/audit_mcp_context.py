#!/usr/bin/env python3
"""Audit MCP descriptor bulk vs harness profiles.

Measures JSON under Cursor's project mcps folder (what *can* be injected).
Does not know Cursor UI toggle state — run after changing MCP settings and
re-open the project if counts look stale.

Usage:
    python scripts/audit_mcp_context.py
    python scripts/audit_mcp_context.py --profile harness_dev
    python scripts/audit_mcp_context.py --mcps-path /path/to/mcps --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PROFILE_PATH = _REPO / "config" / "pre_session" / "mcp.profile.yaml"


def _load_settings() -> dict:
    for name in ("settings.local.yaml", "settings.example.yaml"):
        path = _REPO / "config" / "pre_session" / name
        if path.exists():
            try:
                import yaml  # type: ignore[import-untyped]

                return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass
    return {}


def _load_profile() -> dict:
    if not _PROFILE_PATH.exists():
        return {}
    import yaml  # type: ignore[import-untyped]

    return yaml.safe_load(_PROFILE_PATH.read_text(encoding="utf-8")) or {}


def scan_mcps(mcps_path: Path) -> tuple[int, dict[str, int]]:
    per_server: dict[str, int] = {}
    for f in mcps_path.rglob("tools/*.json"):
        chars = len(f.read_text(encoding="utf-8"))
        server = f.parts[-3] if len(f.parts) >= 3 else "unknown"
        per_server[server] = per_server.get(server, 0) + chars
    total = sum(per_server.values())
    return total, per_server


def resolve_mcps_path(cli_path: str | None) -> Path:
    if cli_path:
        return Path(cli_path)
    settings = _load_settings()
    if settings.get("mcp_descriptors_path"):
        return Path(settings["mcp_descriptors_path"])
    return _REPO / "tests" / "fixtures" / "mcp_minimal"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit MCP pre-session token bulk")
    parser.add_argument("--mcps-path", help="Cursor project mcps folder")
    parser.add_argument(
        "--profile",
        default="harness_dev",
        help="Profile from config/pre_session/mcp.profile.yaml",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if heavy servers present or over warn threshold",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    mcps_path = resolve_mcps_path(args.mcps_path)
    if not mcps_path.is_dir():
        print(f"ERROR: mcps path not found: {mcps_path}", file=sys.stderr)
        print("Set config/pre_session/settings.local.yaml mcp_descriptors_path", file=sys.stderr)
        return 1

    profile_doc = _load_profile()
    profiles = profile_doc.get("profiles", {})
    prof = profiles.get(args.profile, {})
    disable_daily = set(profile_doc.get("disable_for_daily_dev", []))
    recommended = set(prof.get("recommended_enabled", []))

    total_chars, per_server = scan_mcps(mcps_path)
    total_tok = total_chars // 4
    warn_tok = int(profile_doc.get("warn_total_tokens", 12000))

    heavy_present = [s for s in per_server if s in disable_daily]
    heavy_tok = sum(per_server.get(s, 0) for s in heavy_present) // 4
    optional_tok = total_tok - heavy_tok

    report = {
        "mcps_path": str(mcps_path),
        "profile": args.profile,
        "total_tools": sum(1 for _ in mcps_path.rglob("tools/*.json")),
        "total_tokens_est": total_tok,
        "heavy_servers_on_disk": heavy_present,
        "heavy_tokens_est": heavy_tok,
        "warn_threshold_tokens": warn_tok,
        "recommended_enabled": sorted(recommended),
    }

    if args.json:
        report["per_server_tokens"] = {k: v // 4 for k, v in sorted(per_server.items(), key=lambda x: -x[1])}
        print(json.dumps(report, indent=2))
    else:
        print(f"MCP path: {mcps_path}")
        print(f"Profile:  {args.profile} — {prof.get('description', '').strip()}")
        print(f"Tools:    {report['total_tools']}")
        print(f"Estimate: ~{total_tok:,} tokens (descriptor JSON / 4)")
        print(f"Threshold: warn > {warn_tok:,} tok")
        print()
        print("Per server (est. tokens):")
        for server, chars in sorted(per_server.items(), key=lambda x: -x[1]):
            tok = chars // 4
            flag = ""
            if server in disable_daily:
                flag = " [DISABLE for daily dev]"
            elif server in recommended:
                flag = " [recommended for profile]"
            print(f"  {server:42} {tok:6,}{flag}")
        print()
        if heavy_present:
            print(f"Heavy servers still on disk ({len(heavy_present)}): ~{heavy_tok:,} tok")
            print("  -> Disable in Cursor: Settings > MCP (or uninstall plugin)")
            print("  -> See docs/CURSOR_CONTEXT_HYGIENE.md")
        if total_tok > warn_tok:
            print(f"WARNING: over {warn_tok:,} token estimate — trim MCPs before long sessions")
        else:
            print("OK: within recommended pre-session budget")

    failed = False
    if args.strict and total_tok > warn_tok:
        failed = True
    if args.strict and heavy_present and args.profile == "harness_dev":
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
