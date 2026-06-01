#!/usr/bin/env python3
"""Skill inventory — generates a report of all installed skills, their paths,
invocation frequency (from chronicle events), and deprecation candidates.

Usage:
    python scripts/skill_inventory.py
    python scripts/skill_inventory.py --json        # machine-readable (dashboard)
    python scripts/skill_inventory.py --unused      # show only unused skills
    python scripts/skill_inventory.py --deprecation-candidates  # unused > N days
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()

# Canonical skill search roots (in priority order)
SKILL_ROOTS = [
    REPO / ".claude" / "skills",
    HOME / ".claude" / "skills",
    HOME / ".agents" / "skills",
    REPO / ".claude" / "plugins",
    HOME / ".claude" / "plugins",
]

# Chronicle events file — source of invocation frequency data
CHRONICLE_PATH = REPO / ".agents" / "chronicle" / "events.jsonl"

# A skill is "stale" if not invoked within this many days
STALE_THRESHOLD_DAYS = 30

# A skill is a "deprecation candidate" if stale AND invocation count is low
DEPRECATION_INVOCATION_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------


def _discover_skills(roots: list[Path]) -> list[dict[str, Any]]:
    """Walk skill roots and return one dict per skill."""
    skills: dict[str, dict[str, Any]] = {}  # name → dict

    for root in roots:
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            name = entry.name
            if name.startswith(".") or name.startswith("_"):
                continue

            # Skills can be directories (with skill.md / README.md / *.md)
            # or symlinks pointing elsewhere, or direct .md files
            skill_path: Path | None = None
            skill_type = "unknown"

            if entry.is_symlink():
                target = entry.resolve()
                skill_path = entry
                skill_type = "symlink"
                resolved = str(target)
            elif entry.is_dir():
                skill_path = entry
                skill_type = "directory"
                resolved = str(entry)
            elif entry.is_file() and entry.suffix in (".md", ".yaml", ".yml", ".py"):
                skill_path = entry
                skill_type = "file"
                name = entry.stem
                resolved = str(entry)
            else:
                continue

            if name in skills:
                # Already found from a higher-priority root — record alternate path
                skills[name].setdefault("alternate_paths", []).append(str(skill_path))
                continue

            # Find primary doc (skill.md, SKILL.md, README.md, call.md, *.md)
            doc_path: str | None = None
            if entry.is_dir():
                for candidate in ("skill.md", "SKILL.md", "README.md", "call.md"):
                    p = entry / candidate
                    if p.is_file():
                        doc_path = str(p)
                        break
                if doc_path is None:
                    mds = sorted(entry.glob("*.md"))
                    if mds:
                        doc_path = str(mds[0])

            mtime: float | None = None
            try:
                mtime = skill_path.stat().st_mtime if skill_path else None
            except OSError:
                pass

            skills[name] = {
                "name": name,
                "path": str(skill_path),
                "resolved": resolved,
                "type": skill_type,
                "root": str(root),
                "doc_path": doc_path,
                "mtime": mtime,
                "mtime_iso": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime)) if mtime else None),
            }

    return list(skills.values())


# ---------------------------------------------------------------------------
# Chronicle analysis
# ---------------------------------------------------------------------------


def _load_chronicle() -> list[dict[str, Any]]:
    """Load events from chronicle JSONL. Fail-safe — returns [] on any error."""
    if not CHRONICLE_PATH.is_file():
        return []
    events: list[dict[str, Any]] = []
    try:
        for line in CHRONICLE_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                pass
    except OSError:
        pass
    return events


def _extract_skill_invocations(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return {skill_name: {count, last_used_ts, last_used_iso}} from events."""
    usage: dict[str, dict[str, Any]] = {}

    for ev in events:
        # Chronicle events may record skill invocations in various fields
        skill_name: str | None = None
        ts: str | None = ev.get("timestamp")

        # Direct skill_name field
        if ev.get("skill_name"):
            skill_name = str(ev["skill_name"])
        # skill_invoked event
        elif ev.get("event") in ("skill_invoked", "skill_start", "skill_end"):
            skill_name = str(ev.get("skill") or ev.get("name") or "")
        # Generic event with skill key
        elif "skill" in ev:
            skill_name = str(ev["skill"])
        # Slash-command style: /skill-name
        elif ev.get("command", "").startswith("/"):
            skill_name = ev["command"].lstrip("/").split()[0]

        if not skill_name:
            continue

        # Parse timestamp
        ts_epoch: float | None = None
        if ts:
            try:
                import datetime

                ts_epoch = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except (ValueError, ImportError):
                pass

        if skill_name not in usage:
            usage[skill_name] = {"count": 0, "last_used_ts": None, "last_used_iso": None}

        usage[skill_name]["count"] += 1
        if ts_epoch and (usage[skill_name]["last_used_ts"] is None or ts_epoch > usage[skill_name]["last_used_ts"]):
            usage[skill_name]["last_used_ts"] = ts_epoch
            usage[skill_name]["last_used_iso"] = ts

    return usage


