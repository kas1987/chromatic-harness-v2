#!/usr/bin/env python3
"""E2E epic-review rollup (Policy SS5 of docs/governance/ISSUE_TO_BEAD_POLICY.md).

For each child bead in the target epic:
  - reads description via `bd show <id> --json`
  - parses the '## Eval requirements (definition of done)' checkbox items
  - reports child status + eval item count

Produces a per-child rollup, combined status, and a ship/no-ship decision:
  ship   = ALL children are closed
  no-ship = any child is open or in_progress (blockers listed)

Artifacts written to:
  07_LOGS_AND_AUDIT/epic_reviews/<epic-id>.json
  07_LOGS_AND_AUDIT/epic_reviews/latest.json

With --apply (and all children closed), posts a review summary as a note on the
epic bead via `bd update <epic-id> --body-file -` (ASCII-only, appended).

Usage:
    python scripts/epic_review.py --review nzn0
    python scripts/epic_review.py --review "CI & Quality Hardening"
    python scripts/epic_review.py --review nzn0 --apply
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED_STATE = REPO / "07_LOGS_AND_AUDIT" / "seed_state" / "issue_to_bead.json"
REVIEW_DIR = REPO / "07_LOGS_AND_AUDIT" / "epic_reviews"

# Mirror from seed_issues_to_beads.py
EPIC_THEMES: dict[str, list[int]] = {
    "CI & Quality Hardening": [57, 58, 60],
    "Governance & Review Layer": [59, 63, 64, 65],
    "Release & Ops Readiness": [61, 62],
    "Queue Infrastructure": [51],
}


# epic title -> ledger key (mirrors ensure_epic logic)
def _epic_ledger_key(title: str) -> str:
    return "epic-" + title.lower().replace(" ", "-").replace("&", "and").replace("--", "-")


_EXE_CACHE: dict[str, str] = {}


def _resolve_exe(name: str) -> str:
    if name not in _EXE_CACHE:
        _EXE_CACHE[name] = shutil.which(name) or name
    return _EXE_CACHE[name]


def _run(cmd: list[str], *, timeout: int = 30, stdin: str | None = None) -> tuple[int, str]:
    if cmd:
        cmd = [_resolve_exe(cmd[0]), *cmd[1:]]
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout, input=stdin)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:
        return 1, str(exc)


def load_ledger() -> dict[str, str]:
    if not SEED_STATE.exists():
        return {}
    try:
        return json.loads(SEED_STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def bd_show(bead_id: str) -> dict | None:
    """Return the first record from `bd show <id> --json`, or None on error."""
    code, out = _run(["bd", "show", bead_id, "--json"], timeout=20)
    if code != 0 or not out.strip():
        return None
    try:
        data = json.loads(out.strip())
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return None


def parse_eval_items(description: str) -> list[dict]:
    """Parse checkbox items from the '## Eval requirements' section.

    Returns a list of dicts with keys: 'checked' (bool), 'text' (str).
    """
    items: list[dict] = []
    in_section = False
    for line in description.splitlines():
        if re.match(r"^##\s+Eval requirements", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            # Stop at the next ## heading
            if line.startswith("##"):
                break
            m = re.match(r"^\s*-\s+\[([xX ]?)\]\s+(.*)", line)
            if m:
                items.append({"checked": m.group(1).strip().lower() == "x", "text": m.group(2).strip()})
    return items


def resolve_epic(query: str, ledger: dict[str, str]) -> tuple[str, str, list[int]] | None:
    """Resolve epic query (id suffix, full id, or title fragment) to (epic_id, title, issue_nums).

    Returns None if not found.
    """
    # Try by ledger key directly (full or suffix)
    for title, issue_nums in EPIC_THEMES.items():
        key = _epic_ledger_key(title)
        epic_id = ledger.get(key)
        if not epic_id:
            continue
        # Match by full bead id, id suffix, or case-insensitive title fragment
        if query == epic_id or epic_id.endswith(query) or query.lower() in title.lower():
            return epic_id, title, issue_nums
    return None


def review_child(bead_id: str, ext_ref: str) -> dict:
    """Fetch and analyse one child bead. Returns a result dict."""
    record = bd_show(bead_id)
    if record is None:
        return {
            "bead_id": bead_id,
            "ext_ref": ext_ref,
            "status": "unknown",
            "eval_items": [],
            "eval_total": 0,
            "eval_checked": 0,
            "error": "bd show failed or returned no data",
        }
    description = record.get("description", "")
    status = record.get("status", "unknown")
    title = record.get("title", "")
    items = parse_eval_items(description)
    checked = sum(1 for i in items if i["checked"])
    return {
        "bead_id": bead_id,
        "ext_ref": ext_ref,
        "title": title,
        "status": status,
        "eval_items": items,
        "eval_total": len(items),
        "eval_checked": checked,
    }


def build_review(epic_id: str, epic_title: str, issue_nums: list[int], ledger: dict[str, str]) -> dict:
    """Run full review for an epic. Returns the review dict."""
    children = []
    for issue_num in issue_nums:
        ext_ref = f"gh-{issue_num}"
        bead_id = ledger.get(ext_ref)
        if bead_id is None:
            children.append(
                {
                    "bead_id": None,
                    "ext_ref": ext_ref,
                    "status": "not_seeded",
                    "eval_items": [],
                    "eval_total": 0,
                    "eval_checked": 0,
                    "error": "no bead id in ledger",
                }
            )
        else:
            children.append(review_child(bead_id, ext_ref))

    # Ship decision: all children must be closed
    blockers = [c for c in children if c.get("status") != "closed"]
    ship = len(blockers) == 0

    total_eval = sum(c["eval_total"] for c in children)
    checked_eval = sum(c["eval_checked"] for c in children)

    return {
        "epic_id": epic_id,
        "epic_title": epic_title,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "children": children,
        "child_count": len(children),
        "ship": ship,
        "decision": "SHIP" if ship else "NO-SHIP",
        "blockers": [
            {"ext_ref": b["ext_ref"], "bead_id": b.get("bead_id"), "status": b.get("status")} for b in blockers
        ],
        "eval_summary": {
            "total_items": total_eval,
            "checked_items": checked_eval,
            "percent": round(100 * checked_eval / total_eval, 1) if total_eval else 0.0,
        },
    }


def write_artifacts(review: dict) -> tuple[Path, Path]:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    epic_id = review["epic_id"]
    payload = json.dumps(review, indent=2)
    named = REVIEW_DIR / f"{epic_id}.json"
    latest = REVIEW_DIR / "latest.json"
    named.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")
    return named, latest


def print_summary(review: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"EPIC REVIEW: {review['epic_title']} ({review['epic_id']})")
    print(f"{'=' * 60}")
    for child in review["children"]:
        bead = child.get("bead_id") or "(no bead)"
        title = child.get("title") or child["ext_ref"]
        status = child["status"]
        ev = child["eval_total"]
        chk = child["eval_checked"]
        print(f"  [{status:12s}] {bead}  {title[:50]}")
        print(f"               eval: {chk}/{ev} items checked")
        if child.get("error"):
            print(f"               ERROR: {child['error']}")
    es = review["eval_summary"]
    print(f"\nEval rollup: {es['checked_items']}/{es['total_items']} ({es['percent']}%) gates passed")
    decision = review["decision"]
    print(f"\nDecision: {decision}")
    if review["blockers"]:
        print("Blockers:")
        for b in review["blockers"]:
            print(f"  - {b['ext_ref']} ({b['bead_id'] or 'unseeded'}) status={b['status']}")
    print(f"{'=' * 60}\n")


def build_note_text(review: dict) -> str:
    """Build ASCII-only review note for appending to the epic bead."""
    lines = [
        "",
        "## E2E Review Rollup",
        f"Timestamp: {review['timestamp']}",
        f"Decision: {review['decision']}",
        "",
        "| Bead | Ext Ref | Status | Eval |",
        "|------|---------|--------|------|",
    ]
    for child in review["children"]:
        bead = child.get("bead_id") or "none"
        ext = child["ext_ref"]
        status = child["status"]
        ev = f"{child['eval_checked']}/{child['eval_total']}"
        lines.append(f"| {bead} | {ext} | {status} | {ev} |")
    es = review["eval_summary"]
    lines += [
        "",
        f"Eval rollup: {es['checked_items']}/{es['total_items']} ({es['percent']}%) gates passed",
    ]
    if review["blockers"]:
        lines.append("Blockers: " + ", ".join(b["ext_ref"] for b in review["blockers"]))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="E2E epic review rollup")
    ap.add_argument("--review", required=True, metavar="EPIC", help="Epic id suffix or title fragment")
    ap.add_argument("--apply", action="store_true", help="Post review note to epic bead (only when ship)")
    args = ap.parse_args()

    ledger = load_ledger()
    if not ledger:
        print("error: ledger empty or missing — run seed_issues_to_beads.py first", file=sys.stderr)
        return 1

    resolved = resolve_epic(args.review, ledger)
    if resolved is None:
        print(f"error: could not resolve epic '{args.review}'", file=sys.stderr)
        print("Known epics:", list(EPIC_THEMES.keys()), file=sys.stderr)
        return 1

    epic_id, epic_title, issue_nums = resolved
    print(f"Reviewing epic: {epic_id} ({epic_title})")
    print(f"Children: {[f'gh-{n}' for n in issue_nums]}")

    review = build_review(epic_id, epic_title, issue_nums, ledger)
    print_summary(review)

    named, latest = write_artifacts(review)
    print("Artifacts written:")
    print(f"  {named}")
    print(f"  {latest}")

    if args.apply:
        if not review["ship"]:
            print("--apply skipped: decision is NO-SHIP (not all children closed)")
        else:
            # Append review note to epic bead description
            epic_record = bd_show(epic_id)
            existing_desc = (epic_record or {}).get("description", "") if epic_record else ""
            note = build_note_text(review)
            new_desc = existing_desc.rstrip() + "\n" + note
            code, out = _run(
                ["bd", "update", epic_id, "--body-file", "-"],
                timeout=60,
                stdin=new_desc,
            )
            if code != 0:
                print(f"error: bd update failed: {out}", file=sys.stderr)
                return 1
            print(f"Review note posted to epic bead {epic_id}.")
    else:
        if review["ship"]:
            print("(dry-run) Would post review note to epic — pass --apply to write.")

    return 0 if review["ship"] else 2


if __name__ == "__main__":
    sys.exit(main())
