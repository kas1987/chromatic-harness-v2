#!/usr/bin/env python3
"""Validate Wiki EPIC-0001 ↔ Harness bead sync map.

Usage:
  python scripts/check_wiki_harness_sync.py
  python scripts/check_wiki_harness_sync.py --json
  python scripts/check_wiki_harness_sync.py --github
  python scripts/check_wiki_harness_sync.py --strict
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SYNC_PATH = REPO / "config" / "wiki_harness_sync.yaml"
ISSUES_JSONL = REPO / ".beads" / "issues.jsonl"


def _load_bead_statuses() -> dict[str, str]:
    statuses: dict[str, str] = {}
    if not ISSUES_JSONL.is_file():
        return statuses
    for line in ISSUES_JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("_type") == "issue" and row.get("id"):
            statuses[row["id"]] = row.get("status", "unknown")
    return statuses


def _github_issue_states(repo: str) -> dict[int, str]:
    try:
        proc = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "100", "--json", "number,state"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return {}
    if proc.returncode != 0:
        return {}
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return {}
    return {int(r["number"]): str(r.get("state", "")).lower() for r in rows}


def _collect_bead_ids(data: dict) -> set[str]:
    ids: set[str] = set()
    for row in data.get("route_tasks", []):
        bid = row.get("harness_bead")
        if bid:
            ids.add(bid)
    for row in data.get("wiki_tasks", []):
        for bid in row.get("harness_beads", []) or []:
            ids.add(bid)
    return ids


def run(*, github: bool, strict: bool) -> dict:
    if not SYNC_PATH.is_file():
        raise FileNotFoundError(f"missing {SYNC_PATH.relative_to(REPO)}")

    data = yaml.safe_load(SYNC_PATH.read_text(encoding="utf-8")) or {}
    statuses = _load_bead_statuses()
    gh_states = _github_issue_states(data.get("wiki_repo", "")) if github else {}

    errors: list[str] = []
    route_rows: list[dict] = []
    wiki_rows: list[dict] = []

    for row in data.get("route_tasks", []):
        bead = row.get("harness_bead", "")
        expected = row.get("harness_status_expected", "")
        actual = statuses.get(bead, "missing")
        ok = actual == expected if expected else bead in statuses
        if not ok:
            errors.append(f"{row.get('route')}: {bead} expected {expected}, got {actual}")
        route_rows.append(
            {
                "route": row.get("route"),
                "harness_bead": bead,
                "expected": expected,
                "actual": actual,
                "ok": ok,
            }
        )

    for row in data.get("wiki_tasks", []):
        wk = row.get("wk", "")
        if not re.match(r"WK-0\d{2}", wk):
            errors.append(f"invalid wk id: {wk}")
            continue
        beads = row.get("harness_beads", []) or []
        bead_status = {b: statuses.get(b, "missing") for b in beads}
        gh_num = row.get("github_issue")
        gh_state = gh_states.get(int(gh_num)) if gh_num is not None and gh_states else None
        missing = [b for b, s in bead_status.items() if s == "missing"]
        if missing:
            errors.append(f"{wk}: missing harness beads in export: {', '.join(missing)}")
        wiki_rows.append(
            {
                "wk": wk,
                "github_issue": gh_num,
                "github_state": gh_state,
                "harness_beads": bead_status,
                "route_refs": row.get("route_refs", []),
                "ok": not missing,
            }
        )

    # Ensure WK-002..WK-020 present
    wk_ids = {r.get("wk") for r in data.get("wiki_tasks", [])}
    for n in range(2, 21):
        label = f"WK-{n:03d}"
        if label not in wk_ids:
            errors.append(f"missing wiki task entry: {label}")

    report = {
        "sync_config": str(SYNC_PATH.relative_to(REPO)),
        "beads_loaded": len(statuses),
        "route_checks": route_rows,
        "wiki_checks": wiki_rows,
        "errors": errors,
        "ok": not errors,
    }
    if strict and errors:
        raise SystemExit(1)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Wiki ↔ Harness sync map")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--github", action="store_true", help="Fetch Wiki issue states via gh")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on drift")
    args = parser.parse_args()

    report = run(github=args.github, strict=False)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Wiki harness sync: {'OK' if report['ok'] else 'DRIFT'}")
        print(f"  beads in export: {report['beads_loaded']}")
        print(f"  route tasks: {len(report['route_checks'])}")
        print(f"  wiki tasks WK-002..020: {len(report['wiki_checks'])}")
        for err in report["errors"]:
            print(f"  - {err}")

    if args.strict and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
