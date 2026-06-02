#!/usr/bin/env python3
"""Continuous Execution & Bead Review SOP checker.

Enforces docs/governance/CONTINUOUS_EXECUTION_SOP.md: surfaces ready work and
ready-queue noise so an agent never idles on a decision it could make itself.

Advisory by default (exit 0). With --strict, exits 1 when there is ready work
but no recorded next-step intent — a signal that the agent stopped without
proceeding.

Usage:
  python scripts/continuous_execution_check.py
  python scripts/continuous_execution_check.py --strict
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

# Clusters of auto-generated beads that pollute the ready queue. Each entry is a
# regex on the bead title; >NOISE_THRESHOLD matches in one cluster is flagged.
NOISE_PATTERNS = {
    "epic_swot_seed": re.compile(r"Generate next EPIC-SWOT.*before final closeout", re.I),
    "post_closeout_seed": re.compile(r"Post-Closeout SWOT Seed", re.I),
}
NOISE_THRESHOLD = 3


def _extract_json(text: str):
    """Parse a JSON array/object even if bd prints a preamble line before it."""
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass
    # Fall back to the outermost [...] span.
    start, end = stripped.find("["), stripped.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except Exception:
            return None
    return None


def _bd_ready_json() -> list[dict]:
    # Resolve bd's real path: on Windows it's a .cmd shim that bare CreateProcess
    # can't find, so shutil.which (with shell fallback) is required.
    bd = shutil.which("bd")
    attempts = []
    if bd:
        attempts.append({"args": [bd, "ready", "--json", "--quiet"], "shell": False})
    attempts.append({"args": "bd ready --json --quiet", "shell": True})
    for attempt in attempts:
        out = run_safe(attempt["args"], cwd=REPO, timeout=30, shell=attempt["shell"])
        data = _extract_json(out.stdout)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("issues", [])
    return []


def _title(item: dict) -> str:
    return item.get("title") or item.get("summary") or ""


def analyze(items: list[dict]) -> dict:
    titles = [_title(i) for i in items]
    noise = Counter()
    for t in titles:
        for name, pat in NOISE_PATTERNS.items():
            if pat.search(t):
                noise[name] += 1
    flagged = {k: v for k, v in noise.items() if v > NOISE_THRESHOLD}
    by_priority = Counter(str(i.get("priority", "?")) for i in items)
    return {
        "ready_count": len(items),
        "by_priority": dict(by_priority),
        "noise_clusters": flagged,
        "noise_total": sum(flagged.values()),
        "top_actionable": [
            {"id": i.get("id"), "priority": i.get("priority"), "title": _title(i)[:80]}
            for i in items
            if not any(p.search(_title(i)) for p in NOISE_PATTERNS.values())
        ][:5],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Continuous Execution & Bead Review SOP check")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument(
        "--next-steps-recorded",
        action="store_true",
        help="Caller asserts the current response recorded next steps",
    )
    args = ap.parse_args()

    items = _bd_ready_json()
    report = analyze(items)
    report["ok"] = True

    if report["noise_clusters"]:
        report["advice_noise"] = (
            "Ready queue has auto-generated noise; dedupe/close these clusters "
            "so bead review stays meaningful (SOP: keep the ready queue clean)."
        )
    if report["ready_count"] and not args.next_steps_recorded:
        report["advice_proceed"] = (
            "Ready work exists — proceed to the top actionable bead or your "
            "identified next step. Do not stop and wait (SOP)."
        )

    print(json.dumps(report, indent=2))

    if args.strict and report["ready_count"] and not args.next_steps_recorded:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
