#!/usr/bin/env python3
"""queue_self_review.py — read-only beads/epics hygiene reviewer (bead gl6t).

Detects the exact queue-rot conditions that previously needed manual cleanup, and
writes PROPOSALS to a staging artifact. It is read-only by default: it never
mutates the bead DB unless `--apply` is passed explicitly (the human gate), and
even then only performs safe, reversible closes.

Findings:
  unclaimed_active   — status in_progress but no assignee (must be claimed).
  ready_to_close     — open/in_progress with eval checkboxes ALL checked [x].
  duplicate_ref      — two+ beads sharing one external_ref (seeding collision).
  epic_ready_close   — epic open while every child is closed.
  stale_in_progress  — in_progress with no update in > N days (default 3).

Artifact: 07_LOGS_AND_AUDIT/queue_self_review/latest.json  (proposals only).

Per the repo's governance rule, background review is read-only and writes
proposals to staging; only an explicit human-triggered `--apply` enacts the safe
subset (ready_to_close + epic_ready_close).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common_harness import run_safe  # noqa: E402

OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "queue_self_review"
LATEST = OUT_DIR / "latest.json"

CHECKED_RE = re.compile(r"-\s*\[x\]", re.IGNORECASE)
UNCHECKED_RE = re.compile(r"-\s*\[ \]")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _bd() -> str | None:
    return shutil.which("bd") or shutil.which("bd.cmd")


def _run_bd(args: list[str], timeout: int = 30) -> tuple[int, str]:
    bd = _bd()
    if not bd:
        return 1, ""
    # run_safe reaps the process tree on timeout (rc=124) and never raises.
    r = run_safe([bd, *args], cwd=REPO, timeout=timeout)
    return r.returncode, (r.stdout or "")


def load_beads() -> list[dict]:
    """All beads via `bd list --json`. [] if bd unavailable or output unparseable."""
    code, out = _run_bd(["list", "--all", "--json"])
    if code != 0 or not out.strip():
        code, out = _run_bd(["list", "--json"])
    if code != 0 or not out.strip():
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else data.get("issues", [])


# ── Pure detectors (testable without bd) ─────────────────────────────────────


def eval_state(description: str) -> tuple[int, int]:
    """Return (checked, unchecked) eval-checkbox counts in a description."""
    return len(CHECKED_RE.findall(description or "")), len(UNCHECKED_RE.findall(description or ""))


def _status(b: dict) -> str:
    return str(b.get("status", "")).lower()


def _assignee(b: dict) -> str:
    return str(b.get("assignee") or "").strip()


def _is_epic(b: dict) -> bool:
    return str(b.get("issue_type", b.get("type", ""))).lower() == "epic"


def _age_days(b: dict) -> float | None:
    raw = b.get("updated_at") or b.get("updated") or b.get("updatedAt")
    if not raw:
        return None
    s = str(raw).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round((_utc_now() - dt).total_seconds() / 86400, 1)
    except ValueError:
        return None


def find_findings(beads: list[dict], stale_days: float = 3.0) -> list[dict]:
    findings: list[dict] = []
    by_id = {b.get("id"): b for b in beads}

    # duplicate external_ref
    ref_map: dict[str, list[str]] = {}
    for b in beads:
        ref = (b.get("external_ref") or b.get("externalRef") or "").strip()
        if ref:
            ref_map.setdefault(ref, []).append(b.get("id"))
    for ref, ids in ref_map.items():
        if len(ids) > 1:
            findings.append({"kind": "duplicate_ref", "external_ref": ref, "beads": ids, "severity": "warn"})

    # children-by-parent for epic rollup
    children: dict[str, list[dict]] = {}
    for b in beads:
        parent = b.get("parent") or b.get("parent_id") or b.get("epic")
        if parent:
            children.setdefault(parent, []).append(b)

    for b in beads:
        bid = b.get("id")
        status = _status(b)
        desc = b.get("description") or b.get("body") or ""

        if status == "in_progress" and not _assignee(b):
            findings.append(
                {
                    "kind": "unclaimed_active",
                    "bead": bid,
                    "title": b.get("title"),
                    "severity": "warn",
                    "proposal": "claim or release (bd update --claim / --status open)",
                }
            )

        if status in {"open", "in_progress"}:
            checked, unchecked = eval_state(desc)
            if checked > 0 and unchecked == 0:
                findings.append(
                    {
                        "kind": "ready_to_close",
                        "bead": bid,
                        "title": b.get("title"),
                        "checked": checked,
                        "severity": "info",
                        "proposal": f"close ({checked}/{checked} eval boxes checked)",
                    }
                )

        if status == "in_progress":
            age = _age_days(b)
            if age is not None and age > stale_days:
                findings.append(
                    {
                        "kind": "stale_in_progress",
                        "bead": bid,
                        "title": b.get("title"),
                        "age_days": age,
                        "severity": "warn",
                        "proposal": "review: complete, reclaim, or release",
                    }
                )

        if _is_epic(b) and status in {"open", "in_progress"}:
            kids = children.get(bid, [])
            if kids and all(_status(k) in {"closed", "done"} for k in kids):
                findings.append(
                    {
                        "kind": "epic_ready_close",
                        "bead": bid,
                        "title": b.get("title"),
                        "children": len(kids),
                        "severity": "info",
                        "proposal": f"close epic ({len(kids)}/{len(kids)} children closed)",
                    }
                )

    # keep stable, grouped order
    order = {
        "unclaimed_active": 0,
        "stale_in_progress": 1,
        "duplicate_ref": 2,
        "ready_to_close": 3,
        "epic_ready_close": 4,
    }
    findings.sort(key=lambda f: (order.get(f["kind"], 9), str(f.get("bead", f.get("external_ref", "")))))
    return findings


def build_report(beads: list[dict], stale_days: float = 3.0) -> dict:
    findings = find_findings(beads, stale_days)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    return {
        "generated_at_utc": _ts(),
        "beads_reviewed": len(beads),
        "finding_counts": counts,
        "findings": findings,
        "auto_closeable": [f["bead"] for f in findings if f["kind"] in {"ready_to_close", "epic_ready_close"}],
    }


def summarize() -> dict:
    try:
        if not LATEST.exists():
            return {"status": "no_scan", "finding_counts": {}}
        data = json.loads(LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "beads_reviewed": data.get("beads_reviewed"),
            "finding_counts": data.get("finding_counts", {}),
            "auto_closeable": len(data.get("auto_closeable", [])),
            "generated_at_utc": data.get("generated_at_utc"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "finding_counts": {}}


def write_artifact(report: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return LATEST


def apply_safe_closes(report: dict) -> list[dict]:
    """Human-gated (--apply): close only ready_to_close + epic_ready_close beads."""
    results = []
    for f in report["findings"]:
        if f["kind"] not in {"ready_to_close", "epic_ready_close"}:
            continue
        bid = f["bead"]
        reason = f"queue_self_review: {f.get('proposal', 'eval-complete')}"
        code, out = _run_bd(["close", bid, "--reason", reason])
        results.append({"bead": bid, "closed": code == 0, "detail": out.strip()[-120:]})
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only beads/epics queue hygiene reviewer (bead gl6t)")
    ap.add_argument(
        "--write", action="store_true", help="persist proposals to 07_LOGS_AND_AUDIT/queue_self_review/latest.json"
    )
    ap.add_argument(
        "--apply", action="store_true", help="HUMAN GATE: enact safe closes (ready_to_close + epic_ready_close)"
    )
    ap.add_argument("--stale-days", type=float, default=3.0)
    args = ap.parse_args()

    beads = load_beads()
    report = build_report(beads, args.stale_days)

    if args.write or args.apply:
        write_artifact(report)

    if args.apply:
        report["applied"] = apply_safe_closes(report)

    print(json.dumps(report, indent=2))
    # Non-zero only when an action-required finding exists (unclaimed/stale), so a
    # session-end hook can surface it. info-level (ready_to_close) does not fail.
    action_required = any(f["severity"] == "warn" for f in report["findings"])
    return 1 if action_required and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
