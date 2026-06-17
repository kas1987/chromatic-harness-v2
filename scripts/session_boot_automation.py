#!/usr/bin/env python3
"""Hands-off pre-session boot: doc guard, MCP audit, manifest, intake validation.

Designed for Cursor sessionStart hooks, Claude SessionStart, and Task Scheduler.
Skips rework when a fresh manifest already exists (default 6h).

Usage:
    python scripts/session_boot_automation.py --invoked-by cursor
    python scripts/session_boot_automation.py --invoked-by scheduler --force
    python scripts/session_boot_automation.py --full   # includes context report --log
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"

sys.path.insert(0, str(_SCRIPTS))
from common_harness import run_safe  # noqa: E402


def _repo_root() -> Path:
    override = os.environ.get("CHROMATIC_REPO")
    return Path(override).resolve() if override else _REPO


def _manifest_path() -> Path:
    override = os.environ.get("CHROMATIC_PRE_SESSION_DIR")
    if override:
        return Path(override).resolve() / "latest.json"
    return _repo_root() / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json"


def _parse_ts(iso: str) -> datetime | None:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def manifest_is_fresh(max_age_hours: float) -> bool:
    manifest = _manifest_path()
    if not manifest.is_file():
        return False

    # BOOT_CONTEXT.md must exist; if absent the context is stale/unbuilt.
    boot_ctx = _repo_root() / ".agents" / "context" / "BOOT_CONTEXT.md"
    if not boot_ctx.is_file():
        return False

    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        ts = _parse_ts(data.get("generated_at", ""))
        if not ts:
            return False
        age = datetime.now(timezone.utc) - ts.astimezone(timezone.utc)
        if age.total_seconds() >= max_age_hours * 3600:
            return False

        # If any MCP descriptor file is newer than the manifest, MCPs may have
        # changed since the last audit — force a re-run.
        mcps_path = (data.get("mcp_audit") or {}).get("mcps_path")
        if mcps_path:
            manifest_mtime = manifest.stat().st_mtime
            mcps_dir = Path(mcps_path)
            if mcps_dir.is_dir():
                for f in mcps_dir.rglob("*.json"):
                    if f.stat().st_mtime > manifest_mtime:
                        return False

        return True
    except (json.JSONDecodeError, OSError):
        return False


def _read_audit_risk(root: Path) -> str:
    audit_path = root / ".agents" / "context" / "context_trim_audit.json"
    if not audit_path.is_file():
        return "unknown"
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
        return str(data.get("risk_level", "unknown"))
    except (json.JSONDecodeError, OSError):
        return "unknown"


def _load_branch_policy() -> dict:
    cfg = _repo_root() / "config" / "ci" / "branch_governance.yaml"
    if not cfg.is_file():
        return {}
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _run_context_pipeline(*, force: bool) -> int:
    """Trim audit; rebuild + bootstrap when risk is orange/red or --force."""
    root = _repo_root()
    if (
        _run(
            [str(_SCRIPTS / "context_trim_audit.py"), "--root", str(root)],
            timeout=90,
            quiet=True,
        )
        != 0
    ):
        return 1

    risk = _read_audit_risk(root)
    if risk not in ("red", "orange") and not force:
        return 0

    mode = "hard" if risk == "red" else "soft"
    steps = [
        [str(_SCRIPTS / "context_rebuild.py"), "--root", str(root), "--mode", mode],
        [str(_SCRIPTS / "new_session_bootstrap.py"), "--root", str(root)],
    ]
    for step in steps:
        if _run(step, timeout=120, quiet=True) != 0:
            return 1
    return 0


def _run(
    args: list[str],
    *,
    timeout: int = 90,
    quiet: bool = False,
) -> int:
    cmd = [sys.executable, *args]
    r = run_safe(cmd, cwd=_REPO, timeout=timeout)
    if r.returncode == 124:
        print(f"TIMEOUT: {' '.join(args)}", file=sys.stderr)
        return 124
    # run_safe always captures; when not quiet, surface the output (buffered)
    # to preserve the prior streaming-visible behavior for callers.
    if not quiet:
        if r.stdout:
            sys.stdout.write(r.stdout)
        if r.stderr:
            sys.stderr.write(r.stderr)
    return r.returncode


def run_boot(
    *,
    invoked_by: str,
    force: bool = False,
    full: bool = False,
    max_age_hours: float,
    mcps_path: str | None,
) -> int:
    errors: list[str] = []
    notices: list[str] = []
    branch_policy = _load_branch_policy()
    startup_awareness = branch_policy.get("startup_awareness") if isinstance(branch_policy.get("startup_awareness"), dict) else {}
    autonomy_cfg = branch_policy.get("autonomy") if isinstance(branch_policy.get("autonomy"), dict) else {}

    if _run([str(_SCRIPTS / "check_agent_operations.py")], timeout=30, quiet=True) != 0:
        errors.append("check_agent_operations failed")

    fresh = manifest_is_fresh(max_age_hours) and not force
    if fresh:
        print(
            f"Pre-session manifest fresh (<{max_age_hours}h); skipping heavy boot steps.",
            file=sys.stderr,
        )
    else:
        mcp_args = [
            str(_SCRIPTS / "audit_mcp_context.py"),
            "--profile",
            "harness_dev",
            "--strict",
            "--json",
        ]
        if mcps_path:
            mcp_args.extend(["--mcps-path", mcps_path])
        if _run(mcp_args, timeout=120, quiet=True) != 0:
            errors.append("audit_mcp_context failed")

        manifest_args = [
            str(_SCRIPTS / "pre_session_manifest.py"),
            "--write",
            "--invoked-by",
            invoked_by,
        ]
        if mcps_path:
            manifest_args.extend(["--mcps-path", mcps_path])
        if _run(manifest_args, timeout=60, quiet=True) != 0:
            errors.append("pre_session_manifest failed")

    if _run([str(_SCRIPTS / "validate_intake_loop.py")], timeout=60, quiet=True) != 0:
        errors.append("validate_intake_loop failed")

    run_branch_audit = bool(startup_awareness.get("run_branch_audit", True))
    branch_audit_script = _SCRIPTS / "branch_governance_audit.py"
    if run_branch_audit and branch_audit_script.is_file():
        if _run([str(branch_audit_script), "--write"], timeout=120, quiet=True) != 0:
            notices.append("branch_governance_audit failed")

    env_mode = os.environ.get("CHROMATIC_BRANCH_SELF_HEAL_MODE")
    branch_mode = (env_mode if env_mode is not None else str(autonomy_cfg.get("mode") or "off")).strip().lower()
    if branch_mode in {"local", "subagent", "cloud"}:
        env_apply = os.environ.get("CHROMATIC_BRANCH_SELF_HEAL_APPLY")
        if env_apply is None:
            branch_apply = bool(autonomy_cfg.get("apply_mutations", False))
        else:
            branch_apply = env_apply in {"1", "true", "yes", "on"}
        autonomy_args = [
            str(_SCRIPTS / "branch_governance_autonomy.py"),
            "--mode",
            branch_mode,
            "--write",
        ]
        if branch_apply:
            autonomy_args.append("--apply")
        if _run(autonomy_args, timeout=240, quiet=True) != 0:
            notices.append(f"branch_governance_autonomy failed ({branch_mode})")

    if not fresh or force:
        if _run_context_pipeline(force=force) != 0:
            errors.append("context_rebuild_pipeline failed")

    if full and not fresh:
        ctx_args = [
            str(_SCRIPTS / "session_context_report.py"),
            "--log",
            "--invoked-by",
            invoked_by,
            "--manifest",
        ]
        if mcps_path:
            ctx_args.extend(["--mcps-path", mcps_path])
        if _run(ctx_args, timeout=180, quiet=True) != 0:
            errors.append("session_context_report failed")

    manifest = _manifest_path()
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            mcp_audit = data.get("mcp_audit") or {}
            if mcp_audit.get("over_warn_threshold"):
                errors.append("mcp_token_budget_exceeded: disable heavy MCPs (see CURSOR_CONTEXT_HYGIENE.md)")
            generated_at = data.get("generated_at", "")
            manifest_age_h: float | None = None
            ts = _parse_ts(generated_at)
            if ts:
                manifest_age_h = round(
                    (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 3600,
                    2,
                )
            summary = {
                "generated_at": generated_at,
                "manifest_age_hours": manifest_age_h,
                "branch": data.get("branch"),
                "context_tier": data.get("context_tier"),
                "mcp_tokens": mcp_audit.get("estimated_tokens_if_enabled"),
                "mcp_over_budget": mcp_audit.get("over_warn_threshold", False),
                "pack_version": data.get("pack_version"),
                "invoked_by": invoked_by,
                "boot_mode": "fresh_skip" if fresh else ("full" if full else "fast"),
            }
            bg_path = _repo_root() / "07_LOGS_AND_AUDIT" / "ci" / "branch_governance_latest.json"
            if bg_path.is_file():
                try:
                    bg = json.loads(bg_path.read_text(encoding="utf-8"))
                    counts = bg.get("counts") or {}
                    summary["branch_governance"] = {
                        "local_total": counts.get("local_total", 0),
                        "remote_total": counts.get("remote_total", 0),
                        "local_stale": counts.get("local_stale", 0),
                        "remote_stale": counts.get("remote_stale", 0),
                        "violations": len(bg.get("violations") or []),
                    }
                except (json.JSONDecodeError, OSError):
                    pass
            if notices:
                summary["notices"] = notices
            print(json.dumps(summary, indent=2))
        except (json.JSONDecodeError, OSError):
            pass
    else:
        errors.append("manifest missing after boot")

    if notices:
        print("Session boot notices:", ", ".join(notices), file=sys.stderr)

    if errors:
        print("Session boot completed with errors:", ", ".join(errors), file=sys.stderr)
        return 1

    try:
        runtime = _repo_root() / "02_RUNTIME"
        if str(runtime) not in sys.path:
            sys.path.insert(0, str(runtime))
        from activity.log import log_activity  # noqa: E402

        boot_summary = {
            "invoked_by": invoked_by,
            "boot_mode": "fresh_skip" if fresh else ("full" if full else "fast"),
            "errors": errors,
        }
        log_activity(
            _repo_root(),
            event_type="session.boot",
            lane="agent",
            decision="ok",
            summary=json.dumps(boot_summary)[:500],
            agent_role="session_boot",
            lock_owner=os.environ.get("CHROMATIC_SESSION_ID", "").strip(),
        )
    except OSError:
        pass

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Automated pre-session boot")
    parser.add_argument(
        "--invoked-by",
        default=os.environ.get("CHROMATIC_RUNTIME", "automation"),
        choices=["cursor", "claude", "scheduler", "preflight", "automation"],
    )
    parser.add_argument("--force", action="store_true", help="Ignore manifest freshness")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include session_context_report --log (slower)",
    )
    parser.add_argument("--mcps-path", help="Override MCP descriptors path")
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=float(os.environ.get("CHROMATIC_BOOT_MAX_AGE_HOURS", "6")),
        help="Skip heavy steps if manifest is newer than this",
    )
    args = parser.parse_args()

    fast_default = os.environ.get("CHROMATIC_BOOT_FAST", "1") != "0"
    full = args.full or os.environ.get("CHROMATIC_BOOT_FULL", "0") == "1"
    if fast_default and not args.full:
        full = False

    return run_boot(
        invoked_by=args.invoked_by,
        force=args.force,
        full=full,
        max_age_hours=args.max_age_hours,
        mcps_path=args.mcps_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
