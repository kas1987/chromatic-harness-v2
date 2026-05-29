#!/usr/bin/env python3
"""Unified pre-session context report for Cursor, Claude, and Harness.

Measures what we can from disk (rules, MCP descriptors, CRG, handoffs).
Cursor UI MCP toggle state is not visible — descriptor bulk is an upper bound.

Usage:
    python scripts/session_context_report.py
    python scripts/session_context_report.py --json
    python scripts/session_context_report.py --log
    python scripts/session_context_report.py --invoked-by cursor --log
    python scripts/session_context_report.py --runtime harness
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from pre_session_common import (  # noqa: E402
    REPO,
    RUNTIME_DOCS,
    crg_estimates,
    load_profile,
    load_settings,
    measure_rule_files,
    read_handoff,
    resolve_mcps_path,
    scan_mcps,
    scan_skills_catalog,
    tok,
)

LOG_DIR = REPO / ".agents" / "logs"
LOG_FILE = LOG_DIR / "session-context.jsonl"


def _mcp_section(mcps_path: Path, profile_name: str) -> dict:
    profile_doc = load_profile()
    disable_daily = set(profile_doc.get("disable_for_daily_dev", []))
    tool_count, total_chars, per_server = scan_mcps(mcps_path)
    per_server_tok = {k: tok(v) for k, v in per_server.items()}
    heavy = {k: v for k, v in per_server_tok.items() if k in disable_daily}
    return {
        "mcps_path": str(mcps_path),
        "profile": profile_name,
        "tool_count": tool_count,
        "estimated_tokens_if_enabled": tok(total_chars),
        "heavy_servers_on_disk": heavy,
        "heavy_tokens_on_disk": sum(heavy.values()),
        "per_server_tokens": dict(
            sorted(per_server_tok.items(), key=lambda x: -x[1])
        ),
        "warn_threshold": int(profile_doc.get("warn_total_tokens", 12000)),
    }


def build_report(
    *,
    invoked_by: str,
    mcps_path: Path,
    profile_name: str,
) -> dict:
    settings = load_settings()
    skills_path = settings.get("cursor_skills_path")
    skills = scan_skills_catalog(Path(skills_path) if skills_path else None)
    rules = measure_rule_files()
    rules_tok = sum(r["estimated_tokens"] for r in rules if r.get("auto_injected"))
    rules_tok_all = sum(r["estimated_tokens"] for r in rules)
    mcp = _mcp_section(mcps_path, profile_name)
    handoff = read_handoff()
    crg = crg_estimates()
    crg_coding_128k = next(
        r
        for r in crg
        if r["task"] == "coding" and r["max_tokens"] == 128_000
    )

    execution_packet = REPO / ".agents" / "rpi" / "execution-packet.json"
    rpi = {
        "present": execution_packet.is_file(),
        "path": str(execution_packet.relative_to(REPO)),
    }

    warnings: list[str] = []
    if mcp["estimated_tokens_if_enabled"] > mcp["warn_threshold"]:
        warnings.append(
            f"MCP descriptors ~{mcp['estimated_tokens_if_enabled']:,} tok exceed "
            f"warn threshold {mcp['warn_threshold']:,} — disable in Cursor Settings > MCP"
        )
    if not crg_coding_128k["ok"]:
        warnings.append("CRG coding task blocked at 128k (unexpected)")

    cursor_est = rules_tok + mcp["estimated_tokens_if_enabled"]
    # Skills catalog in Cursor is usually names-only; use 25% of full SKILL.md as blurbs guess
    skills_blurb_guess = skills["estimated_tokens"] // 4 if skills["skill_files"] else 0
    cursor_est_upper = cursor_est + skills_blurb_guess + 2000  # native tools guess

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "invoked_by": invoked_by,
        "repo": str(REPO),
        "summary": {
            "repo_rules_tokens_auto": rules_tok,
            "repo_rules_tokens_all_measured": rules_tok_all,
            "mcp_tokens_if_enabled": mcp["estimated_tokens_if_enabled"],
            "skills_full_files_tokens": skills["estimated_tokens"],
            "skills_catalog_guess_tokens": skills_blurb_guess,
            "harness_crg_coding_c3_tokens": crg_coding_128k["estimated_tokens"],
            "cursor_estimated_lower_bound": cursor_est,
            "cursor_estimated_upper_bound": cursor_est_upper,
            "warnings": warnings,
        },
        "cursor": {
            **RUNTIME_DOCS["cursor"],
            "mcp": mcp,
            "rules": rules,
            "skills": skills,
            "estimated_instruction_tokens": {
                "lower_bound": cursor_est,
                "upper_bound": cursor_est_upper,
            },
        },
        "claude": {
            **RUNTIME_DOCS["claude"],
            "hooks_configured": (REPO / ".claude" / "settings.json").is_file(),
            "handoff": handoff,
            "shares_cursor_mcp_and_rules": True,
        },
        "harness": {
            **RUNTIME_DOCS["harness"],
            "crg_estimates": crg,
            "handoff": handoff,
            "rpi_execution_packet": rpi,
            "router_context_max_tokens": int(
                os.environ.get("ROUTER_CONTEXT_MAX_TOKENS", "128000")
            ),
        },
    }


def render_text(report: dict) -> str:
    s = report["summary"]
    lines = [
        "=" * 60,
        "SESSION CONTEXT REPORT",
        f"  generated: {report['generated_at']}",
        f"  invoked_by: {report['invoked_by']}",
        "=" * 60,
        "",
        "SUMMARY (estimated instruction-context tokens)",
        f"  Repo rules (auto-injected):     ~{s['repo_rules_tokens_auto']:,}",
        f"  MCP (if all enabled on disk):   ~{s['mcp_tokens_if_enabled']:,}",
        f"  Skills catalog (guess):         ~{s['skills_catalog_guess_tokens']:,}",
        f"  Cursor likely range:            ~{s['cursor_estimated_lower_bound']:,}"
        f" - {s['cursor_estimated_upper_bound']:,}",
        f"  Harness CRG (coding C3):        ~{s['harness_crg_coding_c3_tokens']:,}",
        "",
    ]
    for w in s.get("warnings", []):
        lines.append(f"  WARNING: {w}")
    if s.get("warnings"):
        lines.append("")

    def _section(title: str, key: str) -> None:
        block = report.get(key, {})
        lines.append("-" * 60)
        lines.append(f"{title}: {block.get('label', key)}")
        lines.append("-" * 60)
        for item in block.get("injects", []):
            lines.append(f"  loads: {item}")
        for hook in block.get("hooks", []):
            lines.append(f"  hook:  {hook}")
        lines.append("")

    _section("CURSOR", "cursor")
    mcp = report["cursor"]["mcp"]
    lines.append(f"  MCP tools on disk: {mcp['tool_count']}")
    lines.append(f"  MCP est. tokens:   ~{mcp['estimated_tokens_if_enabled']:,}")
    lines.append("  Top servers:")
    for srv, t in list(mcp["per_server_tokens"].items())[:6]:
        flag = " [disable for daily]" if srv in mcp["heavy_servers_on_disk"] else ""
        lines.append(f"    {srv:40} ~{t:,}{flag}")
    lines.append("")

    _section("CLAUDE", "claude")
    h = report["claude"]["handoff"]
    lines.append(f"  handoff present: {h.get('present')}")
    if h.get("present"):
        lines.append(f"  mission: {h.get('data', {}).get('mission_id', '?')}")
        lines.append(f"  branch:  {h.get('data', {}).get('branch', '?')}")
    lines.append("")

    _section("HARNESS", "harness")
    lines.append(
        f"  ROUTER_CONTEXT_MAX_TOKENS: {report['harness']['router_context_max_tokens']:,}"
    )
    lines.append("  CRG coding @ 128k:")
    for row in report["harness"]["crg_estimates"]:
        if row["task"] == "coding" and row["max_tokens"] == 128_000:
            lines.append(
                f"    allowed={row['allowed_resources']} "
                f"est={row['estimated_tokens']} ok={row['ok']}"
            )
    lines.append("")
    lines.append(f"Log append: python scripts/session_context_report.py --log")
    lines.append(f"JSON:       python scripts/session_context_report.py --json")
    lines.append("=" * 60)
    return "\n".join(lines)


def append_log(report: dict) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "logged_at": report["generated_at"],
        "invoked_by": report["invoked_by"],
        "summary": report["summary"],
        "cursor_mcp_tokens": report["cursor"]["mcp"]["estimated_tokens_if_enabled"],
        "warnings": report["summary"]["warnings"],
    }
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return LOG_FILE


def main() -> int:
    parser = argparse.ArgumentParser(description="Session context report")
    parser.add_argument("--mcps-path", help="Cursor project mcps folder")
    parser.add_argument("--profile", default="harness_dev")
    parser.add_argument(
        "--invoked-by",
        default=os.environ.get("CHROMATIC_RUNTIME", "manual"),
        choices=["manual", "cursor", "claude", "harness"],
        help="Who triggered this report (for logs)",
    )
    parser.add_argument(
        "--runtime",
        choices=["all", "cursor", "claude", "harness"],
        default="all",
        help="Filter printed sections",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--log",
        action="store_true",
        help=f"Append summary to {LOG_FILE.relative_to(REPO)}",
    )
    args = parser.parse_args()

    mcps_path = resolve_mcps_path(args.mcps_path)
    if not mcps_path.is_dir():
        print(f"ERROR: mcps path not found: {mcps_path}", file=sys.stderr)
        return 1

    report = build_report(
        invoked_by=args.invoked_by,
        mcps_path=mcps_path,
        profile_name=args.profile,
    )

    if args.runtime != "all":
        filtered = {
            k: v
            for k, v in report.items()
            if k in ("generated_at", "invoked_by", "repo", "summary", args.runtime)
        }
        if args.json:
            print(json.dumps(filtered, indent=2))
        else:
            print(render_text({**report, **{args.runtime: report[args.runtime]}}))
    elif args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report))

    if args.log:
        path = append_log(report)
        print(f"\nAppended log: {path.relative_to(REPO)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
