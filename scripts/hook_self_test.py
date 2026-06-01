#!/usr/bin/env python3
"""Hook self-test runner — standalone validation for harness hooks.

Validates hook registration, script existence, syntax, and basic exit-code
behavior. Outputs JSON suitable for the harness health dashboard.

Usage:
    python scripts/hook_self_test.py
    python scripts/hook_self_test.py --probe       # also run hooks with no-op payload
    python scripts/hook_self_test.py --json        # machine-readable output
    python scripts/hook_self_test.py --strict      # non-zero exit on WARN
    python scripts/hook_self_test.py --ci          # CI mode: JSON + strict
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()

# Settings files to scan for hook registrations
SETTINGS_PATHS = [
    REPO / ".claude" / "settings.json",
    REPO / ".claude" / "settings.local.json",
    HOME / ".claude" / "settings.json",
    HOME / ".claude" / "settings.local.json",
]

# Critical hooks required by harness policy — any absence is a FAIL
CRITICAL_HOOKS = {
    "scripts/hooks/git_collision_pretooluse.py": "PreToolUse gate — blocks unsafe git push",
    "scripts/session_start.py": "SessionStart — boot manifest + handoff",
    "scripts/session_closeout.py": "SessionEnd — handoff + telemetry",
    "scripts/hooks/append_session_telemetry.py": "SessionEnd — append telemetry",
    "scripts/hooks/session_knowledge_feedback.py": "SessionEnd — knowledge feedback",
    "scripts/hooks/close_stale_agent_beads.py": "SessionEnd — stale bead cleanup",
    "scripts/hooks/session_priority_check.py": "SessionStart — priority check",
    "02_RUNTIME/router/gate.py": "PreToolUse Agent gate",
}

# No-op payloads per event type
_PAYLOADS = {
    "PreToolUse": json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/noop"}}),
    "PostToolUse": json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/noop"}, "output": ""}),
    "default": json.dumps({}),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _extract_commands(settings: dict, source: str) -> list[dict]:
    """Flatten all hook entries from a settings dict."""
    out: list[dict] = []
    for event, blocks in (settings.get("hooks") or {}).items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            matcher = block.get("matcher", "")
            for h in block.get("hooks", [block]):
                if isinstance(h, dict) and h.get("command"):
                    out.append(
                        {
                            "source": source,
                            "event": event,
                            "matcher": matcher or "(all)",
                            "command": h["command"],
                            "timeout": h.get("timeout", 30),
                        }
                    )
    return out


def _resolve_path(command: str) -> Path | None:
    """Return the resolved Path of the script referenced in command, or None."""
    for token in command.strip().split():
        if token.endswith((".py", ".sh", ".ps1")):
            for base in (Path(token), REPO / token):
                try:
                    if base.is_file():
                        return base.resolve()
                except OSError:
                    pass
    return None


def _syntax_ok(path: Path) -> tuple[bool, str]:
    if path.suffix != ".py":
        return True, ""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.returncode == 0, (r.stderr or "").strip()[:300]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def _probe(command: str, event: str, timeout: int) -> tuple[int | None, str]:
    """Run hook with no-op payload; return (exit_code, stderr_snippet)."""
    parts = command.strip().split()
    if not parts or parts[0] not in ("python", "python3", sys.executable):
        return None, "skipped"
    payload = _PAYLOADS.get(event, _PAYLOADS["default"])
    try:
        r = subprocess.run(
            [sys.executable] + parts[1:],
            input=payload,
            capture_output=True,
            text=True,
            timeout=min(timeout, 10),
            cwd=str(REPO),
        )
        return r.returncode, (r.stderr or "").strip()[:200]
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------


def run_self_test(*, probe: bool = False) -> dict[str, Any]:
    started_at = time.time()
    hook_results: list[dict] = []
    seen: set[str] = set()

    # Gather all hooks from all settings files
    raw_hooks: list[dict] = []
    settings_found: list[str] = []
    for path in SETTINGS_PATHS:
        data = _load_json(path)
        if data:
            settings_found.append(str(path))
            raw_hooks.extend(_extract_commands(data, path.name))

    for hook in raw_hooks:
        cmd = hook["command"]
        if cmd in seen:
            continue
        seen.add(cmd)

        entry: dict[str, Any] = {
            "command": cmd,
            "event": hook["event"],
            "source": hook["source"],
            "status": "pass",
            "findings": [],
        }

        script_path = _resolve_path(cmd)
        if script_path is None:
            entry["status"] = "warn"
            entry["findings"].append("script_file_not_found")
        else:
            entry["script_path"] = str(
                script_path.relative_to(REPO) if script_path.is_relative_to(REPO) else script_path
            )
            ok, err = _syntax_ok(script_path)
            if not ok:
                entry["status"] = "fail"
                entry["findings"].append(f"syntax_error: {err}")
            elif probe:
                code, stderr = _probe(cmd, hook["event"], hook.get("timeout", 30))
                entry["probe_exit_code"] = code
                if code not in (None, 0):
                    entry["status"] = "fail"
                    entry["findings"].append(f"probe_exit_{code}: {stderr}")

        hook_results.append(entry)

    # Check critical hooks
    critical_results: list[dict] = []
    for rel_path, description in CRITICAL_HOOKS.items():
        exists = (REPO / rel_path).is_file()
        critical_results.append(
            {
                "hook": rel_path,
                "description": description,
                "exists": exists,
                "status": "pass" if exists else "fail",
            }
        )
        if not exists:
            # Also add to hook_results for unified counting
            hook_results.append(
                {
                    "command": f"python {rel_path}",
                    "event": "critical_policy_check",
                    "source": "harness_policy",
                    "status": "fail",
                    "findings": [f"critical_hook_missing: {rel_path}"],
                }
            )

    # Tally
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for r in hook_results:
        s = r.get("status", "fail")
        counts[s] = counts.get(s, 0) + 1

    critical_ok = all(c["status"] == "pass" for c in critical_results)
    overall = "pass" if counts["fail"] == 0 and critical_ok else "fail"
    if overall == "pass" and counts["warn"] > 0:
        overall = "warn"

    return {
        "harness_component": "hook_self_test",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_s": round(time.time() - started_at, 2),
        "overall": overall,
        "summary": {
            "total_hooks": len(hook_results),
            "pass": counts["pass"],
            "warn": counts["warn"],
            "fail": counts["fail"],
            "settings_files_scanned": len(settings_found),
        },
        "critical_hooks": critical_results,
        "hook_results": hook_results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Harness hook self-test — validates registration, existence, syntax, and exit-code behavior"
    )
    parser.add_argument(
        "--probe", action="store_true", help="Run each Python hook with a no-op payload to verify exit code"
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output (dashboard integration)")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on WARN as well as FAIL")
    parser.add_argument("--ci", action="store_true", help="Shorthand for --json --strict --probe")
    args = parser.parse_args()

    if args.ci:
        args.json = True
        args.strict = True
        args.probe = True

    report = run_self_test(probe=args.probe)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        overall = report["overall"].upper()
        s = report["summary"]
        print(f"Harness Hook Self-Test - {overall}")
        print(f"  Hooks checked : {s['total_hooks']}")
        print(f"  Pass          : {s['pass']}")
        print(f"  Warn          : {s['warn']}")
        print(f"  Fail          : {s['fail']}")
        print(f"  Settings files: {s['settings_files_scanned']}")
        print()

        # Critical hooks
        print("Critical hooks:")
        for c in report["critical_hooks"]:
            icon = "OK" if c["exists"] else "XX"
            print(f"  [{icon}] {c['hook']}")
            if not c["exists"]:
                print(f"       +-- MISSING -- {c['description']}")
        print()

        # Per-hook detail (non-pass only, unless verbose would be requested)
        non_pass = [r for r in report["hook_results"] if r["status"] != "pass"]
        if non_pass:
            print(f"Issues ({len(non_pass)}):")
            for r in non_pass:
                icon = "WW" if r["status"] == "warn" else "XX"
                print(f"  [{icon}] [{r['event']}] {r['command']}")
                for f in r.get("findings", []):
                    print(f"       +-- {f}")
        else:
            print("All hooks passed.")

    overall = report["overall"]
    if overall == "fail":
        return 1
    if args.strict and overall == "warn":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