# ---------------------------------------------------------------------------
# Enrichment + deprecation scoring
# ---------------------------------------------------------------------------


def _enrich(
    skills: list[dict[str, Any]],
    usage: dict[str, dict[str, Any]],
    now: float,
) -> list[dict[str, Any]]:
    """Merge usage data into skill records and compute deprecation flags."""
    for skill in skills:
        name = skill["name"]
        inv = usage.get(name, {})

        skill["invocation_count"] = inv.get("count", 0)
        skill["last_used_iso"] = inv.get("last_used_iso")
        last_ts = inv.get("last_used_ts")

        days_since: float | None = None
        if last_ts:
            days_since = round((now - last_ts) / 86400, 1)
        skill["days_since_last_use"] = days_since

        # Deprecation candidate scoring
        stale = days_since is None or days_since > STALE_THRESHOLD_DAYS
        low_usage = skill["invocation_count"] < DEPRECATION_INVOCATION_THRESHOLD
        skill["deprecation_candidate"] = stale and low_usage
        skill["stale"] = stale

    return skills


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_inventory(*, roots: list[Path] | None = None) -> dict[str, Any]:
    now = time.time()
    roots = roots or SKILL_ROOTS

    skills = _discover_skills(roots)
    events = _load_chronicle()
    usage = _extract_skill_invocations(events)
    skills = _enrich(skills, usage, now)

    # Sort: deprecation candidates first, then by name
    skills.sort(key=lambda s: (not s["deprecation_candidate"], s["name"]))

    total = len(skills)
    used = sum(1 for s in skills if s["invocation_count"] > 0)
    stale = sum(1 for s in skills if s["stale"])
    candidates = sum(1 for s in skills if s["deprecation_candidate"])

    return {
        "harness_component": "skill_inventory",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "chronicle_events_analyzed": len(events),
        "summary": {
            "total_skills": total,
            "used_skills": used,
            "never_used": total - used,
            "stale_skills": stale,
            "deprecation_candidates": candidates,
        },
        "roots_scanned": [str(r) for r in roots],
        "skills": skills,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Skill inventory — list installed skills, usage, and deprecation candidates"
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output (dashboard integration)")
    parser.add_argument("--unused", action="store_true", help="Show only never-used skills")
    parser.add_argument(
        "--deprecation-candidates", action="store_true", help="Show only deprecation candidates (stale + low usage)"
    )
    args = parser.parse_args()

    report = generate_inventory()
    skills = report["skills"]

    if args.unused:
        skills = [s for s in skills if s["invocation_count"] == 0]
    elif args.deprecation_candidates:
        skills = [s for s in skills if s["deprecation_candidate"]]

    if args.json:
        report["skills"] = skills
        print(json.dumps(report, indent=2))
        return 0

    # Human-readable output
    s = report["summary"]
    print(f"Skill Inventory - {report['timestamp']}")
    print(f"  Total skills       : {s['total_skills']}")
    print(f"  Used (any time)    : {s['used_skills']}")
    print(f"  Never used         : {s['never_used']}")
    print(f"  Stale (>{STALE_THRESHOLD_DAYS}d)      : {s['stale_skills']}")
    print(f"  Deprecation cands  : {s['deprecation_candidates']}")
    print(f"  Chronicle events   : {report['chronicle_events_analyzed']}")
    print()

    if not skills:
        print("No skills match the filter.")
        return 0

    # Column header
    print(f"  {'NAME':<30} {'INVOCATIONS':>11}  {'LAST USED':<22}  {'STALE':>5}  {'DEPR?':>5}")
    print("  " + "-" * 80)
    for skill in skills:
        last = skill.get("last_used_iso") or "never"
        stale_flag = "yes" if skill["stale"] else "no"
        depr_flag = "YES" if skill["deprecation_candidate"] else "no"
        print(f"  {skill['name']:<30} {skill['invocation_count']:>11}  {last:<22}  {stale_flag:>5}  {depr_flag:>5}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
