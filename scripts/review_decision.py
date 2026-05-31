#!/usr/bin/env python3
"""KOS Stage 6: Review & Approve candidates.

Modes:
  --auto               Run automated checks on all pending candidates
  --approve <name>     Manually approve a candidate
  --reject  <name>     Manually reject a candidate
  --notes   <text>     Optional notes for manual approve/reject
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CANDIDATES_DIR = REPO / ".agents" / "candidates"
REVIEWS_DIR = REPO / ".agents" / "reviews"

VALID_CANON_MAPS = {"general", "routing", "security", "knowledge", "operations"}
CONFIDENCE_THRESHOLD = 0.7

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def _set_status(path: Path, new_status: str) -> None:
    """Replace `status: <anything>` in the frontmatter block."""
    text = path.read_text(encoding="utf-8", errors="replace")
    updated = re.sub(
        r"(^---\s*\n.*?)(^status:\s*\S+)(.*?^---\s*\n)",
        lambda m: m.group(1) + f"status: {new_status}" + m.group(3),
        text,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    if updated == text:
        # status line not found — append it to frontmatter
        updated = re.sub(
            r"(^---\s*\n)(.*?)(^---\s*\n)",
            lambda m: m.group(1) + m.group(2) + f"status: {new_status}\n" + m.group(3),
            text,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )
    path.write_text(updated, encoding="utf-8")


def _write_review(record: dict) -> Path:
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", record["candidate"])
    out_path = REVIEWS_DIR / f"{date_str}-{safe_name}.json"
    # If a file already exists for today, append an index
    idx = 1
    while out_path.exists():
        out_path = REVIEWS_DIR / f"{date_str}-{safe_name}-{idx}.json"
        idx += 1
    try:
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"  WARNING: could not write review record: {exc}", file=sys.stderr)
    return out_path


# ---------------------------------------------------------------------------
# Auto-check mode
# ---------------------------------------------------------------------------


def _run_checks(meta: dict, all_names_approved: set[str]) -> dict[str, bool]:
    name = meta.get("name", "").strip()
    raw_conf = meta.get("confidence", "0")
    try:
        conf = float(raw_conf)
    except ValueError:
        conf = 0.0

    confidence_ok = conf >= CONFIDENCE_THRESHOLD
    not_duplicate = name not in all_names_approved
    has_suggested_use = bool(meta.get("suggested_use", "").strip())
    alignment_ok = meta.get("canon_map", "").strip().lower() in VALID_CANON_MAPS

    return {
        "confidence_ok": confidence_ok,
        "not_duplicate": not_duplicate,
        "has_suggested_use": has_suggested_use,
        "alignment_ok": alignment_ok,
    }


def cmd_auto() -> int:
    if not CANDIDATES_DIR.is_dir():
        print(f"ERROR: candidates dir not found: {CANDIDATES_DIR}", file=sys.stderr)
        return 1

    # First pass: collect all currently-approved names (for dupe check)
    approved_names: set[str] = set()
    pending_files: list[Path] = []

    for path in sorted(CANDIDATES_DIR.iterdir()):
        if (
            path.suffix != ".md"
            or path.name in ("SCHEMA.md",)
            or path.name.startswith("_")
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta = _parse_frontmatter(text)
        status = meta.get("status", "pending").strip().lower()
        if status == "approved":
            approved_names.add(meta.get("name", "").strip())
        elif status == "pending":
            pending_files.append(path)

    n_approved = 0
    n_needs_review = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for path in pending_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            print(f"  SKIP (unreadable): {path.name}", file=sys.stderr)
            continue

        meta = _parse_frontmatter(text)
        name = meta.get("name", path.stem).strip()
        checks = _run_checks(meta, approved_names)
        all_pass = all(checks.values())

        if all_pass:
            verdict = "approved"
            notes = "auto-approved: all checks passed"
            _set_status(path, "approved")
            approved_names.add(name)  # update set so later dupes are caught
            n_approved += 1
        else:
            verdict = "needs_review"
            failing = [k for k, v in checks.items() if not v]
            notes = f"requires human review: {', '.join(failing)}"
            # leave status as pending
            n_needs_review += 1

        record = {
            "candidate": name,
            "reviewed_at": now_iso,
            "reviewer": "auto",
            "checks": checks,
            "verdict": verdict,
            "notes": notes,
        }
        review_path = _write_review(record)
        status_label = "AUTO-APPROVED" if all_pass else "NEEDS REVIEW"
        print(f"  [{status_label}] {name}  -> {review_path.name}")

    print(f"\nSummary: {n_approved} auto-approved, {n_needs_review} need human review")
    return 0


# ---------------------------------------------------------------------------
# Manual approve / reject
# ---------------------------------------------------------------------------


def _find_candidate(name: str) -> Path | None:
    for path in CANDIDATES_DIR.iterdir():
        if path.suffix != ".md" or path.name in ("SCHEMA.md",):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta = _parse_frontmatter(text)
        if meta.get("name", "").strip() == name or path.stem == name:
            return path
    return None


def cmd_manual(name: str, verdict: str, notes: str) -> int:
    if not CANDIDATES_DIR.is_dir():
        print(f"ERROR: candidates dir not found: {CANDIDATES_DIR}", file=sys.stderr)
        return 1

    path = _find_candidate(name)
    if path is None:
        print(f"ERROR: candidate not found: {name!r}", file=sys.stderr)
        return 1

    new_status = "approved" if verdict == "approved" else "rejected"
    _set_status(path, new_status)

    record = {
        "candidate": name,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": "human",
        "checks": {},
        "verdict": new_status,
        "notes": notes or f"manually {new_status}",
    }
    review_path = _write_review(record)
    print(f"  [{new_status.upper()}] {name}  -> {review_path.name}")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--auto",
        action="store_true",
        help="Run automated checks on all pending candidates",
    )
    mode.add_argument(
        "--approve", metavar="NAME", help="Manually approve a candidate by name"
    )
    mode.add_argument(
        "--reject", metavar="NAME", help="Manually reject a candidate by name"
    )
    parser.add_argument(
        "--notes", default="", help="Optional notes for manual approve/reject"
    )

    args = parser.parse_args()

    if args.auto:
        return cmd_auto()
    elif args.approve:
        return cmd_manual(args.approve, "approved", args.notes)
    elif args.reject:
        return cmd_manual(args.reject, "rejected", args.notes)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
