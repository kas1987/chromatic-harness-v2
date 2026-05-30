#!/usr/bin/env python3
"""SessionStart hook: handoff, automated pre-session boot, bd prime.

Works for Claude Code (.claude/settings.json) and any runner that invokes
this repo's session_start command. Safe when bd is missing (exit 0).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_GUARD = _REPO / "scripts" / "session_unified_guard.py"
_HANDOFF = _REPO / ".agents" / "handoffs" / "latest.json"
_OPS = _REPO / "AGENT_OPERATIONS.md"
_MANIFEST = _REPO / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json"
_HEALTH = _REPO / "07_LOGS_AND_AUDIT" / "harness_health" / "latest.json"
_BUDGET_FORECAST = _REPO / "scripts" / "budget_forecast_snapshot.py"
_INJECTED_LEARNINGS = _REPO / ".agents" / "context" / "injected_learnings.json"
_LEARNING_USAGE_LOG = _REPO / ".agents" / "metrics" / "learning_usage.jsonl"


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


def _inject_learnings() -> None:
    """Surface top relevant prior learnings so a fresh session isn't blind.

    The SessionStart hook's stdout becomes session context, so printing here
    IS injection for Claude Code. Fail-open.
    """
    try:
        sys.path.insert(0, str(_REPO / "02_RUNTIME"))
        from knowledge.select_learnings import format_for_injection, select_top

        terms: list[str] = []
        try:
            br = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=_REPO,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout.strip()
            # branch like feat/router-loop-guard -> [router, loop, guard]
            terms = [t for t in re.split(r"[/_-]", br) if len(t) > 2]
        except Exception:
            pass
        usage_log = _LEARNING_USAGE_LOG if _LEARNING_USAGE_LOG.exists() else None
        top = select_top(n=3, terms=terms, usage_log=usage_log)
        if top:
            print("--- Prior learnings (apply where relevant) ---")
            print(format_for_injection(top))
            print()
            # Record injected names so session_closeout can emit applied_success/failure
            try:
                _INJECTED_LEARNINGS.parent.mkdir(parents=True, exist_ok=True)
                _INJECTED_LEARNINGS.write_text(
                    json.dumps(
                        {
                            "injected_at": __import__("datetime")
                            .datetime.now(__import__("datetime").timezone.utc)
                            .isoformat(),
                            "terms": terms,
                            "learnings": [
                                {
                                    "name": Path(lc.get("path", "")).stem
                                    or lc.get("title", ""),
                                    "path": lc.get("path", ""),
                                    "title": lc.get("title", ""),
                                }
                                for lc in top
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001
        print(f"  learnings: injection skipped ({exc})", file=sys.stderr)


def main() -> int:
    print("=== Chromatic Harness session start ===\n")

    cold_start = not _HANDOFF.is_file()
    _emit_boot(cold_start)
    _inject_learnings()

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

    if _BUDGET_FORECAST.is_file():
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(_BUDGET_FORECAST),
                    "--write",
                    "--format",
                    "line",
                ],
                cwd=_REPO,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                print(f"  budget_forecast: {proc.stdout.strip()}")
                try:
                    latest = (
                        _REPO / "07_LOGS_AND_AUDIT" / "budget" / "forecast_latest.json"
                    )
                    snap = (
                        json.loads(latest.read_text(encoding="utf-8"))
                        if latest.is_file()
                        else {}
                    )
                    channels = (
                        snap.get("channels")
                        if isinstance(snap.get("channels"), dict)
                        else {}
                    )
                    ranked: list[tuple[str, float, float, float]] = []
                    for name, row in channels.items():
                        if not isinstance(row, dict):
                            continue
                        gap = float(row.get("forecast_gap_to_target_usd", 0.0) or 0.0)
                        current = float(row.get("weekly_spent_usd", 0.0) or 0.0)
                        cap = float(row.get("cap_weekly_usd", 0.0) or 0.0)
                        ranked.append((str(name), gap, current, cap))
                    ranked.sort(key=lambda item: item[1], reverse=True)
                    top = ranked[:2]
                    if top:
                        summary = " | ".join(
                            f"{name} ${current:.2f}/${cap:.2f} gap:${gap:.2f}"
                            for name, gap, current, cap in top
                        )
                        print(f"  budget_channels: {summary}")
                except Exception:
                    pass
            elif proc.stderr.strip():
                print(f"  budget_forecast: unavailable ({proc.stderr.strip()})")
        except (subprocess.SubprocessError, OSError):
            print("  budget_forecast: unavailable")
    print()

    try:
        subprocess.run(["bd", "prime"], cwd=_REPO, check=False)
    except FileNotFoundError:
        print("bd not on PATH — install beads or skip", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
