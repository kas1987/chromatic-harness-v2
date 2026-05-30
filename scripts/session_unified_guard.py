#!/usr/bin/env python3
"""Unified cross-surface guard for session automation.

Runs a consistent automation chain for IDE, CLI, and MCP entrypoints:
1) session_boot_automation
2) token_governance_closed_loop

Writes a machine-readable receipt under 07_LOGS_AND_AUDIT/unified_guard.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], timeout: int = 900) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": cmd,
        "exit_code": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def _codegraph_freshness(stale_after_minutes: int = 60) -> dict[str, Any]:
    """Non-blocking check that the codegraph index is not stale.

    Governance gates (complexity_classifier impact fan-out, expansion-gate spine
    check) read codegraph_impact; a stale graph yields wrong blast-radius. This
    is advisory only — it never fails the guard (fail-open, per WARN policy). It
    compares the newest source-file mtime against the codegraph DB mtime, so it
    needs no codegraph CLI on PATH.
    """
    cg_db = REPO / ".codegraph" / "codegraph.db"
    if not cg_db.exists():
        return {
            "name": "codegraph_freshness",
            "ok": True,  # advisory — absence is not a guard failure
            "status": "absent",
            "advice": "codegraph not initialized: run `codegraph init -i .`",
        }

    db_mtime = cg_db.stat().st_mtime
    source_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml"}
    skip_dirs = {
        ".git",
        ".codegraph",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".worktrees",
        "dist",
        "build",
    }
    newest = 0.0
    newest_file = None
    for path in REPO.rglob("*"):
        if path.suffix not in source_exts or not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        m = path.stat().st_mtime
        if m > newest:
            newest = m
            newest_file = path
    lag_minutes = max(0.0, (newest - db_mtime) / 60.0)
    stale = lag_minutes > stale_after_minutes
    rel = str(newest_file.relative_to(REPO)).replace("\\", "/") if newest_file else None
    return {
        "name": "codegraph_freshness",
        "ok": True,  # advisory — never blocks the guard
        "status": "stale" if stale else "fresh",
        "index_lag_minutes": round(lag_minutes, 1),
        "stale_after_minutes": stale_after_minutes,
        "newest_source": rel,
        "advice": (
            "reindex before relying on impact: run `codegraph index .`"
            if stale
            else "index current"
        ),
    }


def _detect_surface(explicit: str) -> str:
    if explicit != "auto":
        return explicit
    if os.environ.get("VSCODE_PID"):
        return "ide"
    if os.environ.get("CHROMATIC_RUNTIME", "").lower() == "mcp":
        return "mcp"
    return "cli"


def _write_receipt(payload: dict[str, Any]) -> Path:
    out_dir = REPO / "07_LOGS_AND_AUDIT" / "unified_guard"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_path = out_dir / f"session_guard_{stamp}.json"
    latest_path = out_dir / "latest.json"

    text = json.dumps(payload, indent=2)
    run_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    return run_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified session automation guard")
    parser.add_argument(
        "--surface", choices=["auto", "ide", "cli", "mcp", "scheduler"], default="auto"
    )
    parser.add_argument(
        "--invoked-by",
        choices=["cursor", "claude", "scheduler", "preflight", "automation"],
        default="automation",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force fresh boot regardless of manifest age",
    )
    parser.add_argument(
        "--full", action="store_true", help="Run full session boot mode"
    )
    parser.add_argument("--skip-boot", action="store_true")
    parser.add_argument("--skip-token-loop", action="store_true")
    parser.add_argument("--skip-codegraph", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not enqueue/drain intake suggestions"
    )
    parser.add_argument("extras", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    ignored = [x for x in args.extras if x.strip() in {".", "./", ".\\"}]
    if ignored:
        print(f"INFO ignored placeholder args: {' '.join(ignored)}")

    surface = _detect_surface(args.surface)
    steps: list[dict[str, Any]] = []

    if not args.skip_boot:
        boot_cmd = [
            sys.executable,
            str(REPO / "scripts" / "session_boot_automation.py"),
            "--invoked-by",
            args.invoked_by,
        ]
        if args.force:
            boot_cmd.append("--force")
        if args.full:
            boot_cmd.append("--full")
        steps.append({"name": "session_boot_automation", **_run(boot_cmd, timeout=900)})

    if not args.skip_token_loop:
        token_cmd = [
            sys.executable,
            str(REPO / "scripts" / "token_governance_closed_loop.py"),
        ]
        if args.dry_run:
            token_cmd.append("--dry-run")
        else:
            token_cmd.extend(["--enqueue-suggestions", "--drain-intake"])
        steps.append(
            {"name": "token_governance_closed_loop", **_run(token_cmd, timeout=900)}
        )

    cg = None
    if not args.skip_codegraph:
        cg = _codegraph_freshness()
        steps.append(cg)  # advisory: cg["ok"] is always True, never fails the gate
        if cg.get("status") == "stale":
            print(
                f"WARN codegraph index stale by {cg.get('index_lag_minutes')}m "
                f"(newest: {cg.get('newest_source')}) — {cg.get('advice')}"
            )

    ok = all(step.get("ok") for step in steps)
    payload = {
        "ok": ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "surface": surface,
        "invoked_by": args.invoked_by,
        "codegraph_status": cg.get("status") if cg else "skipped",
        "steps": steps,
    }
    run_path = _write_receipt(payload)
    payload["artifact"] = str(run_path.relative_to(REPO)).replace("\\", "/")
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
