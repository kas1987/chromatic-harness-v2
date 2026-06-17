#!/usr/bin/env python3
"""Branch governance enforcement for local branches.

Default mode is dry-run. Use --apply to mutate local branches.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "config" / "ci" / "branch_governance.yaml"
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "ci"
OUT_PATH = ARTIFACT_DIR / "branch_governance_enforce_latest.json"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _load_config() -> dict[str, Any]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _age_days(ts: str) -> float:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return round((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 86400.0, 2)


def _category(name: str) -> str:
    if name.startswith("temp/"):
        return "temp"
    if name.startswith("session/"):
        return "session"
    if name.startswith("worktree-") or name.startswith("worktree/"):
        return "worktree"
    if name.startswith("chore/"):
        return "chore"
    if name.startswith("fix/"):
        return "fix"
    if name.startswith("feat/"):
        return "feature"
    return "default"


def _threshold(config: dict[str, Any], cat: str) -> float:
    table = (config.get("staleness_days") or {}) if isinstance(config.get("staleness_days"), dict) else {}
    val = table.get(cat, table.get("default", 14))
    try:
        return float(val)
    except (TypeError, ValueError):
        return 14.0


def _protected(config: dict[str, Any], branch: str, current: str) -> bool:
    if branch == current:
        return True
    if branch in set(config.get("protected_branches") or []):
        return True
    for p in config.get("protected_prefixes") or []:
        if isinstance(p, str) and branch.startswith(p):
            return True
    return False


def _local_rows() -> list[dict[str, str]]:
    fmt = "%(refname:short)|%(upstream:track)|%(committerdate:iso8601)"
    code, out = _run(["git", "for-each-ref", "refs/heads", f"--format={fmt}"])
    if code != 0:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        rows.append({"name": parts[0].strip(), "track": parts[1].strip(), "last": parts[2].strip()})
    return rows


def _merged(default_branch: str) -> set[str]:
    code, out = _run(["git", "branch", "--merged", f"origin/{default_branch}"])
    if code != 0:
        return set()
    return {ln.replace("*", "").strip() for ln in out.splitlines() if ln.strip()}


def _delete(branch: str, force: bool, apply: bool) -> dict[str, Any]:
    cmd = ["git", "branch", "-D" if force else "-d", "--", branch]
    if not apply:
        return {"branch": branch, "action": "dry_run", "command": " ".join(cmd), "ok": True}
    code, out = _run(cmd)
    return {"branch": branch, "action": "delete", "command": " ".join(cmd), "ok": code == 0, "output": out.strip()}


def main() -> int:
    ap = argparse.ArgumentParser(description="Enforce local branch governance")
    ap.add_argument("--apply", action="store_true", help="Apply deletions")
    ap.add_argument("--write", action="store_true", help="Write latest artifact")
    args = ap.parse_args()

    config = _load_config()
    default_branch = str(config.get("default_branch") or "main")

    _run(["git", "fetch", "--all", "--prune"])
    _, cur_out = _run(["git", "branch", "--show-current"])
    current = cur_out.strip()

    merged = _merged(default_branch)
    rows = _local_rows()

    local_prefixes = [p for p in (config.get("auto_delete") or {}).get("local_prefixes", []) if isinstance(p, str)]
    require_gone = bool((config.get("auto_delete") or {}).get("require_gone_upstream_for_force_delete", True))

    results: list[dict[str, Any]] = []

    for row in rows:
        b = row["name"]
        if _protected(config, b, current):
            continue

        if b in merged and b != default_branch:
            results.append(_delete(b, force=False, apply=args.apply))
            continue

        gone = "[gone]" in row.get("track", "")
        if gone:
            results.append(_delete(b, force=True, apply=args.apply))
            continue

        age = _age_days(row.get("last", ""))
        cat = _category(b)
        stale = age > _threshold(config, cat)
        prefix_match = any(b.startswith(p) for p in local_prefixes)

        if stale and prefix_match:
            if require_gone:
                continue
            results.append(_delete(b, force=True, apply=args.apply))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "current_branch": current,
        "results": results,
        "deleted_count": len([r for r in results if r.get("ok")]),
        "failed_count": len([r for r in results if not r.get("ok")]),
    }

    if args.write:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
