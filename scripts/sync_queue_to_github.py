#!/usr/bin/env python3
"""Mirror AGENT_HANDOFF_QUEUE.md items to GitHub issues (xacy.5 Phase 3).

Usage:
  python scripts/sync_queue_to_github.py            # dry-run (print planned actions)
  python scripts/sync_queue_to_github.py --execute  # create/close issues for real
  python scripts/sync_queue_to_github.py --execute --close-done  # also close done issues

Queue format (01_STATE/AGENT_HANDOFF_QUEUE.md):
  - [ ] <bead-id>: <title>   → open issue
  - [x] <bead-id>: <title>   → closed (will close matching GH issue if --close-done)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_QUEUE = _REPO / "01_STATE" / "AGENT_HANDOFF_QUEUE.md"
_LABEL = "agent-queue"


def _gh(*args: str) -> tuple[int, str]:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, cwd=_REPO)
    return result.returncode, (result.stdout + result.stderr).strip()


def _parse_queue(path: Path) -> list[dict]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \[( |x)\] (\S+):\s+(.+)$", line.strip())
        if not m:
            continue
        items.append(
            {
                "done": m.group(1) == "x",
                "bead_id": m.group(2),
                "title": m.group(3).strip(),
            }
        )
    return items


def _list_gh_issues_by_label(label: str) -> list[dict]:
    code, out = _gh(
        "issue",
        "list",
        "--label",
        label,
        "--state",
        "all",
        "--json",
        "number,title,state,body",
    )
    if code != 0 or not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def _find_matching_issue(issues: list[dict], bead_id: str) -> dict | None:
    for issue in issues:
        body = issue.get("body") or ""
        if f"bead:{bead_id}" in body or bead_id in (issue.get("title") or ""):
            return issue
    return None


def sync(*, execute: bool, close_done: bool) -> list[dict]:
    if not _QUEUE.exists():
        print(f"Queue file not found: {_QUEUE}", file=sys.stderr)
        return []

    items = _parse_queue(_QUEUE)
    existing = _list_gh_issues_by_label(_LABEL)
    actions = []

    for item in items:
        match = _find_matching_issue(existing, item["bead_id"])

        if item["done"]:
            if match and match["state"] == "OPEN" and close_done:
                actions.append(
                    {
                        "action": "close",
                        "bead_id": item["bead_id"],
                        "issue": match["number"],
                        "title": item["title"],
                    }
                )
                if execute:
                    _gh(
                        "issue",
                        "close",
                        str(match["number"]),
                        "--comment",
                        f"Closed: bead `{item['bead_id']}` marked done in queue.",
                    )
            else:
                actions.append({"action": "skip_done", "bead_id": item["bead_id"]})
        else:
            if match:
                actions.append(
                    {
                        "action": "exists",
                        "bead_id": item["bead_id"],
                        "issue": match["number"],
                        "state": match["state"],
                    }
                )
            else:
                body = (
                    f"Mirrored from `01_STATE/AGENT_HANDOFF_QUEUE.md`.\n\n"
                    f"**Bead:** `{item['bead_id']}`  \n"
                    f"bead:{item['bead_id']}\n\n"
                    f"Close this issue when the bead is marked done."
                )
                actions.append(
                    {
                        "action": "create",
                        "bead_id": item["bead_id"],
                        "title": f"[queue] {item['title']}",
                    }
                )
                if execute:
                    code, out = _gh(
                        "issue",
                        "create",
                        "--title",
                        f"[queue] {item['title']}",
                        "--body",
                        body,
                        "--label",
                        _LABEL,
                        "--label",
                        "operating-model",
                    )
                    if code == 0:
                        # out is the issue URL; parse number
                        m = re.search(r"/issues/(\d+)", out)
                        if m:
                            actions[-1]["issue"] = int(m.group(1))
                        actions[-1]["url"] = out.strip()

    # Audit trail (eval 5 of gh-51): record every action on an --execute run.
    if execute:
        try:
            import datetime

            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from queue_sync_mutations import record_sync_action

            ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for a in actions:
                record_sync_action(
                    a.get("action", "unknown"),
                    a.get("bead_id", ""),
                    a.get("issue"),
                    timestamp=ts,
                )
        except Exception:  # noqa: BLE001 — audit must never break the sync
            pass

    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync handoff queue to GitHub issues")
    parser.add_argument("--execute", action="store_true", help="Actually create/close issues")
    parser.add_argument("--close-done", action="store_true", help="Close GH issues for done items")
    args = parser.parse_args()

    actions = sync(execute=args.execute, close_done=args.close_done)

    print(json.dumps({"dry_run": not args.execute, "actions": actions}, indent=2))

    created = sum(1 for a in actions if a["action"] == "create")
    closed = sum(1 for a in actions if a["action"] == "close")
    exists = sum(1 for a in actions if a["action"] == "exists")
    print(
        f"\nsummary: {created} created, {closed} closed, {exists} already exist",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
