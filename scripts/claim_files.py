#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from common_harness import read_json, write_json, repo_root, utc_now, append_jsonl


def norm(root, f):
    p = Path(f)
    return str(p.resolve()) if p.is_absolute() else str((root / p).resolve().relative_to(root))


def _route_collision(root, blocked, writer, session, task):
    """Log a blocked claim and route it to COLLISION_REGISTER.md (OBS-002)."""
    ts = utc_now()
    cid = "COLLISION-" + "".join(c for c in ts if c.isalnum())[:14]
    files = ", ".join(f for f, _ in blocked)
    lines = [
        "",
        f"## {cid}: {files}",
        "",
        "| Field | Value |",
        "|---|---|",
        "| Status | Open |",
        "| Severity | High |",
        f"| Detected At | {ts} |",
        f"| Files Affected | {files} |",
        f"| Incoming Writer | {writer} (session {session}, task {task}) |",
        "",
        "### Existing Writers",
        "",
        "| File | Writer | Session | Claimed Task | Claimed At |",
        "|---|---|---|---|---|",
    ]
    for f, cur in blocked:
        lines.append(
            f"| {f} | {cur.get('writer', '?')} | {cur.get('session', '?')} "
            f"| {cur.get('task', '?')} | {cur.get('claimed_at', '?')} |"
        )
    lines.append("")
    reg = root / "00_META" / "observability" / "COLLISION_REGISTER.md"
    try:
        reg.parent.mkdir(parents=True, exist_ok=True)
        with reg.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass
    try:
        append_jsonl(
            root / "00_META" / "observability" / "COLLISION_LOG.jsonl",
            {
                "id": cid,
                "ts": ts,
                "incoming_writer": writer,
                "session": session,
                "task": task,
                "files": [f for f, _ in blocked],
                "existing": [cur for _, cur in blocked],
            },
        )
    except OSError:
        pass
    return cid


def main():
    ap = argparse.ArgumentParser(description="Claim files before agent/IDE mutation")
    ap.add_argument("--repo-root")
    ap.add_argument("--writer", required=True)
    ap.add_argument("--session", default=os.environ.get("CHROMATIC_SESSION_ID", "manual"))
    ap.add_argument("--task", default="unknown")
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    path = root / ".chromatic/active_writers.json"
    data = read_json(path, {"claims": {}})
    claims = data.setdefault("claims", {})
    blocked = []
    for f in args.files:
        nf = norm(root, f)
        cur = claims.get(nf)
        if cur and cur.get("session") != args.session and not args.force:
            blocked.append((nf, cur))
    if blocked:
        cid = _route_collision(root, blocked, args.writer, args.session, args.task)
        print("CLAIM BLOCKED: existing active writer(s)", file=sys.stderr)
        for f, cur in blocked:
            print(f"- {f}: {cur}", file=sys.stderr)
        print(f"collision routed to COLLISION_REGISTER.md as {cid}", file=sys.stderr)
        return 3
    for f in args.files:
        claims[norm(root, f)] = {
            "writer": args.writer,
            "session": args.session,
            "task": args.task,
            "claimed_at": utc_now(),
        }
    data["updated_at"] = utc_now()
    write_json(path, data)
    print(f"claimed {len(args.files)} file(s) for session {args.session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
