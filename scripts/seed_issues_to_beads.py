#!/usr/bin/env python3
"""Stage 2 of the issue→bead pipeline: AGGREGATE + SEED (gated write).

Consumes the read-only staging file produced by scripts/intake_issues.py
(Stage 1), groups the parsed issues into themed EPICs, and creates the beads:

  staged record (objective / scope / eval requirements / c-level / valid)
    -> group by theme into a parent EPIC bead
    -> create child task bead with --parent <epic> --external-ref gh-<N>
    -> record gh-N -> bead-id in the idempotency ledger

Separation of concerns (per ISSUE_TO_BEAD_POLICY.md):
  Stage 1 (intake_issues.py)  — read-only, fetch+parse, safe to run often.
  Stage 2 (this script)       — the only writer; gated behind --apply.

Idempotent: a local ledger (07_LOGS_AND_AUDIT/seed_state/issue_to_bead.json)
maps each external-ref to its bead id, so re-running never duplicates.
Default-safe: --dry-run unless --apply is passed.

Usage:
    python scripts/seed_issues_to_beads.py --dry-run            # preview from staged
    python scripts/seed_issues_to_beads.py --refresh --apply    # run Stage 1 first, then seed
    python scripts/seed_issues_to_beads.py --apply
    python scripts/seed_issues_to_beads.py --apply --epic "CI & Quality Hardening" --issues 57,58,60
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

STAGE_LATEST = REPO / "07_LOGS_AND_AUDIT" / "issue_intake" / "latest.json"
SEED_STATE = REPO / "07_LOGS_AND_AUDIT" / "seed_state" / "issue_to_bead.json"

# Resolve executables once. On Windows `bd` is a .cmd shim that subprocess
# cannot find without PATHEXT resolution; shutil.which handles that.
_EXE_CACHE: dict[str, str] = {}


def _resolve_exe(name: str) -> str:
    if name not in _EXE_CACHE:
        _EXE_CACHE[name] = shutil.which(name) or name
    return _EXE_CACHE[name]


# Theme map: epic title -> issue numbers (per ISSUE_TO_BEAD_POLICY.md §4)
EPIC_THEMES: dict[str, list[int]] = {
    "CI & Quality Hardening": [57, 58, 60],
    "Governance & Review Layer": [59, 63, 64, 65],
    "Release & Ops Readiness": [61, 62],
    "Queue Infrastructure": [51],
}


def _run(cmd: list[str], *, timeout: int = 60, stdin: str | None = None) -> tuple[int, str]:
    if cmd:
        cmd = [_resolve_exe(cmd[0]), *cmd[1:]]
    r = run_safe(cmd, cwd=REPO, timeout=timeout, stdin=stdin)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ── Staged input (Stage 1 output) ────────────────────────────────────────────


def run_intake() -> bool:
    """Invoke Stage 1 to refresh the staged file. Returns True on success."""
    code, out = _run([sys.executable, str(REPO / "scripts" / "intake_issues.py")], timeout=90)
    if code != 0:
        print(f"error: intake (Stage 1) failed: {out}", file=sys.stderr)
        return False
    return True


def load_staged() -> dict[int, dict]:
    """Load staged records keyed by issue number. {} if no staging file."""
    if not STAGE_LATEST.exists():
        return {}
    try:
        data = json.loads(STAGE_LATEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {r["number"]: r for r in data.get("records", [])}


# ── Idempotency ledger ───────────────────────────────────────────────────────


def _load_seed_state() -> dict[str, str]:
    if not SEED_STATE.exists():
        return {}
    try:
        return json.loads(SEED_STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_seed_state(state: dict[str, str]) -> None:
    SEED_STATE.parent.mkdir(parents=True, exist_ok=True)
    SEED_STATE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _bead_still_open(bead_id: str) -> bool:
    code, out = _run(["bd", "show", bead_id, "--json"], timeout=20)
    return code == 0 and bool(out.strip())


def bead_exists_for_ref(ext_ref: str, state: dict[str, str]) -> str | None:
    bead_id = state.get(ext_ref)
    if bead_id and _bead_still_open(bead_id):
        return bead_id
    return None


# ── Bead description from a staged record ─────────────────────────────────────

# Common non-ASCII glyphs that sneak into descriptions -> safe ASCII. Dolt's
# column charset rejects them with Error 1105, silently failing the write.
_ASCII_MAP = {
    "—": "-",
    "–": "-",  # em/en dash
    "·": "|",
    "•": "-",  # middle dot, bullet
    "§": "section ",  # section sign §
    "→": "->",
    "↳": "->",  # arrows
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",  # smart quotes
}


def ascii_safe(text: str) -> str:
    """Coerce a string to ASCII so it can be stored in the bead DB. Maps known
    glyphs, then drops anything still non-ASCII. Idempotent."""
    for bad, good in _ASCII_MAP.items():
        text = text.replace(bad, good)
    return text.encode("ascii", "ignore").decode("ascii")


def build_bead_description(rec: dict, epic_title: str) -> str:
    return (
        f"{rec['objective']}\n\n"
        f"## Scope\n{rec['scope']}\n\n"
        f"## Eval requirements (definition of done)\n{rec['acceptance']}\n\n"
        f"## Routing\nC-level hint: {rec['c_level']} | owner: {rec['owner'] or 'unassigned'}\n\n"
        f"## Traceability\nEpic: {epic_title} | GitHub: {rec['ext_ref']}"
        + (f" | slug: {rec['slug']}" if rec.get("slug") else "")
    )


# ── Epic + child creation ─────────────────────────────────────────────────────


def ensure_epic(title: str, issue_nums: list[int], state: dict[str, str], *, apply: bool) -> str | None:
    ext_ref = f"epic-{title.lower().replace(' ', '-').replace('&', 'and')}"
    existing = bead_exists_for_ref(ext_ref, state)
    if existing:
        print(f"  epic exists: {existing} ({title})")
        return existing
    desc = (
        f"E2E epic - packs GitHub issues {', '.join(f'#{n}' for n in issue_nums)}.\n\n"
        f"Stays open until all child beads close, then receives a summarized E2E review "
        f"(per-child eval rollup + combined artifacts + single ship/no-ship decision). "
        f"See docs/governance/ISSUE_TO_BEAD_POLICY.md section 5."
    )
    if not apply:
        print(f"  [dry-run] would create EPIC: {title}")
        return f"<dry-run-epic:{title}>"
    # Pass the (multi-line) description via stdin: on Windows `bd` is a .cmd
    # shim and cmd.exe mangles multi-line/special-char args, silently truncating
    # the description to its first line. --body-file - reads it from stdin intact.
    code, out = _run(
        ["bd", "create", title, "--type", "epic", "--priority", "P2", "--external-ref", ext_ref, "--body-file", "-"],
        timeout=60,
        stdin=ascii_safe(desc),
    )
    if code != 0:
        print(f"  ERROR creating epic {title}: {out}", file=sys.stderr)
        return None
    m = re.search(r"(chromatic-harness-v2-[a-z0-9]+)", out)
    bead_id = m.group(1) if m else None
    if bead_id:
        state[ext_ref] = bead_id
        _save_seed_state(state)
    print(f"  created EPIC {bead_id}: {title}")
    return bead_id


def seed_child(rec: dict, epic_id: str | None, epic_title: str, state: dict[str, str], *, apply: bool) -> dict:
    ext_ref = rec["ext_ref"]
    existing = bead_exists_for_ref(ext_ref, state)
    result = {"issue": rec["number"], "ext_ref": ext_ref, "c_level": rec["c_level"]}
    if existing:
        result["status"] = "exists"
        result["bead_id"] = existing
        print(f"    child exists: {existing} ({ext_ref} {rec['title']})")
        return result

    desc = build_bead_description(rec, epic_title)
    priority = "P1" if rec["c_level"] in ("C3", "C4") else "P2"
    if not apply:
        result["status"] = "would-create"
        print(f"    [dry-run] would create child {ext_ref} [{rec['c_level']}] {rec['title']}")
        return result

    cmd = [
        "bd",
        "create",
        rec["title"],
        "--type",
        "task",
        "--priority",
        priority,
        "--external-ref",
        ext_ref,
        "--body-file",
        "-",  # read multi-line description from stdin (Windows .cmd arg-mangle fix)
    ]
    if epic_id and not epic_id.startswith("<dry-run"):
        cmd += ["--parent", epic_id]
    code, out = _run(cmd, timeout=60, stdin=ascii_safe(desc))
    if code != 0:
        result["status"] = "error"
        result["error"] = out[-300:]
        print(f"    ERROR child {ext_ref}: {out}", file=sys.stderr)
        return result
    m = re.search(r"(chromatic-harness-v2-[a-z0-9]+)", out)
    result["bead_id"] = m.group(1) if m else None
    result["status"] = "created"
    if result["bead_id"]:
        state[ext_ref] = result["bead_id"]
        _save_seed_state(state)
    print(f"    created child {result['bead_id']} [{rec['c_level']}] {rec['title']}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 2: seed staged issues into epics + child beads")
    ap.add_argument("--apply", action="store_true", help="Write beads (default: dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="Preview only (default)")
    ap.add_argument("--refresh", action="store_true", help="Run Stage 1 intake first")
    ap.add_argument("--epic", help="Explicit epic title (use with --issues)")
    ap.add_argument("--issues", help="Comma-separated issue numbers for explicit --epic")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    if args.refresh and not run_intake():
        return 1

    staged = load_staged()
    if not staged:
        print(
            "No staged issues found. Run Stage 1 first:\n"
            "  python scripts/intake_issues.py\n"
            "or pass --refresh to run it automatically.",
            file=sys.stderr,
        )
        return 1

    state = _load_seed_state()

    if args.epic and args.issues:
        nums = [int(x) for x in args.issues.split(",") if x.strip()]
        themes = {args.epic: nums}
    else:
        themes = EPIC_THEMES

    summary = {"epics": 0, "children_created": 0, "children_existing": 0, "rejected": []}

    print(f"{'APPLY' if apply else 'DRY-RUN'} — seeding {len(themes)} epic(s) from staged intake\n")
    for epic_title, nums in themes.items():
        present = [n for n in nums if n in staged]
        if not present:
            print(f"EPIC {epic_title}: no matching staged issues, skipping")
            continue
        # Reject staged records that failed policy validation; skip empty epics.
        valid = []
        for n in present:
            rec = staged[n]
            if not rec.get("valid"):
                print(f"EPIC {epic_title}: REJECTED gh-{n} — {rec.get('reason', 'invalid')}")
                summary["rejected"].append(n)
            else:
                valid.append(rec)
        if not valid:
            print(f"EPIC {epic_title}: no valid children, skipping epic\n")
            continue
        print(f"EPIC {epic_title}: issues {[r['number'] for r in valid]}")
        epic_id = ensure_epic(epic_title, [r["number"] for r in valid], state, apply=apply)
        summary["epics"] += 1
        for rec in valid:
            r = seed_child(rec, epic_id, epic_title, state, apply=apply)
            if r["status"] == "created":
                summary["children_created"] += 1
            elif r["status"] == "exists":
                summary["children_existing"] += 1
        print()

    print("=" * 60)
    print(
        f"epics: {summary['epics']} · children created: {summary['children_created']} · "
        f"existing: {summary['children_existing']}"
    )
    if summary["rejected"]:
        print(f"rejected (no acceptance checks): {summary['rejected']}")
    if not apply:
        print("\n(dry-run — re-run with --apply to write beads)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
