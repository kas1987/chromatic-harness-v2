#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SEVERITIES = {"info", "low", "medium", "high", "critical"}
EVENT_TYPES = {
    "info",
    "error",
    "warning",
    "incident",
    "collision",
    "learning",
    "fix",
    "status_update",
    "command_result",
}
CATEGORIES = {
    "tool_failure",
    "file_collision",
    "test_failure",
    "dependency_error",
    "context_drift",
    "scope_breach",
    "secret_exposure",
    "loop_behavior",
    "model_misroute",
    "playbook_gap",
    "git_state",
    "command_failure",
    "manual_note",
    "validation_failure",
    "unknown",
}
STATUSES = {
    "open",
    "routed",
    "queued",
    "active",
    "resolved",
    "ignored",
    "failed",
    "incident_opened",
    "collision_opened",
}
SURFACES = {
    "terminal",
    "vscode",
    "cursor",
    "antigravity",
    "claude",
    "codex",
    "chatgpt",
    "ci",
    "git_hook",
    "agent",
    "manual",
    "unknown",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def event_id():
    return "evt_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]


def repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in [cur] + list(cur.parents):
        if (p / ".git").exists() or (p / "00_META").exists() or (p / ".chromatic").exists():
            return p
    return cur


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, record: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _kill_tree(proc):
    """Terminate proc and ALL descendants (Windows taskkill /T, POSIX killpg).

    A plain proc.kill() reaps only the immediate child; a grandchild that
    inherited the stdout pipe (e.g. git/bd/dolt subprocesses) keeps it open and
    wedges the next caller. See chromatic-harness-v2 bpc5 / j2r0.
    """
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=10)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass
    finally:
        try:
            proc.kill()
        except Exception:
            pass


def run_safe(cmd, cwd: Path | None = None, *, timeout: int = 30, stdin: str | None = None):
    """subprocess.run replacement that reaps the whole process tree on timeout.

    Returns a CompletedProcess-like object exposing .returncode/.stdout/.stderr.
    On Windows, subprocess.run(timeout=) only kills the immediate child, so a
    hung git/bd/dolt call orphans lock-holding grandchildren — this kills the
    tree instead. returncode is 124 on timeout, 1 on spawn/other error.
    """

    class R:
        pass

    kwargs: dict = {
        "text": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "stdin": subprocess.PIPE if stdin is not None else None,
    }
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    if sys.platform != "win32":
        kwargs["start_new_session"] = True  # own group so killpg reaps descendants
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception as e:
        r = R()
        r.returncode = 1
        r.stdout = ""
        r.stderr = str(e)
        return r
    try:
        out, err = proc.communicate(input=stdin, timeout=timeout)
        r = R()
        r.returncode = proc.returncode
        r.stdout = out or ""
        r.stderr = err or ""
        return r
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except Exception:
            out, err = "", ""
        r = R()
        r.returncode = 124
        r.stdout = out or ""
        r.stderr = f"timeout after {timeout}s: {' '.join(map(str, cmd))}"
        return r
    except Exception as e:
        _kill_tree(proc)
        r = R()
        r.returncode = 1
        r.stdout = ""
        r.stderr = str(e)
        return r


def run_git(args, cwd: Path):
    return run_safe(["git"] + args, cwd=cwd, timeout=15)


def git_state(cwd: Path):
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    commit = run_git(["rev-parse", "HEAD"], cwd)
    status = run_git(["status", "--porcelain"], cwd)
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else "unknown",
        "commit": commit.stdout.strip() if commit.returncode == 0 else "unknown",
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
        "status_porcelain": status.stdout.splitlines() if status.returncode == 0 else [],
    }


def priority_for(severity: str, category: str) -> str:
    if severity == "critical" or category in {"secret_exposure"}:
        return "P0"
    if severity == "high" or category in {"file_collision", "scope_breach", "loop_behavior"}:
        return "P1"
    if severity == "medium":
        return "P2"
    return "P3"


def validate_record(record: dict) -> list[str]:
    errors = []
    for k in ["event_id", "timestamp", "repo", "source", "event_type", "severity", "category", "status"]:
        if k not in record or record[k] in (None, ""):
            errors.append(f"missing required field: {k}")
    if not isinstance(record.get("source"), dict):
        errors.append("source must be object")
    else:
        surf = record["source"].get("surface")
        if not surf:
            errors.append("missing required field: source.surface")
        elif surf not in SURFACES:
            errors.append(f"invalid source.surface: {surf}")
    if record.get("severity") not in SEVERITIES:
        errors.append(f"invalid severity: {record.get('severity')}")
    if record.get("event_type") not in EVENT_TYPES:
        errors.append(f"invalid event_type: {record.get('event_type')}")
    if record.get("category") not in CATEGORIES:
        errors.append(f"invalid category: {record.get('category')}")
    if record.get("status") not in STATUSES:
        errors.append(f"invalid status: {record.get('status')}")
    if "files_touched" in record and not isinstance(record["files_touched"], list):
        errors.append("files_touched must be array")
    if "exit_code" in record and record["exit_code"] is not None and not isinstance(record["exit_code"], int):
        errors.append("exit_code must be integer")
    return errors
