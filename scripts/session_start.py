#!/usr/bin/env python3
"""SessionStart hook: handoff, automated pre-session boot, bd prime.

Works for Claude Code (.claude/settings.json) and any runner that invokes
this repo's session_start command. Safe when bd is missing (exit 0).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # retained: the fire-and-forget `bd prime` (console passthrough) stays bare
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

# bd/git output (now decoded as real UTF-8 by run_safe) can contain glyphs like
# ○ ◐ ● that the Windows cp1252 console cannot encode. Make this hook's streams
# UTF-8/replace so printing harness output never raises on the user's terminal.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — older/odd stream objects; best-effort
        pass

_GUARD = _REPO / "scripts" / "session_unified_guard.py"
_HANDOFF = _REPO / ".agents" / "handoffs" / "latest.json"
_OPS = _REPO / "AGENT_OPERATIONS.md"
_MANIFEST = _REPO / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json"
_HEALTH = _REPO / "07_LOGS_AND_AUDIT" / "harness_health" / "latest.json"
_BUDGET_FORECAST = _REPO / "scripts" / "budget_forecast_snapshot.py"
_FORECAST_LATEST = _REPO / "07_LOGS_AND_AUDIT" / "budget" / "forecast_latest.json"
_USAGE_INGEST = _REPO / "scripts" / "usage_ingest.py"
_USAGE_CALIBRATE = _REPO / "scripts" / "usage_calibrate.py"
_USAGE_ROLLUP = _REPO / "scripts" / "usage_rollup.py"
_USAGE_DASHBOARD = _REPO / "scripts" / "usage_dashboard.py"
_TOKEN_GOV_LATEST = _REPO / "07_LOGS_AND_AUDIT" / "token_governance" / "latest.json"
_BASELINE_AUDIT = _REPO / "scripts" / "baseline_audit.py"
_GH_CI_HEALTH = _REPO / "scripts" / "gh_ci_health.py"


def _lean_boot() -> bool:
    """Opt-in leaner pre-session path (A/B). Default off preserves current behavior."""
    return os.environ.get("CHROMATIC_LEAN_BOOT", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _is_fresh(path: Path, *, hours: float = 6.0) -> bool:
    """True if `path` was modified within `hours` (used to skip redundant refreshes)."""
    try:
        import time

        return path.is_file() and (time.time() - path.stat().st_mtime) < hours * 3600
    except OSError:
        return False


def _forecast_line_from_cache() -> str | None:
    """Format the budget line from the cached forecast_latest.json — no recompute.

    The token-governance loop already wrote this file during boot, so re-running
    budget_forecast_snapshot.py is pure duplication. Fail-open → None.
    """
    if not _FORECAST_LATEST.is_file():
        return None
    try:
        import importlib.util

        data = json.loads(_FORECAST_LATEST.read_text(encoding="utf-8"))
        spec = importlib.util.spec_from_file_location("_bfs_fmt", _BUDGET_FORECAST)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod._statusline_line(data)
    except Exception:  # noqa: BLE001 — never break session start
        return None


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
            print(f"  telemetry: session.boot emitted (session {res['session_id'][:8]})")
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
            br = run_safe(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=_REPO,
                timeout=10,
            ).stdout.strip()
            # branch like feat/router-loop-guard -> [router, loop, guard]
            terms = [t for t in re.split(r"[/_-]", br) if len(t) > 2]
        except Exception:
            pass
        top = select_top(n=3, terms=terms)
        if top:
            print("--- Prior learnings (apply where relevant) ---")
            print(format_for_injection(top))
            print()
    except Exception as exc:  # noqa: BLE001
        print(f"  learnings: injection skipped ({exc})", file=sys.stderr)


def _bd_argv(args: list[str]) -> list[str]:
    """Return the resolved argv list for bd, Windows-safe."""
    bd = shutil.which("bd")
    if bd is not None:
        return [bd, *args]
    return ["cmd", "/c", "bd", *args]


def _bd(args: list[str], *, timeout: int = 20) -> tuple[int, str]:
    """Run bd with a Windows-safe PATH fallback (mirrors session_closeout)."""
    r = run_safe(_bd_argv(args), cwd=_REPO, timeout=timeout)
    return r.returncode, (r.stdout or "").strip()


def _inject_ready_queue(limit: int = 8) -> None:
    """Surface the bd ready queue so work is picked from beads, not chat (Gap A).

    Deterministic CLI read injected into SessionStart context; the *judgment*
    (which bead to claim) stays with the agent. Fail-open.
    """
    code, out = _bd(["ready"])
    if code != 0 or not out:
        return
    lines = [ln for ln in out.splitlines() if ln.strip()][:limit]
    if not lines:
        return
    print("--- Ready beads (pick work from here, not chat) ---")
    for ln in lines:
        print(f"  {ln.strip()}")
    print()


def _surface_for_runtime() -> str:
    """Map CHROMATIC_RUNTIME to a baseline surface name (default 'cli')."""
    mapping = {
        "claude": "cli",
        "cli": "cli",
        "cursor": "cursor",
        "vscode": "vscode",
        "app": "app",
    }
    runtime = os.environ.get("CHROMATIC_RUNTIME", "claude").strip().lower()
    return mapping.get(runtime, "cli")


def _call_audit_surface(surface: str) -> dict:
    """Load baseline_audit by path and call audit_surface. Raises on failure (caller catches)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("baseline_audit", _BASELINE_AUDIT)
    if spec is None or spec.loader is None:
        raise ImportError("baseline_audit spec not found")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.audit_surface(surface)  # type: ignore[no-any-return]


