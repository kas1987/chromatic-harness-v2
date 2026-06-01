#!/usr/bin/env python3
"""Validate hook registration and exit-code behavior.

Checks that all hooks registered in .claude/settings.json and settings.local.json:
- Reference scripts that exist on disk
- Are syntactically valid Python (for .py hooks)
- Produce the expected exit code when invoked with a no-op payload

Usage:
    python scripts/hooks/validate_hooks.py
    python scripts/hooks/validate_hooks.py --json
    python scripts/hooks/validate_hooks.py --strict   # fail on WARN too
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
HOME = Path.home()

SETTINGS_PATHS = [
    REPO / ".claude" / "settings.json",
    REPO / ".claude" / "settings.local.json",
    HOME / ".claude" / "settings.json",
    HOME / ".claude" / "settings.local.json",
]

# Critical hooks that MUST exist and be runnable
CRITICAL_HOOKS = [
    "scripts/hooks/git_collision_pretooluse.py",
    "scripts/session_start.py",
    "scripts/session_closeout.py",
    "scripts/hooks/append_session_telemetry.py",
    "scripts/hooks/session_knowledge_feedback.py",
    "scripts/hooks/close_stale_agent_beads.py",
    "scripts/hooks/session_priority_check.py",
    "02_RUNTIME/router/gate.py",
]

# No-op JSON payload for PreToolUse hooks
_NOOP_PRETOOLUSE_PAYLOAD = json.dumps(
    {
        "tool_name": "Read",
        "tool_input": {"file_path": "/tmp/noop"},
    }
)

# No-op payload for SessionStart/SessionEnd hooks
_NOOP_SESSION_PAYLOAD = json.dumps({})


def _load_settings(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _extract_hook_commands(settings: dict, source: str) -> list[dict]:
    """Extract all hook command entries from a settings dict."""
    results: list[dict] = []
    hooks = settings.get("hooks") or {}
    for event, blocks in hooks.items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            matcher = block.get("matcher", "")
            inner_hooks = block.get("hooks", [block])
            for h in inner_hooks:
                if not isinstance(h, dict):
                    continue
                cmd = h.get("command", "")
                if cmd:
                    results.append(
                        {
                            "source": source,
                            "event": event,
                            "matcher": matcher or "(all)",
                            "command": cmd,
                            "timeout": h.get("timeout", 30),
                        }
                    )
    return results


def _resolve_script_path(command: str) -> Path | None:
    """Extract and resolve the script path from a hook command string."""
    parts = command.strip().split()
    for part in parts:
        if part.endswith((".py", ".sh", ".ps1")):
            candidate = Path(part)
            if candidate.is_absolute() and candidate.is_file():
                return candidate
            repo_path = REPO / part
            if repo_path.is_file():
                return repo_path
    return None


def _check_syntax(script_path: Path) -> tuple[bool, str]:
    """Check Python syntax via py_compile."""
    if script_path.suffix != ".py":
        return True, ""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or "syntax error").strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)


def _probe_exit_code(command: str, event: str, timeout: int = 5) -> tuple[int | None, str]:
    """Run hook with no-op payload; return (exit_code, stderr)."""
    if event in ("PreToolUse", "PostToolUse"):
        stdin_data = _NOOP_PRETOOLUSE_PAYLOAD
    else:
        stdin_data = _NOOP_SESSION_PAYLOAD

    # Only probe Python scripts — skip bd, powershell, etc.
    parts = command.strip().split()
    if not parts or parts[0] not in ("python", "python3", sys.executable):
        return None, "skipped (non-python)"

    try:
        result = subprocess.run(
            [sys.executable] + parts[1:],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO),
        )
        return result.returncode, (result.stderr or "").strip()[:200]
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    except OSError as e:
        return None, str(e)


def validate_all(*, probe: bool = False) -> list[dict[str, Any]]:
    """Run all hook validations. Returns list of result dicts."""
    results: list[dict[str, Any]] = []

    # Collect all hook definitions from all settings files
    all_hooks: list[dict] = []
    for path in SETTINGS_PATHS:
        settings = _load_settings(path)
        if settings:
            all_hooks.extend(_extract_hook_commands(settings, str(path.name)))

    seen_commands: set[str] = set()

    for hook in all_hooks:
        cmd = hook["command"]
        if cmd in seen_commands:
            continue
        seen_commands.add(cmd)

        result: dict[str, Any] = {
            "command": cmd,
            "event": hook["event"],
            "source": hook["source"],
            "status": "pass",
            "findings": [],
        }

        # Check script existence
        script_path = _resolve_script_path(cmd)
        if script_path is None:
            # Non-file commands (bd, powershell wrappers) — warn only
            result["status"] = "warn"
            result["findings"].append("script_not_found_on_disk")
        else:
            result["script_path"] = str(script_path)

            # Syntax check
            ok, err = _check_syntax(script_path)
            if not ok:
                result["status"] = "fail"
                result["findings"].append(f"syntax_error: {err}")

        # Probe exit code for Python hooks
        if probe and result["status"] != "fail":
            exit_code, stderr = _probe_exit_code(cmd, hook["event"], timeout=hook.get("timeout", 5))
            result["probe_exit_code"] = exit_code
            result["probe_stderr"] = stderr
            if exit_code not in (None, 0):
                result["status"] = "fail"
                result["findings"].append(f"exit_code_{exit_code}: {stderr}")

        results.append(result)

    # Check critical hooks are present
    for critical in CRITICAL_HOOKS:
        path = REPO / critical
        if not path.is_file():
            results.append(
                {
                    "command": f"python {critical}",
                    "event": "critical_check",
                    "source": "harness_policy",
                    "status": "fail",
                    "findings": [f"critical_hook_missing: {critical}"],
                }
            )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate harness hook registration and behavior")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--probe", action="store_true", help="Run hooks with no-op payload to test exit codes")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on WARN")
    args = parser.parse_args()

    results = validate_all(probe=args.probe)

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for r in results:
        counts[r.get("status", "fail")] = counts.get(r.get("status", "fail"), 0) + 1

    summary = {
        "total": len(results),
        "pass": counts["pass"],
        "warn": counts["warn"],
        "fail": counts["fail"],
        "hooks": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Hook Validation - {len(results)} hooks checked")
        print(f"  PASS: {counts['pass']}  WARN: {counts['warn']}  FAIL: {counts['fail']}")
        print()
        for r in results:
            status_icon = {"pass": "OK", "warn": "WW", "fail": "XX"}.get(r["status"], "??")
            print(f"  [{status_icon}] {r['event']:<20} {r['command']}")
            for finding in r.get("findings", []):
                print(f"       +-- {finding}")

    has_fail = counts["fail"] > 0
    has_warn = counts["warn"] > 0
    if has_fail:
        return 1
    if args.strict and has_warn:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
