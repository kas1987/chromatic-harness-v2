#!/usr/bin/env python3
"""Branch governance audit: branch counts, staleness, and policy violations."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "config" / "ci" / "branch_governance.yaml"
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "ci"
JSON_OUT = ARTIFACT_DIR / "branch_governance_latest.json"
MD_OUT = ARTIFACT_DIR / "branch_governance_latest.md"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _load_config() -> dict[str, Any]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("branch governance config must be a mapping")
    return data


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_days(ts: str) -> float:
    dt = _parse_iso(ts)
    if dt is None:
        return 0.0
    return round((_now() - dt.astimezone(timezone.utc)).total_seconds() / 86400.0, 2)


def _category(name: str) -> str:
    if name.startswith("feat/"):
        return "feature"
    if name.startswith("fix/"):
        return "fix"
    if name.startswith("chore/"):
        return "chore"
    if name.startswith("docs/"):
        return "docs"
    if name.startswith("temp/"):
        return "temp"
    if name.startswith("session/"):
        return "session"
    if name.startswith("worktree-") or name.startswith("worktree/"):
        return "worktree"
    if name.startswith("dependabot/"):
        return "dependabot"
    return "default"


def _threshold(config: dict[str, Any], cat: str) -> float:
    table = (config.get("staleness_days") or {}) if isinstance(config.get("staleness_days"), dict) else {}
    val = table.get(cat, table.get("default", 14))
    try:
        return float(val)
    except (TypeError, ValueError):
        return 14.0


def _is_protected(config: dict[str, Any], branch: str) -> bool:
    exact = set(config.get("protected_branches") or [])
    if branch in exact:
        return True
    for p in config.get("protected_prefixes") or []:
        if isinstance(p, str) and branch.startswith(p):
            return True
    return False


def _open_pr_heads() -> set[str]:
    if shutil.which("gh") is None:
        return set()
    code, out = _run(["gh", "pr", "list", "--state", "open", "--json", "headRefName", "--limit", "300"])
    if code != 0:
        return set()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return set()
    heads = set()
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                head = row.get("headRefName")
                if isinstance(head, str) and head.strip():
                    heads.add(head.strip())
    return heads


def _local_rows() -> list[dict[str, Any]]:
    fmt = "%(refname:short)|%(upstream:short)|%(upstream:track)|%(committerdate:iso8601)"
    code, out = _run(["git", "for-each-ref", "refs/heads", f"--format={fmt}"])
    if code != 0:
        return []

    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        rows.append(
            {
                "name": parts[0].strip(),
                "upstream": parts[1].strip(),
                "upstream_track": parts[2].strip(),
                "last_commit_at": parts[3].strip(),
            }
        )
    return rows


def _remote_rows() -> list[dict[str, Any]]:
    fmt = "%(refname:short)|%(committerdate:iso8601)"
    code, out = _run(["git", "for-each-ref", "refs/remotes/origin", f"--format={fmt}"])
    if code != 0:
        return []

    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("|", 1)
        if len(parts) != 2:
            continue
        ref = parts[0].strip()
        if ref == "origin/HEAD":
            continue
        name = ref[len("origin/") :] if ref.startswith("origin/") else ref
        rows.append(
            {
                "name": name,
                "last_commit_at": parts[1].strip(),
            }
        )
    return rows


def _merged_local(default_branch: str) -> set[str]:
    code, out = _run(["git", "branch", "--merged", f"origin/{default_branch}"])
    if code != 0:
        return set()
    names = set()
    for line in out.splitlines():
        b = line.replace("*", "").strip()
        if b:
            names.add(b)
    return names


def build_report(config: dict[str, Any]) -> dict[str, Any]:
    default_branch = str(config.get("default_branch") or "main")

    _run(["git", "fetch", "--all", "--prune"])

    local = _local_rows()
    remote = _remote_rows()
    merged = _merged_local(default_branch)
    open_heads = _open_pr_heads()

    local_stale: list[dict[str, Any]] = []
    remote_stale: list[dict[str, Any]] = []
    gone_upstream: list[str] = []
    merged_not_default: list[str] = []

    for row in local:
        name = row["name"]
        if name == default_branch:
            continue

        age = _age_days(row["last_commit_at"])
        cat = _category(name)
        threshold = _threshold(config, cat)
        protected = _is_protected(config, name)

        row["age_days"] = age
        row["category"] = cat
        row["stale_threshold_days"] = threshold

        if "[gone]" in row.get("upstream_track", ""):
            gone_upstream.append(name)
        if name in merged and not protected:
            merged_not_default.append(name)
        if not protected and age > threshold:
            local_stale.append(row)

    for row in remote:
        name = row["name"]
        if name == default_branch:
            continue

        age = _age_days(row["last_commit_at"])
        cat = _category(name)
        threshold = _threshold(config, cat)
        protected = _is_protected(config, name)
        has_open_pr = name in open_heads

        row["age_days"] = age
        row["category"] = cat
        row["stale_threshold_days"] = threshold
        row["has_open_pr"] = has_open_pr

        if not protected and not has_open_pr and age > threshold:
            remote_stale.append(row)

    local_cap = int(((config.get("branch_limits") or {}).get("local") or {}).get("max_total") or 35)
    remote_cap = int(((config.get("branch_limits") or {}).get("remote") or {}).get("max_total") or 80)

    violations = []
    if len(local) > local_cap:
        violations.append(f"local branch cap exceeded: {len(local)} > {local_cap}")
    if len(remote) > remote_cap:
        violations.append(f"remote branch cap exceeded: {len(remote)} > {remote_cap}")

    return {
        "generated_at": _now().isoformat(),
        "default_branch": default_branch,
        "caps": {
            "local_max_total": local_cap,
            "remote_max_total": remote_cap,
        },
        "counts": {
            "local_total": len(local),
            "remote_total": len(remote),
            "local_stale": len(local_stale),
            "remote_stale": len(remote_stale),
            "local_gone_upstream": len(gone_upstream),
            "local_merged_candidates": len(merged_not_default),
        },
        "violations": violations,
        "local_stale": local_stale,
        "remote_stale": remote_stale,
        "local_gone_upstream": sorted(gone_upstream),
        "local_merged_candidates": sorted(merged_not_default),
    }


def _write_markdown(report: dict[str, Any]) -> str:
    counts = report.get("counts", {})
    lines = [
        "# Branch Governance Audit",
        "",
        f"Generated: {report.get('generated_at')}",
        "",
        "## Counts",
        "",
        f"- local_total: {counts.get('local_total', 0)}",
        f"- remote_total: {counts.get('remote_total', 0)}",
        f"- local_stale: {counts.get('local_stale', 0)}",
        f"- remote_stale: {counts.get('remote_stale', 0)}",
        f"- local_gone_upstream: {counts.get('local_gone_upstream', 0)}",
        f"- local_merged_candidates: {counts.get('local_merged_candidates', 0)}",
        "",
        "## Violations",
        "",
    ]

    violations = report.get("violations", [])
    if violations:
        for v in violations:
            lines.append(f"- {v}")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Branch governance audit")
    ap.add_argument("--write", action="store_true", help="Write latest JSON/MD artifacts")
    ap.add_argument(
        "--enforce-hard-cap",
        action="store_true",
        help="Exit 1 when branch cap violations are present",
    )
    args = ap.parse_args()

    config = _load_config()
    report = build_report(config)

    if args.write:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        MD_OUT.write_text(_write_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    if args.enforce_hard_cap and report.get("violations"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