def _call_ci_health() -> dict:
    """Load gh_ci_health by path and call check_ci_health. Raises on failure (caller catches)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("gh_ci_health", _GH_CI_HEALTH)
    if spec is None or spec.loader is None:
        raise ImportError("gh_ci_health spec not found")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.check_ci_health()  # type: ignore[no-any-return]


def _emit_baseline_alerts() -> None:
    """Print per-surface baseline drift (warn/over metrics only). Fail-open."""
    try:
        surface = _surface_for_runtime()
        result = _call_audit_surface(surface)
        overall = result.get("overall", "unknown")
        metrics = result.get("metrics", {})

        print("--- Baseline drift ---")
        if overall == "ok":
            print(f"  [ok] {surface} surface within baseline")
        else:
            drifted = [(name, m) for name, m in metrics.items() if m.get("status") in ("warn", "over")]
            if not drifted:
                print(f"  [ok] {surface} surface within baseline")
            else:
                for name, m in drifted:
                    status = m.get("status", "?")
                    value = m.get("value", "?")
                    advice = m.get("advice", "")
                    line = f"  [{status}] {name}={value}"
                    if advice:
                        line += f" — {advice}"
                    print(line)
        print()
    except Exception as exc:  # noqa: BLE001
        print(f"  baseline drift: skipped ({exc})", file=sys.stderr)


def _emit_ci_health() -> None:
    """Print a one-line CI-health warning when status != ok. Fail-open, non-blocking."""
    try:
        import threading

        result: dict = {}
        exc_holder: list[Exception] = []

        def _probe() -> None:
            try:
                result.update(_call_ci_health())
            except Exception as e:  # noqa: BLE001
                exc_holder.append(e)

        t = threading.Thread(target=_probe, daemon=True)
        t.start()
        t.join(timeout=8)

        if exc_holder or not result:
            return  # offline / timeout — skip silently

        status = result.get("status", "ok")
        if status == "ok":
            return

        reasons = result.get("reasons", [])
        reason_str = "; ".join(reasons) if reasons else "CI health degraded"
        print(f"  [CI-{status.upper()}] {reason_str}")
        print()
    except Exception:  # noqa: BLE001
        pass  # never break session start


def _refresh_usage_calibration() -> None:
    """Ingest edge snapshots + recalibrate token caps (fail-open).

    Consumes ~/.claude/usage/snapshots.jsonl into the durable archive + token
    events, then re-derives calibrated_caps.json (and the edge copy the
    statusline reads). Never breaks session start.
    """
    if not (_USAGE_INGEST.is_file() and _USAGE_CALIBRATE.is_file()):
        return
    try:
        run_safe([sys.executable, str(_USAGE_INGEST)], cwd=_REPO, timeout=60)
        proc = run_safe([sys.executable, str(_USAGE_CALIBRATE)], cwd=_REPO, timeout=60)
        if proc.returncode == 0 and proc.stdout.strip():
            first = proc.stdout.strip().splitlines()[0]
            print(f"  usage_calibration: {first}")
        if _USAGE_ROLLUP.is_file():
            rproc = run_safe([sys.executable, str(_USAGE_ROLLUP)], cwd=_REPO, timeout=60)
            if rproc.returncode == 0 and rproc.stdout.strip():
                print(f"  usage_rollup: {rproc.stdout.strip()}")
        if _USAGE_DASHBOARD.is_file():
            run_safe([sys.executable, str(_USAGE_DASHBOARD)], cwd=_REPO, timeout=60)
        print()
    except Exception:  # noqa: BLE001
        pass  # never break session start


def main() -> int:
    print("=== Chromatic Harness session start ===\n")

    cold_start = not _HANDOFF.is_file()
    _emit_boot(cold_start)
    _inject_learnings()
    _inject_ready_queue()

    if _HANDOFF.is_file():
        print("--- Handoff (.agents/handoffs/latest.json) ---")
        print(_HANDOFF.read_text(encoding="utf-8").rstrip())
        print()
    else:
        print("(No handoff file — fresh session)\n")

    print("--- Automated pre-session boot ---")
    runtime = os.environ.get("CHROMATIC_RUNTIME", "claude")
    if _GUARD.is_file():
        guard_cmd = [
            sys.executable,
            str(_GUARD),
            "--surface",
            "cli",
            "--invoked-by",
            runtime,
        ]
        # Lean boot (#2): skip the heavy token-governance loop on the synchronous
        # path when its result is fresh (<6h). The daily scheduler / a forced boot
        # still refreshes it; we just don't re-run it (incl. the slow strict audit)
        # on every interactive session start.
        if _lean_boot() and _is_fresh(_TOKEN_GOV_LATEST):
            guard_cmd.append("--skip-token-loop")
            print("  (lean boot: token-governance loop fresh <6h — skipped)")
        r = run_safe(guard_cmd, cwd=_REPO, timeout=300)
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
            print(f"  checks(pass/warn/fail): {counts.get('pass', 0)}/{counts.get('warn', 0)}/{counts.get('fail', 0)}")
        except (json.JSONDecodeError, OSError):
            print("  readiness_status: unknown")
            print("  readiness_score: n/a")
    else:
        print("  readiness_status: (not written yet)")

    # Budget forecast line (#1): the token-governance loop already wrote
    # forecast_latest.json, so in lean boot we read+format that cache instead of
    # re-running budget_forecast_snapshot.py (pure duplication). Fall back to the
    # recompute if the cache is missing/unreadable.
    printed_forecast = False
    if _lean_boot():
        line = _forecast_line_from_cache()
        if line:
            print(f"  budget_forecast: {line} [cached]")
            printed_forecast = True
    if not printed_forecast and _BUDGET_FORECAST.is_file():
        try:
            proc = run_safe(
                [sys.executable, str(_BUDGET_FORECAST), "--write", "--format", "line"],
                cwd=_REPO,
                timeout=45,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                print(f"  budget_forecast: {proc.stdout.strip()}")
            elif proc.stderr.strip():
                print(f"  budget_forecast: unavailable ({proc.stderr.strip()})")
        except (subprocess.SubprocessError, OSError):
            print("  budget_forecast: unavailable")
    print()

    _refresh_usage_calibration()

    _emit_baseline_alerts()
    _emit_ci_health()

    _bd(["prime"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
