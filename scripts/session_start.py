#!/usr/bin/env python3
"""SessionStart hook: handoff, automated pre-session boot, bd prime.

Works for Claude Code (.claude/settings.json) and any runner that invokes
this repo's session_start command. Safe when bd is missing (exit 0).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_GUARD = _REPO / "scripts" / "session_unified_guard.py"
_HANDOFF = _REPO / ".agents" / "handoffs" / "latest.json"
_OPS = _REPO / "AGENT_OPERATIONS.md"
_MANIFEST = _REPO / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json"
_HEALTH = _REPO / "07_LOGS_AND_AUDIT" / "harness_health" / "latest.json"


def _emit_boot(cold_start: bool) -> None:
    """Emit session.boot telemetry immediately — closes the cold-start gap.

    Fail-open: never let telemetry break session start.
    """
    try:
        sys.path.insert(0, str(_REPO / "02_RUNTIME"))
        from audit.session_events import emit_session_boot

        runtime = os.environ.get("CHROMATIC_RUNTIME", "claude")
        res = emit_session_boot(_REPO, cold_start=cold_start, invoked_by=runtime)
        if res.get("ok"):
            print(
                f"  telemetry: session.boot emitted (session {res['session_id'][:8]})"
            )
    except Exception as exc:  # noqa: BLE001
        print(f"  telemetry: session.boot skipped ({exc})", file=sys.stderr)


def main() -> int:
    print("=== Chromatic Harness session start ===\n")

    cold_start = not _HANDOFF.is_file()
    _emit_boot(cold_start)

    if _HANDOFF.is_file():
        print("--- Handoff (.agents/handoffs/latest.json) ---")
        print(_HANDOFF.read_text(encoding="utf-8").rstrip())
        print()
    else:
        print("(No handoff file — fresh session)\n")

    print("--- Automated pre-session boot ---")
    runtime = os.environ.get("CHROMATIC_RUNTIME", "claude")
    if _GUARD.is_file():
        r = subprocess.run(
            [
                sys.executable,
                str(_GUARD),
                "--surface",
                "cli",
                "--invoked-by",
                runtime,
            ],
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode != 0 and r.stderr:
            print(r.stderr.strip(), file=sys.stderr)
    else:
        print("  (session_unified_guard.py not found — skip)")

    print(f"\n--- Operations: {_OPS.relative_to(_REPO)} ---")
    if _MANIFEST.is_file():
        try:
            m = json.loads(_MANIFEST.read_text(encoding="utf-8"))
            print(f"  Manifest: {_MANIFEST.relative_to(_REPO)}")
            print(f"  generated_at: {m.get('generated_at')}")
            print(f"  branch: {m.get('branch')}")
            tok = m.get("mcp_audit", {}).get("estimated_tokens_if_enabled")
            if tok is not None:
                print(f"  MCP est. tokens: {tok:,}")
        except (json.JSONDecodeError, OSError):
            print(f"  Manifest: {_MANIFEST.relative_to(_REPO)}")
    else:
        print("  Manifest: (not written yet)")

    if _HEALTH.is_file():
        try:
            h = json.loads(_HEALTH.read_text(encoding="utf-8"))
            print(f"  readiness_status: {h.get('overall_status', 'unknown')}")
            print(f"  readiness_score: {h.get('readiness_score', 0)}/100")
            counts = h.get("counts") or {}
            print(
                "  checks(pass/warn/fail): "
                f"{counts.get('pass', 0)}/{counts.get('warn', 0)}/{counts.get('fail', 0)}"
            )
        except (json.JSONDecodeError, OSError):
            print("  readiness_status: unknown")
            print("  readiness_score: n/a")
    else:
        print("  readiness_status: (not written yet)")
    print()

    try:
        subprocess.run(["bd", "prime"], cwd=_REPO, check=False)
    except FileNotFoundError:
        print("bd not on PATH — install beads or skip", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
