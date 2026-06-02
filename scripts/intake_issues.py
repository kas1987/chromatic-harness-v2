#!/usr/bin/env python3
"""Stage 1 of the issue→bead pipeline: INTAKE (read-only).

Fetches open GitHub issues, parses the governance structure
(Objective / Scope / Acceptance checks / Suggested owner agent), assigns a
C-level routing hint, validates against policy, and writes normalized records
to a staging file. It writes NO beads and mutates nothing in GitHub — it is a
pure read-only producer, per docs/governance/ISSUE_TO_BEAD_POLICY.md and the
CLAUDE.md rule that intake/analysis stages stage proposals rather than act.

Stage 2 (scripts/seed_issues_to_beads.py) consumes the staged file, groups
issues into epics, and creates the beads.

Outputs:
  07_LOGS_AND_AUDIT/issue_intake/staged_issues.jsonl   (append-only history)
  07_LOGS_AND_AUDIT/issue_intake/latest.json           (current full snapshot)

Usage:
    python scripts/intake_issues.py                # fetch + stage all open issues
    python scripts/intake_issues.py --print        # also print the parsed summary
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

STAGE_DIR = REPO / "07_LOGS_AND_AUDIT" / "issue_intake"

# Owner-agent / signal -> C-level routing hint (policy §3)
C_LEVEL_BY_OWNER = {
    "sentinel": "C2",
    "auditor": "C2",
    "reviewer": "C3",
    "policy": "C4",
    "consensus": "C4",
    "drift": "C3",
}
_LEVEL_RANK = {"C1": 1, "C2": 2, "C3": 3, "C4": 4}

SECTION_RE = {
    "objective": re.compile(r"##\s*Objective\s*\n(.*?)(?=\n##\s|\nAcceptance:|\Z)", re.S | re.I),
    "scope": re.compile(r"##\s*Scope\s*\n(.*?)(?=\n##\s|\Z)", re.S | re.I),
    "acceptance": re.compile(
        r"(?:##\s*Acceptance(?:\s+checks|\s+criteria)?|Acceptance)\s*:?\s*\n(.*?)"
        r"(?=\n##\s|\nSuggested owner|\Z)",
        re.S | re.I,
    ),
    "owner": re.compile(
        r"(?:##\s*Suggested owner(?:\s+agent)?|Suggested owner)\s*:?\s*\n?(.*?)(?=\n##\s|\Z)",
        re.S | re.I,
    ),
}
BEAD_SLUG_RE = re.compile(r"bead:([a-zA-Z0-9._-]+)")

_EXE_CACHE: dict[str, str] = {}


def _resolve_exe(name: str) -> str:
    if name not in _EXE_CACHE:
        _EXE_CACHE[name] = shutil.which(name) or name
    return _EXE_CACHE[name]


def _run(cmd: list[str], *, timeout: int = 60) -> tuple[int, str]:
    if cmd:
        cmd = [_resolve_exe(cmd[0]), *cmd[1:]]
    r = run_safe(cmd, cwd=REPO, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def fetch_open_issues() -> list[dict]:
    code, out = _run(
        ["gh", "issue", "list", "--state", "open", "--limit", "100", "--json", "number,title,body,labels"],
        timeout=60,
    )
    if code != 0:
        print(f"error: gh issue list failed: {out}", file=sys.stderr)
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def _section(body: str, key: str) -> str:
    m = SECTION_RE[key].search(body)
    return m.group(1).strip() if m else ""


def c_level_for(owner: str, title: str = "") -> str:
    """Pick the C-level hint from owner + title, preferring the higher tier when
    multiple match (e.g. 'Sentinel + reviewer' -> C3)."""
    hay = f"{owner} {title}".lower()
    best, matched = "C3", False
    for sig, lvl in C_LEVEL_BY_OWNER.items():
        if sig in hay and (not matched or _LEVEL_RANK[lvl] > _LEVEL_RANK[best]):
            best, matched = lvl, True
    return best


def _objective_fallback(body: str) -> str:
    cleaned = re.sub(r"^\s*\*\*Bead:.*$", "", body, flags=re.M)
    cleaned = re.sub(r"^\s*bead:.*$", "", cleaned, flags=re.M)
    head = re.split(r"\n(?:##\s*Acceptance|Acceptance\s*:)", cleaned, maxsplit=1, flags=re.I)[0]
    lines = [ln.strip() for ln in head.splitlines() if ln.strip()]
    return lines[0] if lines else ""


def parse_issue(issue: dict) -> dict:
    """Return a normalized staged record. `valid` is False (with `reason`) when
    the issue fails policy §1 (no acceptance checks = no eval requirements)."""
    body = issue.get("body") or ""
    objective = _section(body, "objective") or _objective_fallback(body)
    scope = _section(body, "scope")
    acceptance = _section(body, "acceptance")
    owner = _section(body, "owner")
    slug_m = BEAD_SLUG_RE.search(body)
    slug = slug_m.group(1) if slug_m else ""
    title = re.sub(r"^\[queue\]\s*", "", issue["title"]).strip()

    rec: dict = {
        "number": issue["number"],
        "title": title,
        "ext_ref": f"gh-{issue['number']}",
        "objective": objective,
        "scope": scope or "_(no explicit scope - see objective + eval requirements)_",
        "owner": owner,
        "slug": slug,
        "labels": [lbl.get("name") for lbl in issue.get("labels", [])],
    }

    if not acceptance:
        rec["valid"] = False
        rec["reason"] = "no acceptance checks (policy §1 — eval requirements required)"
        rec["acceptance"] = ""
        rec["c_level"] = None
        return rec

    accept_lines = []
    for ln in acceptance.splitlines():
        s = ln.strip()
        if not s:
            continue
        s = re.sub(r"^[-*]\s*(\[[ xX]\]\s*)?", "", s)
        accept_lines.append(f"- [ ] {s}")
    rec["acceptance"] = "\n".join(accept_lines)
    rec["c_level"] = c_level_for(owner, title)
    rec["valid"] = True
    rec["reason"] = ""
    return rec


def write_staged(records: list[dict], queued_at: str) -> Path:
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    jsonl = STAGE_DIR / "staged_issues.jsonl"
    latest = STAGE_DIR / "latest.json"
    # Append-only history (one line per intake run, per record).
    with jsonl.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps({**rec, "queued_at": queued_at}) + "\n")
    # Current full snapshot for Stage 2 to consume.
    latest.write_text(
        json.dumps({"queued_at": queued_at, "records": records}, indent=2),
        encoding="utf-8",
    )
    return latest


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 1: intake GH issues (read-only)")
    ap.add_argument("--print", action="store_true", dest="show", help="Print parsed summary")
    # queued_at is passed in (Date.now equivalent) so runs are deterministic/testable.
    ap.add_argument("--queued-at", default="", help="ISO timestamp override")
    args = ap.parse_args()

    issues = fetch_open_issues()
    if not issues:
        print("No open issues found (or gh unavailable).", file=sys.stderr)
        return 1

    queued_at = args.queued_at
    if not queued_at:
        import datetime

        queued_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    records = [parse_issue(i) for i in issues]
    valid = [r for r in records if r["valid"]]
    invalid = [r for r in records if not r["valid"]]

    latest = write_staged(records, queued_at)

    print(f"intake: staged {len(records)} issue(s) — {len(valid)} valid, {len(invalid)} rejected")
    print(f"artifact: {latest}")
    if args.show:
        for r in records:
            flag = f"[{r['c_level']}]" if r["valid"] else "[REJECT]"
            print(f"  gh-{r['number']:<3} {flag:9} {r['title']}")
            if not r["valid"]:
                print(f"           -> {r['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
