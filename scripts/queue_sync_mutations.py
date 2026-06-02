#!/usr/bin/env python3
"""Queue<->GitHub mutation mirroring + bidirectional close-sync + audit trail.

Completes bead gh-51 (chromatic-harness-v2-zeky) Phases 3b/3c on top of the
existing scripts/sync_queue_to_github.py (Phase 3a). Provides:
  - record_sync_action(): append every sync action to the audit trail. [eval 5]
  - mirror_mutation(): when a bead transitions (claim/close/fail), post/update a
    GitHub issue comment reflecting the new state. [eval 2]
  - inbound_close_sync(): a closed agent-queue GH issue marks its bead done, or
    logs a pending mutation for the next cycle. [eval 3]

All GitHub writes are gated behind execute=True (dry-run by default). Pure helper
functions are unit-tested without network.

Usage:
    python scripts/queue_sync_mutations.py --mirror <bead-id> <state> [--execute]
    python scripts/queue_sync_mutations.py --inbound-close-sync [--execute]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common_harness import run_safe  # noqa: E402

HISTORY = REPO / "07_LOGS_AND_AUDIT" / "queue_sync" / "history.jsonl"
QUEUE_LABEL = "agent-queue"
BEAD_REF_RE_PREFIX = "bead:"

_EXE_CACHE: dict[str, str] = {}


def _resolve_exe(name: str) -> str:
    if name not in _EXE_CACHE:
        _EXE_CACHE[name] = shutil.which(name) or name
    return _EXE_CACHE[name]


def _run(cmd: list[str], *, timeout: int = 60) -> tuple[int, str]:
    if cmd:
        cmd = [_resolve_exe(cmd[0]), *cmd[1:]]
    try:
        r = run_safe(cmd, cwd=REPO, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:  # defensive; run_safe itself does not raise
        return 1, str(exc)


# ── Eval 5: audit trail ───────────────────────────────────────────────────────


def record_sync_action(
    action: str, bead_id: str, issue_number, *, timestamp: str, extra: dict | None = None, path: Path | None = None
) -> dict:
    """Append one sync action to the audit trail. Returns the record written."""
    target = path or HISTORY
    target.parent.mkdir(parents=True, exist_ok=True)
    rec = {"timestamp": timestamp, "action": action, "bead_id": bead_id, "issue_number": issue_number}
    if extra:
        rec.update(extra)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def read_history(path: Path | None = None) -> list[dict]:
    target = path or HISTORY
    if not target.exists():
        return []
    out = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # partial write — skip, never crash (project rule)
    return out


# ── Pure helpers (unit-tested without network) ───────────────────────────────


def bead_id_from_issue_body(body: str) -> str | None:
    """Extract the `bead:<id>` reference the queue sync embeds in issue bodies."""
    for line in (body or "").splitlines():
        s = line.strip()
        if s.startswith(BEAD_REF_RE_PREFIX):
            ref = s[len(BEAD_REF_RE_PREFIX) :].strip()
            return ref or None
    return None


def mutation_comment(bead_id: str, state: str) -> str:
    """The comment body posted on a bead state transition (ASCII-only)."""
    verb = {
        "claimed": "claimed by an agent",
        "in_progress": "in progress",
        "closed": "closed (done)",
        "failed": "failed - needs attention",
        "blocked": "blocked",
    }.get(state, state)
    return f"[queue-sync] bead {bead_id} is now {verb}."


def beads_to_close_from_closed_issues(issues: list[dict]) -> list[dict]:
    """Given GH issues (each {number, state, body}), return the bead ids to mark
    done for issues that are CLOSED and carry a bead reference."""
    out = []
    for iss in issues:
        if str(iss.get("state", "")).lower() != "closed":
            continue
        bid = bead_id_from_issue_body(iss.get("body", ""))
        if bid:
            out.append({"bead_id": bid, "issue_number": iss.get("number")})
    return out


# ── Eval 2: mutation -> GH comment ────────────────────────────────────────────


def _find_issue_for_bead(bead_id: str) -> dict | None:
    code, out = _run(
        [
            "gh",
            "issue",
            "list",
            "--label",
            QUEUE_LABEL,
            "--state",
            "all",
            "--json",
            "number,body,state",
            "--limit",
            "200",
        ]
    )
    if code != 0:
        return None
    try:
        for iss in json.loads(out):
            if bead_id_from_issue_body(iss.get("body", "")) == bead_id:
                return iss
    except json.JSONDecodeError:
        return None
    return None


def mirror_mutation(bead_id: str, state: str, *, timestamp: str, execute: bool = False) -> dict:
    """Post a comment on the bead's linked GH issue reflecting the new state."""
    issue = _find_issue_for_bead(bead_id)
    result = {"bead_id": bead_id, "state": state, "issue_number": issue.get("number") if issue else None}
    if not issue:
        result["status"] = "no_linked_issue"
        return result
    comment = mutation_comment(bead_id, state)
    if execute:
        code, out = _run(["gh", "issue", "comment", str(issue["number"]), "--body", comment])
        result["status"] = "commented" if code == 0 else "error"
        if code != 0:
            result["error"] = out[-200:]
    else:
        result["status"] = "dry_run"
    record_sync_action(
        "mutation_mirror",
        bead_id,
        result["issue_number"],
        timestamp=timestamp,
        extra={"state": state, "status": result["status"]},
    )
    return result


# ── Eval 3: inbound close-sync ────────────────────────────────────────────────


def inbound_close_sync(*, timestamp: str, execute: bool = False) -> dict:
    """Closed agent-queue GH issues mark their beads done (or log pending)."""
    code, out = _run(
        [
            "gh",
            "issue",
            "list",
            "--label",
            QUEUE_LABEL,
            "--state",
            "closed",
            "--json",
            "number,body,state",
            "--limit",
            "200",
        ]
    )
    if code != 0:
        return {"status": "error", "note": out[-200:], "closed": []}
    try:
        issues = json.loads(out)
    except json.JSONDecodeError:
        return {"status": "error", "note": "bad json", "closed": []}
    targets = beads_to_close_from_closed_issues(issues)
    actioned = []
    for t in targets:
        if execute:
            c, _o = _run(
                ["bd", "close", t["bead_id"], "--reason", f"GH issue #{t['issue_number']} closed (inbound queue-sync)"]
            )
            action = "bead_closed" if c == 0 else "pending"
        else:
            action = "dry_run"
        record_sync_action(
            "inbound_close", t["bead_id"], t["issue_number"], timestamp=timestamp, extra={"result": action}
        )
        actioned.append({**t, "result": action})
    return {"status": "ok", "closed": actioned, "count": len(actioned)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Queue<->GitHub mutation + close sync (gh-51)")
    ap.add_argument("--mirror", nargs=2, metavar=("BEAD_ID", "STATE"))
    ap.add_argument("--inbound-close-sync", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--timestamp", default="")
    args = ap.parse_args()

    ts = args.timestamp
    if not ts:
        import datetime

        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if args.mirror:
        bead_id, state = args.mirror
        print(json.dumps(mirror_mutation(bead_id, state, timestamp=ts, execute=args.execute), indent=2))
    elif args.inbound_close_sync:
        print(json.dumps(inbound_close_sync(timestamp=ts, execute=args.execute), indent=2))
    else:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
